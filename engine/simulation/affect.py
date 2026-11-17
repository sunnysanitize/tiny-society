"""Mood with inertia — emotions push a mood that drifts back to a personal baseline.

`mood` used to be overwritten by every action's `emotional_reaction`, so a character
could go content → angry → hopeful within one afternoon. Following ALMA's layering
(emotion → mood → personality), each character carries a pleasure/arousal/dominance
(PAD) vector:
  - an emotion (the action's reaction, or how a received move landed) pulls the vector;
  - inertia keeps most of the previous state (more for high-neuroticism characters,
    whose affect is measurably stickier — Kuppens et al. 2010);
  - overnight the vector relaxes toward a baseline set by personality (Mehrabian's
    Big Five → PAD regression).
The `mood` label only changes when the new emotion fits the moved vector better than
the current label does, so labels change for a reason and then hold.
"""
from __future__ import annotations

import math

from models import Agent

# PAD prototypes for the fixed mood vocabulary (Mehrabian-style placements).
MOOD_PAD: dict[str, tuple[float, float, float]] = {
    "calm":        (0.4, -0.4, 0.2),
    "content":     (0.6, -0.3, 0.3),
    "hopeful":     (0.5, 0.2, 0.1),
    "excited":     (0.6, 0.7, 0.3),
    "confident":   (0.5, 0.2, 0.7),
    "ambitious":   (0.3, 0.5, 0.6),
    "anxious":     (-0.4, 0.6, -0.5),
    "frustrated":  (-0.5, 0.5, -0.2),
    "angry":       (-0.6, 0.7, 0.4),
    "lonely":      (-0.5, -0.4, -0.4),
    "heartbroken": (-0.8, -0.2, -0.6),
}
# How hard one emotion pulls the mood vector: one's own action vs. something done to you.
OWN_PULL = 0.35
RECEIVED_PULL = 0.2
# Perceived affinity change beyond which a received move registers as an emotion.
RECEIVED_THRESHOLD = 0.12


def baseline(agent: Agent) -> tuple[float, float, float]:
    """Resting PAD from personality (Mehrabian 1996), traits centered to [-1, 1]."""
    p = agent.profile
    if p is None:
        return MOOD_PAD.get(agent.mood, MOOD_PAD["calm"])
    o, c, e, a = (2 * x - 1 for x in (p.openness, p.conscientiousness, p.extraversion, p.agreeableness))
    stab = 1 - 2 * p.neuroticism
    pleasure = 0.21 * e + 0.59 * a + 0.19 * stab
    arousal = 0.15 * o + 0.30 * a - 0.57 * stab
    dominance = 0.25 * o + 0.17 * c + 0.60 * e - 0.32 * a
    return (_clip(pleasure), _clip(arousal), _clip(dominance))


def feel(agent: Agent, emotion: str, pull: float = OWN_PULL) -> None:
    """Apply one emotion to the agent's mood vector and re-derive the label."""
    proto = MOOD_PAD.get(emotion)
    if proto is None:
        return
    base = baseline(agent)
    cur = agent.pad if len(agent.pad) == 3 else list(MOOD_PAD.get(agent.mood, base))
    rho = _inertia(agent)
    agent.pad = [round(_clip(b + rho * (x - b) + pull * (t - b)), 3)
                 for x, b, t in zip(cur, base, proto)]
    # Switch label only if the new emotion now describes the state better.
    if emotion != agent.mood and _dist(agent.pad, proto) < _dist(agent.pad, MOOD_PAD.get(agent.mood, base)):
        agent.mood = emotion


def feel_received(agent: Agent, perceived_delta: float) -> None:
    """How a move that landed on `agent` colors their mood."""
    if abs(perceived_delta) < RECEIVED_THRESHOLD:
        return
    p = agent.profile
    if perceived_delta < 0:
        hot = p is not None and (p.neuroticism > 0.6 or p.agreeableness < 0.35)
        feel(agent, "angry" if hot else "frustrated", RECEIVED_PULL)
    else:
        feel(agent, "hopeful" if (p and p.neuroticism > 0.5) else "content", RECEIVED_PULL)


def overnight(agent: Agent) -> None:
    """Relax toward baseline; a calmed vector can bring the label back down."""
    if len(agent.pad) != 3:
        return
    base = baseline(agent)
    keep = 0.4 + 0.4 * (agent.profile.neuroticism if agent.profile else 0.5)
    agent.pad = [round(b + keep * (x - b), 3) for x, b in zip(agent.pad, base)]
    nearest = min(MOOD_PAD, key=lambda m: _dist(agent.pad, MOOD_PAD[m]))
    if _dist(agent.pad, MOOD_PAD[nearest]) < _dist(agent.pad, MOOD_PAD.get(agent.mood, base)) - 0.15:
        agent.mood = nearest


def _inertia(agent: Agent) -> float:
    return 0.55 + 0.3 * (agent.profile.neuroticism if agent.profile else 0.5)


def _dist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _clip(x: float) -> float:
    return max(-1.0, min(1.0, x))
