from __future__ import annotations

from typing import Optional

from models import Agent, AgentAction, PerceptionNote, Relationship
from .perception import perceive_event
from .memory import make_memory


# A relationship turning into one of these (or forming as one) is a story milestone.
_MILESTONE_TYPES = {"romance", "rivalry", "conflict", "alliance", "friendship"}
# |strength| at/above which a bond is "deep" — crossing it upward is a milestone.
_DEEP_THRESHOLD = 0.6
# Types that mean the same thing narratively — a flip WITHIN a family isn't a real
# turning point (e.g. rivalry⇄conflict just ping-pongs), so we don't report it.
_TYPE_FAMILY = {
    "rivalry": "antagonism", "conflict": "antagonism",
    "friendship": "warmth", "alliance": "warmth", "trust": "warmth", "romance": "romance",
    "influence": "power", "group_membership": "group",
}


def apply_action(
    actor: Agent,
    action: AgentAction,
    all_agents: list[Agent],
    day: int = 0,
) -> tuple[str, list[PerceptionNote], list[str]]:
    """Validate the structured action against the world and apply state updates.

    The actor's own relationship updates are applied directly — they reflect the actor's
    intent. The target's side is routed through the perception layer so each agent
    internalises events through their own personality and history. Each targeted agent
    also records a first-person MEMORY of what was done to them, so relationships are
    remembered two-sidedly (grudges, callbacks, reconciliations) instead of only the
    actor remembering their own move.

    Returns a (log_line, perception_notes, milestones) tuple.
    """
    by_name = {a.name: a for a in all_agents}
    perception_notes: list[PerceptionNote] = []
    milestones: list[str] = []

    # Mood update
    actor.mood = action.emotional_reaction

    # Memory — heuristic importance assigned at creation
    if action.new_memory:
        actor.short_term_memory.append(make_memory(action.new_memory, day=day))

    # AMPLIFY side-effect (Phase 2 #5): boosting/reposting another agent raises THEIR
    # influence — endorsement transfers standing. (Reach/visibility spread is handled in
    # observation.distribute_observation.) Applied on top of any influence_effects.
    AMPLIFY_INFLUENCE_BOOST = 2.0
    if action.action_kind == "amplify":
        for tname in action.target_agents:
            t = by_name.get(tname)
            if t is not None and t.name != actor.name:
                t.influence_score = round(
                    _clamp(t.influence_score + AMPLIFY_INFLUENCE_BOOST, -100, 100), 2
                )

    # Influence
    for target_name, delta in action.influence_effects.items():
        delta = _clamp(delta, -10.0, 10.0)
        if target_name == "self":
            actor.influence_score = round(_clamp(actor.influence_score + delta, -100, 100), 2)
        elif target_name in by_name:
            t = by_name[target_name]
            t.influence_score = round(_clamp(t.influence_score + delta, -100, 100), 2)

    # Relationships — actor side is direct; target side goes through perception
    for target_name, eff in action.relationship_effects.items():
        if target_name not in by_name or target_name == actor.name:
            continue
        target = by_name[target_name]

        # Actor's own relationship: their intent, applied as-is. Capture before/after
        # so we can detect a story milestone (type change or strength crossing).
        prev = actor.relationships.get(target.name)
        prev_type = prev.type if prev else None
        prev_strength = prev.strength if prev else 0.0
        _update_relationship(actor, target.name, eff.type, eff.strength_delta)
        now = actor.relationships.get(target.name)
        if now is not None:
            ms = _detect_milestone(actor.name, target.name, prev_type, prev_strength, now)
            if ms:
                milestones.append(ms)

        # Target's relationship: filtered through their character
        action_summary = action.new_memory or f"{action.action} {target_name}"
        perceived_delta, note = perceive_event(
            perceiver=target,
            actor=actor,
            raw_delta=eff.strength_delta,
            rel_type=eff.type,
            action_summary=action_summary,
        )
        _update_relationship(target, actor.name, eff.type, perceived_delta)
        if note:
            perception_notes.append(note)

        # TWO-SIDED MEMORY: the target remembers what was done TO them. Prefer the
        # perception narrative (it's specific to the target's character); otherwise a
        # plain first-person line. Gated on a non-trivial interaction to avoid noise.
        if abs(eff.strength_delta) >= 0.05:
            if note and note.narrative:
                received = note.narrative
            else:
                received = f"{actor.name} chose to {action.action} toward me."
            target.short_term_memory.append(make_memory(received, day=day))

    # Stance — apply small per-topic deltas to the actor's positions (clamp to [-1, 1]).
    for topic, delta in action.stance_shift.items():
        try:
            d = _clamp(float(delta), -0.3, 0.3)
        except (TypeError, ValueError):
            continue
        current = actor.stance.get(topic, 0.0)
        actor.stance[topic] = round(_clamp(current + d, -1.0, 1.0), 3)

    # ANTI-REPETITION: record this action on the actor's rolling history so the
    # reasoner can show the agent its own recent pattern and push it to vary.
    tgt = ", ".join(action.target_agents) if action.target_agents else "no one"
    actor.recent_actions.append(f"day {day}: {action.action_kind}/{action.action} → {tgt}")
    actor.recent_actions = actor.recent_actions[-6:]

    if action.new_memory:
        log_line = f"[{actor.name}] {action.new_memory} ({action.explanation})"
    else:
        target_str = ", ".join(action.target_agents) if action.target_agents else "alone"
        log_line = f"[{actor.name}] chose to {action.action} {target_str}. {action.explanation}"

    return log_line, perception_notes, milestones


def _detect_milestone(
    a_name: str, b_name: str, prev_type: Optional[str], prev_strength: float, now: Relationship
) -> Optional[str]:
    """Return a human-readable 'turning point' beat if this relationship change is
    narratively significant — a new charged bond, a type flip, or a deepening past
    the threshold. Otherwise None."""
    new_type = now.type
    new_strength = now.strength
    if prev_type is None:
        if new_type in _MILESTONE_TYPES and abs(new_strength) >= 0.2:
            return f"{a_name} and {b_name} formed a {new_type}."
        return None
    if prev_type != new_type:
        # Suppress flips within the same narrative family (rivalry⇄conflict, etc.) —
        # they're not genuine turning points, just noise.
        if _TYPE_FAMILY.get(prev_type) == _TYPE_FAMILY.get(new_type):
            return None
        return f"{a_name} and {b_name}: {prev_type} turned into {new_type}."
    if abs(prev_strength) < _DEEP_THRESHOLD <= abs(new_strength):
        word = "deepened" if new_strength > 0 else "hardened"
        return f"{a_name} and {b_name}'s {new_type} {word}."
    return None


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
