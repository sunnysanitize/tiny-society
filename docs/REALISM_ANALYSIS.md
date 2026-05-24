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

### ✅ ④–⑥ IMPLEMENTED (verified end-to-end on the mock provider)

- **✅ ④ Goal-driven planning — DONE.** `simulation/planner.py` (`form_plan`, marker
  `PLAN_FORMATION`, `PLAN_REFRESH_DAYS`) gives each selected agent a `Agent.plan` /
  `Agent.plan_day` short-term intention, refreshed when stale and injected into the reasoning
  prompt ("YOUR CURRENT PLAN"). *Verified: agents carry plans that bias their actions.*
- **✅ ⑤ Multi-turn exchanges — DONE.** `engine.py` runs a charged-interaction back-and-forth
  (rivalry/romance/conflict or |strength|≥0.4), capped by `MAX_EXCHANGE_TURNS=2` and
  `MAX_EXCHANGES_PER_DAY=3`; response turns reuse `apply_action` + `distribute_observation`.
  *Verified: days show more highlights than the selected count (exchanges fired).*
- **✅ ⑥ World knowledge graph — DONE** (see Phase 2 #7) — `simulation/worldgraph.py` extracts
  entities/relationships/power-structures/topics, injected as a "WORLD FACTS & POWER
  STRUCTURE" prompt section.

**The trap to avoid:** don't just make the prompts longer. MiroFish's realism is
*architectural* — retrieval, reflection, and observation — not prose. With ①–⑥ now in
place, the Phase-1 gap is closed.

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

1. **✅ DONE — Prediction question + per-agent belief/stance.** `World.question` +
   `Agent.stance: dict[topic->float]` (seeded by `simulation/stance.py`), shifted via
   `AgentAction.stance_shift` in `applicator.py`. Foundation for everything else.
2. **✅ DONE — Belief aggregation + uncertainty (`metrics.py`).** `MacroMetrics.topic_means`
   / `topic_uncertainty` / `belief_confidence` computed per day (mean = leaning, spread =
   disagreement = low confidence).
3. **✅ DONE — Causal-chain reporting (`reporter.py`).** `build_forecast` finds pivotal days
   (largest day-over-day distribution shift), attributes them to events/highlights, and emits
   `SimulationResult.forecast` (`Forecast`: means/uncertainty/confidence/pivotal_days/narrative).
4. **✅ DONE — Recommendation-style feed (upgrade ③).** `observation.rank_feed` ranks each
   agent's `Agent.feed` (`FeedEntry`) by interest-match + author influence + recency. (Uses
   token-overlap interest, not TwHIN-BERT embeddings — sufficient for echo-chamber dynamics.)
5. **✅ DONE — Real action space.** `AgentAction.action_kind` ∈ {post, direct, amplify,
   comment, interact}; reach + side-effects routed in `observation.py`/`applicator.py`
   (post=everyone, direct=target only, amplify=boost+spread, etc.).
6. **✅ DONE — Probabilistic activation (`selector.py`).** `select_reasoning_agents(..., rng)`
   now softmax-samples the active set, so high-scorers are likely but not guaranteed daily.
7. **✅ DONE — GraphRAG with power structures (⑥, richer).** `simulation/worldgraph.py`
   (`extract_world_graph`, marker `WORLD_GRAPH_EXTRACTION`) extracts entities, relationships,
   `power_structures`, and `topics`.
8. **◧ MOSTLY DONE — Scale + tiered models.** Built: **concurrent LLM inference** (the day's
   reasoning fan-out runs via `asyncio.gather` bounded by `LLM_MAX_CONCURRENCY`, applied
   sequentially for determinism — replacing the old serial-with-sleep loop) and **tiered models**
   (`tier="cheap"|"strong"` routing routine turns to a cheap model, pivotal/structural/player-facing
   turns to a strong one). *Not built:* true 1M-agent distributed scale (Environment Server +
   clustered inferencer) — premature at tens of characters. See
   [PERFORMANCE_AND_LIVE_EDITING.md](./PERFORMANCE_AND_LIVE_EDITING.md).

Sequence (as executed): **#1 → #2 → #3** turned the sandbox into a predictor; **#4 + #5**
added OASIS-style social mechanics; **#6/#7** done; **#8** concurrency + tiered models done,
distributed 1M-scale intentionally skipped.

---

## Phase 3 — Engagement (the actual goal): MiroFish depth × Tomodachi Life charm

Realism is a *means*; the original goal is an engaging game. The synthesis:
**MiroFish makes agents deep and believable; Tomodachi Life makes the *player* attached and
delighted.** This project's LLM depth (rich memories, reflection, perception) is actually a
superpower *over* Tomodachi — its vignettes are scripted; ours can be genuinely novel and
personal. The job is to *surface* that depth as bite-sized, charming, surprising moments the
player cares about and can nudge.

Tomodachi's engagement DNA (and how to fuse it with the realism work):

- **✅ DONE — Identity injection (its #1 hook).** `Agent.avatar` (emoji/pixel picker in
  `CharacterEditor`) + `Agent.based_on` ("based on a real person"); avatars render on graph
  nodes and the inspector. The LLM depth makes them behave believably.
- **✅ DONE — The check-in / digest feed.** `DaySnapshot.vignettes` + `simulation/digest.py`
  (`build_digest`) surface punchy day cards; the frontend renders a vignette/digest feed
  beside the persistent dialogue feed.
- **◧ PARTIAL — Player intervention as gameplay.** Built: **whisper advice**
  (`POST /agent/{id}/advise` → high-importance memory), **inject event**
  (`POST /inject-event` → `World.pending_event`, consumed next day), and **mid-run character
  injection** — `POST /world/{id}/inject-character` adds a newcomer initialized for the *current*
  day (stance on existing topics, day-stamped memories, arrival beat), surfaced as an "Add
  character" panel in the continue controls; the newcomer's stance + new graph node shift the
  belief aggregation, so an arrival can move the forecast and the prophecy verdict. A Level-2
  `pause_on_days` lets a run stop on a chosen day to inject before resuming. *Not built:*
  matchmake, take-sides/gift (deliberately out of scope per design choice).
- **✅ DONE — Surprise & humor via the LLM.** `simulation/vignette.py` (marker
  `VIGNETTE_GENERATION`) emits dreams / catchphrases / dramatic announcements, capped at
  `MAX_VIGNETTES_PER_DAY=2`.
- **✅ DONE — Prediction as a player-facing hook (the killer fusion).** `World.prophecy`
  (free-text), graded by `simulation/prophecy.py` (marker `PROPHECY_GRADING`) into
  `SimulationResult.prophecy_verdict`; the live `Forecast` is shown alongside. Frontend has
  the prophecy input, forecast panel, and verdict payoff card.
- **☐ NOT BUILT — Emotional stakes & attachment.** Relationship milestones; "someone you care
  about is in crisis" alerts. (Future.)
- **◧ PARTIAL — Charm & presentation.** Avatars + vignette cards done; the graph-as-a-"town"
  framing not done. *Builds on the existing D3 graph + pixel aesthetic.*
- **☐ NOT BUILT — Progression / collection.** Milestones unlocked, memorable quotes saved, a
  "history book" of the town's saga. (Future.)

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
