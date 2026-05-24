# Deployment Readiness

## Summary
The project was assessed to answer: is it deployable, or does the engine/UI need more work? Exploration of both `engine/` (FastAPI sim backend) and `web/` (Next.js 14 frontend) shows **both halves are mature and feature-complete** — the simulation pipeline, REST+SSE API, LLM layer, and the full UI loop all work. The gap to "deployable" is **deployment plumbing and a real-LLM validation pass**, not more feature development.

Hosting target is **not yet decided**, so this stays host-agnostic; the state strategy is presented as options to choose at implementation time.

## Current maturity
- **Engine** — solid/beta: pipeline (`engine/simulation/engine.py`), full API incl. cancel/inject/chat (`engine/main.py`), robust 3-provider LLM layer w/ retry+fallback (`engine/llm.py`), realism tests on mock provider (`engine/tests/test_realism.py`).
- **UI** — ~8.5/10: ~4,500 LOC Next.js app, 13 components, every endpoint wired incl. SSE streaming (`web/`).

## Blockers to address (ordered by leverage)
1. **Containerization / hosting config** — none exists today (no Dockerfile/compose/vercel.json/fly.toml). Add host-agnostic Docker setup so any target works:
   - `engine/Dockerfile` (python:3.11 + uvicorn)
   - `web/Dockerfile` (node:20 + `next build`/`next start`)
   - `docker-compose.yml` at root wiring both services + env files
2. **CORS + startup validation** (`engine/main.py`):
   - Read allowed origins from `FRONTEND_ORIGIN` env instead of hardcoded `*`
   - Add a FastAPI lifespan/startup hook that fail-fasts if LLM/Supabase credentials are missing or unreachable
3. **Active simulation state** (`engine/state.py`) — in-memory `WorldStore` has no eviction; a long-running server accumulates worlds in RAM. Pick one at impl time:
   - **(a) Cap + LRU evict** — smallest change, keeps current design
   - **(b) Redis** — stateless server, most robust, more work
   - **(c) Supabase checkpoint** — persist active worlds between days using existing saves layer
4. **Real-LLM validation pass** — everything is verified only on the deterministic mock provider. Do one full end-to-end run on Anthropic/Groq to validate output quality and cost (BACKLOG ⑪).
5. **Observability** — logging calls exist but no handler config; add structured logging setup in `engine/main.py`.

## Polish (non-blocking)
- Wire prediction `question` field to a UI input (BACKLOG ③) — exists in `web/lib/types.ts` but unsettable.
- Mock-mode demo bugs (BACKLOG ①②) — only affect keyless demo, real LLM unaffected.

## Verification
- `docker-compose up` brings up both services; web reaches engine at configured `NEXT_PUBLIC_API_URL`.
- Startup hook fails fast with a clear error when credentials are absent.
- One real-LLM run completes a full multi-day simulation end-to-end (create → stream → result → save/load round-trip).
- In-memory store stays bounded under repeated world creation (whichever state option is chosen).
