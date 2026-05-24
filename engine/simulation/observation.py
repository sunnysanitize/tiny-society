from __future__ import annotations

import re

from models import Agent, FeedEntry

# Information-asymmetry routing (modeled on OASIS / Generative-Agents observation
# locality). Instead of broadcasting one global event log to every agent, each
# action is distributed only to agents who could plausibly witness it. This is the
# substrate for emergent gossip, factions, and misinformation.
#
# Phase 2 #4/#5 upgrade: reach now depends on the action_kind (post/direct/amplify/
# comment/interact), and each witness stores a structured FeedEntry so their feed can
# be RANKED per viewer by interest-match + hot-score (recommendation-style feed),
# rather than shown as a uniform recent slice.

# Max observations / feed entries retained per agent (bounds snapshot size + prompt weight).
OBSERVATION_WINDOW = 15

# Actors at or above this influence score are treated as PUBLIC figures: their
# actions are visible to everyone (news/celebrity effect), regardless of group ties.
PUBLIC_INFLUENCE_THRESHOLD = 20.0

# ── feed ranking weights (Phase 2 #4) ────────────────────────────────────────────
# rank_feed scores each entry per viewer as:
#   INTEREST_WEIGHT * interest_match            (overlap of entry text with the viewer's
#                                                traits/stance-topics/relationship names)
# + HOT_INFLUENCE_WEIGHT * normalized_influence (the author's standing — "hot" content)
# + HOT_RECENCY_WEIGHT * recency_decay          (newer entries surface first).
# Interest dominates so feeds become echo chambers; influence + recency add virality.
INTEREST_WEIGHT = 3.0
HOT_INFLUENCE_WEIGHT = 1.0
HOT_RECENCY_WEIGHT = 1.5
RECENCY_DECAY = 0.85  # per-day decay applied to (current_day - entry.day)

_TOKEN_RE = re.compile(r"[a-z']{3,}")
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "they", "their",
    "them", "was", "had", "has", "have", "are", "but", "not", "you", "your", "his",
    "her", "she", "him", "who", "what", "when", "made", "felt", "more", "than",
    "chose", "today", "everything", "something", "about", "been", "were",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


def witnesses(
    actor: Agent,
    target_names: list[str],
    all_agents: list[Agent],
    action_kind: str = "interact",
) -> list[Agent]:
    """Return the agents who would plausibly witness `actor`'s action.

    Reach depends on action_kind:
      - "post"            : public broadcast — EVERYONE witnesses it.
      - "direct"          : private — only the actor and the named target(s).
      - "amplify"/"comment"/"interact" : the default witness rule —
            the actor, named targets, group-mates, and (if the actor's influence is
            >= PUBLIC_INFLUENCE_THRESHOLD) everyone.
    """
    if action_kind == "post":
        return list(all_agents)

    targets = {t for t in target_names}

    if action_kind == "direct":
        seen: list[Agent] = []
        seen_ids: set[str] = set()
        for a in all_agents:
            if (a.id == actor.id or a.name in targets) and a.id not in seen_ids:
                seen.append(a)
                seen_ids.add(a.id)
        return seen

    # comment / amplify / interact: actor + targets + group-mates + public-if-high-influence
    if actor.influence_score >= PUBLIC_INFLUENCE_THRESHOLD:
        return list(all_agents)

    actor_groups = set(actor.groups)
    seen = []
    seen_ids = set()
    for a in all_agents:
        is_witness = (
            a.id == actor.id
            or a.name in targets
            or (actor_groups and actor_groups.intersection(a.groups))
        )
        if is_witness and a.id not in seen_ids:
            seen.append(a)
            seen_ids.add(a.id)
    return seen


def distribute_observation(
    log_line: str,
    actor: Agent,
    target_names: list[str],
    all_agents: list[Agent],
    action_kind: str = "interact",
    day: int = 0,
) -> list[Agent]:
    """Append `log_line` to the feed of every witnessing agent (reach by action_kind).

    Each witness gets both the plain-string `observations` entry (back-compat) and a
    structured `FeedEntry` carrying author/influence/day/action_kind for ranking.

    For "amplify", the amplifier additionally spreads the AMPLIFIED target's standing:
    a synthetic entry attributed to the target is injected into the amplifier's own
    witness set, so the target's visibility reaches the amplifier's audience.

    Returns the list of agents who observed it (useful for tests/inspection).
    """
    witnessed = witnesses(actor, target_names, all_agents, action_kind)
    entry = FeedEntry(
        text=log_line,
        author=actor.name,
        author_influence=actor.influence_score,
        day=day,
        action_kind=action_kind,
    )
    for a in witnessed:
        a.observations.append(log_line)
        a.feed.append(entry.model_copy())
        _trim(a)

    if action_kind == "amplify" and target_names:
        by_name = {a.name: a for a in all_agents}
        for tname in target_names:
            target = by_name.get(tname)
            if target is None or target.id == actor.id:
                continue
            amp_line = f"[{actor.name}] amplified {target.name}, spreading their standing."
            amp_entry = FeedEntry(
                text=amp_line,
                author=target.name,                 # the spread content belongs to the target
                author_influence=target.influence_score,
                day=day,
                action_kind="amplify",
            )
            for a in witnessed:
                a.observations.append(amp_line)
                a.feed.append(amp_entry.model_copy())
                _trim(a)

    return witnessed


def _trim(a: Agent) -> None:
    if len(a.observations) > OBSERVATION_WINDOW:
        a.observations = a.observations[-OBSERVATION_WINDOW:]
    if len(a.feed) > OBSERVATION_WINDOW:
        a.feed = a.feed[-OBSERVATION_WINDOW:]


def rank_feed(viewer: Agent, entries: list[FeedEntry], k: int) -> list[FeedEntry]:
    """Return the top-`k` feed entries for `viewer`, ranked by interest + hot-score.

    Score = INTEREST_WEIGHT * interest_match
          + HOT_INFLUENCE_WEIGHT * normalized_author_influence
          + HOT_RECENCY_WEIGHT * recency_decay.

    interest_match = fraction of the viewer's interest tokens (traits + revealed traits
    + stance topics + relationship names) that appear in the entry text. This biases
    each agent's feed toward content about what they care about — an echo chamber.
    """
    if not entries:
        return []
    interest_tokens: set[str] = set()
    for trait in viewer.traits + viewer.revealed_traits:
        interest_tokens |= _tokens(trait)
    for topic in viewer.stance.keys():
        interest_tokens |= _tokens(topic)
    for name in viewer.relationships.keys():
        interest_tokens |= _tokens(name)
    interest_tokens |= _tokens(viewer.name)

    max_inf = max((abs(e.author_influence) for e in entries), default=1.0) or 1.0
    max_day = max((e.day for e in entries), default=0)

    scored: list[tuple[float, int, FeedEntry]] = []
    for idx, e in enumerate(entries):
        etoks = _tokens(e.text)
        if interest_tokens and etoks:
            interest = len(interest_tokens & etoks) / max(1, len(interest_tokens))
        else:
            interest = 0.0
        infl = (e.author_influence / max_inf) if max_inf else 0.0
        recency = RECENCY_DECAY ** max(0, max_day - e.day)
        score = (
            INTEREST_WEIGHT * interest
            + HOT_INFLUENCE_WEIGHT * infl
            + HOT_RECENCY_WEIGHT * recency
        )
        # idx as a stable tie-breaker (preserves recency order among equal scores)
        scored.append((score, idx, e))

    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [e for _, _, e in scored[:k]]
