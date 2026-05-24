from __future__ import annotations

import math
import random

from models import Agent


CONFLICT_TYPES = {"rivalry", "romance", "conflict"}

# Softmax temperature for converting selection scores into probabilities (Phase 2 #6).
# Lower = sharper (closer to deterministic top-N); higher = flatter (more variety).
SOFTMAX_TEMPERATURE = 1.0


def select_reasoning_agents(
    agents: list[Agent],
    event: str | None,
    limit: int,
    rng: random.Random | None = None,
) -> list[Agent]:
    """Pick the agents for AI reasoning this day via WEIGHTED PROBABILISTIC sampling.

    Scores agents by event-proximity / influence / charged-relationships / group
    connectedness (as before), but instead of taking the strict top-`limit`, it converts
    scores to probabilities (softmax) and samples `limit` distinct agents without
    replacement. High-scorers are still likely but not guaranteed every day, so the
    active set varies day to day (Phase 2 #6 — probabilistic, time-based activation).

    `rng` makes selection reproducible; if omitted, a fresh Random is used.
    """
    if not agents:
        return []
    if limit >= len(agents):
        return list(agents)
    if rng is None:
        rng = random.Random()

    scores: dict[str, float] = {a.id: 0.0 for a in agents}

    # Event proximity: agents whose traits/goals/groups appear in the event text
    if event:
        e = event.lower()
        for a in agents:
            tokens = [a.name.lower()] + [t.lower() for t in a.traits + a.goals + a.groups]
            for tok in tokens:
                if tok and tok in e:
                    scores[a.id] += 3.0

    # Influence
    max_inf = max((a.influence_score for a in agents), default=1.0) or 1.0
    for a in agents:
        scores[a.id] += (a.influence_score / max_inf) * 2.0

    # Active charged relationships
    for a in agents:
        for r in a.relationships.values():
            if r.type in CONFLICT_TYPES and abs(r.strength) >= 0.3:
                scores[a.id] += 1.5
                break

    # Group connectedness
    for a in agents:
        scores[a.id] += min(len(a.groups), 3) * 0.5

    return _weighted_sample_without_replacement(agents, scores, limit, rng)


def _weighted_sample_without_replacement(
    agents: list[Agent],
    scores: dict[str, float],
    limit: int,
    rng: random.Random,
) -> list[Agent]:
    """Softmax-weighted sampling of `limit` distinct agents (no replacement)."""
    pool = list(agents)
    # Softmax over current scores (subtract max for numerical stability).
    selected: list[Agent] = []
    for _ in range(min(limit, len(pool))):
        if not pool:
            break
        vals = [scores[a.id] / SOFTMAX_TEMPERATURE for a in pool]
        m = max(vals)
        weights = [math.exp(v - m) for v in vals]
        total = sum(weights)
        if total <= 0:
            chosen = rng.choice(pool)
        else:
            r = rng.random() * total
            acc = 0.0
            chosen = pool[-1]
            for a, w in zip(pool, weights):
                acc += w
                if r <= acc:
                    chosen = a
                    break
        selected.append(chosen)
        pool.remove(chosen)
    return selected
