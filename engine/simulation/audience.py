"""How far an action carries, expressed as physical audience rather than as a channel.

The engine used to make every agent pick from `post | direct | amplify | comment |
interact`. That menu is a social network, and a model handed a social-network menu
writes a social network — which is why a monastery and a war room both produced people
posting and amplifying each other.

An agent now just narrates who was around, in the world's own words, and states the
SCALE of that audience. Scale is setting-neutral in a way a channel is not: "everyone",
"those present" and "one person" are equally true in an abbey, a bridge crew and a
group chat. The fiction rides on `Audience.who`; the mechanics ride on `reach`, which
maps onto exactly the three tiers `observation.witnesses` already implemented — so the
witness model stays deterministic and testable, with no extra LLM call.

This module intentionally does not import from `models` (and `models` must not import
from here) to avoid a circular import: `models.Audience` is the pydantic shape, this
module is the plain-value logic that both `simulation.reasoner` and `models` (via its
own normalize helpers) can depend on.
"""
from __future__ import annotations

REACH_EVERYONE = "everyone"
REACH_PRESENT = "those present"
REACH_ONE = "one person"

_VALID = (REACH_EVERYONE, REACH_PRESENT, REACH_ONE)

# The pre-audience vocabulary, kept only so saved runs and in-flight snapshots load.
_LEGACY = {
    "post": REACH_EVERYONE,
    "direct": REACH_ONE,
    "amplify": REACH_PRESENT,
    "comment": REACH_PRESENT,
    "interact": REACH_PRESENT,
}


def normalize_reach(value: object) -> str:
    """Clamp anything to a valid reach. Defaults to REACH_PRESENT, which is exactly
    what the old `action_kind` default of "interact" produced."""
    if not isinstance(value, str):
        return REACH_PRESENT
    v = value.strip().lower()
    if v in _VALID:
        return v
    return _LEGACY.get(v, REACH_PRESENT)


def reach_from_action_kind(kind: str) -> str:
    """Map a legacy action_kind from an old save onto its equivalent reach."""
    if not isinstance(kind, str):
        return REACH_PRESENT
    return _LEGACY.get(kind.strip().lower(), REACH_PRESENT)


# CORRECTION (Task 6): the plan's original brief called for deleting AgentAction.action_kind
# outright. That would starve simulation/consequence.py's influence math (17 realism tests
# pin its per-kind calibration) and applicator.py's amplify standing-boost, both of which are
# out of scope for this task. action_kind SURVIVES as an internally derived field: the agent
# no longer sees or supplies it (the channel menu is gone from the reasoner prompt), but the
# internal influence/standing mechanics still need a kind, so reasoner._parse_action derives
# one deterministically from the audience the agent DID supply, using the exact rule below.
# Task 7's reach-based witness routing uses this same rule for its standing-spread, so one
# rule serves both consumers.
#
# RULING: this rule can only ever yield {amplify, post, direct, interact} — "comment" is
# retired and "amplify" is narrowed, and both are deliberate, not oversights.
#   - comment is retired because consequence._KIND_SELF_INFLUENCE weights it identically
#     to interact (0.2 each), so collapsing it into "otherwise" costs no influence value.
#   - amplify is narrowed to reach == "everyone" WITH a praise/support intent, whereas the
#     old menu let a model "amplify" during a private exchange, which never made sense —
#     amplifying someone means boosting them PUBLICLY. Rarer but meaningful beats frequent
#     but meaningless. Do not widen this to fire on other reaches; Task 7 keys its
#     standing-spread off the identical condition, and widening here would desync them.
def derive_action_kind(reach: str, intents: dict) -> str:
    """Derive the legacy action_kind from a parsed reach + per-target intents.

    amplify   if any intent is "praise" or "support" AND reach == "everyone"
    post      if reach == "everyone"
    direct    if reach == "one person"
    interact  otherwise
    """
    if reach == REACH_EVERYONE and any(v in ("praise", "support") for v in intents.values()):
        return "amplify"
    if reach == REACH_EVERYONE:
        return "post"
    if reach == REACH_ONE:
        return "direct"
    return "interact"
