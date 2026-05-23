# Tiny Society AI — Multi-Agent Social Simulation

> A MiroFish-inspired multi-agent social simulation platform where fictional AI agents reason about their world, make context-aware decisions, and generate emergent social dynamics over 30 simulated days.

---

> ## ⚠️ Status: this is the original MVP design doc (historical)
>
> The project has since shipped **well beyond** this MVP scope. Several things listed below as
> *"future"* or *"MVP does not include"* are now built: persistent **Supabase** saves + **auth**,
> **mid-simulation injected events** *and* **mid-run character injection**, a **scrubbable
> timeline**, **per-agent/per-day LLM narration** (vignettes + story chapters), and a full
> **prediction engine** (per-agent belief stances → population forecast with swarm confidence →
> prophecy grading) that didn't exist in this plan at all. The engine also added
> **relevance-based memory retrieval, reflection, observation locality, goal-driven planning,
> multi-turn exchanges, a world knowledge graph, concurrent LLM inference, and tiered models.**
>
> For the **current state**, read:
> - **[README.md](./README.md)** — what the project is and does today.
> - **[REALISM_ANALYSIS.md](./REALISM_ANALYSIS.md)** — the realism roadmap and what's implemented.
> - **[CALCULATIONS.md](./CALCULATIONS.md)** — every metric and formula.
> - **[PERFORMANCE_AND_LIVE_EDITING.md](./PERFORMANCE_AND_LIVE_EDITING.md)** — concurrency, tiered models, mid-run injection.
> - **[BACKLOG.md](./BACKLOG.md)** — what's still open.
>
> The text below is preserved as the original design intent.

---

## Project Overview

Tiny Society AI is an agent-based social simulation platform. The user defines a fictional world, populates it with characters, injects a starting event, and runs a multi-day simulation. Each day, agents reason about their situation and choose actions. Relationships shift — friendships form, rivalries emerge, romances develop. After the simulation ends, a macro report summarizes how the society changed over the full period.

This is not a game clone. It is an **AI systems and social dynamics project** built to demonstrate agent reasoning, structured output, graph modeling, and multi-day state tracking.

---

## Core Differentiator: AI Agent Reasoning

**Traditional life sims select character moments from a fixed library of predetermined event templates.** The character pool is static, and outcomes are constrained by what the developers scripted in advance.

**Tiny Society AI is different.** Each important character uses AI reasoning to make context-aware decisions based on their own personality, memories, goals, relationships, and the current event. The simulation then measures how those individual decisions accumulate into macro-level changes in the relationship graph.

This means:
- No two simulations of the same world produce the same outcome
- Characters with different traits react differently to the same event
- Social dynamics emerge from agent decisions — they are not authored in advance
- The system can explain *why* a relationship changed, not just *that* it changed

---

## MiroFish-Inspired Architecture

The project follows the MiroFish-inspired pattern:

```
world seed → agent personas → relationship graph → interaction rounds → memory updates → event logs → macro report
```

The MVP implements a smaller custom version of this:

```
world prompt → custom/generated agents → user-injected event → AI-assisted agent decisions → structured state updates → graph metrics → final report
```

MiroFish's core insight — that a seed description can be turned into a live agent graph that simulates, remembers, and reports — is the conceptual foundation. The MVP does **not** directly integrate MiroFish. A future release may include an optional MiroFish adapter for more sophisticated multi-round reasoning.

---

## Hybrid Simulation Architecture

The MVP uses a **hybrid architecture**: AI reasoning for important agents, deterministic rules for background agents. This keeps the simulation meaningful without making an LLM call for every agent every day.

### 1. AI Agent Reasoning Layer

Each important agent receives a context prompt containing:

```
- Name, role, traits, goals
- Current mood
- Active memories (short-term and long-term)
- Current relationships and their strengths
- Group memberships
- The active world event
- Recent event log entries
```

The agent uses this context to choose an intention and action for the day.

### 2. Structured Output Contract

The AI does not freely rewrite world state. It returns structured JSON that the simulation engine validates before applying:

```json
{
  "action": "confront",
  "target_agents": ["Aria"],
  "emotional_reaction": "frustrated",
  "relationship_effects": {
    "Aria": { "type": "rivalry", "strength_delta": +0.2 }
  },
  "influence_effects": {
    "self": +3,
    "Aria": -2
  },
  "new_memory": "Mika confronted Aria publicly over the club selections. It did not go well.",
  "explanation": "Mika is ambitious and easily annoyed. After being passed over for the club, she chose to confront the person she sees as a rival rather than withdraw."
}
```

The simulation engine applies this output to:
- Agent memories (short-term and long-term)
- Moods
- Relationship types and strengths
- Romance / friendship / rivalry / trust / conflict states
- Influence scores
- Per-day event logs
- Macro metrics

### 3. Background Deterministic Rules

For agents not selected for AI reasoning, the simulation uses lightweight deterministic rules:

- Social agents passively strengthen existing friendships
- Isolated agents drift further if no interaction occurs
- Group members exchange minor trust increments on shared-event days
- Rivalry strength decays slightly without reinforcing events

**Agents selected for AI reasoning each day:**
- Agents directly affected by the user-injected event
- The top N agents by current influence score
- Agents with an active rivalry, romance, or conflict
- Agents connected to multiple important groups

This means the most socially active and narratively interesting characters drive the simulation, while the rest evolve plausibly in the background.

---

## MVP Scope

The MVP is a locally-run simulation. LLM calls are made only for selected agent decisions and the final report — not for every agent every day.

### Main flow

```
Create world
  → Add custom characters (manual)
  → Auto-generate remaining agents to reach target population (20–30 total)
  → Build initial relationship network
  → Inject starting event
  → Choose simulation length (7-day quick mode or 30-day default)
  → Run daily ticks for each simulated day:
      Morning  → update moods and goals
      Afternoon → selected agents reason via AI; background agents run deterministic rules
      Evening  → apply structured JSON outputs; update all relationship and influence states
      Night    → write memories; finalize event log; save graph snapshot
  → Show timeline, character memory panels, macro metrics, and final report
```

### Simulation length

| Mode | Days | Purpose |
|---|---|---|
| Quick mode | 7 days | Fast preview, early testing |
| MVP default | 30 days | Full simulation arc |
| Future: semester | 90 days | Extended social dynamics |
| Future: year | 365 days | Long-arc compressed simulation |

### Character creation

**1. Manual custom characters** — defined by the user before simulation:
- Name, role, traits, goals, starting mood
- Group memberships
- Optional starting memories
- Optional starting relationships with other named characters

**2. Auto-generated filler agents** — filled in by the system to reach target population size, based on the world prompt context.

Both types are treated identically by the simulation engine.

**MVP includes:**
- One fictional world (text prompt)
- Manual custom character creation + auto-generated filler agents (20–30 total)
- Initial relationship network
- One user-injected starting event
- 7-day or 30-day simulation
- Hybrid daily tick loop (AI reasoning for selected agents, deterministic rules for background agents)
- Structured JSON output contract validated before state application
- Per-day event logs and graph snapshots stored in memory
- Updated agent states per day: moods, memories, relationships, influence scores
- Day-by-day timeline view with daily highlights
- Character memory and history panels
- Before/after macro metrics (Day 0 vs. final day)
- Final simulation report (LLM-generated)
- Static relationship graph view (snapshot per day)

**MVP does not include:**
- Authentication or payments
- Persistent database
- Direct MiroFish integration
- Backboard.io memory adapter
- AI reasoning for every agent every day
- Animated graph transitions or heatmaps
- Scrubbable timeline replay
- Additional user-injected events mid-simulation
- Character import/export or saved presets
- Semester or year-long simulation modes
- Production deployment

---

## Technical Architecture

```
Next.js frontend (React + Tailwind)
        ↓
FastAPI backend (Python)
        ↓
Hybrid simulation engine
  - agent selector (who gets AI reasoning today)
  - AI reasoning caller → structured JSON output
  - JSON validator + state applicator
  - deterministic rule engine (background agents)
  - per-day event log builder
  - graph snapshot store
  - macro metrics calculator
  - final report generator (LLM call)
        ↓
In-memory store (MVP) → Postgres / Supabase (future)
        ↓
Timeline + relationship graph + final report (frontend)
```

**Stack:**
- **Frontend**: Next.js + Tailwind CSS
- **Backend**: FastAPI (Python)
- **Graph visualization**: React Flow or D3.js (static snapshots per day)
- **LLM**: Anthropic Claude API (agent reasoning + final report)
- **Database**: In-memory for MVP; Supabase/Postgres in future

---

## Data Model

Each agent carries this internal state:

```json
{
  "id": "agent_001",
  "name": "Mika",
  "age_group": "student",
  "traits": ["ambitious", "social", "easily annoyed"],
  "goals": ["become club president", "make close friends"],
  "mood": "frustrated",
  "influence_score": 42,
  "groups": ["Cooking Club", "Dorm B"],
  "relationships": {
    "Leo": { "type": "friendship", "strength": 0.7 },
    "Aria": { "type": "rivalry", "strength": 0.5 }
  },
  "short_term_memory": [
    "Mika felt ignored at the club meeting on Day 1."
  ],
  "long_term_memory": [
    "Mika was rejected from the elite club in Week 1."
  ]
}
```

**Relationship types:**
- `friendship` / `rivalry` / `romance` / `trust`
- `influence` / `alliance` / `conflict` / `group_membership`

All relationships are between fictional agents only. Romance is one component of the broader social graph.

---

## Memory System

Memory is implemented locally within the app session — no external memory service in the MVP.

**Each agent has:**
- **Short-term memory**: events from the current simulated day (used as context for that day's AI reasoning; reset each morning)
- **Long-term memory**: important events flagged during the night tick (persists across all days; included in future AI reasoning prompts)
- **Relationship history**: notable interactions per relationship pair, accumulated across the full simulation

Memory entries are what allow the AI reasoning layer to produce context-aware decisions — an agent with a long-term memory of being betrayed by another will reason differently about interacting with them than one with a positive history.

**Future upgrade**: Backboard.io could replace the local memory arrays for cross-session persistent agent memory in longer or recurring simulations.

---

## Macro Metrics

Computed after each day and summarized in the final report:

| Metric | Description |
|---|---|
| Friendship count | Total active friendship edges |
| Rivalry / conflict count | Total active rivalry or conflict edges |
| Romance count | Total active romance edges |
| Average relationship strength | Mean edge weight across all relationships |
| Average trust score | Mean trust value across all agent pairs |
| Influence gainers / losers | Agents whose influence score changed most |
| Most connected agents | Agents with the highest edge count |
| Relationship volatility | Relationship type changes per day |
| Social fragmentation score | Ratio of isolated agents to total agents |
| Group centrality | Groups with the most cross-group connections |

---

## Visualizations

### MVP
- Static relationship graph snapshots (one per day, navigable via timeline)
- Day-by-day timeline with daily highlights
- Character memory and history panels (scrollable per agent)
- Macro metrics panel (Day 0 vs. final day comparison)
- Final simulation report (LLM-generated)

### Future
- Animated relationship graph (real-time transitions between days)
- Influence heatmap overlay (cool → warm gradient by influence score)
- Cluster / group bubble view
- Scrubbable event timeline with graph replay
- Character detail drawer (mood, goals, memory log, relationship bars)
- Daily newspaper-style feed (AI headlines per day, tagged by category)
- World stats dashboard with trust score line chart
- Weekly and monthly intermediate summary reports

---

## Example Simulation

**World prompt**: A small fictional university island with students, clubs, dorms, and rival friend groups.

**Event injected**: "A new AI entrepreneurship club launches with only 12 spots."

**Day 1 AI reasoning output (Mika):**
> Mika is ambitious and easily annoyed. She was passed over for the club. She chooses to confront Aria, who she sees as responsible. Rivalry with Aria increases. Influence +3. New memory: "Mika confronted Aria publicly — it drew attention but not sympathy."

**Day 7:** A previously low-influence student organized an alternative club and entered the top 5 by influence score. The original club's average trust score has been declining.

**Day 30 Final Report:**
- Two factions consolidated: original club vs. alternative club.
- The alternative club surpassed the original in average trust score by Day 22.
- Four romances developed — three within the same faction, one cross-faction.
- The most isolated agent at Day 1 became the 4th most connected by Day 30 after bridging both groups.
- Average friendship strength increased 34%. Average rivalry strength increased 19%.

---

## Future Features

- 90-day semester and 365-day year-long simulation modes
- Mid-simulation user-injected events (beyond the starting event)
- Weekly and monthly intermediate summary reports
- LLM narration per agent and per day
- AI reasoning for all agents (not just selected ones)
- Optional MiroFish adapter for advanced multi-round agent reasoning
- Optional Backboard.io adapter for cross-session persistent memory
- Postgres / Supabase database backend
- Authentication and saved worlds
- All advanced visualizations listed above
- Character import/export (JSON), saved presets, reusable archetype templates
- Production deployment

---

## Important Constraints

- All agents are fictional — no simulating real people
- No Nintendo branding, Mii references, or game-clone framing
- Romance is one relationship type among many — not the focus
- AI reasoning is used selectively — not for every agent every day in the MVP
- Memory uses local arrays in the MVP — no Backboard.io, no external memory service
- MiroFish is not directly integrated in the MVP
- Tone: AI systems project and social science lab, not casual game

---

## Portfolio Value

This project demonstrates:
- **AI agent reasoning** — context-aware decisions from personality, memory, goals, and relationships
- **Structured LLM output** — agents return validated JSON; the engine applies it — LLM does not freely mutate state
- **Hybrid simulation design** — AI for selected agents, deterministic rules for background agents
- **Graph / network modeling** — eight relationship types, edge weights, evolving social graph over 30 days
- **Multi-day state tracking** — per-day snapshots, long-term memory, compounding social dynamics
- **Backend orchestration** — FastAPI engine, agent selector, JSON validator, state applicator
- **Frontend data visualization** — React Flow / D3.js graph, timeline, macro metrics panel
- **Simulation design thinking** — explainable loop, scoped MVP, emergent outcomes from agent decisions

---

## Resume Description

- **Tiny Society AI** — Built a multi-agent AI social simulation in Next.js and FastAPI where 20–30 fictional agents use LLM reasoning to make context-aware decisions based on their traits, memories, goals, and relationships, then return structured JSON that a simulation engine validates and applies to update a social relationship graph over 30 simulated days.
- Designed a hybrid simulation architecture that selects the most narratively relevant agents for AI reasoning each day (based on influence, active conflicts, and event proximity) while running lightweight deterministic rules for background agents — balancing simulation depth with performance.
- Implemented a structured output contract between the LLM reasoning layer and the simulation engine, preventing free-form world mutation while enabling emergent social dynamics across eight relationship types (friendship, rivalry, romance, trust, influence, alliance, conflict, group membership), visualized with React Flow and summarized via a final Claude API-generated macro report.
