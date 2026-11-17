from __future__ import annotations

import hashlib
import json
import random as _random
import re
from typing import Optional

from models import Agent, AgentAction, Audience, WorldGraph, normalize_mood
from llm import call_llm, acall_llm
from .audience import derive_action_kind, normalize_reach
from .memory import retrieve
from .observation import rank_feed
from .premise import premise_lines
from .needs import urgent_need
from .dynamics import CONFLICT_LABELS, tensions

# How many other agents to surface in a reasoning prompt (bounds prompt size). The roster
# is RANKED so every agent stays reachable over time, rather than always showing the first
# N by insertion order (which left the back half of a large population unreferenceable).
ROSTER_LIMIT = 30

REASONER_SYSTEM = """AGENT_REASONING
You are a single fictional character in a multi-agent social simulation.
You will be given your personality, memories, relationships, and the current world event.
Reason about what your character would actually do today, then return STRICT JSON only — no prose.

You do NOT control relationship numbers. You only decide WHAT YOU DO and YOUR INTENT toward
each person; the world decides the consequences, and relationships change slowly, only through
sustained, mutual behavior (a romance can't happen in a day, or one-sidedly).

JSON schema:
{
  "action": "short verb phrase summarizing the move (e.g. 'confront', 'open up to', 'rally')",
  "audience": {
    "who": "who was around when you did this, in this world's own words",
    "reach": "everyone | those present | one person"
  },
  "target_agents": ["Name", ...],
  "about_agents": ["Name", ...],
  "utterance": "what you actually say or do, in YOUR voice — under 25 words, how a person talks, not a speech",
  "intents": {
    "TargetName": "one intent verb from the list below"
  },
  "emotional_reaction": "calm|excited|frustrated|heartbroken|ambitious|anxious|content|angry|hopeful|lonely|confident",
  "stance_shift": { "TopicName": -0.3 to 0.3 },
  "new_memory": "first-person past-tense sentence describing what you did today",
  "explanation": "your private thought as you do it, in your own voice — one short sentence, not an analysis of yourself",
  "attempt": "what you are trying to accomplish whose result isn't yours to decide, or \"\"",
  "basis": "if you confront, rebuke, undermine or reject someone: the memory or report it rests on, briefly quoted; else \"\""
}

  audience : who witnessed this. `who` is your own phrasing — where you were, who could
             hear. `reach` is how far it carried: "everyone" if the whole world learns of
             it, "those present" if your circle saw it, "one person" if it was private
             between you and your named target. Most days are "those present".
  target_agents : people you actually interacted with today — they were there.
  attempt       : fill this when you try to MAKE something happen in the world — search,
                  track, fix, hunt, hide, steal, catch, prove, cure ("find who altered the
                  oxygen logs"). The world decides whether it works; you'll learn the
                  result. Leave it "" for conversation and social moves: what someone else
                  feels or decides is up to them, not an attempt.
                  Never write the result into new_memory — say what you did, not what came of it.
  about_agents  : people this was ABOUT who were not there and do not know. Working
                  alone on something because of someone, avoiding them, preparing for
                  them, stewing about them. They do not learn anything from this.

INTENT VERBS (pick the one that matches your true intent toward each target):
  warmth:     befriend, support, comfort, praise, reconcile, confide, trust
  romance:    flirt, court          (only use these if you genuinely feel romantic — they're rare)
  strategic:  ally, collaborate
  antagonism: confront, rebuke, reject, undermine, challenge, compete, distance
  neutral:    talk, observe

CRITICAL RULES:
- ANTI-REPETITION: read YOUR RECENT ACTIONS. If you keep engaging the same person the same way,
  you MUST change course — escalate, resolve, withdraw, or turn to someone new. Ongoing efforts
  must move: show the result of yesterday's attempt instead of repeating it.
- KNOW ONLY WHAT YOU KNOW. Act on your memories, what has reached you, and the event as
  everyone knows it. Don't accuse someone, or rely on a fact, that nothing in front of you
  supports; don't invent family ties or history that isn't in your memories.
- Stay in character. Let traits, mood, goals, and memories drive the choice and the utterance.
- BE REALISTIC: most days are ordinary. Reserve romance ('flirt'/'court') for when there is a
  real, established, mutual closeness — never as a sudden leap. Don't manufacture drama.
- PURSUE YOUR PLAN if one is present (unless the event makes it impossible).
- Only reference agent names from the roster — never invent names. Put each target in BOTH
  target_agents and intents.
- stance_shift: ONLY topics you actually engaged with today, small magnitudes (-0.3..0.3), else {}.
- NAME SOMEONE. Every action names at least one person — in target_agents if you
  actually dealt with them, in about_agents if it was about them but they were not
  there. Never leave both empty. A day spent alone is fine; a day about nobody is not.
- Output only JSON. No markdown, no commentary, no preamble.
"""


def reason_for_agent(
    agent: Agent,
    roster: list[Agent],
    event: Optional[str],
    current_day: int = 1,
    world_graph: Optional[WorldGraph] = None,
    tier: str = "cheap",
    world_premise: Optional[str] = None,
    crowded: Optional[list[str]] = None,
) -> Optional[AgentAction]:
    import logging
    user = _build_prompt(agent, roster, event, current_day, world_graph, world_premise, crowded)
    try:
        raw = call_llm(REASONER_SYSTEM, user, json_mode=True, max_tokens=1024, tier=tier)
    except Exception as e:
        logging.warning(f"LLM call failed for agent {agent.name}: {e}")
        return None
    return _parse_action(agent, raw)


async def areason_for_agent(
    agent: Agent,
    roster: list[Agent],
    event: Optional[str],
    current_day: int = 1,
    world_graph: Optional[WorldGraph] = None,
    tier: str = "cheap",
    world_premise: Optional[str] = None,
    crowded: Optional[list[str]] = None,
) -> Optional[AgentAction]:
    import logging
    user = _build_prompt(agent, roster, event, current_day, world_graph, world_premise, crowded)
    try:
        raw = await acall_llm(REASONER_SYSTEM, user, json_mode=True, max_tokens=1024, tier=tier)
    except Exception as e:
        logging.warning(f"LLM call failed for agent {agent.name}: {e}")
        return None
    return _parse_action(agent, raw)


def _parse_action(agent: Agent, raw: str) -> Optional[AgentAction]:
    import logging
    data = _safe_json(raw)
    if not data:
        logging.warning(f"Empty/invalid JSON from LLM for agent {agent.name}: {raw[:100]!r}")
        return None
    try:
        intents = {
            str(name): str(verb).strip().lower()
            for name, verb in (data.get("intents") or {}).items()
            if isinstance(verb, str) and verb.strip()
        }
        targets = [str(t) for t in (data.get("target_agents") or [])][:5]
        about = [str(t) for t in (data.get("about_agents") or [])][:5]
        # Someone named in both is an interaction, not a referent.
        about = [a for a in about if a not in targets]
        if not targets and not about:
            logging.warning(f"Action from {agent.name} named nobody; rejecting")
            return None
        # Be forgiving: if intents are missing but targets exist, default to neutral contact
        # so the action still has consequence-layer effects.
        for t in targets:
            intents.setdefault(t, "talk")
        stance_shift = {
            str(k): _clamp(float(v), -0.3, 0.3)
            for k, v in (data.get("stance_shift") or {}).items()
            if isinstance(v, (int, float))
        }
        # AUDIENCE (Task 6): the agent narrates who was around instead of picking a
        # channel. `aud` is the new shape; its absence means either an old save or a
        # model that answered in the pre-audience schema, so fall back to mapping its
        # legacy `action_kind` onto the equivalent reach.
        aud = data.get("audience")
        if isinstance(aud, dict):
            who = str(aud.get("who") or "").strip()[:160]
            reach = normalize_reach(aud.get("reach"))
        else:
            who = ""
            reach = normalize_reach(data.get("action_kind"))
        audience = Audience(who=who, reach=reach)
        return AgentAction(
            action=str(data.get("action", "observe"))[:60],
            # action_kind is no longer agent-authored (see models.AgentAction and
            # simulation/audience.py) — it's derived here from the audience + intents
            # this agent actually supplied, so the internal influence math keeps working.
            action_kind=derive_action_kind(reach, intents),
            audience=audience,
            target_agents=targets,
            about_agents=about,
            emotional_reaction=normalize_mood(data.get("emotional_reaction"), default=agent.mood),
            intents=intents,
            utterance=_trim(str(data.get("utterance", "")), 400),
            stance_shift=stance_shift,
            new_memory=_trim(str(data.get("new_memory", "")), 280),
            explanation=_trim(str(data.get("explanation", "")), 280),
            attempt=_trim(str(data.get("attempt") or ""), 200),
            basis=_trim(str(data.get("basis") or ""), 240),
        )
    except Exception:
        return None


def _build_prompt(
    agent: Agent,
    roster: list[Agent],
    event: Optional[str],
    current_day: int = 1,
    world_graph: Optional[WorldGraph] = None,
    world_premise: Optional[str] = None,
    crowded: Optional[list[str]] = None,
) -> str:
    rel_lines = []
    for name, r in agent.relationships.items():
        known = "well" if r.closeness >= 0.5 else ("somewhat" if r.closeness >= 0.25 else "barely")
        conflict = f", conflict: {CONFLICT_LABELS[r.conflict]}" if r.conflict else ""
        rel_lines.append(f"  - {name}: {r.type} (strength {r.strength:+.2f}, you know them {known}{conflict})")
    rel_lines += [f"  ! {t}" for t in tensions(agent, roster)]
    roster_lines = [
        f"- {a.name}: {a.role}, traits={a.traits}, groups={a.groups}"
        for a in _ranked_roster(agent, roster, current_day, ROSTER_LIMIT)
    ]

    # RELEVANCE-BASED RETRIEVAL: long-term memory is selected by relevance + recency +
    # importance rather than pure recency truncation. The query is what today is about
    # for THIS agent: the event, their plan and goals, what has just reached them, and
    # the people they know (their likely targets).
    recent_feed = [e.text for e in agent.feed[-3:]]
    query = " ".join(filter(None, [event or "", agent.plan or ""] + agent.goals
                            + recent_feed + list(agent.relationships.keys())))
    retrieved = retrieve(
        agent.long_term_memory,
        query,
        current_day=current_day,
        k=10,
    )

    # Extract last action from short-term memory (today) to surface it explicitly
    last_pool = agent.short_term_memory or agent.long_term_memory
    last_action = last_pool[-1].text if last_pool else None
    # Rolling action history (structured: kind/verb → targets) drives anti-repetition —
    # the model sees its OWN recent pattern, not just one stale line.
    recent_actions = agent.recent_actions[-5:]

    # WORLD FACTS & POWER STRUCTURE: compact shared ground truth from the knowledge
    # graph, plus the contested topics + this agent's current stance on them.
    topics = world_graph.topics if world_graph else []
    fact_lines: list[str] = []
    if world_graph:
        for e in world_graph.entities[:6]:
            desc = f" — {e.description}" if e.description else ""
            fact_lines.append(f"- {e.name} ({e.kind}){desc}")
        for p in world_graph.power_structures[:3]:
            fact_lines.append(f"- POWER: {p}")
    # RANKED FEED (interest + hot-score): show this viewer the top entries from their
    # structured feed, ordered by how much the content matches their interests plus the
    # author's influence and recency — different agents see different, biased feeds.
    ranked_feed = rank_feed(agent, agent.feed, k=8)

    topic_lines = []
    for t in topics:
        pos = agent.stance.get(t)
        if pos is not None:
            topic_lines.append(f"- {t} (your current stance: {pos:+.2f})")
        else:
            topic_lines.append(f"- {t}")

    efforts = [e for e in agent.efforts if not e.done]
    crowded = [n for n in (crowded or []) if n != agent.name]
    voice = ""
    if agent.profile and (agent.profile.voice or agent.profile.speech_samples):
        voice = agent.profile.voice + "".join(f'\n  e.g. "{x}"' for x in agent.profile.speech_samples)
    parts = [
        *premise_lines(world_premise),
        "WORLD FACTS & POWER STRUCTURE",
        "\n".join(fact_lines) if fact_lines else "(none extracted)",
        "",
        "WORLD TOPICS (stance axes; shift only those you engage with, -0.3..0.3)",
        "\n".join(topic_lines) if topic_lines else "(none)",
        "",
        "YOUR CHARACTER",
        f"Name: {agent.name}",
        f"Role: {agent.role}",
        f"Traits: {', '.join(agent.traits + agent.revealed_traits) or '(none)'}",
        f"Goals: {', '.join(agent.goals) or '(none)'}",
        f"Mood: {agent.mood}",
        f"Influence score: {agent.influence_score:.1f}",
        f"Groups: {', '.join(agent.groups) or '(none)'}",
        "",
        "YOUR RELATIONSHIPS",
        "\n".join(rel_lines) if rel_lines else "(none yet)",
        "",
        *(["WHERE YOU STAND (your own account)", agent.self_summary, ""] if agent.self_summary else []),
        *(["YOUR CURRENT PLAN", agent.plan, ""] if agent.plan else []),
        *(["WHAT YOU NEED (a pull, not an order)", urgent, ""] if (urgent := urgent_need(agent)) else []),
        *(["YOUR ONGOING EFFORTS (continue one by naming it in `attempt`, or let it go)",
           "\n".join(f"- {e.name}: {e.filled}/{e.segments} of the way, {e.attempts} attempt(s) so far"
                     for e in efforts), ""] if efforts else []),
        "YOUR SHORT-TERM MEMORY (today so far)",
        "\n".join(f"- {m.text}" for m in agent.short_term_memory[-4:]) or "(empty)",
        "",
        "YOUR LONG-TERM MEMORY (most relevant to today)",
        "\n".join(f"- {m.text}" for m in retrieved) or "(empty)",
        "",
        "YOUR RECENT ACTIONS (vary from these — do NOT repeat the same target or the same move)",
        "\n".join(f"- {r}" for r in recent_actions)
            or f"- {last_action or '(none — this is your first day)'}",
        "→ If you keep engaging the same person, you MUST change course: escalate it, resolve it, "
        "withdraw, or turn to someone new. Repeating yesterday verbatim is always wrong.",
        "→ If you are continuing an effort from an earlier day (a search, a hunt, a vigil, a "
        "repair), today shows what came of it — you find something, fail, give up, or decide "
        "something — rather than making the same attempt again.",
        "",
        "CURRENT WORLD EVENT",
        event or "(no specific event today)",
        "",
        "WHAT HAS REACHED YOU (ranked by your interests + what's most talked about)",
        "\n".join(f"- {e.text}" for e in ranked_feed) or "(nothing notable yet)",
        "",
        "OTHER AGENTS IN THE WORLD",
        "\n".join(roster_lines),
        *([f"Already crowded: {', '.join(crowded)} had several people come at them yesterday. "
           "Only add to that if you truly must — someone else may need you more."] if crowded else []),
        "",
        *(["YOUR VOICE", voice, ""] if voice else []),
        "Return your action as JSON now.",
    ]
    return "\n".join(parts)


def _ranked_roster(
    agent: Agent, roster: list[Agent], current_day: int, limit: int
) -> list[Agent]:
    """Pick up to `limit` other agents to show this agent, prioritizing the ones it can
    most plausibly act on (existing relationships, then group-mates, then recent feed
    authors), and filling the rest with a DAY-SEEDED rotating sample of everyone else so
    the whole population stays reachable over the run instead of only the first N by list
    order. Deterministic: the sample seed is a stable hash of (agent id, day), so the
    day-by-day path stays byte-identical to a batch run."""
    others = [a for a in roster if a.id != agent.id]
    if len(others) <= limit:
        return others

    rel_names = set(agent.relationships.keys())
    groups = set(agent.groups)
    feed_authors = {e.author for e in agent.feed if e.author}

    def priority(a: Agent) -> int:
        if a.name in rel_names:
            return 0
        if groups and (groups & set(a.groups)):
            return 1
        if a.name in feed_authors:
            return 2
        return 3

    seed = int(hashlib.sha256(f"{agent.id}|{current_day}".encode()).hexdigest()[:8], 16)
    rng = _random.Random(seed)
    # Sort by priority tier, breaking ties with a per-day deterministic jitter so the
    # lowest-priority tier (strangers) rotates which members are shown each day.
    decorated = sorted(others, key=lambda a: (priority(a), rng.random()))
    return decorated[:limit]


def _safe_json(raw: str) -> dict:
    if not raw:
        return {}
    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw).strip()
    # Try full parse first
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        pass
    # Find outermost { ... } (handles preamble/postamble)
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _trim(text: str, limit: int = 280) -> str:
    """Trim to `limit` characters on a word boundary.

    A bare `text[:280]` slice produced cuts like "...present it publi" in the UI.
    Prefer ending on a sentence; otherwise drop the partial word and mark the cut.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for end in (". ", "! ", "? "):
        idx = cut.rfind(end)
        if idx >= limit // 2:
            return cut[:idx + 1].strip()
    idx = cut.rfind(" ")
    trimmed = cut[:idx] if idx > 0 else cut
    return trimmed.rstrip(" ,;:—-") + "…"
