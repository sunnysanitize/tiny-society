from __future__ import annotations

import random
from statistics import mean

from models import Agent, Relationship
from . import consequence


SOCIAL_TRAITS = {"social", "charismatic", "loyal", "patient"}
ISOLATING_TRAITS = {"introverted", "anxious", "lonely"}
# Traits that resist conformity — these agents drift AWAY from their group's mean
# stance (polarization) instead of toward it.
CONTRARIAN_TRAITS = {"contrarian", "rebellious", "stubborn", "skeptical", "independent", "defiant"}

# Bonds fade toward neutral without contact (applied to background agents per day).
DECAY = 0.01
# Social agents keep their warm bonds a touch warmer instead of letting them fade.
WARMTH_UPKEEP = 0.02
# How strongly a background agent's stance drifts toward (or, for contrarians, away
# from) its group-mates' mean on each topic per day. Small so the aggregate moves
# believably rather than snapping to consensus.
CONFORMITY = 0.02
# Influence regresses gently toward 0 without active self-promotion, so it isn't a
# one-way ratchet that pushes everyone past the public-figure threshold over a long run.
INFLUENCE_REGRESSION = 0.99


def apply_background_rules(
    agents: list[Agent],
    all_agents: list[Agent],
    rng: random.Random,
) -> list[str]:
    """Lightweight evolution for agents not selected for AI reasoning.

    Operates on the SIGNED affinity convention (rivalry/conflict are negative): bonds
    fade toward neutral, social agents keep warm bonds warm, and every touched edge is
    re-derived via the consequence layer so its TYPE stays consistent with its affinity.
    Background agents also drift their belief stance toward their group's mean (conformity)
    or away (contrarians), so the population aggregate isn't frozen between the few agents
    that reason each day."""
    log: list[str] = []
    by_name = {a.name: a for a in all_agents}

    for a in agents:
        is_social = bool(set(a.traits) & SOCIAL_TRAITS)
        is_isolating = bool(set(a.traits) & ISOLATING_TRAITS)

        # Relationship upkeep / fade — sign-correct, then re-derive the type.
        for name, r in list(a.relationships.items()):
            other = by_name.get(name)
            if is_social and r.strength > 0:
                r.strength = round(min(1.0, r.strength + WARMTH_UPKEEP), 3)
            elif r.strength > 0:
                r.strength = round(max(0.0, r.strength - DECAY), 3)
            elif r.strength < 0:
                r.strength = round(min(0.0, r.strength + DECAY), 3)
            consequence.realize(a, name, other)

        # Isolation drift
        if is_isolating and not a.relationships:
            a.influence_score = round(max(-10.0, a.influence_score - 0.1), 2)

        # Shared-group trust drip (sign-correct positive nudge, then re-derive).
        for other in all_agents:
            if other.id == a.id:
                continue
            shared = set(a.groups) & set(other.groups)
            if shared and rng.random() < 0.08:
                _drip(a, other.name, 0.01)
                _drip(other, a.name, 0.01)
                consequence.realize(a, other.name, other)
                consequence.realize(other, a.name, a)

        # BELIEF DRIFT (Phase 3): conform toward / polarize away from group-mates' mean.
        _drift_stance(a, all_agents)

        # Influence regresses gently toward 0 (Phase 5) so standing isn't a one-way ratchet.
        if a.influence_score:
            a.influence_score = round(a.influence_score * INFLUENCE_REGRESSION, 2)

    return log


def _drip(agent: Agent, target_name: str, delta: float) -> None:
    """A small affinity nudge that also counts as an interaction (dwell time)."""
    if target_name == agent.name:
        return
    rel = agent.relationships.get(target_name)
    if rel is None:
        rel = Relationship(type="trust", strength=0.0)
        agent.relationships[target_name] = rel
    rel.strength = round(max(-1.0, min(1.0, rel.strength + delta)), 3)
    rel.interactions += 1


def _drift_stance(agent: Agent, all_agents: list[Agent]) -> None:
    """Nudge each of the agent's topic stances toward its group-mates' mean (or away,
    for contrarian agents). Deterministic and bounded."""
    if not agent.stance:
        return
    contrarian = bool(set(agent.traits) & CONTRARIAN_TRAITS)
    groups = set(agent.groups)
    if not groups:
        return
    for topic, val in list(agent.stance.items()):
        peers = [
            o.stance[topic]
            for o in all_agents
            if o.id != agent.id and topic in o.stance and (groups & set(o.groups))
        ]
        if not peers:
            continue
        target = mean(peers)
        delta = (target - val) * CONFORMITY
        if contrarian:
            delta = -delta
        agent.stance[topic] = round(max(-1.0, min(1.0, val + delta)), 3)
