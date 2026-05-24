"""Realism calibration / test harness (Stage 4 of the realism re-architecture).

This module is the *calibration anchor* for the simulation's social dynamics. It does
not test that the code "runs"; it tests that the emergent behaviour is REALISTIC and
stays realistic as the model evolves. "Calibrated" here means a small, defensible set
of quantitative invariants hold:

  - Bonds are EARNED and (for romance/alliance) MUTUAL — no relationship springs from a
    single turn or one-sided wishful thinking.
  - Change is SLOW. On any given day only a tiny fraction of relationships flip type;
    relationships mostly persist rather than churn (a base-rate / "world doesn't reset
    every morning" check).
  - Drama is RARE and never fabricated from thin air — romance must arise as a *transition*
    from a prior positive bond ("X and Y: friendship turned into romance"), never as a
    bare "formed a romance", and romance stays rare relative to friendship.
  - The engine is DETERMINISTIC: advancing one day at a time (threading state) is
    byte-identical to running the whole span in one batch call. This is what lets a
    streaming UI resume mid-run without diverging from a replay.
  - Influence stays physically bounded.

Two layers of test:
  * UNIT-LEVEL — drive simulation.consequence.accumulate/realize directly (no LLM).
  * SYSTEM-LEVEL — run the full engine on LLM_PROVIDER=mock (offline, no network/keys).

Calibration thresholds (#6, #7) are documented inline with the values actually OBSERVED
on mock at the time of writing, so future drift is visible as a failing assertion rather
than silent realism rot.

Run:
    LLM_PROVIDER=mock python3 -m pytest tests/test_realism.py -q     # if pytest present
    LLM_PROVIDER=mock python3 tests/test_realism.py                  # plain-script fallback
"""
from __future__ import annotations

import copy
import hashlib
import os
import sys

# Ensure mock provider + import path BEFORE importing project modules.
os.environ.setdefault("LLM_PROVIDER", "mock")
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from models import Agent, World, SimulationConfig  # noqa: E402
from simulation import consequence  # noqa: E402
from simulation import generator  # noqa: E402
from simulation import engine  # noqa: E402


# ── helpers ─────────────────────────────────────────────────────────────────────

def _agent(name: str) -> Agent:
    return Agent(id=f"id_{name}", name=name, role="citizen")


def _exchange(a: Agent, b: Agent, a_type: str, a_delta: float,
              b_type: str, b_delta: float, rounds: int) -> None:
    """Simulate `rounds` reciprocal interactions: each round both sides bid toward the
    other, then both directions are realized (mirroring engine ordering)."""
    for _ in range(rounds):
        consequence.accumulate(a, b.name, a_type, a_delta)
        consequence.accumulate(b, a.name, b_type, b_delta)
        consequence.realize(a, b.name, b)
        consequence.realize(b, a.name, a)


def _build_world(seed_pop: int = 12, prompt: str = "A small town of rivals and lovers"):
    """Build a fully-populated world on mock. Generation uses uuids and is NOT
    deterministic across calls, so callers that need a fixed roster must deepcopy the
    returned agents and reuse them (see test_determinism)."""
    w = World(prompt=prompt, target_population=seed_pop)
    w.agents = generator.generate_fillers(w, seed_pop)
    w.starting_event = "A festival begins."
    return w


def _all_rel_pairs(agents):
    return [(a, name, rel) for a in agents for name, rel in a.relationships.items()]


# ── UNIT-LEVEL INVARIANTS ─────────────────────────────────────────────────────────

def test_romance_requires_sustained_mutual_bids():
    """#1: romance forms ONLY with sustained MUTUAL romantic bids; one-sided romantic
    bids never yield romance; mutual platonic warmth yields friendship, not romance."""
    # (a) mutual sustained flirting/courting over >=4 interactions -> romance
    a, b = _agent("A"), _agent("B")
    _exchange(a, b, "romance", 0.3, "romance", 0.3, rounds=5)
    assert a.relationships["B"].type == "romance", a.relationships["B"]
    assert b.relationships["A"].type == "romance", b.relationships["A"]

    # (b) ONE-SIDED romantic pursuit -> never romance (B only ever does neutral talk)
    c, d = _agent("C"), _agent("D")
    for _ in range(8):
        consequence.accumulate(c, d.name, "romance", 0.3)   # C pines
        consequence.accumulate(d, c.name, "trust", 0.05)    # D is merely cordial
        consequence.realize(c, d.name, d)
        consequence.realize(d, c.name, c)
    assert c.relationships["D"].type != "romance", c.relationships["D"]
    assert d.relationships["C"].type != "romance", d.relationships["C"]

    # (c) mutual PLATONIC closeness (befriend) -> friendship, never romance/alliance
    e_, f = _agent("E"), _agent("F")
    btype, bdelta = consequence.intent_to_bid("befriend")
    _exchange(e_, f, btype, bdelta, btype, bdelta, rounds=8)
    assert e_.relationships["F"].type == "friendship", e_.relationships["F"]
    assert f.relationships["E"].type == "friendship", f.relationships["E"]
    assert e_.relationships["F"].type not in ("romance", "alliance")


def test_alliance_requires_mutual_ally_bids():
    """#2: alliance needs mutual `ally` bids — mere warmth (befriend) does not suffice."""
    # mutual ally bids -> alliance
    a, b = _agent("A"), _agent("B")
    _exchange(a, b, "alliance", 0.25, "alliance", 0.25, rounds=4)
    assert a.relationships["B"].type == "alliance", a.relationships["B"]
    assert b.relationships["A"].type == "alliance", b.relationships["A"]

    # warmth without allying -> friendship, not alliance
    c, d = _agent("C"), _agent("D")
    _exchange(c, d, "friendship", 0.2, "friendship", 0.2, rounds=6)
    assert c.relationships["D"].type == "friendship", c.relationships["D"]
    assert c.relationships["D"].type != "alliance"


def test_conflict_is_gradual_and_may_be_one_sided():
    """#3: a single antagonistic bid does NOT instantly create conflict; sustained
    hostility does. Antagonism may be one-sided."""
    a, b = _agent("A"), _agent("B")
    ctype, cdelta = consequence.intent_to_bid("confront")   # ("conflict", -0.22)
    # ONE bid: max affinity move is |delta|*DAMP = 0.11, far above CONFLICT_AFFINITY=-0.5
    consequence.accumulate(a, b.name, ctype, cdelta)
    consequence.realize(a, b.name, b)
    assert a.relationships["B"].type != "conflict", a.relationships["B"]

    # SUSTAINED one-sided hostility -> conflict eventually (B never retaliates)
    for _ in range(12):
        consequence.accumulate(a, b.name, ctype, cdelta)
        consequence.realize(a, b.name, b)
    assert a.relationships["B"].type == "conflict", a.relationships["B"]
    # one-sided: B has no relationship pushed (A only ever bid toward B)
    assert "A" not in b.relationships


def test_intent_to_bid_is_bounded_and_sensible():
    """#4: every known verb maps to a bounded, sign-sensible (type, delta); unknown
    verbs get a mild neutral default."""
    valid_types = {"friendship", "trust", "romance", "alliance", "conflict", "rivalry"}
    antagonistic = {"confront", "rebuke", "reject", "undermine", "challenge", "compete", "distance"}
    for verb, (rtype, delta) in consequence.INTENT_EFFECTS.items():
        assert rtype in valid_types, (verb, rtype)
        assert -0.4 <= delta <= 0.4, (verb, delta)          # within accumulate's clamp band
        if verb in antagonistic:
            assert delta < 0, (verb, delta)
        elif verb in {"flirt", "court"}:
            assert rtype == "romance" and delta > 0, (verb, rtype, delta)
        elif verb in {"ally", "collaborate"}:
            assert rtype == "alliance" and delta > 0, (verb, rtype, delta)
    # unknown / blank -> mild neutral default
    assert consequence.intent_to_bid("xyzzy") == consequence._DEFAULT_INTENT
    assert consequence.intent_to_bid("") == consequence._DEFAULT_INTENT
    dtype, ddelta = consequence._DEFAULT_INTENT
    assert dtype in valid_types and abs(ddelta) <= 0.1


def test_persona_veto_blocks_implausible_romance():
    """#10 (Stage 3): the persona veto downgrades romantic intents a character would not
    act on — heartbroken mood, an unresolved rift, or a guarded near-stranger — and leaves
    plausible ones intact."""
    from models import AgentAction
    from simulation.persona import vet_action

    def _action(intents):
        return AgentAction(action="approach", action_kind="direct",
                           target_agents=list(intents), intents=dict(intents),
                           new_memory="I approached them.", explanation="testing")

    # (a) heartbroken -> 'court' is held back to 'talk'
    grieving = _agent("Grieving"); grieving.mood = "heartbroken"
    other = _agent("Other")
    act = _action({"Other": "court"})
    notes = vet_action(grieving, act, {"Other": other})
    assert act.intents["Other"] == "talk", act.intents
    assert notes and "heartbroken" in notes[0]

    # (b) open rift -> 'flirt' becomes 'reconcile' (mend first)
    foe_a, foe_b = _agent("FoeA"), _agent("FoeB")
    _exchange(foe_a, foe_b, "conflict", -0.3, "conflict", -0.3, rounds=4)
    assert foe_a.relationships["FoeB"].type in ("conflict", "rivalry")
    act = _action({"FoeB": "flirt"})
    vet_action(foe_a, act, {"FoeB": foe_b})
    assert act.intents["FoeB"] == "reconcile", act.intents

    # (c) reserved character + near-stranger -> 'court' held back to 'talk'
    shy = _agent("Shy"); shy.traits = ["reserved", "bookish"]
    stranger = _agent("Stranger")
    act = _action({"Stranger": "court"})
    vet_action(shy, act, {"Stranger": stranger})
    assert act.intents["Stranger"] == "talk", act.intents

    # (d) an established, calm couple's 'flirt' is NOT vetoed
    lover_a, lover_b = _agent("LoverA"), _agent("LoverB")
    lover_a.mood = "content"
    _exchange(lover_a, lover_b, "romance", 0.3, "romance", 0.3, rounds=5)
    act = _action({"LoverB": "flirt"})
    notes = vet_action(lover_a, act, {"LoverB": lover_b})
    assert act.intents["LoverB"] == "flirt", act.intents
    assert notes == []

    # (e) non-romantic intents are never touched, even while heartbroken
    act = _action({"Other": "support"})
    notes = vet_action(grieving, act, {"Other": other})
    assert act.intents["Other"] == "support" and notes == []


def test_seeded_antagonism_persists():
    """#11: a seeded rivalry/conflict is stored as NEGATIVE affinity and survives realize
    (it used to be seeded positive and flip to warmth on first contact). Mutual romance/
    alliance seeds realize bilaterally."""
    a, b = _agent("A"), _agent("B")
    consequence.seed_relationship(a, b, "rivalry", 0.4, mutual=False)
    assert a.relationships["B"].type == "rivalry", a.relationships["B"]
    assert a.relationships["B"].strength < 0, a.relationships["B"]
    assert "A" not in b.relationships  # one-sided antagonism

    # an ordinary neutral interaction must not flip the rivalry to warmth
    consequence.accumulate(a, b.name, "trust", 0.05)
    consequence.realize(a, b.name, b)
    assert a.relationships["B"].type in ("rivalry", "conflict"), a.relationships["B"]

    c, d = _agent("C"), _agent("D")
    consequence.seed_relationship(c, d, "conflict", 0.6, mutual=True)
    assert c.relationships["D"].type == "conflict" and d.relationships["C"].type == "conflict"

    e_, f = _agent("E"), _agent("F")
    consequence.seed_relationship(e_, f, "romance", 0.6, mutual=True)
    assert e_.relationships["F"].type == "romance" and f.relationships["E"].type == "romance"


def test_background_rivalry_not_zeroed():
    """#12: the background (deterministic) layer fades a negative-affinity rivalry toward
    neutral by at most one DECAY step — it must NOT snap it to 0 (the old positive-only
    rule did), and the type stays consistent with the affinity."""
    import random as _r
    from simulation.deterministic import apply_background_rules, DECAY

    a, b = _agent("A"), _agent("B")
    consequence.seed_relationship(a, b, "rivalry", 0.4, mutual=True)
    before = a.relationships["B"].strength
    assert before < 0
    apply_background_rules([a, b], [a, b], _r.Random(1))
    after = a.relationships["B"].strength
    assert after < 0, after
    assert abs(after - before) <= DECAY + 1e-9, (before, after)
    assert a.relationships["B"].type in ("rivalry", "conflict"), a.relationships["B"]


def test_metrics_count_one_sided_rivalry():
    """#13: macro metrics count a one-sided rivalry as a rivalry (the old `//2` symmetric
    counting reported 0 for a single directed antagonistic edge)."""
    from simulation.metrics import compute_metrics

    a, b = _agent("A"), _agent("B")
    consequence.seed_relationship(a, b, "rivalry", 0.4, mutual=False)
    m = compute_metrics([a, b])
    assert m.rivalry_count == 1, m.rivalry_count


def test_mood_normalization_keeps_action():
    """#14: off-enum moods are mapped onto the Mood enum (or fall back) so building an
    AgentAction never raises — which previously dropped the agent's entire turn."""
    from models import normalize_mood, AgentAction

    assert normalize_mood("happy") == "content"
    assert normalize_mood("FURIOUS") == "angry"
    assert normalize_mood("calm") == "calm"
    assert normalize_mood("zxcv", default="hopeful") == "hopeful"
    assert normalize_mood("ecstatic", default="calm") == "calm"

    act = AgentAction(
        action="x",
        emotional_reaction=normalize_mood("totally-not-a-mood", default="calm"),
        new_memory="m", explanation="e",
    )
    assert act.emotional_reaction == "calm"


def test_stance_grounded_in_disposition():
    """#15: starting stances correlate with character disposition (openness↔caution),
    not pure hash noise — an open-disposition agent leans more positive than a cautious one."""
    from simulation.stance import initialize_stances, _disposition

    opener = _agent("Opener"); opener.traits = ["idealistic", "creative", "ambitious"]
    guard = _agent("Guard"); guard.traits = ["traditional", "cautious", "stubborn"]
    assert _disposition(opener) > 0
    assert _disposition(guard) < 0

    topics = ["tradition versus progress"]
    initialize_stances([opener, guard], topics)
    assert opener.stance[topics[0]] > guard.stance[topics[0]], (
        opener.stance, guard.stance
    )


# ── SYSTEM-LEVEL INVARIANTS (full engine on mock) ──────────────────────────────────

# A modest-length run is enough for arcs to form without being expensive on mock.
_SYS_DAYS = 18
_SYS_POP = 12
_SYS_RPD = 3
_SYS_SEED = 7


def _run_system(seed: int = _SYS_SEED, days: int = _SYS_DAYS):
    w = _build_world(_SYS_POP)
    return w, engine.run_simulation(
        w, SimulationConfig(days=days, reasoning_agents_per_day=_SYS_RPD), seed=seed
    )


def test_every_romance_edge_is_mutual():
    """#5: if A->B is romance then B->A is romance too (scan final snapshot)."""
    _, result = _run_system()
    final = result.snapshots[-1].agents
    by_name = {a.name: a for a in final}
    romance_edges = 0
    for a, other, rel in _all_rel_pairs(final):
        if rel.type == "romance":
            romance_edges += 1
            partner = by_name.get(other)
            assert partner is not None, other
            back = partner.relationships.get(a.name)
            assert back is not None and back.type == "romance", (
                f"{a.name}->{other} is romance but {other}->{a.name} is "
                f"{getattr(back, 'type', None)}"
            )
    # The assertion is meaningful whether or not romance occurred on this seed; we just
    # record the count for visibility. (Observed: 0 romance edges on mock seed 7.)
    print(f"  [#5] romance edges (must be mutual): {romance_edges}")


def test_changes_are_slow_base_rate():
    """#6: relationship TYPE churn is low. Milestones are the engine's record of *earned*
    type transitions/deepenings, so milestones-per-day is our churn proxy.

    Calibration: with 12 agents there are up to ~12*11 = 132 directed relationship slots.
    A realistic society does not re-label a meaningful share of them daily. We require the
    average milestones/day to stay well below the agent count (< _SYS_POP), i.e. on a
    typical day fewer than one relationship per agent changes character.

    OBSERVED on mock (18 days, pop 12): ~0.17-0.28 milestones/day across seeds 7/21/99
    (exact value drifts because each run generates a fresh roster via uuids). The
    threshold of `< _SYS_POP` (=12) is ~40x the observed rate, so it is comfortably
    satisfied yet would still catch a regression that made bonds churn every turn (the
    old "thin air" behaviour)."""
    for seed in (7, 21, 99):
        _, result = _run_system(seed=seed)
        total_ms = sum(len(s.milestones) for s in result.snapshots)
        per_day = total_ms / len(result.snapshots)
        print(f"  [#6] seed={seed} milestones/day={per_day:.2f} (total={total_ms})")
        assert per_day < _SYS_POP, (seed, per_day)
        # Sanity: a strictly positive but low rate (we don't want a frozen world either,
        # but zero is acceptable on a quiet seed — only the upper bound is the invariant).


def test_no_thin_air_drama():
    """#7: zero milestones of the literal 'formed a romance' form (romance must arise via
    a 'turned into romance' transition from a prior bond), and romance is rare relative to
    friendship in the final state.

    OBSERVED on mock (18 days): 'formed a romance' count = 0 across seeds 7/21/99;
    final romance edges = 0 vs friendship edges 8-10. The rarity assertion uses
    `romance_edges <= friendship_edges` which is the calibration claim (romance never
    outnumbers friendship); it holds even on seeds that do produce romance."""
    for seed in (7, 21, 99):
        _, result = _run_system(seed=seed)
        formed_romance = sum(
            1 for s in result.snapshots for m in s.milestones
            if "formed a romance" in m.lower()
        )
        assert formed_romance == 0, (
            f"seed={seed}: romance must arise via a 'turned into romance' transition, "
            f"not be fabricated as 'formed a romance' ({formed_romance} found)"
        )
        final = result.snapshots[-1].agents
        rom = sum(1 for _, _, rel in _all_rel_pairs(final) if rel.type == "romance")
        fri = sum(1 for _, _, rel in _all_rel_pairs(final) if rel.type == "friendship")
        print(f"  [#7] seed={seed} formed_romance={formed_romance} romance_edges={rom} "
              f"friendship_edges={fri}")
        assert rom <= fri, (seed, rom, fri)


def test_determinism_day_by_day_equals_batch():
    """#8: N days in one run_simulation call == advancing one day at a time, byte-for-byte
    on the concatenated event log. Day-by-day threads initial_agents, day_offset,
    baseline_influence, prior_event_log (lines from prior snapshots) and active_event_in.

    Generation is non-deterministic (uuids), so we generate ONE roster and reuse a deep
    copy of it for both paths."""
    base = _build_world(_SYS_POP)
    fixed_agents = copy.deepcopy(base.agents)
    days = 6  # plenty to exercise event carry-over / dynamic-event timing differences

    # BATCH
    w_batch = base.model_copy(deep=True)
    w_batch.world_graph = None
    r_batch = engine.run_simulation(
        w_batch, SimulationConfig(days=days, reasoning_agents_per_day=_SYS_RPD),
        seed=_SYS_SEED, initial_agents=copy.deepcopy(fixed_agents),
    )
    batch_log = [line for s in r_batch.snapshots for line in s.event_log]

    # DAY-BY-DAY
    w_step = base.model_copy(deep=True)
    w_step.world_graph = None
    cur_agents = copy.deepcopy(fixed_agents)
    day_offset = 0
    baseline = None
    active_in = None
    prior_log: list[str] = []
    step_log: list[str] = []
    for _ in range(days):
        r = engine.run_simulation(
            w_step, SimulationConfig(days=1, reasoning_agents_per_day=_SYS_RPD),
            seed=_SYS_SEED,
            initial_agents=cur_agents,
            day_offset=day_offset,
            baseline_influence=baseline,
            prior_event_log=list(prior_log),
            active_event_in=active_in,
        )
        snap = r.snapshots[-1]
        step_log.extend(snap.event_log)
        cur_agents = snap.agents
        day_offset += 1
        prior_log.extend(snap.event_log)
        baseline = r.baseline_influence
        active_in = snap.active_event

    h_batch = hashlib.sha256("\n".join(batch_log).encode()).hexdigest()
    h_step = hashlib.sha256("\n".join(step_log).encode()).hexdigest()
    print(f"  [#8] batch={h_batch[:16]} step={h_step[:16]}")
    assert batch_log == step_log, "day-by-day diverged from batch"
    assert h_batch == h_step


def test_influence_stays_bounded():
    """#9: influence_score stays within [-100, 100] for every agent on every day."""
    for seed in (7, 21, 99):
        _, result = _run_system(seed=seed)
        lo = min(a.influence_score for s in result.snapshots for a in s.agents)
        hi = max(a.influence_score for s in result.snapshots for a in s.agents)
        print(f"  [#9] seed={seed} influence range=[{lo:.1f}, {hi:.1f}]")
        for s in result.snapshots:
            for a in s.agents:
                assert -100.0 <= a.influence_score <= 100.0, (seed, a.name, a.influence_score)


# ── plain-script fallback (used when pytest is not installed) ──────────────────────

_TESTS = [
    test_romance_requires_sustained_mutual_bids,
    test_alliance_requires_mutual_ally_bids,
    test_conflict_is_gradual_and_may_be_one_sided,
    test_intent_to_bid_is_bounded_and_sensible,
    test_persona_veto_blocks_implausible_romance,
    test_seeded_antagonism_persists,
    test_background_rivalry_not_zeroed,
    test_metrics_count_one_sided_rivalry,
    test_mood_normalization_keeps_action,
    test_stance_grounded_in_disposition,
    test_every_romance_edge_is_mutual,
    test_changes_are_slow_base_rate,
    test_no_thin_air_drama,
    test_determinism_day_by_day_equals_batch,
    test_influence_stays_bounded,
]


def _main() -> int:
    failures = 0
    for t in _TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as exc:  # noqa: BLE001 — harness wants to report, not crash
            failures += 1
            import traceback
            print(f"FAIL  {t.__name__}: {exc}")
            traceback.print_exc()
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
