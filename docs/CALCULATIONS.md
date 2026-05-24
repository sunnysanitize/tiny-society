# Calculations & Measurements Reference

Every number the simulation computes — what it means, the exact formula, its range, and
where it lives in code. Use this to interpret the UI, tune behavior, or extend the engine.

> Conventions: relationship/stance strengths live in **[-1, 1]**; influence in **[-100, 100]**;
> importance in **[1, 10]**. "Day" = one simulated tick (morning→afternoon→evening→night).

---

## 1. Macro metrics (per day)
`simulation/metrics.py → compute_metrics()`, stored on `DaySnapshot.metrics` (`MacroMetrics`).

Relationships are stored on **both** agents (A→B and B→A), so undirected counts are halved.

| Measurement | Meaning | Formula | Range |
|---|---|---|---|
| `friendship_count` / `rivalry_count` / `conflict_count` / `romance_count` / `alliance_count` | How many relationships of each type exist | count of edges of that type **÷ 2** (de-duplicates the two directions) | ≥ 0 |
| `average_relationship_strength` | Overall intensity of bonds, regardless of sign | mean of **\|strength\|** over every relationship | 0–1 |
| `average_trust_score` | Average signed strength of `trust`-type edges only | mean of `strength` over trust edges (signed) | −1 to 1 |
| `most_connected` | The 3 most socially central characters | top-3 by number of outgoing relationships | names |
| `relationship_volatility` | How much churn happened today | count of relationship **type flips** this day (a delta ≥ 0.15 that changed an edge's type) | ≥ 0 |
| `social_fragmentation` | Fraction of the town that is isolated | `agents_with_zero_relationships ÷ total_agents` | 0–1 |
| `group_centrality` | Which groups bridge to outsiders most | per group, count of relationships to non-members; top 5 | counts |
| `influence_gainers` / `influence_losers` | Who rose / fell since Day 0 | top/bottom 3 by `influence_score − baseline_influence` (only if gain>0 / loss<0) | names |

`baseline_influence` is captured once at the start (`snapshot_influence()`), so gainers/losers
are measured against Day 0, not yesterday.

---

## 2. Swarm forecasting (belief aggregation)
`metrics.py` (per-day aggregation) + `simulation/reporter.py` (forecast assembly).

Each agent holds a `stance: dict[topic → float]` in [−1, 1]. The "swarm" view aggregates
those individual opinions into a population distribution per topic.

| Measurement | Meaning | Formula | Range |
|---|---|---|---|
| `topic_means[topic]` | Where the population **leans** on that axis | population **mean** of `agent.stance[topic]` | −1 to 1 |
| `topic_uncertainty[topic]` | How much the population **disagrees** | population **standard deviation** (`pstdev`) of the stances; 0 if only one agent holds it | ~0 to ~1 |
| `belief_confidence` ("swarm confidence") | How sure the swarm is overall | `1 − mean(topic_uncertainty over all topics)`, clamped to [0, 1] | 0–1 |

**Swarm confidence read-out:** `1.0` = total consensus (trust the forecast); `0.0` = the town
is maximally split (the forecast is a coin-flip). Tight agreement → high confidence; scattered
opinions → low confidence.

### Forecast object (`reporter.build_forecast`, on `SimulationResult.forecast`)
- `topic_means` / `topic_uncertainty` / `confidence` — copied from the **final day's** metrics.
- `pivotal_days` — the days the distribution moved most. **Drift** for a day = `Σ |Δ topic_mean|`
  across topics vs. the previous day (`_topic_drift`); days ranked by drift, top **3** kept
  (`MAX_PIVOTAL_DAYS`), drift > 0.
- `narrative` — prose from the single `FINAL_REPORT` LLM call, fed the belief trajectory +
  pivotal-day causal attributions.
- `question` — the player's prediction question (currently unwired; see `BACKLOG.md` ③).

---

## 3. Memory retrieval
`simulation/memory.py`. Replaces recency-only truncation with relevance-weighted recall
(Stanford "Generative Agents" style).

**Importance** (`score_importance`, assigned when a memory is created):
```
importance = 1.0
           + min(len(text) / 60, 4.0)            # detail: ~1 pt per 60 chars, cap 4
           + min(emotional_keyword_hits * 1.5, 5.0)   # emotional/relational loading, cap 5
→ clamped to [1, 10]
```
(Reflections override this to **9.0**; whisper-advice memories to **10.0**.)

**Retrieval** (`retrieve(memories, query, current_day, k=8)`): each candidate scored, top-k returned.
```
score = RELEVANCE_WEIGHT·relevance + RECENCY_WEIGHT·recency + IMPORTANCE_WEIGHT·importance
        (all weights = 1.0; each component min-max normalized across candidates first)

relevance = |query_tokens ∩ memory_tokens| / |query_tokens|     # stopword-filtered overlap, 0–1
recency   = 0.85 ^ (current_day − last_accessed_day)            # ~15%/day decay, (0, 1]
importance = stored_importance / 10                              # 0–1
```
Retrieved memories get `last_accessed_day = current_day` (recall refreshes recency).

---

## 4. Information feed (who sees what)
`simulation/observation.py`. Replaces a global event log with a per-agent ranked feed.

**Reach** (`witnesses`, by `action_kind`):
| action_kind | Who witnesses it |
|---|---|
| `post` | **everyone** (public broadcast) |
| `direct` | only the actor + named target(s) |
| `comment` / `interact` / `amplify` | actor + targets + group-mates, **plus everyone** if the actor's influence ≥ `PUBLIC_INFLUENCE_THRESHOLD` (20.0) |

`amplify` additionally injects a synthetic entry attributed to the amplified target into the
audience's feed (spreads the target's standing). Each agent's feed is capped at
`OBSERVATION_WINDOW` = **15** entries.

**Ranking** (`rank_feed(viewer, entries, k)`):
```
score = INTEREST_WEIGHT·interest + HOT_INFLUENCE_WEIGHT·influence + HOT_RECENCY_WEIGHT·recency
        (3.0)                      (1.0)                            (1.5)

interest  = |viewer_interest_tokens ∩ entry_tokens| / |viewer_interest_tokens|
            (interest tokens = traits + revealed traits + stance topics + relationship names + own name)
influence = entry.author_influence / max_author_influence_in_feed
recency   = 0.85 ^ (max_day − entry.day)
```
Interest dominates (weight 3) → feeds become **echo chambers**; influence + recency add virality.

---

## 5. Agent selection (who acts today)
`simulation/selector.py → select_reasoning_agents()`.

**Score** each agent, then **softmax-sample** `limit` distinct agents (not strict top-N — so the
active set varies day to day):
```
score  = 3.0  if any trait/goal/group/name token appears in today's event text  (event proximity)
       + 2.0 · (influence / max_influence)                                       (standing)
       + 1.5  if it holds a charged relationship (rivalry/romance/conflict, |strength| ≥ 0.3)
       + 0.5 · min(group_count, 3)                                               (connectedness)

P(select) = softmax(score / SOFTMAX_TEMPERATURE)   # temperature = 1.0; lower = sharper, higher = flatter
```
`reasoning_agents_per_day` defaults to **8** (1–30). If `limit ≥ population`, everyone acts.

---

## 6. Relationship dynamics
`simulation/applicator.py → _update_relationship()`. An action proposes per-target
`{type, strength_delta}` (the LLM is told to keep deltas modest, −0.4..+0.4).

- **New edge:** created at `strength = clamp(delta, −1, 1)` → counts as a type change.
- **Same type:** `strength = clamp(strength + delta, −1, 1)`.
- **Different type — flip rule:** if `|delta| ≥ 0.15`, the edge **flips** to the new type at the
  new strength (and counts toward `relationship_volatility`). If `|delta| < 0.15`, no flip;
  instead `strength += delta · 0.5` (the dampened "erosion" of the old bond).

The **actor's** side is applied directly (their intent); the **target's** side is routed through
the perception layer (§8) first.

---

## 7. Influence
`applicator.py`. Actions carry `influence_effects: {self: Δ, TargetName: Δ}`.
- Each delta is clamped to **[−10, 10]**; the resulting score is clamped to **[−100, 100]**.
- `amplify` grants the amplified target a fixed **+2.0** (`AMPLIFY_INFLUENCE_BOOST`).
- Influence feeds: selection scoring (§5), feed hot-score (§4), and the public-figure threshold (§4).

---

## 8. Perception (subjective interpretation)
`simulation/perception.py → perceive_event()`. When another character acts on you, the raw
`strength_delta` is reinterpreted through your personality before it lands.
- Fires only when the event is **significant** (|raw_delta| ≥ 0.05 **and** you have a prior
  relationship with, or a memory mentioning, the actor) — otherwise the raw delta applies as-is.
- An LLM call returns `perceived_delta` (clamped [−1, 1]) — which may amplify or dampen the raw
  signal (a kind gesture from someone you distrust lands weakly; a blunt act from a respected
  rival can land positively) — plus a narrative note and an optional newly-`revealed_trait`
  (fed back into the agent, capped at 10).

---

## 9. Stance shift
`reasoner.py` parses an optional `stance_shift: {topic → Δ}` from each action; `applicator.py`
applies it to the **actor's** stance, clamped per-topic to **[−1, 1]**. The LLM is instructed to
only shift topics it actually engaged with, magnitudes **−0.3..0.3**.

---

## 10. Deterministic background rules
`simulation/deterministic.py`. Cheap, no-LLM evolution for agents NOT selected to reason that day.
- **Social-trait agents** (social/charismatic/loyal/patient): friendships drift **+0.02/day**
  (cap 1.0); their rivalries cool **−0.015/day** (floor 0).
- **Isolating-trait agents** (introverted/anxious/lonely) with no relationships: influence
  drifts **−0.1/day** (floor −10).
- **Shared-group trust drip:** for each co-group pair, with **8%** probability per day, both gain
  **+0.01** trust toward each other.
- **Rivalry decay:** any rivalry erodes **−0.005/day** without reinforcement.

---

## 11. Cadence & cap constants (tuning knobs)
| Constant | Value | Where | Effect |
|---|---|---|---|
| `reasoning_agents_per_day` | 8 (1–30) | `SimulationConfig` | LLM-reasoning agents per day |
| `REFLECT_EVERY_DAYS` | 4 | `engine.py` | Selected agents synthesize reflections every N days |
| `PLAN_REFRESH_DAYS` | 3 | `engine.py` | A plan refreshes if older than N days |
| `MAX_EXCHANGE_TURNS` | 2 | `engine.py` | Extra back-and-forth turns per charged interaction |
| `MAX_EXCHANGES_PER_DAY` | 3 | `engine.py` | Charged-exchange chains per day |
| Multi-turn trigger | type ∈ {rivalry,romance,conflict} or \|strength\|≥0.4, or a charged effect with \|delta\|≥0.2 | `engine.py _is_charged` | When a response exchange fires |
| `MAX_VIGNETTES_PER_DAY` | 2 | `engine.py` | Theatrical vignettes per day (≈70% gated) |
| Dynamic event cadence | every 5 days, after day 3 | `engine.py` | Auto-generated mid-run events |
| Starting event lifespan | days 1–3 | `engine.py` | How long the initial event stays "active" |
| `OBSERVATION_WINDOW` | 15 | `observation.py` | Feed entries retained per agent |
| `PUBLIC_INFLUENCE_THRESHOLD` | 20.0 | `observation.py` | Influence at which actions go public |
| `SOFTMAX_TEMPERATURE` | 1.0 | `selector.py` | Selection randomness (↑ = more variety) |
| `RECENCY_DECAY` | 0.85 | `memory.py`, `observation.py` | Per-day recency decay |
| Reflection / advice importance | 9.0 / 10.0 | `reflector.py`, `main.py` | Forced high importance so they dominate recall |
| `BATCH_SIZE` | 3 | `generator.py` | Filler agents generated per LLM call (small batches avoid output-token truncation) |
| `MAX_PIVOTAL_DAYS` | 3 | `reporter.py` | Pivotal days surfaced in the forecast |
| `LLM_MAX_CONCURRENCY` | 6 (env) | `llm.py` | Max simultaneous LLM calls in the day's reasoning fan-out |

---

## 12. Execution model (performance)
Not a "calculation," but it affects how the per-day numbers above are produced.
- **Concurrent reasoning.** Each day, the selected agents' plan+reason LLM calls fan out
  concurrently (`asyncio.gather`, bounded by `LLM_MAX_CONCURRENCY`), then results are **applied
  sequentially in selection order** so relationship/influence/stance mutations stay deterministic.
  Multi-turn exchanges remain serial (each turn depends on the prior turn's applied state). The
  old per-agent `LLM_CALL_DELAY_SECS` sleep was retired — the semaphore bounds the rate instead.
- **Tiered models.** Each call site requests a `tier`: routine reasoning, vignettes, fillers,
  planning, and dynamic events use `cheap`; reflection, world-graph extraction, prophecy grading,
  the final report, and player chat use `strong`. Model names resolve from `*_MODEL_CHEAP` /
  `*_MODEL_STRONG`, falling back to the single `*_MODEL` var. None of this changes the formulas
  above — only which model produces the structured output they consume.

---

## 13. Quick glossary
- **Stance** — an agent's opinion on a topic axis, [−1, 1].
- **Topic** — a stance axis the society divides on, extracted from the world prompt/question.
- **Belief mean / uncertainty** — population average / disagreement on a topic.
- **Swarm confidence** — `1 − average disagreement`; how sure the crowd is.
- **Pivotal day** — a day the aggregate opinion moved the most.
- **Charged interaction** — a rivalry/romance/conflict or strong-strength exchange that triggers a back-and-forth.
- **Public figure** — an agent whose influence ≥ 20, so their actions reach everyone.
