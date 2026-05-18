from __future__ import annotations

from models import Agent


CONFLICT_TYPES = {"rivalry", "romance", "conflict"}


def select_reasoning_agents(
    agents: list[Agent],
    event: str | None,
    limit: int,
) -> list[Agent]:
    """Pick the most narratively relevant agents for AI reasoning this day."""
    if not agents:
        return []
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

    ranked = sorted(agents, key=lambda a: scores[a.id], reverse=True)
    return ranked[:limit]
