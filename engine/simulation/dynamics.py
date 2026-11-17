"""Daily social dynamics — familiarity, conflict, balance and opinion.

Encodes the social-science models the LLM shouldn't be asked to invent (see
reports/Realistic generative agent societies.md):

  - CLOSENESS is slow familiarity from days of contact (Hall: friendship is
    accumulated time), separate from fast signed affinity, and fades without contact.
  - CONFLICT is a 0-4 ladder (tension → open disagreement → hostile acts →
    coalition-seeking → rupture). Hostile moves climb it; only a reconciliation the
    other side ACCEPTS steps it down — acceptance rises with their agreeableness and
    their remaining affinity.
  - BALANCE (Heider): in a strongly unbalanced triad — my friend's friend is my enemy —
    the weakest edge drifts a little toward balance each day.
  - OPINIONS move by bounded confidence (Deffuant–Weisbuch) only between people who
    actually met: you shift toward views near your own, weighted by how you feel about
    the speaker; hostile pairs push apart; everyone is anchored to their original stance
    (Friedkin–Johnsen stubbornness). Stable factions survive instead of the old
    group-average drift that converged everyone to consensus.
Rates are design values chosen for a 7-day story, not measured constants.
"""
from __future__ import annotations

from models import Agent, AgentAction, WorldEvent
from . import consequence

CLOSENESS_STEP = 0.06       # per day of contact
CLOSENESS_FADE = 0.02       # per day without contact
_HOSTILE = {"confront", "rebuke", "undermine", "reject", "challenge"}
_MENDING = {"reconcile", "comfort", "support", "praise"}
CONFLICT_LABELS = ["", "tension", "open disagreement", "hostile acts", "seeking allies against them", "rupture"]
BALANCE_EDGE = 0.3          # |affinity| for an edge to count in a triad
BALANCE_NUDGE = 0.03
OPINION_RATE = 0.15         # mu
HOSTILE_PUSH = 0.05
ANCHOR_PULL = 0.1           # daily pull back toward one's original stance


def on_action(actor: Agent, action: AgentAction, by_name: dict[str, Agent]) -> list[str]:
    """Climb or descend the conflict ladder for this action. Returns log notes."""
    notes = []
    for t, intent in action.intents.items():
        other = by_name.get(t)
        mine = actor.relationships.get(t)
        if other is None or mine is None:
            continue
        theirs = other.relationships.get(actor.name)
        if intent in _HOSTILE:
            for rel in filter(None, (mine, theirs)):
                rel.conflict = min(4, rel.conflict + 1)
        elif intent in _MENDING and mine.conflict > 0:
            agree = other.profile.agreeableness if other.profile else 0.5
            felt = theirs.strength if theirs else 0.0
            # Accepted when they're agreeable enough and don't loathe you yet.
            if 0.3 * agree + 0.5 * (felt + 1) / 2 >= 0.35:
                for rel in filter(None, (mine, theirs)):
                    rel.conflict = max(0, rel.conflict - 1)
                notes.append(f"[mending] {t} accepted {actor.name}'s attempt to make peace.")
            else:
                notes.append(f"[mending] {t} wasn't ready to accept {actor.name}'s olive branch.")
    return notes


def daily(agents: list[Agent], day_events: list[WorldEvent]) -> None:
    """End-of-day pass over everyone: closeness, balance, opinions."""
    by_name = {a.name: a for a in agents}
    met: set[tuple[str, str]] = set()
    for e in day_events:
        for t in e.targets:
            if t in by_name and e.actor in by_name and t in e.known_by:
                met.add((e.actor, t))
                met.add((t, e.actor))

    for a in agents:
        for name, rel in a.relationships.items():
            if (a.name, name) in met:
                rel.closeness = round(min(1.0, rel.closeness + CLOSENESS_STEP), 3)
            else:
                rel.closeness = round(max(0.0, rel.closeness - CLOSENESS_FADE), 3)

    _balance(agents, by_name)
    _opinions(agents, by_name, met)


def tensions(agent: Agent, roster: list[Agent]) -> list[str]:
    """Felt imbalances for the prompt: a friend who likes someone you're at odds with."""
    by_name = {a.name: a for a in roster}
    lines = []
    for b_name, ab in agent.relationships.items():
        b = by_name.get(b_name)
        if b is None or ab.strength < BALANCE_EDGE:
            continue
        for c_name, ac in agent.relationships.items():
            bc = b.relationships.get(c_name)
            if c_name == b_name or bc is None:
                continue
            if ac.strength <= consequence.RIVALRY_AFFINITY and bc.strength >= BALANCE_EDGE:
                lines.append(f"{b_name} is close to {c_name}, whom you're at odds with.")
    return lines[:3]


def _balance(agents: list[Agent], by_name: dict[str, Agent]) -> None:
    for a in agents:
        for b_name, ab in list(a.relationships.items()):
            b = by_name.get(b_name)
            if b is None or abs(ab.strength) < BALANCE_EDGE:
                continue
            for c_name, bc in b.relationships.items():
                ac = a.relationships.get(c_name)
                if c_name == a.name or ac is None or abs(bc.strength) < BALANCE_EDGE \
                        or abs(ac.strength) < BALANCE_EDGE:
                    continue
                if ab.strength * bc.strength * ac.strength >= 0:
                    continue  # balanced
                # Nudge a's weaker edge toward the sign that would balance the triad.
                if abs(ab.strength) <= abs(ac.strength):
                    want = 1 if bc.strength * ac.strength > 0 else -1
                    ab.strength = round(max(-1, min(1, ab.strength + want * BALANCE_NUDGE)), 3)
                    consequence.realize(a, b_name, b)
                else:
                    want = 1 if ab.strength * bc.strength > 0 else -1
                    ac.strength = round(max(-1, min(1, ac.strength + want * BALANCE_NUDGE)), 3)
                    consequence.realize(a, c_name, by_name.get(c_name))


def _opinions(agents: list[Agent], by_name: dict[str, Agent], met: set[tuple[str, str]]) -> None:
    before = {a.name: dict(a.stance) for a in agents}
    for a_name, b_name in met:
        a, b = by_name[a_name], by_name[b_name]
        radius = 0.2 + 0.3 * (a.profile.openness if a.profile else 0.5)
        rel = a.relationships.get(b_name)
        aff = rel.strength if rel else 0.0
        for topic, x in a.stance.items():
            y = before[b_name].get(topic)
            if y is None:
                continue
            if aff <= consequence.RIVALRY_AFFINITY:
                step = -HOSTILE_PUSH if y > x else HOSTILE_PUSH
            elif abs(y - x) < radius:
                step = OPINION_RATE * (0.5 + 0.5 * max(0.0, aff)) * (y - x)
            else:
                continue
            a.stance[topic] = round(max(-1.0, min(1.0, a.stance[topic] + step)), 3)
    for a in agents:
        for topic, x in a.stance.items():
            anchor = a.stance_anchor.get(topic)
            if anchor is not None:
                a.stance[topic] = round(x + ANCHOR_PULL * (anchor - x), 3)
