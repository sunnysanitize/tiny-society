# Tiny Society AI

A multi-agent AI social simulation. Build a fictional world, populate it with characters, fire off a starting event, and watch a cast of LLM-driven agents reason, form relationships, and evolve over 7–30 simulated days.

![Stack](https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square) ![Stack](https://img.shields.io/badge/frontend-Next.js%2014-000000?style=flat-square) ![Stack](https://img.shields.io/badge/LLM-Anthropic%20%7C%20Groq%20%7C%20Mock-5A4FCF?style=flat-square)

---

## How it works

Each simulated day a subset of agents receives an LLM prompt containing their traits, mood, memories, relationships, the world event, and the recent event log. They return structured JSON — target, emotional reaction, relationship deltas, influence changes, new memory, one-sentence explanation — which the engine validates and applies to shared world state. Background agents evolve via deterministic rules. No two runs of the same world produce the same outcome.

---

## Architecture

```
Next.js 14 frontend (React, Tailwind, D3 force graph)
    │
    │  HTTP / Server-Sent Events
    ▼
FastAPI backend
    │
    ▼
Simulation engine
  ├── Agent selector      — event proximity, influence, active conflicts
  ├── AI reasoner         — LLM call → structured JSON per selected agent
  ├── JSON validator      — Pydantic + roster cross-check
  ├── State applicator    — applies relationship / memory / influence updates
  ├── Deterministic rules — background agents who didn't get an LLM call
  ├── Macro metrics       — trust, cohesion, conflict, influence Gini
  └── Final reporter      — single LLM narrative at simulation end
    │
    ▼
In-memory world store (per session)
```

---

## Project layout

```
backend/
  main.py                 REST + SSE endpoints
  models.py               Pydantic models (Agent, World, SimulationResult, …)
  state.py                In-memory world store
  llm.py                  LLM adapter — Anthropic / OpenAI-compat / mock
  simulation/
    engine.py             Daily tick loop (morning → afternoon → evening → night)
    selector.py           Picks which agents get AI reasoning each day
    reasoner.py           Builds context prompts; parses structured JSON
    deterministic.py      Background rules for non-AI agents
    applicator.py         Validates + applies updates to world state
    metrics.py            Macro metrics calculator
    generator.py          LLM-generates filler characters to hit population target
    reporter.py           Final narrative report

frontend/
  app/page.tsx            Main flow: setup → characters → event → simulation
  components/
    WorldSetup.tsx         World prompt + population picker
    CharacterEditor.tsx    Add / remove custom characters
    EventAndRun.tsx        Starting event + simulation length
    SimulationView.tsx     Day-by-day timeline + live SSE progress
    RelationshipGraph.tsx  D3 force graph of agent relationships
    CharacterPanel.tsx     Agent detail drawer
    Inspector.tsx          Click-to-inspect relationships and memories
    MetricsPanel.tsx       Before/after macro metrics comparison
    Timeline.tsx           Day scrubber
  lib/api.ts              Backend client
  lib/types.ts            Shared TypeScript types
```

---

## LLM providers

Set `LLM_PROVIDER` in `backend/.env` to one of three options:

| Provider | Cost | Notes |
|---|---|---|
| `mock` | Free, no key | Deterministic fake JSON. Full UI smoke-test with no API key. |
| `openai_compat` | Free tier available | Works with Groq (free fast Llama), OpenRouter, or OpenAI itself. |
| `anthropic` | Paid (a few cents for a full run) | Best structured-output quality. Recommended for production. |

### Groq free tier (recommended for testing)

1. Get a free key at [console.groq.com/keys](https://console.groq.com/keys)
2. Add to `backend/.env`:

```env
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
OPENAI_COMPAT_API_KEY=gsk_...
OPENAI_COMPAT_MODEL=llama-3.3-70b-versatile
```

### Anthropic

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
```

### Mock (no key, UI testing only)

```env
LLM_PROVIDER=mock
```

---

## Getting started

### 1 — Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit with your LLM provider choice
uvicorn main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/health` — should return `{"ok":true,"llm_provider":"..."}`.

### 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## User flow

| Step | What you do |
|---|---|
| 1 | Write a 1-paragraph world prompt and pick a target population (5–60). |
| 2 | Add custom characters — name, role, traits, goals, mood, groups, starting memories. |
| 3 | Auto-generate filler agents to hit the population target (LLM-written). |
| 4 | Inject a one-sentence starting event the whole society will react to. |
| 5 | Pick simulation length — 7-day quick mode or 30-day default. |
| 6 | Run — streams day-by-day via SSE. Selected agents reason via LLM; background agents evolve deterministically. |
| 7 | Explore — scrub the timeline, click nodes in the relationship graph, read memory logs, compare macro metrics, read the final narrative report. |
| 8 | Chat — send a message to any agent and they'll reply in character. |
| 9 | Continue — extend any completed simulation by additional days from where it left off. |

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | LLM provider status |
| `POST` | `/world` | Create a new world |
| `GET` | `/world/{id}` | Get world state |
| `POST` | `/world/{id}/character` | Add a custom character |
| `DELETE` | `/world/{id}/character/{agent_id}` | Remove a character |
| `POST` | `/world/{id}/generate-fillers` | LLM-generate filler characters |
| `POST` | `/world/{id}/event` | Set the starting event |
| `POST` | `/world/{id}/simulate` | Run simulation (blocking) |
| `POST` | `/world/{id}/simulate/stream` | Run simulation (SSE stream) |
| `POST` | `/world/{id}/simulate/continue` | Continue from last day (blocking) |
| `POST` | `/world/{id}/simulate/continue/stream` | Continue from last day (SSE stream) |
| `GET` | `/world/{id}/result` | Fetch latest simulation result |
| `POST` | `/world/{id}/agent/{agent_id}/chat` | Chat with an agent in character |

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Cost estimates

Default: `reasoning_agents_per_day = 8`

| Run | LLM calls | Anthropic Sonnet | Groq free tier |
|---|---|---|---|
| 7-day quick | ~57 | ~$0.02 | Fits in free tier |
| 30-day default | ~241 | ~$0.08 | Fits in free tier |

---

## Known limitations

- **In-memory only** — restarting the backend wipes all worlds. Persistence (Postgres / Supabase) is a future feature.
- **No auth or multi-tenancy** — single-user, local use only.
- **No mid-run event injection** — one starting event per simulation run.
- **No automated test suite** — the mock provider smoke-test covers the critical path.

---

## Roadmap

See [projectplan.md](./projectplan.md) for the full design doc and future features list.
