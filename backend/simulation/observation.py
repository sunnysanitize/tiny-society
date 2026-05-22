from __future__ import annotations

from models import Agent

# Information-asymmetry routing (modeled on OASIS / Generative-Agents observation
# locality). Instead of broadcasting one global event log to every agent, each
# action is distributed only to agents who could plausibly witness it. This is the
# substrate for emergent gossip, factions, and misinformation.

# Max observations retained per agent (bounds snapshot size + prompt weight).
OBSERVATION_WINDOW = 15

# Actors at or above this influence score are treated as PUBLIC figures: their
# actions are visible to everyone (news/celebrity effect), regardless of group ties.
PUBLIC_INFLUENCE_THRESHOLD = 20.0


def witnesses(
    actor: Agent,
    target_names: list[str],
    all_agents: list[Agent],
) -> list[Agent]:
    """Return the agents who would plausibly witness `actor`'s action.

    Witness rule:
      - the actor itself,
      - any named target agents,
      - agents sharing at least one group with the actor,
      - if the actor is high-influence (PUBLIC), EVERYONE observes it.
    """
    if actor.influence_score >= PUBLIC_INFLUENCE_THRESHOLD:
        return list(all_agents)

    targets = {t for t in target_names}
    actor_groups = set(actor.groups)
    seen: list[Agent] = []
    seen_ids: set[str] = set()
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
) -> list[Agent]:
    """Append `log_line` to the observation feed of every witnessing agent.

    Returns the list of agents who observed it (useful for tests/inspection).
    """
    witnessed = witnesses(actor, target_names, all_agents)
    for a in witnessed:
        a.observations.append(log_line)
        if len(a.observations) > OBSERVATION_WINDOW:
            a.observations = a.observations[-OBSERVATION_WINDOW:]
    return witnessed
