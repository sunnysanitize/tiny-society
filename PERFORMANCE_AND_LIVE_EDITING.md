# Performance & Live Editing — Implementation Guide

**Status: ✅ all three features implemented and verified on the mock provider.** This document
was the build spec; it now also records what shipped. See the **"What shipped"** note under each
section for the actual code locations.

Three features:
- **A. Concurrent (async/batched) LLM inference** — the OASIS-inspired speed win. ✅ **Done.**
- **B. Tiered models** — cheap model for routine turns, strong model for pivotal ones. ✅ **Done.**
- **C. Mid-run character injection** — pause on a chosen day and add a character whose
  arrival can change the outcome. ✅ **Done** (Level 1 endpoint + UI, and Level 2 `pause_on_days`).

> Context: OASIS reaches a million agents via sparse activation + asynchronous batched
> inference + a distributed environment server. At this project's scale (tens of characters)
> the **full distributed stack is premature** — but A and B are direct wins *today*, and C is
> a new gameplay/causality feature. The full distributed Environment Server / Scalable
> Inferencer is intentionally **out of scope** (see "Explicitly skip" at the end).

---

## A. Concurrent LLM inference (the big speed win)

> **✅ What shipped.** `llm.py` gained `acall_llm(...)` (async paths for anthropic via
> `AsyncAnthropic`, openai_compat via `httpx.AsyncClient` mirroring the full retry/backoff/429
> logic, and mock via `asyncio.to_thread`), bounded by a lazily-created semaphore
> `LLM_MAX_CONCURRENCY` (default 6). `reasoner.py` gained `areason_for_agent(...)` sharing a new
> `_parse_action` helper with the sync path. `engine.py`'s day loop now fans out plan+reason
> concurrently via `asyncio.gather` (run with `asyncio.run` per day — `run_simulation` stays
> sync, safe under both the sync endpoint and the streaming thread) and applies results
> **sequentially in selection order** for determinism. Multi-turn exchanges stay serial. The
> per-agent `time.sleep(LLM_CALL_DELAY_SECS)` in the fan-out was retired (the semaphore replaces
> it). *Verified: 4-day + continue mock run, no crash.*

### The problem
`engine.py`'s day loop calls the LLM **serially**, with a sleep between agents:
```python
for i, actor in enumerate(selected):
    if i > 0: time.sleep(LLM_CALL_DELAY_SECS)   # default 2s
    action = reason_for_agent(actor, ...)        # blocking LLM call
    apply_action(actor, action, agents, day)     # mutates shared state
```
With the new realism layers (planning, perception, reflection, vignettes, multi-turn) the
per-day call count multiplied, so a 30-day run is slow. The agents' **reasoning** calls within
a single day are independent (they all read the same start-of-day state), so they can run
**concurrently** — only the *application* of results must stay ordered.

### The key restructure: split "reason" (parallel) from "apply" (sequential)
Reasoning is read-only on shared state → safe to parallelize. `apply_action` mutates
relationships/influence/feeds → must run sequentially (and deterministically, for reproducible
seeds). So:

```python
# 1) PARALLEL: gather all selected agents' actions concurrently
actions = await gather_actions(selected, agents, event, day)   # asyncio.gather
# 2) SEQUENTIAL: apply in a fixed order (e.g. selection order) for determinism
for actor, action in zip(selected, actions):
    if action: apply_action(actor, action, agents, day)
```

### Implementation steps
1. **`llm.py` — add an async path.** Add `acall_llm(system, user, *, json_mode, max_tokens, tier)`:
   - `anthropic`: use `from anthropic import AsyncAnthropic`.
   - `openai_compat`: use `httpx.AsyncClient` (mirror the existing retry/backoff/429 logic).
   - `mock`: it's pure CPU — wrap the sync `_mock` in `asyncio.to_thread` or just call it.
   Keep the sync `call_llm` for non-loop callers (final report, etc.).
2. **Bound concurrency with a semaphore** (avoid hammering rate limits):
   ```python
   _SEM = asyncio.Semaphore(int(os.getenv("LLM_MAX_CONCURRENCY", "6")))
   async def acall_llm(...):
       async with _SEM: ...
   ```
   Retire `LLM_CALL_DELAY_SECS` for the loop (it exists only because calls were serial);
   the semaphore + per-call backoff replace it.
3. **`reasoner.py` — add `areason_for_agent(...)`** that awaits `acall_llm`; keep `_build_prompt`
   and parsing unchanged.
4. **`engine.py` — make the day's reasoning concurrent.** Wrap the reasoning fan-out in
   `asyncio.gather`, then apply sequentially. Run the whole day loop under `asyncio.run` (or make
   `run_simulation` async and have the endpoints await it).
5. **Perception calls** inside `apply_action` can *also* be parallelized later (one per target),
   but start with the reasoning fan-out — it's the bulk of the calls.

### The multi-turn caveat
Multi-turn exchanges (`engine.py` charged-interaction loop) **depend on the prior turn's applied
state**, so they can't join the first parallel pass. Keep them **sequential**, after the parallel
first pass. Net effect: the big day-1 fan-out is parallel; the (capped, ≤3/day) exchanges remain
serial. Reflection/planning for the day's agents can also be gathered concurrently.

### Determinism
Parallel *execution* is fine as long as *application order is fixed* (iterate `selected` in its
original order when applying). The RNG (`random.Random(seed)`) is only used in selection and
deterministic rules, not in the async calls, so seeds stay reproducible.

### Expected payoff
A day that took `N_agents × (latency + 2s sleep)` now takes ≈ `max(latency)` for the fan-out.
At 8 agents that's roughly an **8×+ wall-clock reduction** per day. No new model needed.

---

## B. Tiered models (cost control)

> **✅ What shipped.** `call_llm`/`acall_llm` (and the anthropic/openai_compat helpers) take a
> keyword-only `tier: str = "strong"`. Model resolution prefers `ANTHROPIC_MODEL_{TIER}` /
> `OPENAI_COMPAT_MODEL_{TIER}` and falls back to the existing single `*_MODEL` var (fully
> backward compatible — with no new env vars, behavior is identical to before). Mock ignores
> tier. Call sites routed: routine reasoning, vignettes, fillers, relationship seeding, planning,
> and dynamic events → `cheap`; reflection, world-graph extraction, prophecy grading, the final
> report, and player-facing chat → `strong`. `backend/.env.example` documents the new vars.

### Idea
Route routine work to a cheap/fast model and reserve a strong model for moments that matter.

### Implementation steps
1. **`llm.py` — add a `tier` arg** to `call_llm`/`acall_llm`: `tier: Literal["cheap","strong"] = "strong"`.
   Resolve the model per tier per provider:
   ```env
   ANTHROPIC_MODEL_STRONG=claude-sonnet-4-5-...
   ANTHROPIC_MODEL_CHEAP=claude-haiku-...
   OPENAI_COMPAT_MODEL_STRONG=llama-3.3-70b-versatile
   OPENAI_COMPAT_MODEL_CHEAP=llama-3.1-8b-instant
   ```
   Fall back to the existing single `*_MODEL` if a tier var is unset (backward compatible).
2. **Routing table** (which caller uses which tier):
   | Call site | Tier | Why |
   |---|---|---|
   | Routine reasoning (`post`/`comment`/`interact`, background) | cheap | volume |
   | Charged/multi-turn reasoning, pivotal actors | strong | quality matters |
   | Reflection, world-graph extraction | strong | structural, infrequent |
   | Vignettes, filler generation, dynamic events | cheap | flavor/bulk |
   | Final report, prophecy grading | strong | player-facing payoff |
3. Mock ignores tier (one code path), so keyless runs are unaffected.

---

## C. Mid-run character injection ("pause on a day, add a character")

> **✅ What shipped.** **Level 1:** `POST /world/{wid}/inject-character` (`main.py`, body
> `CharacterInput`) builds the newcomer via a shared `_build_agent_from_input` helper (also used
> by `add_character`), initialized **for the current day** — stance seeded on the existing world
> topics, memories day-stamped at the current day (not day 0), feed/observations/plan cleared,
> best-effort relationship seeding, name de-dup. It writes the agent into both `w.agents` and the
> latest result snapshot and appends an arrival line to that snapshot's `event_log`, so the
> existing **continue** flow picks it up with no further changes. **Level 2:** `pause_on_days:
> list[int]` on `SimulateRequest`/`ContinueRequest` threads into `run_simulation`, which breaks
> the day loop after saving the snapshot on a pause day; the stream's `done` event carries a
> `paused`/`paused_on` flag. **Frontend:** `api.injectCharacter` + an "Add character" panel in the
> CONTINUE controls (in `Engagement.tsx`, surfaced from `SimulationView.tsx`), with a confirmation
> that the character will arrive on the current day when the run continues. *Verified end-to-end
> via TestClient (inject → continue → newcomer present) and `tsc --noEmit`.*

### Goal
Let the player **stop the simulation on a chosen day, add a new character, and resume** — a
deliberate new variable whose arrival can change the trajectory and the forecast.

### It plugs straight into the existing "continue" flow
`simulate_continue` already resumes from the **last snapshot's agents** at `day_offset=last_snap.day`
(`main.py:174-179`). So "pause on day X and add a character" decomposes into:
1. Run to day X (the `days` parameter already stops there).
2. Inject the new character **into the last snapshot's roster** (the exact state continue seeds from).
3. Continue from day X+1 — the newcomer participates immediately.

Two UX levels — ship #1 first, #2 is polish:

#### Level 1 — segmented runs + an inject endpoint (minimal, reuses everything)
- The player runs N days (that's the pause point), the run ends, then the existing CONTINUE UI
  gains an **"+ Add character"** option before resuming.
- **New endpoint `POST /world/{wid}/inject-character`** (`main.py`), body = `CharacterInput`
  (name, role, traits, goals, mood, groups, starting_memories, avatar, based_on). It must
  initialize the newcomer **for the current day**, not day 0:
  ```python
  @app.post("/world/{wid}/inject-character", response_model=Agent)
  def inject_character(wid: str, body: CharacterInput):
      w = _require(wid)
      prev = store.get_result(wid)
      day = prev.snapshots[-1].day if prev else 0
      agent = _build_agent_from_input(body, is_custom=True)        # reuse add_character's builder
      # initialize belief stance on the EXISTING world topics
      from simulation.stance import initialize_stances
      initialize_stances([agent], w.world_graph.topics)
      # stamp starting memories at the current day (so retrieval recency is correct)
      from simulation.memory import make_memory
      agent.short_term_memory = []
      agent.long_term_memory = [make_memory(m, day) for m in body.starting_memories]
      agent.feed, agent.observations, agent.plan = [], [], None
      # add to BOTH the persistent roster and the live state continue seeds from
      w.agents.append(agent)
      if prev:
          prev.snapshots[-1].agents.append(agent)
          store.save_result(wid, prev)
      # arrival beat so it shows in the story and can move the forecast
      if prev:
          prev.snapshots[-1].event_log.append(f"[{agent.name}] arrived in the world on day {day}.")
      return agent
  ```
- Optionally seed 1–3 relationships for the newcomer (reuse `generator._seed_relationships`
  over the existing roster) so they aren't fully isolated on arrival.
- Then the player hits **Continue** → the newcomer reasons from day X+1 onward.

#### Level 2 — true in-stream "pause on day X" (smoother)
- Add `pause_on_days: list[int]` to `SimulateRequest`/`ContinueRequest`.
- In `_make_stream_response`'s `on_day`/run loop, when `abs_day` ∈ `pause_on_days`, emit a
  `{"type":"paused","day":abs_day}` SSE event and **stop the run** after saving the snapshot
  (treat it like a natural end — the partial result is stored).
- Frontend: on `paused`, show the "add character / inject event / set prophecy, then resume"
  panel; resume calls `simulate/continue/stream`. (Internally this is the same as Level 1 — a
  pause is just an early, intentional stop — so it reuses the inject endpoint.)

### Initialization checklist (so the newcomer behaves correctly mid-run)
- **stance**: `initialize_stances([agent], world.world_graph.topics)` — must match existing topics.
- **memories**: wrapped as `Memory(day=current_day)` so recency scoring is right (not day 0).
- **feed/observations**: empty — they've witnessed nothing yet; they'll accrue from day X+1.
- **plan/plan_day**: None/0 — a plan forms on their first active day.
- **influence**: default; or a small starting value if they're meant to be high-status.
- **relationships**: empty, or a few seeded so they're not an island.

### Why it can change the result (the point)
- A newcomer adds a node to the social graph, new feed content, and new stance values → the
  daily **belief aggregation** shifts, which moves `topic_means`/`belief_confidence` and can
  flip the **forecast** and the player's **prophecy verdict**.
- A high-influence newcomer crossing `PUBLIC_INFLUENCE_THRESHOLD` becomes a public broadcaster
  → outsized effect, mirroring "a new player enters the scene."
- The arrival event itself is a natural candidate to surface as a story "inciting moment."

### Frontend changes
- `CharacterEditor` already builds a `CharacterInput` + avatar — reuse it in a "mid-run add"
  modal opened from the CONTINUE controls (and from the `paused` state in Level 2).
- `lib/api.ts`: add `injectCharacter(worldId, input)`.
- Show an arrival card in the story feed for the day the character joined.

### Edge cases
- Injecting before any run exists → behaves like the normal `add_character` (day 0).
- Name collision → de-dupe like `generate_fillers` does (`-suffix`).
- Save/load: the newcomer is already in `world.agents` + the snapshot, so it persists normally.

---

## Build order (as executed — all complete)
1. ✅ **A. Concurrent inference** — biggest immediate quality-of-life win; unblocks longer runs.
2. ✅ **B. Tiered models** — cost control once runs are concurrent (concurrency makes a cheap tier
   even more valuable).
3. ✅ **C. Level 1 mid-run injection** — new gameplay, reuses the continue flow, small surface area.
4. ✅ **C. Level 2 in-stream pause** — `pause_on_days`, on top of Level 1.

### New env vars (all optional, backward compatible)
| Var | Default | Effect |
|---|---|---|
| `LLM_MAX_CONCURRENCY` | 6 | Max simultaneous in-flight LLM calls in the day fan-out |
| `ANTHROPIC_MODEL_STRONG` / `_CHEAP` | falls back to `ANTHROPIC_MODEL` | Per-tier Anthropic model |
| `OPENAI_COMPAT_MODEL_STRONG` / `_CHEAP` | falls back to `OPENAI_COMPAT_MODEL` | Per-tier OpenAI-compat model |

## Explicitly skip (for now)
- A distributed **Environment Server** (separate DB service for agent state) and a clustered
  **Scalable Inferencer** (vLLM fleet) — OASIS needs these for a *million* agents; at tens of
  characters they're pure overhead. The in-memory store + concurrent calls are right for this scale.
- Sub-3-minute **Time Engine** activation modeling — the existing softmax `select_reasoning_agents`
  is the right-sized version of sparse activation here.
