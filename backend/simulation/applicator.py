from __future__ import annotations

from models import Agent, AgentAction, Relationship


def apply_action(
    actor: Agent,
    action: AgentAction,
    all_agents: list[Agent],
) -> str:
    """Validate the structured action against the world and apply state updates.

    Returns a one-line log entry describing what happened.
    """
    by_name = {a.name: a for a in all_agents}

    # Mood update
    actor.mood = action.emotional_reaction

    # Memory
    if action.new_memory:
        actor.short_term_memory.append(action.new_memory)

    # Influence
    for target_name, delta in action.influence_effects.items():
        delta = _clamp(delta, -10.0, 10.0)
        if target_name == "self":
            actor.influence_score = round(_clamp(actor.influence_score + delta, -100, 100), 2)
        elif target_name in by_name:
            t = by_name[target_name]
            t.influence_score = round(_clamp(t.influence_score + delta, -100, 100), 2)

    # Relationships (bidirectional, mirrored)
    for target_name, eff in action.relationship_effects.items():
        if target_name not in by_name or target_name == actor.name:
            continue
        target = by_name[target_name]
        _update_relationship(actor, target.name, eff.type, eff.strength_delta)
        _update_relationship(target, actor.name, eff.type, eff.strength_delta)

    target_str = ", ".join(action.target_agents) if action.target_agents else "alone"
    return f"{actor.name} {action.action} {target_str} — {action.explanation}"


def _update_relationship(agent: Agent, target_name: str, rtype: str, delta: float) -> bool:
    """Return True if the relationship type changed (volatility signal)."""
    existing = agent.relationships.get(target_name)
    changed = False
    if existing is None:
        agent.relationships[target_name] = Relationship(
            type=rtype,
            strength=round(_clamp(delta, -1.0, 1.0), 3),
        )
        return True
    if existing.type != rtype:
        # Type flip happens when delta is strong enough to override
        if abs(delta) >= 0.15:
            existing.type = rtype
            existing.strength = round(_clamp(delta, -1.0, 1.0), 3)
            changed = True
        else:
            existing.strength = round(_clamp(existing.strength + delta * 0.5, -1.0, 1.0), 3)
    else:
        existing.strength = round(_clamp(existing.strength + delta, -1.0, 1.0), 3)
    return changed


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
