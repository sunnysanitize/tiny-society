"""Persona veto — a hard consistency gate between intent and consequence.

Stages 1–2 made relationship *outcomes* earned and bilateral (the consequence layer)
and made agents express in-character *intents* instead of fabricated numbers (the action
contract). But the model can still PROPOSE something out of character — e.g. a freshly
heartbroken, guarded person trying to `court` a near-stranger the same week. The consequence
layer would refuse to *realize* that as romance (no accumulated mutual signal), but the agent
would still narrate flirting, which reads as fake.

This module is the missing half of Stage 3: a deterministic veto that rejects intents a
character plausibly would NOT act on, given their current mood, traits, and standing with the
target, and substitutes the nearest in-character alternative. It is intentionally CONSERVATIVE
— it only intercepts the implausible-intimacy cases that broke realism, so ordinary behavior
(and engagement) is untouched. The veto returns human-readable notes for the day log so the
"why nothing happened" is visible rather than silent.
"""
from __future__ import annotations

from models import Agent, AgentAction
from . import consequence

# Acute emotional states under which initiating a *new* romance is not believable.
# (Mood enum is fixed in the reasoner schema; "heartbroken" is the grief/loss signal.)
_ROMANCE_BLOCKING_MOODS = {"heartbroken"}

# Traits that make bold, public, or fast intimacy out of character. Matched as substrings
# so "very reserved", "emotionally guarded", etc. all count.
_RESERVED_TRAIT_HINTS = ("reserved", "introvert", "shy", "guarded", "private", "stoic", "aloof", "withdrawn")

_ROMANTIC_INTENTS = {"flirt", "court"}

# A near-stranger: too few interactions for a guarded character to make a romantic move.
_FAMILIARITY_MIN_INTERACTIONS = 2


def _has_reserved_trait(agent: Agent) -> bool:
    blob = " ".join(agent.traits + agent.revealed_traits).lower()
    return any(hint in blob for hint in _RESERVED_TRAIT_HINTS)


def vet_action(actor: Agent, action: AgentAction, by_name: dict[str, Agent]) -> list[str]:
    """Filter `action.intents` in place against `actor`'s persona/mood/standing, replacing
    any intent the character implausibly would not act on with its nearest in-character
    fallback. Returns a list of veto notes (empty if nothing was changed).

    All current rules guard the *romance* failure mode (the one that broke realism): you do
    not start courting while heartbroken, while in open conflict with the person, or — if
    you're a guarded character — when you barely know them. Each veto downgrades to a softer
    in-character move (`reconcile` if there's a rift to mend, otherwise `talk`)."""
    notes: list[str] = []
    if not action.intents:
        return notes

    for target_name, intent in list(action.intents.items()):
        verb = (intent or "").strip().lower()
        if verb not in _ROMANTIC_INTENTS:
            continue

        target = by_name.get(target_name)
        rel = actor.relationships.get(target_name)
        aff = rel.strength if rel else 0.0
        rel_type = rel.type if rel else None
        interactions = rel.interactions if rel else 0

        reason: str | None = None
        fallback = "talk"

        # R1 — grief blocks a new courtship. You can't authentically open a romance while
        # acutely heartbroken; the urge to connect doesn't read as flirtation.
        if actor.mood in _ROMANCE_BLOCKING_MOODS:
            reason = f"{actor.name} is {actor.mood} and isn't in a place to pursue romance"

        # R2 — you mend a rift before you flirt across it. Open hostility must resolve first.
        elif rel_type in {"conflict", "rivalry"} or aff <= consequence.RIVALRY_AFFINITY:
            reason = f"{actor.name} is still at odds with {target_name} — there's a rift to mend first"
            fallback = "reconcile"

        # R3 — a guarded character doesn't court someone they barely know.
        elif _has_reserved_trait(actor) and interactions < _FAMILIARITY_MIN_INTERACTIONS:
            reason = f"{actor.name} is too reserved to make a romantic move on someone they barely know"

        if reason is None:
            continue

        action.intents[target_name] = fallback
        notes.append(f"[persona] {actor.name}'s '{verb}' toward {target_name} held back — {reason}.")

    return notes
