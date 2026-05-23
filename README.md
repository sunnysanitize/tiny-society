# Tiny Society AI

A multi-agent AI social simulation **and prediction engine**. Build a world, populate it with
pixel characters (some based on real people), fire off an event, and watch a cast of LLM-driven
agents reason, remember, reflect, form relationships, and shift opinions over 7–30 simulated days
— then read the swarm's forecast of where it's all heading. Part living town,
part MiroFish-style prediction engine.

![Stack](https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square) ![Stack](https://img.shields.io/badge/frontend-Next.js%2014-000000?style=flat-square) ![Stack](https://img.shields.io/badge/LLM-Anthropic%20%7C%20Groq%20%7C%20Mock-5A4FCF?style=flat-square) ![Stack](https://img.shields.io/badge/auth%2Bsaves-Supabase-3FCF8E?style=flat-square)

---

## How it works

Each simulated day a subset of agents is selected (weighted-probabilistic) to receive an LLM
prompt containing their personality, **relevance-retrieved memories**, relationships, the world
event, and their **personal feed** of what they've witnessed. They return structured JSON — an
action (post / direct / amplify / comment), targets, emotional reaction, relationship deltas,
influence changes, a new memory, a belief/stance shift, and an explanation — which the engine
validates and applies. Targets reinterpret events through a **perception** layer; charged
encounters spark **multi-turn exchanges**; agents periodically **reflect** to form higher-level
beliefs and **plan** toward goals. Background agents evolve via deterministic rules. Every day the
engine aggregates agent stances into a **population forecast with a confidence score**, and at the
end an LLM writes the town's story and grades the player's **prophecy**. No two runs are alike.

> Deep-dive docs: **[CALCULATIONS.md](./CALCULATIONS.md)** (every metric & formula).

---

## Features

**Believable agents (Generative-Agents style)**
- **Relevance memory retrieval** — memories scored by relevance · recency · importance, not just recency.
- **Reflection** — agents periodically synthesize higher-level insights from recent memories.
- **Perception** — the same event lands differently depending on who receives it and their history.
- **Goal-driven planning** + **multi-turn exchanges** for charged relationships.

**Living social world (OASIS style)**
- **Real action space** — post (broadcast), direct (private), amplify (boost someone), comment.
- **Per-agent feed** ranked by interest + influence + recency → echo chambers, virality, factions.
- **World knowledge graph** — entities, relationships, and power structures extracted up front.

**Prediction engine (MiroFish style)**
- Per-agent **belief/stance** on auto-derived topics, aggregated daily into a population distribution.
- **Forecast** with **swarm confidence** (consensus vs. disagreement) and **pivotal-day** causal tracing.

**Engagement**
- **Pixel-character avatars** (seeded, mood-driven expressions) + "based on a real person."
- **Story view** — each day reads as a "chapter" with narrative beats.
- **Nudges** — whisper advice to a character, inject an event, or **add a new character mid-run**
  (a newcomer initialized for the current day whose arrival can move the forecast).
- **Prophecy** — write a free-text prediction; the AI grades it against the outcome.
- Responsive UI with an immersive pixel-town background.

**Performance**
- **Concurrent inference** — each day's agent reasoning fans out in parallel (`asyncio.gather`,
  bounded by `LLM_MAX_CONCURRENCY`) and is applied sequentially for deterministic ordering.
- **Tiered models** — routine turns route to a cheap model, pivotal/player-facing turns to a
  strong one (`*_MODEL_CHEAP` / `*_MODEL_STRONG`).

---

## Architecture

```
Next.js 14 frontend (React, Tailwind, D3 force graph, pixel avatars, responsive)
    │   HTTP / Server-Sent Events
    ▼
FastAPI backend  ──  Supabase (auth + saved worlds)
    │
    ▼
Simulation engine (daily tick: morning → afternoon → evening → night)
  ├── World graph      — one-time entity/relationship/power-structure + topic extraction
  ├── Agent selector   — softmax-weighted sampling (event proximity, influence, conflict, groups)
  ├── Planner          — short-term goal intentions, refreshed when stale
  ├── AI reasoner      — LLM → structured action JSON (incl. action_kind + stance shift)
  ├── Perception       — targets reinterpret incoming events through their own character
  ├── Multi-turn       — charged encounters spark back-and-forth exchanges
  ├── Reflector        — periodic higher-level belief synthesis
  ├── Observation/feed — interest+hot-score routing → per-agent feeds
  ├── Applicator       — validates + applies relationship / memory / influence / stance updates
  ├── Deterministic    — background agents who didn't get an LLM call
  ├── Vignettes        — occasional theatrical moments (dreams, catchphrases, announcements)
  ├── Metrics          — relationship counts, influence, belief means + uncertainty + confidence
  └── Reporter         — final narrative + structured forecast + prophecy grading
    │
    ▼
In-memory world store (per session) · Supabase persistence for saves
```

---

## Project layout

```
backend/
  main.py                 REST + SSE endpoints
  models.py               Pydantic models (Agent, World, WorldGraph, Memory, Forecast, …)
  state.py                In-memory world store
  llm.py                  LLM adapter — Anthropic / OpenAI-compat / mock (marker-dispatched)
  auth.py                 Supabase JWT auth dependency
  supabase_db.py          Saved-world persistence (Supabase)
  simulation/
    engine.py             Daily tick loop; orchestrates everything below
    selector.py           Softmax-weighted probabilistic agent selection
    reasoner.py           Builds context prompts; parses structured actions
    perception.py         Subjective reinterpretation of incoming events
    reflector.py          Periodic higher-level belief synthesis
    planner.py            Goal-driven short-term intentions
    observation.py        Witness routing + interest/hot-score feed ranking
    worldgraph.py         Entity/relationship/power-structure + topic extraction
    stance.py             Per-agent belief initialization
    applicator.py         Applies relationship / memory / influence / stance updates
    deterministic.py      Background rules for non-AI agents
    metrics.py            Macro metrics + belief aggregation + swarm confidence
    vignette.py           Theatrical character moments
    prophecy.py           Grades the player's prediction against the outcome
    digest.py             Punchy day-card assembly
    generator.py          LLM-generates filler characters
    reporter.py           Final narrative report + structured forecast

frontend/
  app/page.tsx            Main flow: setup → characters → event → simulation
  components/
    WorldSetup, CharacterEditor, EventAndRun, SimulationView, RelationshipGraph,
    Inspector, CharacterPanel, StoryChapter, Engagement, PixelAvatar, AuthScreen, …
  lib/api.ts, lib/types.ts, lib/useViewport.ts
```

---

## LLM providers

Set `LLM_PROVIDER` in `backend/.env`:

| Provider | Cost | Notes |
|---|---|---|
| `mock` | Free, no key | Deterministic fake JSON. Full end-to-end smoke-test with no API key. |
| `openai_compat` | Free tier available | Groq (free fast Llama), OpenRouter, or OpenAI. |
| `anthropic` | Paid (cents per run) | Best structured-output quality. Recommended for production. |

```env
# Groq (free tier, good for testing)
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
OPENAI_COMPAT_API_KEY=gsk_...
OPENAI_COMPAT_MODEL=llama-3.3-70b-versatile

# Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929

# Mock (no key)
LLM_PROVIDER=mock
```

**Optional — performance & cost tuning** (all backward compatible; unset = previous behavior):

```env
LLM_MAX_CONCURRENCY=6                 # max simultaneous LLM calls in the day fan-out
# Tiered models — cheap for routine turns, strong for pivotal/player-facing ones.
# Each falls back to the single *_MODEL var above if unset.
ANTHROPIC_MODEL_STRONG=claude-sonnet-4-5-20250929
ANTHROPIC_MODEL_CHEAP=claude-haiku-4-5-20251001
OPENAI_COMPAT_MODEL_STRONG=llama-3.3-70b-versatile
OPENAI_COMPAT_MODEL_CHEAP=llama-3.1-8b-instant
```

**Optional — Supabase (auth + saved worlds).** Without these, the core simulation works fully;
only the save/load feature is disabled.

```env
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...        # backend only
# frontend/.env.local:
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```
Run `supabase_migration.sql` in the Supabase SQL editor to create the `saves` table (incl. the
`service_role` grants).

---

## Getting started

```bash
# 1 — Backend
cd backend
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # pick your LLM provider
uvicorn main:app --reload --port 8000
# verify: curl http://localhost:8000/health  →  {"ok":true,"llm_provider":"..."}

# 2 — Frontend
cd frontend
npm install
npm run dev          # http://localhost:3000
```

---

## User flow

| Step | What you do |
|---|---|
| 1 | Write a 1-paragraph world prompt and pick a target population. |
| 2 | Add custom characters — name, role, traits, goals, mood, groups, a **pixel avatar**, and optionally "based on a real person." |
| 3 | Auto-generate filler characters to hit the population target. |
| 4 | Set a starting event, and optionally write a **prophecy** (free-text prediction). |
| 5 | Pick simulation length (7-day quick or 30-day default) and run — streams day-by-day via SSE. |
| 6 | Follow the **story** — each day is a chapter of beats; scrub the timeline, click characters, read the **feed**, watch the **forecast** + swarm confidence move. |
| 7 | **Nudge** — whisper advice to a character, inject an event, or add a new character mid-run. |
| 8 | **Chat** with any character in-character. |
| 9 | Read the final narrative report and the AI's **verdict** on your prophecy. |
| 10 | **Continue** a finished run for more days, or **save/load** worlds (Supabase). |

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | LLM provider status |
| `POST` | `/world` | Create a world |
| `GET` | `/world/{id}` | Get world state |
| `POST` | `/world/{id}/character` | Add a custom character (incl. avatar / based_on) |
| `POST` | `/world/{id}/inject-character` | Add a character mid-run — initialized for the current day, joins on continue |
| `DELETE` | `/world/{id}/character/{agent_id}` | Remove a character |
| `POST` | `/world/{id}/generate-fillers` | LLM-generate filler characters |
| `POST` | `/world/{id}/event` | Set the starting event |
| `POST` | `/world/{id}/inject-event` | Queue a player-authored event for the next day |
| `POST` | `/world/{id}/prophecy` | Set the player's free-text prediction |
| `POST` | `/world/{id}/simulate`(`/stream`) | Run simulation (blocking / SSE). Optional `pause_on_days` stops the stream on chosen days. |
| `POST` | `/world/{id}/simulate/continue`(`/stream`) | Continue from last day (blocking / SSE). Also honors `pause_on_days`. |
| `GET` | `/world/{id}/result` | Fetch latest result (incl. forecast + prophecy verdict) |
| `POST` | `/world/{id}/agent/{agent_id}/chat` | Chat with a character |
| `POST` | `/world/{id}/agent/{agent_id}/advise` | Whisper advice (enters the character's memory) |
| `*` | `/saves`, `/saves/{id}`, `/saves/{id}/load` | Save / list / load worlds (auth required) |

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Cost notes

The realism layers (planning, multi-turn exchanges, perception, reflection, vignettes,
world-graph, forecasting, prophecy) add LLM calls well beyond a one-call-per-agent baseline, so
runs are richer but heavier than earlier versions. On the **mock** provider everything is free
and runs end-to-end with no key. Two levers keep paid runs fast and cheap (see
[PERFORMANCE_AND_LIVE_EDITING.md](./PERFORMANCE_AND_LIVE_EDITING.md)):
- **Concurrent inference** — each day's reasoning fans out in parallel (tune `LLM_MAX_CONCURRENCY`),
  so a day takes ≈ one call's latency instead of N × (latency + delay).
- **Tiered models** — route routine turns to a cheap model (`*_MODEL_CHEAP`) and reserve a strong
  model for pivotal/player-facing ones (`*_MODEL_STRONG`).

Also tune `reasoning_agents_per_day` to trade depth for cost.

---

## Known limitations

- **In-memory runtime store** — active worlds live in memory; persistence is via Supabase saves.
- **Mock-verified** — the engine is verified end-to-end on the mock provider; a real-LLM quality
  pass and an automated test suite are still open (see [BACKLOG.md](./BACKLOG.md)).
- **Prediction `question` not yet wired to the UI** — `prophecy` is; see [BACKLOG.md](./BACKLOG.md) §③.
- **Scale** — designed for tens of characters, not OASIS-scale millions. Concurrent inference and
  tiered models are implemented; the distributed Environment Server / clustered inferencer for
  true 1M-agent scale is intentionally out of scope.

---

## Roadmap

Design rationale and status: **[REALISM_ANALYSIS.md](./REALISM_ANALYSIS.md)**. Concrete next
steps with implementation notes: **[BACKLOG.md](./BACKLOG.md)**. Original design doc:
[projectplan.md](./projectplan.md).
