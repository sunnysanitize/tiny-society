# Backlog — Diagnosed Issues & Future Improvements

A working implementation guide produced from a full-stack check (in-process API
exercise via FastAPI TestClient + frontend `tsc`). The system runs end-to-end with
no crashes; everything below is a **quality gap, wiring gap, or enhancement** — not a
blocker. Each item says *what it means*, *why it matters*, and *roughly how to do it*.

Status legend: 🔴 bug · 🟡 gap · 🟢 enhancement · ⏳ deferred · ✅ done

> **Update.** The performance & live-editing roadmap (concurrent LLM inference, tiered models,
> and mid-run character injection) has since been **implemented** — see
> [PERFORMANCE_AND_LIVE_EDITING.md](./PERFORMANCE_AND_LIVE_EDITING.md). This resolves the
> tiered-models half of §⑤ below (concurrency replaced the serial-with-sleep loop; a cheap/strong
> tier split is live). Items ⑥–⑬ remain open.
>
> **Update 2 (2026-05-24).** Part 1 ①–④ are now **done** (mock-mode dynamic-event + relationship-seeding
> branches, the prediction-`question` wiring end-to-end, and the dead `initials()` removal); verified on
> the mock provider (15 pytest pass, frontend `tsc` clean).

---

## Part 1 — Diagnosed issues (fix these first)

### ✅ ① Dynamic events are nonsense on the mock provider — DONE
**What it means.** `simulation/engine.py`'s `_generate_dynamic_event` calls the LLM with a
plain instruction string that has **no unique marker**. The mock provider (`llm.py` `_mock`)
dispatches on markers (e.g. `AGENT_REASONING`, `VIGNETTE_GENERATION`); with no marker this
call falls through to the generic **chat fallback**, which returns conversational prose like
*"You'll have to give me more than that."*. That string is longer than the 10-char guard, so
it gets **accepted as a real world event**.
**Why it matters.** This is the source of the recurring `WARNING:root:_safe_json could not
parse…` log line, and it means any keyless/demo run injects junk "events" mid-simulation.
(With a real LLM provider it works fine — this only bites the free mock path.)
**How to fix.** Give the dynamic-event call a unique marker (e.g. start its system prompt
with `DYNAMIC_EVENT_GENERATION`) and add a matching branch in `llm.py` `_mock` that returns a
short, plausible event sentence derived from recent activity (mirror how the other mock
branches parse the prompt). Mirrors the pattern already used for vignettes/plans.

### ✅ ② Relationship seeding silently no-ops on the mock provider — DONE
**What it means.** During filler generation the social graph is seeded via an LLM call whose
system prompt starts with `RELATIONSHIP_SEEDING` — but there is **no mock branch** for that
marker, so on mock it hits the chat fallback, returns prose, fails JSON parsing, and seeds
**no starting relationships**.
**Why it matters.** Keyless/demo simulations begin with an empty social graph instead of the
pre-wired relationships the feature intends, so early days look flat. (Real LLM is fine.)
**How to fix.** Add a `RELATIONSHIP_SEEDING` branch to `llm.py` `_mock` returning deterministic
valid JSON (a handful of plausible relationships among the provided agent names), following the
established `_mock` dispatch pattern.

### ✅ ③ The prediction "question" is never settable — DONE
**What it means.** Phase 2 introduced `World.question` (the player's prediction question that
should anchor the whole forecast). Slice F added a UI only for `World.prophecy` (the free-text
bet). Nothing in the API or UI ever sets `World.question`, so `Forecast.question` is always
`null` and the world-graph extractor never receives the question as context.
**Why it matters.** Half of the headline "prediction engine" feature is unwired — the forecast
runs off auto-derived topics only, and the question→topics→forecast chain is broken at the top.
**How to fix.** Add `POST /world/{id}/question` (body `{question: str}`) in `main.py` that sets
`world.question`; add an input for it in `components/EventAndRun.tsx` (next to the prophecy
input); pass `world.question` into `worldgraph.extract_world_graph` so topics derive from it,
and confirm it flows into `Forecast.question`.

### ✅ ④ Dead code — DONE
**What it means.** `initials()` in `components/RelationshipGraph.tsx` is unused after pixel
avatars replaced initial-tiles on graph nodes.
**Why it matters.** Minor — clutter only (tsconfig doesn't flag unused locals).
**How to fix.** Delete the function.

---

## Part 2 — Cost & scale

### ✅ ⑤ Tiered models + concurrency (was the deferred Phase 2 #8) — DONE
**What it was.** Every realism layer added (planning, multi-turn exchanges, vignettes,
perception, reflection, world-graph, prophecy grading) issues its own LLM call, so calls-per-run
multiplied well beyond the README's old "~241 for 30 days." With the old serial-with-sleep loop
(`LLM_CALL_DELAY_SECS=2`) and a paid provider, long runs were slow and costly.
**What shipped.** (a) **Concurrency** — the day's plan+reason fan-out now runs via
`asyncio.gather` bounded by `LLM_MAX_CONCURRENCY` (default 6), applied sequentially for
determinism; the `time.sleep` delay was removed. (b) **Tiered models** — `tier="cheap"|"strong"`
on the LLM adapter, routing routine turns to a cheap model and pivotal/structural/player-facing
work to a strong one, via `*_MODEL_CHEAP`/`*_MODEL_STRONG` env vars (fall back to the single
model var). See [PERFORMANCE_AND_LIVE_EDITING.md](./PERFORMANCE_AND_LIVE_EDITING.md).
**Still open (nice-to-have).** Per-feature depth toggles (planning / vignettes / multi-turn /
perception) in `SimulationConfig` so users can trade depth for cost — not yet built.

### 🟢 ⑥ Embedding-based memory retrieval
**What it means.** `simulation/memory.py` `retrieve()` scores relevance by stopword-filtered
**token overlap**. Embeddings would capture semantic similarity (e.g. "scholarship" ≈ "the
award") that token overlap misses.
**Why it matters.** Sharper retrieval = more coherent, in-character behavior — the core
generative-agents realism lever.
**How to fix.** Add an optional embedding backend (compute + cache per `Memory`), score by
cosine similarity blended with the existing recency/importance weights; keep the token-overlap
path as the no-API/mock default.

---

## Part 3 — Engagement (the not-built Phase 3 items)

### 🟢 ⑦ Emotional-stakes alerts & milestones
**What it means.** Surface high-emotion moments to the player: "someone you care about is in
crisis," relationship milestones (a friendship becomes romance, a rivalry erupts).
**Why it matters.** These are the attachment hooks that make a Tomodachi-style game sticky —
the player checks in *because* they're invested in specific characters.
**How to fix.** Detect threshold-crossing events in `applicator.py`/`metrics.py` (mood hitting
heartbroken/angry, relationship type flips, |strength| crossings); emit them as a typed
`alerts` list on `DaySnapshot`; render them as prominent cards in the story view.

### 🟢 ⑧ Progression / collection ("history book")
**What it means.** A persistent record the player accumulates: a saved saga/history of the
town, captured memorable quotes, milestones unlocked.
**Why it matters.** Progression gives a reason to return and a sense of an ongoing story across
runs — the long-tail engagement layer.
**How to fix.** Persist notable highlights/vignettes/verdicts per world (ties into Supabase
saves); add a "History" view in the frontend that reads them back as a scrapbook/timeline.

### 🟢 ⑨ Remaining nudges + literal-town view
**What it means.** Two intervention types were deliberately left out: **matchmake** (push two
characters toward romance/friendship) and **take-sides/gift** (boost a character's standing).
Separately, the pastel town background could become a literal "town" layout the social graph
maps onto, instead of a force-directed graph.
**Why it matters.** More agency for the player; stronger spatial/charm payoff from the art.
**How to fix.** Add `POST /world/{id}/matchmake` and `/back` endpoints that write to
memory/stance/influence (mirror the existing `advise`/`inject-event` handlers); for the town
view, position graph nodes onto fixed "building" coordinates over `town-bg.png`.

---

## Part 4 — Hardening

### 🟢 ⑩ Automated test suite
**What it means.** There is no real test suite — correctness rests on the mock smoke-test and
the per-slice manual runs done during development.
**Why it matters.** Six-plus interdependent slices now share `models.py`/`engine.py`; a
regression in one silently breaks others. Tests turn that from "hope" into "known."
**How to fix.** Add `pytest`: an in-process engine run on mock asserting the invariants checked
during development (topics populated, stances move, forecast built, vignettes capped, prophecy
graded, feeds asymmetric), plus FastAPI `TestClient` tests for each endpoint.

### 🟢 ⑪ Real-LLM validation pass
**What it means.** Everything was verified on the **mock** provider only (no API key needed in
the dev sandbox). Mock prose is deterministic and simplified.
**Why it matters.** Prompt quality, JSON-mode adherence, and narrative coherence can only be
judged on a real provider; mock can hide prompt bugs.
**How to fix.** Run a short sim on the configured `anthropic`/`openai_compat` provider; review
plan/vignette/forecast/prophecy/report text quality; tighten the system prompts as needed.

### 🟢 ⑫ Visual / responsive QA
**What it means.** The UI work (town background, pixel avatars, responsive layout, story
chapters) passed `tsc` but was **not** viewed in a browser in this environment.
**Why it matters.** Type-safety ≠ looks right. Contrast over the background, sprite charm,
story-card hierarchy, and narrow-screen stacking need a human eye.
**How to fix.** `cd frontend && npm run dev`; check at ~375 / 768 / 1440 / ultrawide and on a
short viewport; verify text legibility over the background and that graph/inspector stack
correctly on phones.

### 🟡 ⑬ Supabase persistence of the enlarged schema
**What it means.** The `World`/`Agent`/`DaySnapshot`/`SimulationResult` models grew many new
fields. Saves serialize via `model_dump()` into Supabase `jsonb` and reload via Pydantic.
Serialization is confirmed (the API `response_model`s validate it), but save→load was **not**
tested against a live DB because the new project's `service_role` lacks table grants (see the
earlier `42501` issue).
**Why it matters.** If saves predate the new fields, or grants aren't applied, load could fail
or drop data.
**How to fix.** Run the GRANTs in `supabase_migration.sql` on the new project, then save a
post-upgrade world and load it back; confirm all new fields (stance, plan, feed, vignettes,
forecast, prophecy_verdict, avatar) round-trip.

---

## Suggested order

1. **Part 1 ①–④** — quick, makes demo runs coherent and finishes the prediction feature.
2. **Part 4 ⑩** — a test suite, before building more on top.
3. ~~**Part 2 ⑤** — cost/scale~~ ✅ done (concurrency + tiered models). Embedding retrieval (⑥) remains.
4. **Part 3 ⑦–⑨** — engagement depth (the actual product goal).
5. **Part 4 ⑪–⑬** — validation/hardening, ongoing.
