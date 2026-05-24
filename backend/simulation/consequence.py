"""Consequence layer — relationships evolve, they are not asserted.

The old model let an agent's single LLM call *declare* a relationship type and delta
(`{"type": "romance", "strength_delta": 0.3}`), which the engine applied verbatim. That
produced bonds "out of thin air": one agent could manufacture a romance (or alliance, or
rivalry) in a single turn, with no buildup and no agreement from the other person.

Here, an agent's proposed `(type, delta)` is treated only as a *bid* — a push on the
underlying **affinity** (continuous sentiment) between the two, damped to a realistic
per-interaction size. The relationship's *type* is then **derived** from accumulated state:

  - affinity (how warm/cold the bond is now),
  - interactions (dwell time — sustained contact, not one moment),
  - romantic signal (rises only on romantic overtures),
  - and, for mutual bonds, the OTHER person's matching state.

So a romance only forms when both people are warmly disposed, both have shown romantic
interest, and they've interacted enough — i.e. it's *earned* and *mutual*. The same earned/
mutual logic generalizes to alliances; antagonism (rivalry/conflict) can be one-sided, as in
life. This is Stage 1 of the realism re-architecture: changes are derived, bilateral, and
rate-calibrated rather than fabricated per turn.
"""
from __future__ import annotations

from models import Agent, Relationship

# ── Calibration (kept deliberately gradual so trajectories look like real life) ──
# A single interaction nudges affinity by at most |delta|*DAMP, so bonds build over days.
AFFINITY_DAMP = 0.5
# Each romantic / allying overture adds this to its accumulator (capped at 1.0). Romance
# and alliance are "special" bonds that need their OWN signal, not just warmth — so close
# friends aren't relabeled as lovers or strategic allies merely for being close.
SIGNAL_STEP = 0.25

# Type thresholds on affinity (and, for mutual bonds, the partner's state / dwell).
ROMANCE_AFFINITY = 0.5          # both sides must be at least this warm
ROMANCE_SIGNAL = 0.4            # both sides must have shown this much romantic interest
ROMANCE_INTERACTIONS = 4        # sustained contact, not a single meeting
ALLIANCE_AFFINITY = 0.35        # mutual positive regard
ALLIANCE_SIGNAL = 0.4           # both sides must have actively allied
ALLIANCE_INTERACTIONS = 3
FRIENDSHIP_AFFINITY = 0.3       # one-sided is fine — you can consider someone a friend
TRUST_AFFINITY = 0.1            # mild positive acquaintance
RIVALRY_AFFINITY = -0.25        # one-sided antagonism is realistic
CONFLICT_AFFINITY = -0.5        # open hostility


# ── Intent → calibrated bid ──────────────────────────────────────────────────────
# The agent chooses a social INTENT (a verb); the *magnitudes* live here, set by design,
# not invented by the model. Each maps to (proposed relationship dimension, affinity bid).
# Positive = warmth, negative = antagonism. These are bids — `accumulate` damps them.
INTENT_EFFECTS: dict[str, tuple[str, float]] = {
    # warmth / closeness
    "befriend":    ("friendship", 0.18),
    "support":     ("friendship", 0.15),
    "comfort":     ("friendship", 0.16),
    "praise":      ("friendship", 0.12),
    "reconcile":   ("friendship", 0.20),
    "confide":     ("trust", 0.18),
    "trust":       ("trust", 0.15),
    # romance (only a romantic intent raises the romantic signal)
    "flirt":       ("romance", 0.15),
    "court":       ("romance", 0.22),
    # strategic / coalition (only these raise the alliance signal)
    "ally":        ("alliance", 0.20),
    "collaborate": ("alliance", 0.16),
    # antagonism (one-sided is fine)
    "confront":    ("conflict", -0.22),
    "rebuke":      ("conflict", -0.18),
    "reject":      ("conflict", -0.20),
    "undermine":   ("rivalry", -0.20),
    "challenge":   ("rivalry", -0.15),
    "compete":     ("rivalry", -0.12),
    "distance":    ("trust", -0.12),   # cooling off
    # neutral contact
    "talk":        ("trust", 0.05),
    "observe":     ("trust", 0.02),
}
_DEFAULT_INTENT = ("trust", 0.05)


def intent_to_bid(intent: str) -> tuple[str, float]:
    """Map a social-intent verb to its (relationship dimension, calibrated affinity bid).
    Unknown/blank intents become mild neutral contact."""
    return INTENT_EFFECTS.get((intent or "").strip().lower(), _DEFAULT_INTENT)


# Derived standing effects (replacing agent-authored influence numbers). Small + calibrated.
_KIND_SELF_INFLUENCE = {"post": 0.6, "amplify": 0.3, "comment": 0.2, "interact": 0.2, "direct": 0.1}
ANTAGONISM_ACTOR_INFLUENCE = 0.3   # publicly challenging a peer raises your profile a touch
ANTAGONISM_TARGET_INFLUENCE = -0.4  # being attacked dents standing


def derive_influence(action_kind: str, is_antagonistic: bool) -> tuple[float, float]:
    """Return (self_delta, target_delta) standing changes derived from HOW the agent acted,
    not from numbers the agent invented. Kept small so influence drifts believably."""
    self_delta = _KIND_SELF_INFLUENCE.get(action_kind, 0.2)
    target_delta = 0.0
    if is_antagonistic:
        self_delta += ANTAGONISM_ACTOR_INFLUENCE
        target_delta = ANTAGONISM_TARGET_INFLUENCE
    return self_delta, target_delta


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def accumulate(agent: Agent, other_name: str, proposed_type: str, delta: float) -> None:
    """Apply one agent's *bid* toward `other_name`: nudge the latent affinity (damped),
    bump the interaction count, and raise the romantic signal on a romantic overture.
    Does NOT decide the relationship type — that's `realize`."""
    if other_name == agent.name:
        return
    step = _clamp(delta, -0.4, 0.4) * AFFINITY_DAMP
    rel = agent.relationships.get(other_name)
    if rel is None:
        rel = Relationship(type="trust", strength=0.0)
        agent.relationships[other_name] = rel
    rel.strength = round(_clamp(rel.strength + step, -1.0, 1.0), 3)
    rel.interactions += 1
    if proposed_type == "romance":
        rel.romantic = round(min(1.0, rel.romantic + SIGNAL_STEP), 3)
    elif proposed_type == "alliance":
        rel.allied = round(min(1.0, rel.allied + SIGNAL_STEP), 3)


def realize(agent: Agent, other_name: str, other_agent: Agent | None) -> None:
    """Derive `agent`'s relationship TYPE toward `other_name` from accumulated state.

    Mutual bonds (romance, alliance) also consult the OTHER direction, so they only form
    when both people qualify. Antagonism can be one-sided. Called after `accumulate` for
    both directions so each side reflects the latest bilateral state."""
    rel = agent.relationships.get(other_name)
    if rel is None:
        return
    aff = rel.strength
    rev = other_agent.relationships.get(agent.name) if other_agent else None
    partner_aff = rev.strength if rev else 0.0
    partner_rom = rev.romantic if rev else 0.0
    partner_allied = rev.allied if rev else 0.0
    inter = rel.interactions

    if (aff >= ROMANCE_AFFINITY and partner_aff >= ROMANCE_AFFINITY
            and rel.romantic >= ROMANCE_SIGNAL and partner_rom >= ROMANCE_SIGNAL
            and inter >= ROMANCE_INTERACTIONS):
        rel.type = "romance"
    elif (aff >= ALLIANCE_AFFINITY and partner_aff >= ALLIANCE_AFFINITY
            and rel.allied >= ALLIANCE_SIGNAL and partner_allied >= ALLIANCE_SIGNAL
            and inter >= ALLIANCE_INTERACTIONS):
        rel.type = "alliance"
    elif aff <= CONFLICT_AFFINITY:
        rel.type = "conflict"
    elif aff <= RIVALRY_AFFINITY:
        rel.type = "rivalry"
    elif aff >= FRIENDSHIP_AFFINITY:
        rel.type = "friendship"
    elif aff >= TRUST_AFFINITY:
        rel.type = "trust"
    # else: affinity is near-neutral — keep the current label (acquaintance-level churn
    # shouldn't relabel a bond on every minor interaction).
