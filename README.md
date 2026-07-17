# Tiny Society AI

**An experimental multi-agent platform for studying memory, social structure, information
exposure, and collective belief change in LLM-driven populations.**

Tiny Society AI simulates small societies of language-model agents over 7–30 virtual days.
Agents remember events, form relationships, receive different information, revise topic stances,
and act within a shared world. The system records how those individual changes become
population-level patterns.

> **Research status:** this is an exploratory simulation, not a calibrated model of human
> behavior. Its forecasts describe simulated agents and should not be treated as real-world
> predictions.

**Technical supplement:** [Calculations and measurement definitions](./CALCULATIONS.pdf)

## Research overview

The project is designed to support questions such as:

- How do memory, reflection, and planning affect an agent's later decisions?
- How do relationships and network position change what information an agent sees?
- When does a population converge on a shared stance, and when does it remain divided?
- Which interactions produce the largest changes in group-level beliefs?
- How do stochastic LLM responses interact with fixed numerical update rules?

The unit of analysis is a simulated agent. Each agent has traits, goals, memories, relationships,
influence, topic stances, and a personal feed. The main outputs are daily social metrics, stance
means and disagreement, pivotal events, and a final narrative summary.

## Relationship to prior work

Tiny Society AI builds on the memory, reflection, and planning architecture introduced by Park et
al. in *Generative Agents: Interactive Simulacra of Human Behavior* [1]. Both systems store agent
experiences in natural language and retrieve memories using relevance, recency, and importance.

This implementation adds several mechanisms for population-level experiments:

- Directed relationships with numeric strength and derived social categories
- Per-agent information feeds based on witnesses, shared interests, influence, and recency
- Topic-level stances and daily measures of population agreement
- Probabilistic selection of agents for LLM reasoning
- Fixed background updates for agents that are not selected
- Explicit influence, relationship, and stance transition rules
- Pivotal-day tracing and a final simulation forecast

The Stanford study provides the architectural starting point. The
[technical supplement](./CALCULATIONS.pdf) defines this project's formulas and implementation
choices.

## Simulation method

### Initialization

A run begins with a world prompt, a population of custom or generated agents, a starting event,
and an optional prediction written by the user. The engine extracts entities, social structure,
and stance topics before the first simulated day.

### Daily update cycle

1. **Select active agents.** A softmax-weighted sampler uses event relevance, influence, charged
   relationships, and group membership. The default limit is eight reasoning agents per day.
2. **Build individual context.** Each selected agent receives its traits, goals, relationships,
   relevant memories, plan, witnessed events, and ranked personal feed.
3. **Generate structured actions.** The LLM returns an action, targets, emotional response,
   relationship intent, memory, explanation, and any stance shift.
4. **Apply social interpretation.** Recipients can interpret the same action differently based on
   personality and prior history. Charged relationships may create short multi-turn exchanges.
5. **Update state.** The engine validates and applies relationship, influence, memory, and stance
   changes in a fixed order.
6. **Evolve background agents.** Agents without an LLM turn still receive deterministic bond,
   group, stance, and influence updates.
7. **Measure the population.** Daily metrics summarize the relationship graph, influence changes,
   topic means, disagreement, and forecast confidence.

A simulated day contains morning, afternoon, evening, and night phases. Generated actions can run
concurrently, but state changes are applied sequentially so a fixed set of outputs produces a
consistent update order.

## Measurements

| Output | Interpretation |
|---|---|
| Relationship counts | Number of friendship, rivalry, conflict, romance, and alliance pairs |
| Average relationship strength | Mean absolute strength across stored relationships |
| Influence gainers and losers | Largest changes from each agent's initial influence |
| Social fragmentation | Fraction of agents with no outgoing relationships |
| Topic mean | Average population stance on a topic, from `-1` to `1` |
| Topic uncertainty | Population standard deviation of stances on a topic |
| Swarm confidence | One minus mean topic disagreement, clamped to `0–1` |
| Pivotal days | Days with the largest aggregate movement in topic means |

Swarm confidence measures agreement among simulated agents. It is **not** the probability that a
forecast is correct. Complete definitions, equations, thresholds, and parameter ranges are in
[CALCULATIONS.pdf](./CALCULATIONS.pdf).

## Experimental use and reproducibility

For a comparable set of runs, keep the following values fixed and report them with the results:

- World prompt, starting event, and initial character definitions
- LLM provider and exact model identifiers
- Simulation length and reasoning-agent limit
- Concurrency, model-tier, and recency settings
- Any user interventions, injected events, or mid-run characters

The `mock` provider supplies deterministic structured responses and is useful for testing the
engine. Real LLM providers introduce run-to-run variation. Research comparisons should therefore
use repeated runs and report distributions rather than a single outcome.

## Research interface

### Narrative timeline

![Daily narrative and agent activity](./web/public/story.png)

### Relationship network

![Directed social relationship network](./web/public/network.png)

### Population forecast

![Topic forecast and confidence view](./web/public/forecast.png)

## System architecture

```text
Next.js research interface
    |  HTTP / Server-Sent Events
    v
FastAPI API  ----  optional Supabase authentication and saved runs
    |
    v
Simulation engine
  |-- World graph       entities, relationships, groups, and stance topics
  |-- Agent selector    weighted probabilistic sampling
  |-- Planner           short-term goal intentions
  |-- Reasoner          LLM context and structured action generation
  |-- Memory            relevance, recency, and importance retrieval
  |-- Observation       witness routing and personal feed ranking
  |-- Perception        recipient-specific interpretation
  |-- Multi-turn        short exchanges for charged interactions
  |-- Applicator        validated state transitions
  |-- Deterministic     background-agent updates
  |-- Metrics           social and belief aggregation
  `-- Reporter          final narrative and structured forecast
    |
    v
In-memory run state  ----  optional Supabase persistence
```

## Repository structure

```text
engine/
  main.py                    FastAPI routes and streaming endpoints
  models.py                  Agent, world, memory, and forecast schemas
  llm.py                     Anthropic, OpenAI-compatible, and mock adapters
  state.py                   In-memory run store
  simulation/
    engine.py                Daily simulation loop
    selector.py              Probabilistic active-agent selection
    reasoner.py              Context assembly and structured actions
    memory.py                Memory scoring and retrieval
    observation.py           Witness routing and feed ranking
    perception.py            Recipient-specific interpretation
    planner.py               Short-term planning
    reflector.py             Higher-order memory synthesis
    applicator.py            Relationship, influence, memory, and stance updates
    deterministic.py         Background-agent rules
    metrics.py               Population measurements
    reporter.py              Final report and forecast
  tests/test_realism.py      Mock-provider simulation tests

web/
  app/                       Next.js application routes
  components/                Setup, simulation, network, and forecast views
  lib/                       API client, types, authentication, and utilities

CALCULATIONS.pdf             Methods and calculations supplement
```

## Running locally

### 1. Backend

```bash
cd engine
python3 -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

Verify the backend:

```bash
curl http://localhost:8000/health
```

### 2. Frontend

```bash
cd web
npm install
npm run dev
```

The interface runs at [http://localhost:3000](http://localhost:3000). Interactive API
documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## LLM configuration

Set `LLM_PROVIDER` in `engine/.env`.

| Provider | Purpose | Key requirement |
|---|---|---|
| `mock` | Deterministic engine tests and local development | None |
| `openai_compat` | OpenAI-compatible services such as Groq or OpenRouter | Provider API key |
| `anthropic` | Anthropic models | Anthropic API key |

Example configurations:

```env
# Deterministic local run
LLM_PROVIDER=mock

# OpenAI-compatible provider
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
OPENAI_COMPAT_API_KEY=...
OPENAI_COMPAT_MODEL=llama-3.3-70b-versatile

# Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
```

Optional performance controls:

```env
LLM_MAX_CONCURRENCY=6
ANTHROPIC_MODEL_STRONG=claude-sonnet-4-5-20250929
ANTHROPIC_MODEL_CHEAP=claude-haiku-4-5-20251001
OPENAI_COMPAT_MODEL_STRONG=llama-3.3-70b-versatile
OPENAI_COMPAT_MODEL_CHEAP=llama-3.1-8b-instant
```

Supabase is optional. Without it, the simulation works but saved runs and authentication are
disabled. Configuration variables are documented in `engine/.env.example` and
`web/.env.local.example`.

## Tests

The simulation tests use the mock provider and do not require a paid API key.

```bash
cd engine
pytest -q
```

For frontend verification:

```bash
cd web
npm run build
```

## API summary

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Report backend and LLM-provider status |
| `POST` | `/world` | Create a simulated world |
| `GET` | `/world/{id}` | Read the current world state |
| `POST` | `/world/{id}/character` | Add an initial agent |
| `POST` | `/world/{id}/inject-character` | Add an agent during a run |
| `DELETE` | `/world/{id}/character/{agent_id}` | Remove an agent |
| `POST` | `/world/{id}/generate-fillers` | Generate additional agents |
| `POST` | `/world/{id}/event` | Set the initial event |
| `POST` | `/world/{id}/inject-event` | Queue a new event |
| `POST` | `/world/{id}/prophecy` | Record a user prediction |
| `POST` | `/world/{id}/simulate/stream` | Stream a simulation run |
| `POST` | `/world/{id}/simulate/continue/stream` | Continue an existing run |
| `GET` | `/world/{id}/result` | Read the latest measurements and forecast |
| `POST` | `/world/{id}/agent/{agent_id}/chat` | Interview an agent in character |
| `POST` | `/world/{id}/agent/{agent_id}/advise` | Add user advice to an agent's memory |
| `*` | `/saves`, `/saves/{id}`, `/saves/{id}/load` | Manage authenticated saved runs |

## Limitations

- The model has not been validated against longitudinal human interaction data.
- LLM outputs vary by provider, model version, prompt, and sampling behavior.
- Numeric thresholds and weights are modeling assumptions, not estimated human parameters.
- Relationship labels, influence, and confidence are simulation-specific constructs.
- The active world store is in memory; Supabase persistence is optional.
- The intended scale is tens of agents, not population-scale social forecasting.
- Mock-provider tests verify software behavior but do not establish real-LLM output quality.
- User interventions make a run path-dependent and should be reported in experimental results.

## Reference

[1] J. S. Park, J. C. O'Brien, C. J. Cai, M. R. Morris, P. Liang, and M. S. Bernstein,
“Generative Agents: Interactive Simulacra of Human Behavior,” *Proceedings of the 36th Annual ACM
Symposium on User Interface Software and Technology (UIST '23)*, 2023, pp. 1–22.
[doi:10.1145/3586183.3606763](https://doi.org/10.1145/3586183.3606763)

## Technical supplement

The research supplement contains the complete formulas for social metrics, stance aggregation,
memory retrieval, feed ranking, agent selection, relationship and influence updates, background
evolution, and forecast confidence:

**[Tiny Society AI: Calculations and Measurements (PDF)](./CALCULATIONS.pdf)**
