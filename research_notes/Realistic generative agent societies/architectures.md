# Architectures for believable LLM-driven generative agent simulations

Scope: which architectural choices measurably improved believability or realism, and what transfers to Tiny Society (5–7 agents, 7 simulated days, story plus report output). Research date: 2026-11-16. Concordia mechanisms were read directly from the google-deepmind/concordia `main` branch source code. Other claims come from the papers' arXiv HTML. Where only a figure (not text) holds a number, that is noted.

## Q1. Park et al. 2023 "Generative Agents": which components mattered in the ablations, and what failures did they report?

### Takeaway
In the controlled ablation, every component added believability. The full architecture beat every ablation, and removing observation, reflection and planning dropped agents below human crowdworkers. But the field deployment showed the same failures Tiny Society has: memories exist but aren't retrieved, agents invent embellishments, and information spreads to only a third to half of the town over 2 game days.

### Cited Findings
- **Paper:** Park et al., "Generative Agents: Interactive Simulacra of Human Behavior" (arXiv 2304.03442, April 2023; UIST 2023). — [arXiv](https://arxiv.org/html/2304.03442)
- **Ablation design:** agents were interviewed and responses ranked for believability, scored with TrueSkill (μ, σ).
  - Full architecture: μ = 29.89 (σ 0.72)
  - No reflection: 26.88 (0.69)
  - No reflection, no planning: 25.64 (0.68)
  - Human crowdworkers role-playing the agents: 22.95 (0.69)
  - No observation, reflection or planning (the "prior work" baseline): 21.21 (0.70)
  — [arXiv](https://arxiv.org/html/2304.03442)
- **Statistics:** Kruskal-Wallis H(4) = 150.29, p < 0.001. Dunn post-hoc tests with Holm-Bonferroni correction found every pairwise difference significant (p < 0.001) except crowdworkers vs. the fully ablated baseline. Full architecture vs. prior-work baseline: Cohen's d = 8.16. — [arXiv](https://arxiv.org/html/2304.03442)
- **Retrieval mechanism:**
  - Score = recency + importance + relevance, each min-max normalized to [0,1], all weights α = 1.
  - Recency: exponential decay of 0.995 per game hour since the memory was last retrieved.
  - Importance: LLM-rated 1–10 when the memory is created.
  - Relevance: embedding cosine similarity.
  — [arXiv](https://arxiv.org/html/2304.03442)
- **Reflection:** triggers when the summed importance of recent events exceeds 150 (about 2–3 times per game day). The 100 most recent memories generate salient questions, those questions drive retrieval, and insights are written with cited evidence pointers. Reflections can build on reflections, forming trees. — [arXiv](https://arxiv.org/html/2304.03442)
- **Planning:**
  - The agent first sketches the day in 5–8 broad chunks, then recursively decomposes them into hour-long and then 5–15-minute actions.
  - Plans carry location, start time and duration, and are stored in the memory stream.
  - Agents react to observations and regenerate the plan from that point.
  — [arXiv](https://arxiv.org/html/2304.03442)
- **Information diffusion over 2 game days, 25 agents:**
  - Sam's mayoral candidacy: known by 1 agent (4%) at the start, 8 (32%) at the end.
  - Isabella's Valentine's party: 1 (4%) → 13 (52%).
  - Network density rose from 0.167 to 0.74.
  - Of 12 invited agents, 5 attended the party.
  — [arXiv](https://arxiv.org/html/2304.03442)
- **Reported failure modes** — [arXiv](https://arxiv.org/html/2304.03442)
  - (a) Retrieval failures. Rajiv said "I haven't been following the election too closely" despite having heard about Sam's candidacy. Tom recalled the party plan but not that the party existed.
  - (b) Hallucinated embellishment. Isabella claimed Sam "is going to make an announcement tomorrow," which was never discussed.
  - (c) World-knowledge leakage. A neighbor named Adam Smith was credited with *Wealth of Nations*.
  - (d) Overly formal and cooperative speech, attributed to instruction tuning.
  - (e) Location and physical-norm errors, such as lunch at a bar or crowding a single-occupancy bathroom.
  - (f) Hallucinated awareness of other agents in 6 of 453 responses (1.3%).

### Inferences
- Reflection gave the largest single increment (about 3 μ points) and planning the next (about 1.2). Both are the components Tiny Society already has. The ablation never tested retrieval-scoring variants, so it does not show that embedding relevance itself matters. That is consistent with Tiny Society finding no gain from embeddings.
- Even the reference architecture spreads information slowly: 32–52% of the town over 2 days with 25 agents and many conversations. If information spreads only through agent choice, a small cast with few interactions per day will look under-propagated. Some deterministic routing of "who heard/observed" is needed (see Concordia below).
- Failure (b), embellishment, is the "acting on facts they couldn't know" problem. The paper offered no architectural fix.

### Gaps
- Park et al. did not ablate retrieval weights or the embedding choice, and did not measure believability over long horizons. The ablation is based on interviews, not on emergent plot quality.

## Q2. Successors and alternatives: architectural ideas and evidence

### Takeaway
Measured gains come mainly from four things:
- Explicit internal-state variables (needs, emotion, closeness) that verifiably steer behavior.
- Memory consolidation and self-monitoring summaries, which ablate to "dramatic" drops in Lyfe Agents.
- A coherence bottleneck that keeps speech and action consistent (PIANO).
- Social-awareness modules that produce more accurate and differentiated relationships (PIANO).

Large-scale platforms (AgentSociety, OASIS) mostly validate against macro-level real-world data rather than ablating believability.

### Cited Findings
**Humanoid Agents** (Wang et al., arXiv 2310.05418, 9 October 2023; EMNLP 2023 Demos) — [arXiv HTML](https://arxiv.org/html/2310.05418)
- **Mechanisms:** System-1-style state variables of basic needs (fullness, social, fun, health, energy), emotion, and per-relationship closeness.
  - Each need has a set likelihood of dropping by 1 over time, at fixed rates. For example, fullness and health drop 1 per 5 hours.
  - Plans are revised when emotion is non-neutral or any need is at or below 3.
  - Closeness adapts conversations.
- **Evaluation against human annotation of one simulated day (κ / micro-F1):**
  - Fullness 0.972 / 0.972
  - Energy 0.88 / 0.861
  - Social 0.833 / 0.743
  - Health 0.917 / 0.694
  - Fun 0.806 / 0.66
  - Emotion 0.823 / 0.84
  - Closeness 0.556 / 0.9
  - Health was over-predicted: 34% of activities vs. 4.9% in human annotation.
- **Controllability:**
  - Zeroing a need raised time spent on activities that fulfil it: health +156%, energy +56%, fullness +35%, social +12%, fun −9%.
  - Fixing an emotion raised expressive activities: anger +15, sadness +10, fear +10.
  - No ablation against the Generative Agents baseline.

**Lyfe Agents** (Kaiya et al., arXiv 2310.02172, 3 October 2023) — [arXiv HTML](https://arxiv.org/html/2310.02172)
- **Mechanisms:**
  - (1) Option-action framework: high-level option choice, then cheap low-level actions.
  - (2) Asynchronous self-monitoring: an LLM continually rewrites a narrative summary from the old summary, recent internal states and motivation, emphasizing novel and goal-relevant content. It is run 35 times for one agent in one simulation.
  - (3) Summarize-and-Forget memory: workmem holds about 4–5 items, plus recentmem and longmem. On transfer, memories are clustered by cosine similarity and each cluster is LLM-summarized. New memories above a similarity threshold θ delete older redundant ones.
- **Murder-mystery ablations:**
  - The full system had the police officer identify the right suspect over 60% of the time within 15 minutes, even with 9 agents.
  - Removing self-monitoring "dramatically lowers the performance." Removing Summarize-and-Forget also drops performance sharply, and the full system beats plain memory at 3, 6 and 9 agents. Exact numbers are only in Figure 3b.
  - Removing option-action gave no performance gain at higher cost.
- **Cost:** about $0.50 per agent per human-hour on GPT-3.5, vs. an estimated about $25 for Park et al.

**Project Sid / PIANO** (Altera, arXiv 2411.00114, October/November 2024) — [arXiv HTML](https://arxiv.org/html/2411.00114)
- **Mechanisms:**
  - About 10 modules run concurrently at different speeds over a shared Agent State: memory, action awareness, goal generation, social awareness, talking, skill execution.
  - A Cognitive Controller receives a filtered subset of the state (an information bottleneck) and makes high-level decisions. It broadcasts them to the talk and motor modules so that speech and actions stay coherent.
- **Evidence:**
  - Social modules raised the slope of perceived vs. true likeability from 0.175 to 0.365 (r = 0.646 vs. 0.610, 1-observer threshold). With more observers, r rose to 0.907 at 11 observers.
  - Without social modules, relationships were more neutral, and specialized roles (farmer, guard, explorer…) did not emerge or persist.
  - In the tax-amendment experiment, deposits fell from about 20% to about 9% after an amendment to 5–10%. Ablating key modules removed this bidirectional rule-following effect.
  - Action awareness improved item progression, but numbers are only in Figure 5A. The paper gives no quantitative talk-action incoherence or hallucination rate.

**AgentSociety** (Piao et al., Tsinghua, arXiv 2502.08691, 12 February 2025; v2 2026) — [arXiv HTML](https://arxiv.org/html/2502.08691v1)
- **Mechanisms:**
  - Profile (stable) vs. Status (dynamic).
  - Emotions: six core emotions rated 0–10.
  - Maslow-hierarchy needs, with Theory of Planned Behavior driving plans.
  - Cognition: attitudes 0–10, updated from behavior descriptions.
  - Memory is split into an Event Flow (actions, passive events, environment changes) and a Perception Flow (thoughts and attitudes, each linked to event nodes).
  - The environment grounds actions. Agents form movement intentions, and a simulator executes them and returns feedback (e.g., arrived or not) into memory. Economic and social spaces are likewise simulated outside the LLM.
- **Evidence:** validation is macro-level alignment with real-world experiments (polarization, inflammatory messages, UBI, hurricane). No component ablation was found in the read portion. Numbers were in the unread portion of the paper.

**OASIS** (arXiv 2411.11581, 18 November 2024; v5 March 2025) — [arXiv](https://arxiv.org/abs/2411.11581)
- **Mechanisms:** a social-media simulator for up to 1M agents. A recommender system (interest-based or hot-score) decides what each agent sees, so visibility is controlled by the environment, not by the agent.
- **Evidence:** it replicates herd-effect experiments. A secondary summary says the agents show a stronger herd effect than humans (unverified against the primary text).

**Sotopia** (Zhou et al., ICLR 2024; arXiv 2310.11667) — [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2024/hash/b3075b88e583a0e98d8b24338a613060-Abstract-Conference.html)
- Episodes give each agent a private social goal and secrets. SOTOPIA-EVAL scores 7 dimensions, including believability (naturalness and consistency with the profile), knowledge, secret-keeping, relationship and goal completion.
- GPT-4 was the best model tested but fell below humans on the hardest scenarios.
- GPT-4-as-judge correlates with humans on goal, financial and relationship dimensions. It is weaker on believability, knowledge, secret-keeping and social rules, per [ICLR slides](https://iclr.cc/media/iclr-2024/Slides/17897.pdf) and secondary summaries.

**"Is this the real life?"** (Zhou, Su, Eisape, Kim, Sap; arXiv 2403.05020, March 2024; EMNLP 2024) — [arXiv HTML](https://arxiv.org/html/2403.05020v4)
- **Setup:** compares "Script" mode (one omniscient LLM writes all characters) against "Agents" mode (separate LLM per character, with information asymmetry).
- **Goal score, GPT-3.5:** Agents 6.95, Mindreaders 7.45, Script 8.44.
- **Craigslist deal rate:** Script 94% vs. Agents 30%.
- In Script mode the mutual friend's name is "guessed" almost immediately (first-mention position 0.13 vs. 0.39).
- Script output was judged more natural. Agents mode was more verbose and repetitive.
- Fine-tuning on Script data made agents exploit information they shouldn't have, or become overly agreeable.
- Conclusion: "addressing information asymmetry remains a fundamental challenge."

### Inferences
- For a 5–7 agent story sim, the evidence favors these, roughly in order:
  - (1) A per-agent running self-summary or "self-monitoring" narrative (Lyfe's strongest ablation). It counters persona drift and repetition cheaply.
  - (2) Memory consolidation and dedup (Summarize-and-Forget). This directly targets repetitive loops, because redundant memories stop re-cueing the same action.
  - (3) A small set of explicit state variables with mechanical decay and thresholds that trigger replanning (Humanoid Agents). These verifiably move behavior.
  - (4) A coherence step that keeps what an agent says aligned with what it does (PIANO's controller).
- The Zhou et al. result is a direct warning for Tiny Society. Any prompt that gives one LLM call several characters' private knowledge (e.g., a narrator or reporter, or a combined interaction prompt) will leak knowledge and inflate "smoothness." Per-agent prompts must contain only that agent's knowledge.

### Gaps
- Could not verify architectural details or evidence for AgentSims, S3, WarAgent, or SocioVerse within the tool budget. Treat them as uncovered; no claims are made here.
- AgentSociety's quantitative real-world alignment numbers were in the unread part of the paper.
- Park et al.'s 2024 "Generative Agent Simulations of 1,000 People" (interview-grounded personas) was not verified this session.

## Q3. Concordia's Game Master pattern, component by component

### Takeaway
Concordia separates *proposing* an action (players write free-text "putative events") from *resolving* it. A Game Master entity runs a chain of reasoning steps that turns the attempt into a definite, uncertainty-free event. It then updates world-state components (variables, locations, clock, inventory) and asks "which entities are aware of this event?" to route the resolved event only to those players' observation queues. No published ablation quantifies its benefit. It is an engineering pattern, not a measured result.

### Cited Findings
- **Papers:** Vezhnevets et al., "Generative agent-based modeling with actions grounded in physical, social, or digital space using Concordia" (arXiv 2312.03664, December 2023), and "Multi-Actor Generative AI as a Game Engine" (arXiv 2507.08892, 10 July 2025, Google DeepMind). — [2312.03664](https://arxiv.org/html/2312.03664); [2507.08892](https://arxiv.org/html/2507.08892v1)
- **2023 paper:**
  - Agents describe their action in natural language.
  - The GM samples an event statement from its components' states plus the attempted action, then stores it in its associative memory.
  - The GM checks plausibility and validates the action against "grounded variables" (money, possessions, votes). Example: it prevents spending money the agent doesn't have. Invalid actions are reported back to the agent.
  - The GM emits per-player observations. If a player didn't observe an event, nothing is sent.
  - Components can be plain code or external models (ODEs, state machines).
  — [arXiv 2312.03664](https://arxiv.org/html/2312.03664)
- **2025 paper:**
  - An entity-component architecture in which the GM is itself an entity built from components.
  - Engines can be simultaneous, sequential (turn order fixed or set by the GM) or asynchronous.
  - The paper names three design stances: Evaluationist, Dramatist (the GM as "narrative director," possibly with information asymmetry such as an antagonist knowing future plot points), and Simulationist (causal consistency).
  - It reports no new experimental results. Evidence cited is the Concordia Contest (NeurIPS).
  — [arXiv 2507.08892](https://arxiv.org/html/2507.08892v1)
- **Code (concordia/components/game_master/event_resolution.py, read from GitHub main):**
  - **Proposal:** the player's attempt is written into GM memory tagged as a putative event. `EventResolution.pre_act` (on an action spec of type RESOLVE) pulls the latest putative event from the currently active player, as determined by the NextActing component.
  - **Context:** it concatenates the states of designated GM components (instructions, player characters, relevant memories, recent events display).
  - **Resolution:** it runs a configurable list of "thought-chain" steps on the putative event.
  - **Observer routing:** it then asks, "Which entities are aware of the event? Answer with a comma-separated list of entity names," and pushes the event into each named player's queue in the MakeObservation component.
  - An alternative component, `SendEventToRelevantPlayers`, asks per player: "Is {name} aware of the latest event above?"
  — [concordia repo](https://github.com/google-deepmind/concordia/tree/main/concordia/components/game_master)
- **Thought-chain steps available in the same file** — [concordia repo](https://github.com/google-deepmind/concordia/tree/main/concordia/components/game_master)
  - `determine_success_and_why`: "Does the attempted action succeed? If the attempted action is easy to accomplish then the attempt should be successful unless there is a specific reason for it to fail." On failure it adds "Why did the attempt fail?" The output is "{attempt}, and was (not) successful. However, {why}".
  - `attempt_to_most_likely_outcome`: asks "Where is X?", then "What is X trying to do?", then "List at least 3 possible direct consequences… Never assume any other person will take a voluntary action. Be specific and concrete. Never beg the question… wrong to say 'Alex finds something'… specify exactly what Alex finds," then "Which outcome is the most likely?"
  - `result_to_causal_statement`: "Because of that, what happens as a result?", then a rewrite into one sentence that highlights cause and effect. "Do not express uncertainty (e.g. say 'Francis released the demon' not '…could release…')."
  - `result_to_who_what_where`: rewrites the event to name who, where, what, and the result, with verbatim speech and no uncertainty.
  - `extract_direct_quote` / `restore_direct_quote`: preserve exact speech through the processing.
  - `AccountForAgencyOfOthers`: detects whether the candidate event implies voluntary actions by non-active players. It asks *each such player's own agent*, "Is the following possible action something that {name} would do in this situation?" (Yes/No). For each "No," it generates "what would have happened but for {player}" and re-resolves the event. This stops one agent's action from puppeteering another.
  - `maybe_inject_narrative_push`: asks "Is the story traced out by the above list of events repetitive?" If yes, it generates 5 plausible complications "the game master of a typical tabletop RPG would be able to decide on their own without reducing the players' feelings of agency… never assume a player character takes a voluntary action. Non-player characters… can always be used to push the narrative forward," and folds one in.
  - `Conversation`: resolves a suggested conversation by asking each participant's agent what it would say.
- **Default generic GM prefab** (prefabs/game_master/generic.py): resolution steps are `[maybe_inject_narrative_push, AccountForAgencyOfOthers, result_to_who_what_where]`, and extra steps (e.g., `determine_success_and_why`) can be added by name. Components: associative memory, instructions, player roster, last-N observations, DisplayEvents, AllSimilarMemories, MakeObservation, NextActing (fixed, random or LLM-chosen order), NextActionSpec, EventResolution. — [concordia repo](https://github.com/google-deepmind/concordia/tree/main/concordia/prefabs/game_master)
- **World-state components** (world_state.py):
  - `WorldState`, after each event, asks which state variables matter given the prior state plus the latest event, in "name|value" format.
  - `Locations` updates each person's location only on explicit physical movement: "Talking, observing, or mentioning a place is NOT a move… respond with 'SAME'".
  - `GenerativeClock` advances time per event.
  - There are also `inventory.py`, `payoff_matrix.py`, `scene_tracker.py`, `terminate.py`, and in contrib `stock_flow_ledger.py`, `narrative_event_resolution.py`, `npc_event_generator.py`, `location_based_filter.py`, `death.py`.
  — [concordia repo](https://github.com/google-deepmind/concordia/tree/main/concordia/components/game_master)
- **Observation delivery** (make_observation.py): when a player is about to act, the GM drains that player's queue of routed events into the observation. If the queue is empty and LLM fallback is enabled, it asks "What does {name} observe now? Never repeat information that was already provided… Keep the story moving forward." — [concordia repo](https://github.com/google-deepmind/concordia/tree/main/concordia/components/game_master)

### Inferences
These map directly onto the Tiny Society failures:
- **Unresolved outcomes** (hunts and searches never succeed or fail): add a resolver pass per non-trivial action using `determine_success_and_why` plus `attempt_to_most_likely_outcome` (concrete: "specify exactly what Alex finds"). Write the resolved, uncertainty-free event to a canonical event log that becomes the only source of truth for later prompts and the report.
- **Information not propagating:** after resolving each event, run an explicit "who is aware of this?" step. It can be deterministic (co-location, participants, an addressee) plus an LLM check. Push the event into those agents' observation queues and memories. Confessions then reach exactly the people present, and gossip can be modeled as a new event when an aware agent tells someone.
- **Characters acting on unknowable facts:** because agents only ever receive routed events, and the resolver rejects or re-resolves actions that presuppose unknown facts, knowledge stays per-agent correct. This is the architectural answer to Zhou et al.'s omniscience leakage.
- **Repetitive loops / weak story progression:** `maybe_inject_narrative_push` is a cheap, documented pattern. A repetition check over recent events triggers an NPC- or world-driven complication that never forces a player character's voluntary action.
- **Report faithfulness:** generate the report from the GM's canonical resolved-event log and world-state variables, not from agents' memories or plans.
- **Puppeteering:** `AccountForAgencyOfOthers` prevents one agent's JSON action from deciding another agent's reaction, which is a likely source of causal incoherence.
- **Cost:** a GM pass per action is roughly 3–6 extra LLM calls. With 5–7 agents over 7 days this is affordable, and the steps can be restricted to actions flagged as consequential.

### Gaps
- No published ablation measures how much the GM's resolution chain improves believability or coherence. The Concordia papers give demonstrations and a validation framework, not metrics.
- The Concordia Contest results (Smith et al., 2025) were not retrieved.

## Q4. Coherent outcomes, world state, information flow, per-agent knowledge correctness

### Takeaway
Across systems, coherence comes from moving ground truth out of the agents' LLM context:
- An environment or GM owns world state and resolves actions: Concordia's grounded variables, AgentSociety's simulators, OASIS's recommender controlling visibility.
- Agents receive only observations routed to them.

Evidence that per-agent information separation matters is strong (Zhou et al.). Evidence for specific state-tracking designs is mostly qualitative.

### Cited Findings
- Concordia validates actions against grounded variables, updates world-state components after each event, and sends observations only to players judged aware. — [arXiv 2312.03664](https://arxiv.org/html/2312.03664); [concordia repo](https://github.com/google-deepmind/concordia/tree/main/concordia/components/game_master)
- AgentSociety executes agent intentions in environment simulators and writes the feedback (e.g., destination reached) back to memory. Its Event Flow / Perception Flow split keeps facts separate from interpretations, with interpretations linked to event nodes. — [arXiv 2502.08691](https://arxiv.org/html/2502.08691v1)
- In OASIS, the recommender system determines what content each agent sees. — [arXiv 2411.11581](https://arxiv.org/abs/2411.11581)
- In PIANO, the Cognitive Controller broadcasts one decision to both the talk and act modules to prevent say/do mismatch. An action-awareness module compares expected with actual outcomes, and improved progression (Figure 5A). — [arXiv 2411.00114](https://arxiv.org/html/2411.00114)
- Omniscient single-LLM simulation inflates goal success (8.44 vs. 6.95) and produces an unrealistic early "guessing" of hidden information. — [arXiv 2403.05020](https://arxiv.org/html/2403.05020v4)
- In Generative Agents, information spread only through agent dialogue: 32% and 52% reach over 2 days. Embellishment errors appeared as information passed between agents. — [arXiv 2304.03442](https://arxiv.org/html/2304.03442)

### Inferences
- Recommended Tiny Society pipeline per action:
  1. Agent proposes a JSON intent.
  2. The GM resolves it into a definite outcome: success/fail plus a concrete result, checking the agency of the other agents involved.
  3. A world-state ledger is updated: facts, possessions, locations, injuries, secrets known by whom.
  4. Observers are computed and the event is enqueued to each.
  5. Relationship affinity is updated from the *resolved* event rather than the intended verb.
- A "who knows fact X" table (fact → set of agents) is a cheap, checkable structure. It lets the reasoner prompt include "facts you know" and lets an automated check flag actions referencing facts outside the agent's set. That set can feed the judge's "event grounding" metric.

### Gaps
- No study found that quantitatively compares knowledge-graph or fact-ledger world state against free-text GM memory for narrative coherence in small simulations.

## Q5. Does embedding-based retrieval matter in small simulations? Memory architecture evidence

### Takeaway
There is no controlled evidence that better embedding retrieval improves believability in small agent simulations. Park et al. never ablated the retrieval weights. The memory interventions with measured effects are summarization, consolidation, forgetting and self-summary (Lyfe Agents) and reflection (Park et al.). This is consistent with Tiny Society's null result for embeddings.

### Cited Findings
- Park et al. ablated observation, reflection and planning, but not the recency, importance or relevance terms. All α weights were fixed at 1. — [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- The paper's failure examples are retrieval misses, where a memory existed but wasn't surfaced (Rajiv, Tom). — [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- Lyfe Agents ablations: removing Summarize-and-Forget (cluster, summarize, deduplicate) or removing the self-monitoring summary each "dramatically" lowered murder-mystery success at 3, 6 and 9 agents. — [arXiv 2310.02172](https://arxiv.org/html/2310.02172)
- AgentSociety separates episodic events (Event Flow) from interpretations and attitudes (Perception Flow, linked to events), but no ablation was found. — [arXiv 2502.08691](https://arxiv.org/html/2502.08691v1)
- Outside simulations, MemMachine (arXiv 2604.04853, 2026) argues that full context triggers "lost in the middle." It favors a summary plus selectively retrieved raw episodes, with evidence on QA benchmarks (LongMemEval, LoCoMo) rather than believability. — [MemMachine](https://arxiv.org/html/2604.04853v1)
- A targeted search found no 2024–2026 study that directly compares retrieval, summary and full context for believability in a small simulation. — search result summary; see also [A-Mem](https://arxiv.org/pdf/2502.12110)

### Inferences
- With 5–7 agents over 7 days, each agent's total memory likely fits in context once consolidated. Expect the gains to come from:
  - (a) structured, always-included summaries: a self-narrative, per-relationship summaries, and known facts and open threads;
  - (b) deduplicating or merging repeated memories, which counters loops;
  - (c) always including unresolved commitments and open threads, such as an ongoing hunt or a pending confession reaction.
- Retrieval ranking quality matters less than these. Tiny Society's null embedding result fits this picture.
- Semantic facts (who knows what, possessions, relationships) are better kept in structured state than in an episodic stream, where retrieval misses cause "forgot that X happened" errors.

### Gaps
- No ablation found anywhere on knowledge-graph memory vs. episodic retrieval for believability in social simulations.
- Lyfe's exact ablation numbers are only in Figure 3b.
