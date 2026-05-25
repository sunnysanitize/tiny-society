# Deployment Readiness

## Summary
The project was assessed to answer: is it deployable, or does the engine/UI need more work? Exploration of both `engine/` (FastAPI sim backend) and `web/` (Next.js 14 frontend) shows **both halves are mature and feature-complete** — the simulation pipeline, REST+SSE API, LLM layer, and the full UI loop all work. The gap to "deployable" is **deployment plumbing and a real-LLM validation pass**, not more feature development.

Hosting target is **not yet decided**, so this stays host-agnostic; the state strategy was implemented as the smallest option (cap + LRU eviction).

## Current maturity
- **Engine** — solid/beta: pipeline (`engine/simulation/engine.py`), full API incl. cancel/inject/chat (`engine/main.py`), robust 3-provider LLM layer w/ retry+fallback (`engine/llm.py`), realism tests on mock provider (`engine/tests/test_realism.py`).
- **UI** — ~8.5/10: ~4,500 LOC Next.js app, 13 components, every endpoint wired incl. SSE streaming (`web/`).

## Progress log

### ✅ DONE — "cheap cluster" (items 1, 2, 3a, 5), verified on mock provider
Completed 2026-05-24. All changes verified: `engine` imports cleanly, all 15 realism tests pass, startup validation + LRU eviction unit-checked.

1. **Containerization / hosting config** — DONE (host-agnostic Docker):
   - `engine/Dockerfile` (python:3.11-slim + uvicorn, no `--reload`)
   - `web/Dockerfile` (multi-stage node:20, uses Next standalone output)
   - `web/next.config.js` — added `output: "standalone"` for a lean image
   - `docker-compose.yml` at root wiring both services + `engine/.env` + NEXT_PUBLIC_* build args
   - `engine/.dockerignore`, `web/.dockerignore`
2. **CORS + startup validation** (`engine/main.py`) — DONE:
   - CORS now reads `FRONTEND_ORIGIN` (comma-separated) instead of hardcoded `*` (`_allow_origins`)
   - `_validate_config()` runs in a FastAPI `lifespan` hook: fail-fasts if `LLM_PROVIDER=anthropic` lacks `ANTHROPIC_API_KEY`, if `openai_compat` lacks base URL/key, or if Supabase is half-configured; warns for mock/no-Supabase.
3a. **State eviction** (`engine/state.py`) — DONE:
   - `WorldStore` rewritten as an LRU (OrderedDict) with `MAX_LIVE_WORLDS` cap (default 200, env-overridable). Evicts least-recently-used world + its result together. All accessors touch-on-use under the existing lock.
5. **Observability** (`engine/main.py`) — DONE:
   - `logging.basicConfig` root handler (level via `LOG_LEVEL`, default INFO) so the existing `logging.*` calls across simulation modules now surface. Logger named `tiny_society`.

### ⏳ REMAINING — to pick up next
4. **Real-LLM validation pass** — NOT STARTED. This is the expensive/risky one (burns real Anthropic/Groq API credits + lots of context watching a streamed multi-day run). Do as its own focused session. Goal: one full end-to-end run on a real provider — create → stream → result → save/load round-trip — to validate output quality and cost (BACKLOG ⑪). Set `LLM_PROVIDER=anthropic` (or `openai_compat`) in `engine/.env` first.

### Polish (non-blocking, not started)
- Wire prediction `question` field to a UI input (BACKLOG ③) — exists in `web/lib/types.ts` but unsettable.
- Mock-mode demo bugs (BACKLOG ①②) — only affect keyless demo, real LLM unaffected.

## How to verify (current state)
- Engine import + tests: `cd engine && python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest && LLM_PROVIDER=mock .venv/bin/python -m pytest tests/ -q` → 15 passed.
- Docker: `docker compose up --build` brings up engine (:8000) and web (:3000); web reaches engine at configured `NEXT_PUBLIC_API_URL`. *(Not yet run in this environment — Docker build untested here; verify on a machine with Docker.)*
- Startup fail-fast: `LLM_PROVIDER=anthropic ANTHROPIC_API_KEY= uvicorn main:app` should refuse to boot.
- Store stays bounded: set `MAX_LIVE_WORLDS` low and create more worlds than the cap; oldest are evicted.

## Notes for next context window
- A working venv may exist at `engine/.venv` (gitignored) with deps + pytest installed — reuse it to skip reinstall.
- Docker images were authored but **not built/run here**; a `docker compose up --build` smoke test on a Docker-capable machine is the one unchecked box in the done cluster.
- Nothing has been committed. Changes are unstaged in the working tree.
