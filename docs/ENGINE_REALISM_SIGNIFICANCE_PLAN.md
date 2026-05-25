# Engine realism & significance improvements

> **For a fresh-context implementer.** This is an approved implementation plan. Read this
> orientation first, then implement §1–§7. The codebase already has a `docs/REALISM_ANALYSIS.md`
> describing prior realism work — skim it for background.
>
> **Engine architecture (where things live, all under `engine/`):**
> - `simulation/engine.py` — `run_simulation(...)`: the daily loop (morning memory promotion →
>   afternoon select+reason → evening background rules → night metrics+snapshot). Per-day seeded
>   RNG `day_rng = random.Random(seed + abs_day)` (line ~127) makes day-by-day advancing
>   byte-identical to a batch run — **this invariant is sacred**.
> - `simulation/reasoner.py` — builds the per-agent LLM prompt; emits a structured `AgentAction`.
> - `simulation/applicator.py` — `apply_action(...)`: applies an action's consequences (relationships
>   via the consequence layer, influence, stance, memory, milestones).
> - `simulation/consequence.py` — the model to imitate: agents emit *intent verbs*, not numbers;
>   relationship type is **derived** from accumulated bilateral affinity/dwell/signal. Calibrated,
>   damped, earned. §1 applies this same philosophy to beliefs.
> - `simulation/perception.py` — modulates how an incoming action "lands" for the target.
> - `simulation/observation.py` — `witnesses(...)` / `distribute_observation(...)`: who sees an action
>   (echo chambers, information asymmetry).
> - `simulation/metrics.py` — `compute_metrics(...)`: relationship counts, belief mean/spread, influence
>   gainers/losers. Signed-affinity unordered-pair logic at lines ~26-42.
> - `simulation/reporter.py` — `build_forecast(...)` (numeric, from real metrics) + `generate_final_report(...)`
>   (single LLM narrative call). Pivotal days currently = belief-drift only.
> - `simulation/deterministic.py` — `apply_background_rules(...)`: off-screen agents' bond decay,
>   belief conformity drift, influence regression.
> - `simulation/selector.py` — softmax-weighted agent selection per day.
> - `models.py` — Pydantic models: `Agent`, `AgentAction`, `Relationship`, `MacroMetrics`, `Forecast`,
>   `SimulationConfig`, `DaySnapshot`.
> - `llm.py` — `call_llm(...)` with tiers + a `mock` provider (deterministic fake JSON) used by tests.
>
> **Hard invariants — preserve all three:** (a) day-by-day == batch, byte-identical (event-log +
> milestone + volatility hash, checked in `backend/tests/test_realism.py`); (b) the `mock` provider
> must work with no API keys; (c) no new **per-day** LLM calls. All new logic here is deterministic
> math over existing state (no RNG, no LLM), so these hold by construction.
>
> **Suggested build order:** §1 (belief layer) → §6 (bounded-confidence, folds into §1) →
> §3 (factions) → §7 (balance) → §2 (significance, depends on §3/§7) → §4 (mood) → §5 (ensemble,
> depends on §1/§6). Run the determinism harness after each step.

## Context

The simulation engine is already sophisticated: a consequence layer makes relationships
*earned and bilateral* rather than asserted (`engine/simulation/consequence.py`), a
perception layer reinterprets events per-personality, memory uses MMR-diversified
Stanford-style retrieval, and charged interactions spark multi-turn exchanges. The
product goal is **engagement** — stories must have visible, evolving arcs.

Two structural gaps remain, plus two smaller realism gaps:

1. **Beliefs still change "by fiat."** The reasoner emits `stance_shift: dict[topic,float]`
   — self-authored numbers the engine applies verbatim (`applicator.py:132-139`). This is
   the exact anti-pattern the project already removed for relationships. Beliefs also only
   ever move for the *acting* agent's own topics; persuasion doesn't spread through the
   network from sources to witnesses. So aggregate sentiment is driven by ungrounded
   numbers, which is also what the forecast/prophecy are graded against.

2. **Significance is single-factor.** Pivotal days are ranked purely by belief-mean drift
   (`reporter.py:_topic_drift`). An earned betrayal, a romance, an influence upheaval, or a
   faction collapse that doesn't move aggregate stance scores **zero** significance — so the
   narrative spine can miss the most dramatic moments.

3. **No faction structure.** Metrics count raw relationship types but never cluster the
   social graph, so faction formation/merger/collapse — the most significant social events —
   are invisible.

4. **Mood has no continuity.** `actor.mood = action.emotional_reaction` snaps each day
   (`applicator.py:50`); background agents' moods never change at all. Emotions don't
   persist or decay, which reads as erratic.

This plan addresses all four (broad sweep), preserving three hard invariants:
**(a)** day-by-day (`/advance`) must stay **byte-identical** to a batch run (verified via
event-log/milestone hash in `backend/tests/test_realism.py`); **(b)** the `mock` provider
must keep working with no API keys; **(c)** no new per-day LLM calls (cost-bounded).
All new logic is deterministic math over existing state — no RNG, no LLM — so determinism
and mock-safety hold by construction.

It also adds three **"simulator, not LLM-wrapper"** items (§5–§7). The LLM is the agent
*policy* (what a character would say/do); the world's physics — propagation, belief
dynamics, structural tension, and now forecasting — should be real models in our code, not
LLM judgment calls. These move genuine behavior into the deterministic substrate so the
LLM becomes one component rather than the whole engine.

---

## 1. Belief change as a derived consequence (`belief.py`)

Mirror the consequence-layer philosophy: the agent declares an **intent toward a topic**,
not a number; the magnitude is derived from source credibility, the receiver's conviction,
and homophily — and beliefs **spread** from a speaker to their witnesses.

**New file `engine/simulation/belief.py`** with calibrated constants (parallel to
`consequence.py`):

- `STANCE_INTENT_EFFECTS: dict[str, tuple[float, ...]]` — verbs → signed pushes:
  - `advocate`/`push` → strong move in the actor's current stance direction
  - `reaffirm` → small self-entrenchment
  - `question`/`doubt` → small move toward 0
  - `concede` → move toward the interlocutor/away from own pole
  - `none`/blank → no change
- `self_shift(agent, topic, intent)` — the actor's own entrenchment from speaking
  (replaces the self-authored number). Damped, e.g. `SELF_DAMP = 0.15`.
- `persuade(viewer, source, topic, source_stance) -> float` — the **network effect**:
  a witness updates toward the source's position by
  `base * credibility * (1 - conviction)`, where
  - `credibility(viewer→source)` = blend of `viewer.relationships[source].strength`
    (trust) and normalized `source.influence_score`, in `[-1, 1]`;
  - `conviction(viewer)` = `abs(viewer.stance[topic])` (extremists resist);
  - **backfire**: when credibility < 0 (distrusted source), the delta flips sign — a
    hostile source pushes the viewer the *other* way. Bounded by `PERSUADE_MAX`.

**Wiring (`applicator.py`):**
- Replace the `for topic, delta in action.stance_shift.items()` block (lines 132-139)
  with: for each engaged topic, apply `belief.self_shift` to the actor.
- Add network persuasion: after computing witnesses, for each witness and each topic the
  actor engaged, apply `belief.persuade`. Reuse the witness set from
  `observation.witnesses(...)` (already computed in `distribute_observation`) — have
  `distribute_observation` return the witness list, or expose a small helper, so persuasion
  routes to exactly the agents who saw the move (preserves the existing information-asymmetry
  / echo-chamber model).

**Schema (`models.py` + `reasoner.py`):**
- `AgentAction`: replace `stance_shift: dict[str,float]` with
  `stance_intents: dict[str,str]` (topic → verb). Keep `stance_shift` as an optional,
  ignored back-compat field so old saved actions still parse.
- Update `REASONER_SYSTEM` JSON schema + rules in `reasoner.py`: agents pick a topic verb
  ("advocate/reaffirm/question/concede"), never a number — same framing as the existing
  "you do NOT control relationship numbers" rule.
- Update the `mock` AGENT_REASONING branch in `engine/llm.py` to emit `stance_intents`.

---

## 2. Multi-factor significance scoring (`reporter.py`, `metrics.py`)

Replace the belief-drift-only pivotal-day ranking with a composite **day significance**
that captures drama, not just sentiment movement.

- Add `compute_day_significance(prev: MacroMetrics, cur: MacroMetrics, milestones: list[str])`
  (in `metrics.py`) combining, with calibrated weights:
  - **belief drift** — existing `_topic_drift` logic (move it here),
  - **relationship milestones weighted by surprise** — a milestone is more significant when
    it violates expectation: trust/friendship → conflict/rivalry (betrayal) scores higher
    than an expected rivalry hardening. Detect surprise from the `prev_type → new_type`
    transition; surface this by having `_detect_milestone` (`applicator.py`) also return a
    structured surprise weight (e.g. cross-family flips, especially warmth→antagonism, score
    highest), stored on the snapshot,
  - **influence upheaval** — count/magnitude of gainer/loser turnover vs the prior day,
  - **faction shift** — formation/merger/collapse from §3.
- Store the scalar on the snapshot: add `day_significance: float` to `MacroMetrics` (computed
  in `compute_metrics`, which already takes `type_changes_today`; pass milestones in too).
- In `reporter.py`, rank pivotal days by `day_significance` instead of `_topic_drift`, and
  enrich the FINAL_REPORT prompt's "PIVOTAL DAYS" section with *why* each day mattered
  (the dominant factor), so the report traces real turning points.

**Optional (tension-driven events):** replace the fixed `abs_day % 5 == 0` dynamic-event
cadence (`engine.py:138`) with a trigger on accumulated tension (rolling sum of recent
`day_significance` / negative-affinity pressure) once it crosses a threshold, gated by a
min-gap and max-cadence to bound cost. Must carry "days since last event" across
continue/advance calls alongside `active_event` (see `active_event_in` carry pattern,
`engine.py:97-100`) to keep day-by-day == batch. Mark as a follow-up if it risks the
determinism harness.

---

## 3. Faction detection (`factions.py`, `metrics.py`)

**New file `engine/simulation/factions.py`:**
- `detect_factions(agents) -> list[list[str]]` — build an undirected graph with an edge
  between two agents when *either* direction's affinity ≥ a `FACTION_AFFINITY` threshold
  (reuse the signed-affinity convention and the unordered-pair logic already in
  `metrics.py:26-42`), then cluster via **deterministic** label propagation / connected
  components (iterate agents in stable name order, fixed tie-breaks — no RNG). Returns
  factions as sorted name lists, sorted by size then first name for stable output.
- `diff_factions(prev, cur) -> list[str]` — human-readable faction events:
  "A new faction formed around X, Y, Z", "the X and Y blocs merged", "the Z bloc fractured".

**Wiring:**
- `MacroMetrics`: add `factions: list[list[str]]` and `faction_count: int`
  (populated in `compute_metrics`).
- `engine.py`: after computing metrics, diff against the previous snapshot's factions and
  append faction events to `day_milestones` (so they flow into the milestone-driven story
  spine, the StoryChapter "Turning points" block, and §2 significance).
- Surface `factions` in the FINAL_REPORT prompt so the report can describe the society's
  final shape as blocs, not just pairwise counts.

---

## 4. Mood inertia (`mood.py` or inline in `applicator.py` + `deterministic.py`)

Give emotion continuity instead of a per-day snap.

- Add `mood_intensity: float = 0.0` to `Agent` in `models.py` (a 0..1 scalar; mood label
  stays categorical).
- **Reasoning agents (`applicator.py:50`):** the declared `emotional_reaction` is a *bid*.
  The mood label flips only when the action is charged/significant **or** the same new mood
  is declared while intensity is already high; otherwise intensity bumps but the label
  persists. Calibrated so a single mild day doesn't whipsaw a character's mood.
- **Background agents (`deterministic.py`):** decay `mood_intensity` toward 0 per day and,
  once it falls below a floor, relax the mood label toward `calm` — so off-screen agents
  cool down believably instead of being frozen in last-shown mood.
- The reasoner prompt already shows `mood`; optionally include intensity ("simmering",
  "intense") so the model reflects emotional momentum. Deterministic; no new calls.

---

## 5. Monte Carlo forecasting — predict by simulating, not by prompting (`ensemble.py`)

Today `build_forecast` (`reporter.py:58`) reports the *single* run's final state, and
`Forecast.confidence` is just `final.belief_confidence` — a within-population consensus
point estimate, **not** predictive uncertainty across possible futures. Replace this with a
distribution from running the dynamics many times.

**Cost-bounded default — substrate projection (no extra LLM calls):**
- New file `engine/simulation/ensemble.py`. After the single real (LLM-driven) run, take the
  final agent state and **project it forward N times** using only the deterministic
  dynamical layers — `belief.persuade`/bounded-confidence (§1/§6), affinity decay +
  `consequence.realize`, background drift (`deterministic.apply_background_rules`), influence
  regression — each with a distinct seed (`base_seed + k*OFFSET`). No reasoning/LLM calls in
  the projection, so it's fast and mock-safe.
- Aggregate the N projected endpoints: per-topic **mean-of-means** and **cross-run spread**
  (genuine forecast uncertainty — how much outcomes vary across futures), plus an
  **outcome distribution** (fraction of runs where each topic ends positive, where a
  faction/romance persists, modal influence winners).
- `Forecast.confidence` becomes **ensemble agreement** (1 − normalized cross-run spread, or
  fraction agreeing on the directional outcome) — a real predictive confidence.

**Opt-in high-fidelity ensemble (costly):** `SimulationConfig.ensemble_runs: int = 1`. When
`>1`, run the full `run_simulation` N times (seeds `base_seed + k*OFFSET`; each run stays
internally deterministic) and aggregate the real final metrics. Default `1` preserves
current cost/behavior exactly; the substrate projection above runs regardless since it's cheap.

**Schema (`models.py`):** `Forecast` gains `outcome_distribution: dict`,
`cross_run_uncertainty: dict[str,float]`, `ensemble_runs: int`. `SimulationConfig` gains
`ensemble_runs`. Enrich the FINAL_REPORT prompt so the narrative cites the distribution
("in ~70% of projected futures the council bloc holds") instead of a lone trajectory.

**Determinism:** each run/projection is seeded and independent; the *real* run is unchanged,
so the existing day-by-day == batch hash still holds. Ensemble seeds are derived, not RNG-live.

## 6. Bounded-confidence belief dynamics (folds into §1 `belief.py` + `deterministic.py`)

Ground persuasion in an established opinion-dynamics model (Deffuant / Hegselmann–Krause)
so polarization and consensus *emerge* rather than being narrated.

- In `belief.persuade` (§1): only move a witness toward a source when the stance gap is
  within a **confidence bound** `CONFIDENCE_BOUND` (`|viewer.stance − source.stance| ≤ μ`);
  beyond it, no pull (HK), or **backfire** when the source is also distrusted — entrenchment.
  This composes cleanly with the credibility/conviction terms already in §1.
- In `deterministic._drift_stance` (`deterministic.py:97`): background conformity pulls only
  toward group-mates **within the bound**, so the population can settle into *multiple*
  stable clusters (polarization) instead of collapsing to one global mean.
- Result: belief trajectories show real bounded-confidence behavior (consensus when tolerant,
  polarization when not) — theoretically grounded and LLM-free. Deterministic; no new calls.

## 7. Structural-balance tension (Heider) — drama from graph theory (`balance.py`)

Use signed-graph balance theory to *generate* tension deterministically instead of hoping
the LLM invents it.

- New file `engine/simulation/balance.py`:
  - `unstable_triads(agents) -> list[tuple[str,str,str]]` — over the signed affinity graph,
    a triad is **unbalanced** when the product of its three edge signs is negative (friend-of-
    a-friend is an enemy; friend-of-an-enemy is a friend). Classic Heider/Cartwright–Harary.
    Reuse the unordered-pair/sign convention from `metrics.py:26-42`; iterate in stable name
    order (deterministic, no RNG).
  - `tension_score(agents) -> float` — count/severity of unstable triads, normalized.
- **Significance (feeds §2):** `tension_score` is a component of `day_significance` and (if
  built) the tension-driven event trigger.
- **Drive drama (feeds selection):** add a small score term in
  `selector.select_reasoning_agents` (`selector.py`) for agents embedded in unstable triads —
  they're under real pressure to resolve, so they act more. Surface "X is caught between ally
  Y and rival Z" as a beat in the day log / milestones.
- **Metrics:** add `unstable_triads: int` to `MacroMetrics`.

---

## Critical files

| File | Change |
|------|--------|
| `engine/simulation/belief.py` | **new** — derived belief shift + network persuasion + bounded-confidence (§1/§6) |
| `engine/simulation/factions.py` | **new** — deterministic clustering + diffing |
| `engine/simulation/ensemble.py` | **new** — substrate projection + opt-in full ensemble forecasting (§5) |
| `engine/simulation/balance.py` | **new** — Heider unstable-triad detection + tension score (§7) |
| `engine/simulation/selector.py` | unstable-triad pressure term in agent selection (§7) |
| `engine/simulation/applicator.py` | swap `stance_shift`→belief calls; route persuasion to witnesses; structured milestone surprise; mood-bid logic |
| `engine/simulation/reasoner.py` | `stance_intents` schema + prompt rules |
| `engine/simulation/metrics.py` | `compute_day_significance`, factions, faction_count, day_significance, unstable_triads |
| `engine/simulation/reporter.py` | rank pivotal days by significance; enrich prompt with factions + why; cite ensemble distribution (§5) |
| `engine/simulation/deterministic.py` | mood decay for background agents; bounded-confidence conformity (§6) |
| `engine/simulation/observation.py` | expose/return witness set for persuasion |
| `engine/simulation/engine.py` | diff factions into milestones; (optional) tension-driven events |
| `engine/models.py` | `AgentAction.stance_intents`; `Agent.mood_intensity`; `MacroMetrics.factions/faction_count/day_significance/unstable_triads`; `Forecast.outcome_distribution/cross_run_uncertainty/ensemble_runs`; `SimulationConfig.ensemble_runs` |
| `engine/llm.py` | mock AGENT_REASONING emits `stance_intents` |
| `backend/tests/test_realism.py` | new invariants (below) |

## Reuse (don't re-invent)
- Calibration/`_clamp` + bid-then-derive pattern from `consequence.py`.
- Signed-affinity unordered-pair logic from `metrics.py:26-42` for faction edges.
- `observation.witnesses(...)` for persuasion reach (echo chambers already modeled).
- `_detect_milestone` (`applicator.py:156`) extended, not replaced, for surprise weight.
- `build_forecast` (`reporter.py:58`) already computes numeric forecast fields from real
  metrics — §5 extends it with the ensemble distribution rather than rewriting it.
- `run_simulation` (`engine.py:51`) reused verbatim for the opt-in full ensemble (§5);
  per-day seeded RNG (`day_rng`, `engine.py:127`) already gives independent seeded runs.

## Verification

1. **Determinism (hard invariant):** `LLM_PROVIDER=mock python3 backend/tests/test_realism.py`
   — the existing day-by-day == batch byte-identical check (event log + milestones +
   volatility) must still pass with all changes in.
2. **Mock end-to-end:** `LLM_PROVIDER=mock pytest backend/tests` — all 15 current tests green.
3. **New realism invariants** in `test_realism.py`:
   - belief change is bounded and zero when no topic is engaged / no witnesses;
   - a distrusted source's advocacy moves a witness *away* (backfire), a trusted source
     moves them *toward*;
   - high-conviction (extreme-stance) agents move less than moderates;
   - faction clustering is deterministic across repeated runs and stable under name order;
   - `day_significance` is higher on a day with a betrayal milestone than on a quiet day
     with equal belief drift;
   - mood does not flip on a single mild (non-charged) action;
   - **(§5)** the substrate projection is deterministic for a fixed seed set, and ensemble
     `cross_run_uncertainty` is ≥ 0 and grows when runs diverge; the single real run's
     event-log/milestone hash is unchanged by enabling forecasting;
   - **(§6)** with a tight `CONFIDENCE_BOUND`, two far-apart stance clusters do **not**
     converge (polarization holds); with a loose bound they converge (consensus);
   - **(§7)** `unstable_triads` correctly flags a friend–friend–enemy triad and clears it
     once an edge sign resolves; clustering/triad detection is order-stable.
4. **Live smoke (optional):** run a ~10-day world via `uvicorn main:app --reload --port 8000`
   and confirm the final report's pivotal days cite faction/betrayal turning points and that
   stances move through persuasion, not self-declaration.
