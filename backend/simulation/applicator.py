from __future__ import annotations

from typing import Optional

from models import Agent, AgentAction, PerceptionNote, Relationship
from .perception import perceive_event
from .memory import make_memory
from . import consequence


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
    # standing — endorsement transfers influence. (Reach/visibility is handled in
    # observation.distribute_observation.)
    AMPLIFY_INFLUENCE_BOOST = 2.0
    if action.action_kind == "amplify":
        for tname in action.target_agents:
            t = by_name.get(tname)
            if t is not None and t.name != actor.name:
                t.influence_score = round(
                    _clamp(t.influence_score + AMPLIFY_INFLUENCE_BOOST, -100, 100), 2
                )

    # SOCIAL MOVE → CONSEQUENCE. The agent expressed an in-character INTENT toward each
    # target (not a number). For each, map the intent to a calibrated affinity bid, route
    # the target's side through perception, accumulate both directions, then DERIVE each
    # side's relationship type from the bilateral state. Bonds are earned, never asserted.
    for target_name in action.target_agents:
        if target_name not in by_name or target_name == actor.name:
            continue
        target = by_name[target_name]
        intent = action.intents.get(target_name, "talk")
        proposed_type, base_delta = consequence.intent_to_bid(intent)

        # Snapshot the actor's prior bond so we can detect a story milestone afterward.
        prev = actor.relationships.get(target.name)
        prev_type = prev.type if prev else None
        prev_strength = prev.strength if prev else 0.0

        # The target's SUBJECTIVE reception of the move (perception modulates how it lands).
        action_summary = action.utterance or action.new_memory or f"{action.action} {target_name}"
        perceived_delta, note = perceive_event(
            perceiver=target,
            actor=actor,
            raw_delta=base_delta,
            rel_type=proposed_type,
            action_summary=action_summary,
        )
        if note:
            perception_notes.append(note)

        consequence.accumulate(actor, target.name, proposed_type, base_delta)
        consequence.accumulate(target, actor.name, proposed_type, perceived_delta)
        consequence.realize(actor, target.name, target)
        consequence.realize(target, actor.name, actor)

        now = actor.relationships.get(target.name)
        if now is not None:
            ms = _detect_milestone(
                actor.name, target.name, prev_type, prev_strength, now, action.explanation
            )
            if ms:
                milestones.append(ms)

        # DERIVED INFLUENCE: standing shifts from HOW the agent acted, not invented numbers.
        is_antagonistic = base_delta < 0
        self_inf, target_inf = consequence.derive_influence(action.action_kind, is_antagonistic)
        actor.influence_score = round(_clamp(actor.influence_score + self_inf, -100, 100), 2)
        if target_inf:
            target.influence_score = round(_clamp(target.influence_score + target_inf, -100, 100), 2)

        # TWO-SIDED MEMORY: the target remembers what was done TO them — prefer the
        # perception narrative (it's written from the target's perspective); else a neutral
        # line in the target's POV (NOT the actor's first-person utterance).
        if note and note.narrative:
            received = note.narrative
        else:
            received = f"{actor.name} chose to {action.action} toward me."
        target.short_term_memory.append(make_memory(received, day=day))

    # If the agent acted on no one (e.g. a public post to the world), still reflect the
    # standing effect of speaking up.
    if not action.target_agents:
        self_inf, _ = consequence.derive_influence(action.action_kind, False)
        actor.influence_score = round(_clamp(actor.influence_score + self_inf, -100, 100), 2)

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
    a_name: str, b_name: str, prev_type: Optional[str], prev_strength: float,
    now: Relationship, explanation: str = "",
) -> Optional[str]:
    """Return a human-readable 'turning point' beat if this relationship change is
    narratively significant — a new charged bond, a type flip, or a deepening past the
    threshold. The actor's `explanation` (why they acted) is appended as the WHY, which
    is what players want most — so a milestone reads "X and Y formed a romance — <why>"
    instead of a bare label. Otherwise None."""
    new_type = now.type
    new_strength = now.strength
    label: Optional[str] = None
    if prev_type is None:
        if new_type in _MILESTONE_TYPES and abs(new_strength) >= 0.2:
            label = f"{a_name} and {b_name} formed a {new_type}."
    elif prev_type != new_type:
        # Suppress flips within the same narrative family (rivalry⇄conflict, etc.) —
        # they're not genuine turning points, just noise.
        if _TYPE_FAMILY.get(prev_type) != _TYPE_FAMILY.get(new_type):
            label = f"{a_name} and {b_name}: {prev_type} turned into {new_type}."
    elif abs(prev_strength) < _DEEP_THRESHOLD <= abs(new_strength):
        word = "deepened" if new_strength > 0 else "hardened"
        label = f"{a_name} and {b_name}'s {new_type} {word}."

    if label is None:
        return None
    why = (explanation or "").strip().rstrip(".")
    return f"{label.rstrip('.')} — {why}." if why else label


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
