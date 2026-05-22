# Realism Analysis — Tiny Society AI vs. MiroFish

A comparison of this project against MiroFish and the canonical "Generative Agents"
realism recipe, plus a prioritized plan to close the gap.

---

## What MiroFish actually is

MiroFish ([github.com/666ghj/MiroFish](https://github.com/666ghj/MiroFish)) isn't doing
magic — it stands on three well-known pillars, and this project implements thin versions
of all three:

1. **GraphRAG world grounding** — parses seed material into an *entity-relationship
   knowledge graph* before any agent acts. Agents share a factual ground truth.
2. **Zep temporal memory** — persistent, time-aware memory that knows *what was true
   when*, retrieved by relevance, not recency.
3. **The OASIS engine** (CAMEL-AI) — agents take 23 distinct social actions (post,
   comment, follow, repost…) and **observe each other through a feed**. Realism emerges
   from interaction, not from a script.

The canonical realism recipe behind all of this is Stanford's *Generative Agents* paper
(Park et al., 2023): **observe → retrieve relevant memories → reflect → plan → act**.
That loop is what makes agents feel coherent over time.

---

## Why this sim feels less realistic

The architecture is solid (the `perception.py` subjective-interpretation layer is *better*
than vanilla generative agents — keep it). But measured against the recipe above, here are
the gaps, ranked by impact:

### 1. Memory is truncation, not retrieval
`reasoner.py:117` feeds `long_term_memory[-8:]` — the 8 *most recent* memories, regardless
of relevance to today's situation. Generative agents score every memory by
**relevance + recency + importance** and retrieve the top-k. An agent reasoning about a
rival should surface its memories *about that rival*, not whatever happened last Tuesday.
This is the single biggest realism lever.

### 2. No reflection
`engine.py:64-72` just promotes the last short-term memory to long-term. Agents never
*synthesize* — they never go from "I avoided three confrontations" to the belief "I'm
conflict-averse." Reflection is what produces self-consistent characters across 30 days.
`revealed_traits` is a seed of this, but it's reactive, not introspective.

### 3. Everyone sees everything
`full_event_log[-10:]` is a global feed — perfect information. Real societies run on
*asymmetry*: gossip, factions, who-knows-what. MiroFish's realism largely comes from
agents observing only their slice of the world. Per-agent observation queues would
generate emergent factions and misinformation for free.

### 4. Relationships collapse to one float
`Relationship(type, strength)` can't represent "I trust her on work but not personally."
MiroFish tracks *stances on topics* that shift through debate content. `strength_delta`
throws away the content of the interaction.

### 5. Goals are inert; no planning
Agents have `goals` strings that are never advanced or planned toward. Generative agents
form a daily plan from goals, then react. Without this, behavior is purely reactive
Brownian motion — no narrative arc.

### 6. Background agents are numeric drift
`deterministic.py` evolves most of the population by mechanical increments
(+0.02 friendship). At population 60 with 8 reasoning slots, ~85% of the society is on
rails — that reads as "mechanical" exactly where MiroFish reads as "alive."

---

## How to mirror the realism — prioritized

Tackle in order; the first two give the most realism per line of code.

### ✅ ①–③ IMPLEMENTED (verified end-to-end on the mock provider)

- **① Memory retrieval — DONE.** Added a `Memory` model (`text`, `importance` 1-10, `day`,
  `last_accessed_day`) and migrated `Agent.short_term_memory`/`long_term_memory` from
  `list[str]` to `list[Memory]`. New `simulation/memory.py` exposes
  `retrieve(memories, query, current_day, k)` scoring `relevance + recency + importance`
  (equal weights, each min-max normalized): relevance = stopword-filtered token overlap,
  recency = `0.85 ** (current_day − last_accessed_day)`, importance = stored/10. Importance
  is set by a cheap heuristic (`score_importance`) — no LLM call, mock-safe.
  `reasoner._build_prompt` now uses `retrieve(...)` keyed on the event + relationship names
  instead of the old `[-8:]` slice. *Verified: memories are `Memory` objects,
  `last_accessed_day` bumps on retrieval.*
- **② Reflection pass — DONE.** New `simulation/reflector.py` (`reflect(agent, current_day)`)
  runs every `REFLECT_EVERY_DAYS = 4` days for the day's selected agents, making one LLM
  call (system marker `REFLECTION_SYNTHESIS`, JSON `{"insights": [...]}`) to synthesize 1-3
  first-person realizations from retrieved memories. Insights are stored as high-importance
  (`9.0`) `Memory` objects so they dominate later retrieval. A matching `_mock` branch in
  `llm.py` keeps it key-free. *Verified: day-4 reflections fire with introspective content,
  e.g. "I keep ending up in conflict, and I'm starting to think I provoke it more than I
  admit."*
- **③ Observation locality — DONE.** Added `Agent.observations: list[str]` and
  `simulation/observation.py` (`witnesses`, `distribute_observation`, `OBSERVATION_WINDOW=15`,
  `PUBLIC_INFLUENCE_THRESHOLD=20.0`). Each action's log line is routed only to the actor,
  named targets, group-mates, and — if the actor's influence ≥ 20 — everyone (public).
  `reasoner._build_prompt`'s world-log section now reads the agent's own `observations[-8:]`
  ("WHAT YOU'VE OBSERVED") instead of the global log. The global `full_event_log` is kept
  for the selector summary, dynamic events, and the UI's `DaySnapshot.event_log`.
  *Verified: per-agent observation counts vary (e.g. 3→14), reflection still fires.*

### Still open

- **④ Goal-driven planning** — a lightweight daily intention per agent derived from its
  goal; let the selector prioritize agents whose plan is "due."
- **⑤ Multi-turn exchanges** — when two agents engage on a charged relationship, run a 2-4
  turn dialogue instead of one one-directional delta. Emergence lives in the back-and-forth.
- **⑥ World knowledge graph** — one upfront LLM call turning the world prompt into
  structured entities/facts injected into every prompt (a cheap GraphRAG equivalent).

**The trap to avoid:** don't just make the prompts longer. MiroFish's realism is
*architectural* — retrieval, reflection, and observation — not prose. With ①–③ now in
place, most of the perceived gap should be closed; ④–⑥ are incremental polish.

---

## Phase 2 — the Prediction Engine (what most makes it "MiroFish")

The biggest difference isn't a feature, it's **purpose**: MiroFish is a *prediction
engine*; this project is a *sandbox observer*. MiroFish's pipeline is seed doc + a
**prediction question** → simulate → **aggregate agent beliefs into a population
distribution** → forecast *with quantified uncertainty* (variance across agents), tracing
the causal chain of which events moved sentiment. This project has no question, no belief
state, and no aggregation. Adding them reuses existing machinery (`metrics.py`,
`reporter.py`).

New levers, ranked by "MiroFish-ness" (these are *beyond* ④–⑥ above):

1. **Prediction question + per-agent belief/stance.** A world carries a question; each
   `Agent` gets `stance: dict[topic -> float]` that shifts through interaction (same
   mechanic as relationship deltas). Foundation for everything else.
2. **Belief aggregation + uncertainty (upgrade `metrics.py`).** Each day aggregate stances
   into a distribution; report the mean as the forecast and the **variance as confidence**.
3. **Causal-chain reporting (upgrade `reporter.py`).** Find the days the distribution moved
   most, attribute them to specific interactions, emit forecast + causal trace. Mirrors
   MiroFish's ReportAgent.
4. **Recommendation-style feed (upgrade ③).** OASIS uses a RecSys (TwHIN-BERT, interest +
   "hot score"), not a global log. Ranking what each agent sees by interest-match + recency/
   engagement produces echo chambers, virality, and cascades.
5. **Real action space.** OASIS agents take **21 actions** (post, repost, comment, like,
   follow…). This project collapses everything into one verb + a relationship delta.
   Distinguishing broadcast vs. private vs. amplify is what makes influence emerge.
6. **Probabilistic, time-based activation (upgrade `selector.py`).** OASIS activates agents
   by hourly probability; this project deterministically picks top-N (same agents repeat).
7. **GraphRAG with power structures (⑥, richer).** Also extract hierarchy/who-controls-what.
8. **Scale + tiered models.** Batch LLM calls; cheap model for routine actions, strong model
   for pivotal ones. More *active* agents = richer dynamics.

Sequence: **#1 → #2 → #3** is one coherent vertical slice that turns the sandbox into a
predictor. **#4 + #5** are the OASIS social-media realism upgrade. **#6–#8** are scaling.

---

## Phase 3 — Engagement (the actual goal): MiroFish depth × Tomodachi Life charm

Realism is a *means*; the original goal is an engaging game. The synthesis:
**MiroFish makes agents deep and believable; Tomodachi Life makes the *player* attached and
delighted.** This project's LLM depth (rich memories, reflection, perception) is actually a
superpower *over* Tomodachi — its vignettes are scripted; ours can be genuinely novel and
personal. The job is to *surface* that depth as bite-sized, charming, surprising moments the
player cares about and can nudge.

Tomodachi's engagement DNA (and how to fuse it with the realism work):

- **Identity injection (its #1 hook).** Players make Miis of real people — themselves,
  friends. Seeing "your friend" fall in love or melt down is the hook. Add: create
  characters from real people (name + avatar + a few traits); the LLM depth makes them
  behave believably. *Builds on the existing custom-character flow.*
- **The check-in / notification loop.** Reframe the 30-day batch run into a **daily digest**:
  3–5 punchy vignettes ("Maya confessed to Theo", "Sam is spiraling about the scholarship").
  Bite-sized, ritual, notification-driven. *Builds on `DayHighlight` / the new dialogue feed.*
- **Player intervention as gameplay.** Let the player nudge — matchmake, drop an event/gift,
  whisper advice, take sides. Each nudge writes to agent memory/stance (ties to Phase 2
  belief state). Low-effort, high-meaning. *The `chat` endpoint is already a seed of this.*
- **Surprise & humor via the LLM.** Agents occasionally generate dreams, catchphrases, hot
  takes, dramatic announcements — theatrical vignette cards, not just relationship deltas.
  *The reflection step (②) can emit these.*
- **Prediction as a player-facing hook (the killer fusion).** Turn the Phase 2 prediction
  question into a **bet/prophecy** the player makes ("Will Maya and Theo end up together?").
  The swarm forecast + the actual outcome creates suspense and payoff. This fuses MiroFish's
  belief-aggregation with Tomodachi's emergent-drama investment.
- **Emotional stakes & attachment.** Relationship milestones; "someone you care about is in
  crisis" alerts; the social graph as a living thing you're invested in.
- **Charm & presentation.** Mood-driven expressions/avatars, the graph as a "town", vignette
  cards. *Builds on the existing D3 graph + pixel aesthetic.*
- **Progression / collection.** Milestones unlocked, memorable quotes saved, a "history book"
  of the town's saga.

**The unifying loop:** *check in → get delighted/surprised → nudge → make a prophecy →
watch the payoff.* Depth (MiroFish) feeds surprise; surprise feeds attachment; attachment
makes the prophecy matter; the nudge gives agency. That loop — not raw realism — is the
engagement engine.

---

## Sources

- [Generative Agents: Interactive Simulacra of Human Behavior (Park et al., 2023)](https://arxiv.org/abs/2304.03442)
- [MiroFish — GitHub (666ghj/MiroFish)](https://github.com/666ghj/MiroFish)
- [MiroFish: The Open-Source AI Engine That Builds Digital Worlds to Predict the Future (DEV)](https://dev.to/arshtechpro/mirofish-the-open-source-ai-engine-that-builds-digital-worlds-to-predict-the-future-ki8)
- [What is MiroFish? (blocmates)](https://www.blocmates.com/articles/what-is-mirofish-the-agent-engine-that-can-predict-anything-and-everything)
- [OASIS — CAMEL-AI (GitHub)](https://github.com/camel-ai/oasis) · [OASIS docs](https://docs.oasis.camel-ai.org/introduction)
- [CAMEL-AI Open-Sources OASIS — 1M-agent social simulator (MarkTechPost)](https://www.marktechpost.com/2024/12/27/camel-ai-open-sourced-oasis-a-next-generation-simulator-for-realistic-social-media-dynamics-with-one-million-agents/)
- [MiroFish: Multi-Agent Swarm Intelligence for Predictive Simulation (Medium)](https://medium.com/@balajibal/mirofish-multi-agent-swarm-intelligence-for-predictive-simulation-09771e60b188)
- [Tomodachi Life review — emergent storytelling & player investment (Eneba)](https://www.eneba.com/hub/games/tomodachi-life-review/)
