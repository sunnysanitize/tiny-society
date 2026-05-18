# Tiny Society AI — MVP

Multi-agent AI social simulation. Fictional agents reason via LLM, return structured JSON, and the simulation engine applies validated state updates over 7 or 30 simulated days. See [projectplan.md](./projectplan.md) for the full design doc.

## Architecture (MVP)

```
Next.js frontend
    ↓ HTTP
FastAPI backend
    ↓
Hybrid simulation engine
  ├─ Agent selector (event proximity, influence, active conflicts)
  ├─ AI reasoner — LLM call returning structured JSON per agent
  ├─ JSON validator + state applicator
  ├─ Deterministic rule engine (background agents)
  ├─ Macro metrics calculator
  └─ Final report generator (single LLM call at end)
    ↓
In-memory store (per session)
```

## Project layout

```
backend/                FastAPI + simulation engine
  main.py               REST endpoints
  models.py             Pydantic models (Agent, Relationship, AgentAction, etc.)
  state.py              In-memory world store
  llm.py                LLM adapter (Anthropic / OpenAI-compat / mock)
  simulation/
    engine.py           Daily tick loop (morning → afternoon → evening → night)
    selector.py         Picks who gets AI reasoning each day
    reasoner.py         Builds context prompts; parses structured JSON
    deterministic.py    Background rules for non-AI agents
    applicator.py       Validates + applies structured updates to state
    metrics.py          Macro metrics calculator
    generator.py        Auto-generates filler characters via LLM
    reporter.py         Final narrative report

frontend/               Next.js 14 + Tailwind + React Flow
  app/page.tsx          Main flow: setup → characters → event → simulation
  components/           Graph, timeline, character panel, metrics, report
  lib/api.ts            Backend client
```

## LLM provider options

The MVP supports three LLM backends. Pick one via the `LLM_PROVIDER` env var.

| Provider | Cost | Setup |
|---|---|---|
| `mock` | free, no key | Deterministic fake JSON. Runs end-to-end so you can verify the UI. |
| `openai_compat` | free tier available | Works with Groq (free fast Llama), OpenRouter, OpenAI itself. |
| `anthropic` | paid (cheap for MVP) | Production path. Best structured-output quality. |

### Groq free tier (recommended for testing)

1. Get a free API key at https://console.groq.com/keys
2. Set in `backend/.env`:
   ```
   LLM_PROVIDER=openai_compat
   OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
   OPENAI_COMPAT_API_KEY=gsk_...
   OPENAI_COMPAT_MODEL=llama-3.3-70b-versatile
   ```

### Anthropic (production)

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
```

### Mock (no key, UI testing)

```
LLM_PROVIDER=mock
```

## Run

### Backend (terminal 1)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then edit with your provider choice
uvicorn main:app --reload --port 8000
```

Backend serves at `http://localhost:8000`. Visit `/health` to check the LLM provider.

### Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Frontend at `http://localhost:3000`.

## User flow

1. **Create world** — write a 1-paragraph world prompt, pick target population (5–60).
2. **Add custom characters** — name, role, traits, goals, mood, groups, optional starting memory.
3. **Auto-generate filler agents** — LLM fills the rest up to target population.
4. **Inject starting event** — a single sentence the agents will react to.
5. **Pick length** — 7-day quick mode or 30-day default.
6. **Run** — the engine ticks day by day. Each day a subset of agents gets an LLM reasoning call; their structured JSON outputs are validated and applied. Background agents evolve via deterministic rules.
7. **Explore** — navigate the day-by-day timeline, click nodes in the relationship graph, read memory logs, compare before/after macro metrics, read the final LLM narrative.

## What makes this different from a traditional life sim

Traditional life sims pick character moments from a fixed library of scripted templates.

In Tiny Society AI, selected agents each day get an LLM prompt containing their own traits, mood, memories, relationships, the world event, and the recent event log. They return a structured JSON action: target, emotional reaction, relationship deltas, influence changes, new memory, and a one-sentence explanation. The engine validates this JSON against the existing agent roster and applies the updates. No two simulations of the same world produce the same outcome.

## Costs (real provider)

Rough order-of-magnitude with default `reasoning_agents_per_day=8`:
- 7-day quick: ~56 reasoning calls + 1 report ≈ fits easily in any free tier
- 30-day default: ~240 reasoning calls + 1 report — Groq free tier handles this; Anthropic is a few cents

## Constraints

- All characters fictional. No real people.
- AI reasoning runs for selected agents only — not every agent every day.
- Memory is in-process. Restarting the backend clears all worlds.
- No persistence, auth, or production deployment in the MVP.

## Verified working (initial build)

- Backend imports cleanly; mock provider runs a full 7-day simulation in seconds.
- HTTP API tested end-to-end: create world → add custom character → generate 9 filler agents → inject event → run 7-day simulation. Result: 3 friendships, 2 rivalries, 2 romances formed; 4 daily highlights on day 7; final report generated.
- Frontend type-checks and builds cleanly (`npm run build` → 51.6 kB main route).
- LLM adapter exercised with the `mock` provider. `anthropic` and `openai_compat` paths are wired but require valid API keys to run.

## Deferred items (intentional MVP scope)

- **In-memory only** — restarting the backend wipes all worlds and results. Persistence (Supabase / Postgres) is a future feature.
- **Default LLM is mock** — runs end-to-end with no API key. Swap to `openai_compat` + Groq free tier for real agent reasoning, or `anthropic` for production quality.
- **No automated tests** — the smoke test in `README` / engine validation is the verification. A pytest suite is a fast follow-up.
- **No graph animation** — graph snapshots are static per day, navigated via the timeline strip. Animated transitions are a future feature.
- **No mid-simulation event injection** — only one starting event per run. Mid-run events are a future feature.
- **No auth, no payments, no production deployment.**

## Docker?

Not needed for the MVP. The backend is `pip install + uvicorn`, the frontend is `npm install + npm run dev` — no system deps, no database. Add Docker (and a `docker-compose.yml`) when you introduce Postgres/Supabase persistence or deploy to a cloud host.

## Roadmap

See [projectplan.md](./projectplan.md) — Future Features section.
