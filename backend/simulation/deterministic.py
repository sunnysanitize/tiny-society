from __future__ import annotations

import random

from models import Agent, Relationship


SOCIAL_TRAITS = {"social", "charismatic", "loyal", "patient"}
ISOLATING_TRAITS = {"introverted", "anxious", "lonely"}


def apply_background_rules(
    agents: list[Agent],
    all_agents: list[Agent],
    rng: random.Random,
) -> list[str]:
    """Lightweight evolution for agents not selected for AI reasoning."""
    log: list[str] = []
    by_name = {a.name: a for a in all_agents}

    for a in agents:
        is_social = bool(set(a.traits) & SOCIAL_TRAITS)
        is_isolating = bool(set(a.traits) & ISOLATING_TRAITS)

        # Friendship reinforcement among social agents
        if is_social and a.relationships:
            for name, r in list(a.relationships.items()):
                if r.type == "friendship" and r.strength < 0.95:
                    r.strength = round(min(1.0, r.strength + 0.02), 3)
                if r.type == "rivalry" and r.strength > 0.1:
                    r.strength = round(max(0.0, r.strength - 0.015), 3)

        # Isolation drift
        if is_isolating and not a.relationships:
            a.influence_score = round(max(-10.0, a.influence_score - 0.1), 2)

        # Shared-group trust drip
        for other in all_agents:
            if other.id == a.id:
                continue
            shared = set(a.groups) & set(other.groups)
            if shared and rng.random() < 0.08:
                _bump_relationship(a, other.name, "trust", 0.01)
                _bump_relationship(other, a.name, "trust", 0.01)

        # Rivalry decay without reinforcement
        for name, r in list(a.relationships.items()):
            if r.type == "rivalry":
                r.strength = round(max(0.0, r.strength - 0.005), 3)

    return log


def _bump_relationship(agent: Agent, target_name: str, rtype: str, delta: float) -> None:
    if target_name == agent.name:
        return
    existing = agent.relationships.get(target_name)
    if existing is None:
        agent.relationships[target_name] = Relationship(type=rtype, strength=round(delta, 3))
    else:
        existing.strength = round(max(-1.0, min(1.0, existing.strength + delta)), 3)
