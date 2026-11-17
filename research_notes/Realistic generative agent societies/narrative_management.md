# Narrative / Drama Management Techniques for Coherent, Causal, Progressing Emergent Stories (Tiny Society)

Scope: methods that keep emergent multi-character stories coherent, causally grounded and moving, so they can be implemented as a light layer around the LLM calls in Tiny Society (5–7 LLM characters, up to 7 days, an engine that never adjudicates outcomes, a 5-day "dynamic event", and an LLM-judged final report). Every finding below has a source. Where a claim comes from background knowledge I could not verify in this session, it is listed under Gaps.

---

## 1. Game-master adjudication: deciding whether an action succeeds and who learns the result

### Takeaway
The best-documented LLM pattern, Concordia's Game Master, makes outcome adjudication an explicit chain of LLM questions: does the attempt succeed and why, list the concrete consequences and pick the most likely, rewrite the result as a definite causal sentence, then decide which entities observed it. Tabletop practice adds the part Tiny Society is missing for repeated efforts: progress clocks. A multi-day search, hunt or repair fills a 4/6/8-segment clock, so effort accumulates and has to resolve once the clock is full.

### Cited Findings
**Concordia (Google DeepMind, Vezhnevets et al., arXiv 2312.03664, 2023)**
- The Game Master (GM) is modelled on tabletop RPG game masters. It "consumes agent actions and creates event statements" that define what happened because of an attempted action. Its jobs are to keep the world state consistent and grounded, tell agents what they can observe, decide the effect of actions, and resolve conflicts between agents' actions — [Concordia paper](https://arxiv.org/html/2312.03664v2)
- The GM frames each step as four questions: what is the state of the world; given that state, what event results from the players' activity; what observation does each player make; and what effect does the event have on grounded variables. "Grounded variables" such as money are called the GM's most important responsibility. The GM can, for example, stop an agent from paying more than it has, and it tells the agent when an action violates grounding — [Concordia paper](https://arxiv.org/html/2312.03664v2)
- When the GM judges that a player did not observe an event, no observation is sent to that player — [Concordia paper](https://arxiv.org/html/2312.03664v2)
- The GM components in the current repo include `event_resolution`, `world_state`, `inventory`, `scene_tracker`, `next_acting`, `make_observation`, `switch_act`, `terminate`, `payoff_matrix` and `script` — [Concordia repo, concordia/components/game_master](https://github.com/google-deepmind/concordia/tree/main/concordia/components/game_master)
- The resolution thought-chain prompts in `event_resolution.py`, quoted from the repo:
  - `determine_success_and_why`: "Does the attempted action succeed? If the attempted action is easy to accomplish then the attempt should be successful unless there is a specific reason for it to fail." On failure it asks "Why did the attempt fail?" and appends "…and was not successful. However, {why}" — [event_resolution.py](https://github.com/google-deepmind/concordia/blob/main/concordia/components/game_master/event_resolution.py)
  - `attempt_to_most_likely_outcome`: asks "Where is X?" and "What is X trying to do?", then "List at least 3 possible direct consequences of X's action. Never assume any other person will take a voluntary action. Be specific and concrete. Never beg the question. For instance, it is wrong to say 'Alex finds something'. Instead specify exactly what Alex finds", and then "Which outcome is the most likely?" — [event_resolution.py](https://github.com/google-deepmind/concordia/blob/main/concordia/components/game_master/event_resolution.py)
  - `result_to_causal_statement`: asks "Because of that, what happens as a result?" and then rewrites the result as one sentence: "Do not express uncertainty (e.g. say 'Francis released the demon' not 'Francis could release the demon')" — [event_resolution.py](https://github.com/google-deepmind/concordia/blob/main/concordia/components/game_master/event_resolution.py)
  - Observer routing: after the event is fixed, the GM asks "Which entities are aware of the event? Answer with a comma-separated list of entity names." and queues the event statement as an observation for each name in the answer — [event_resolution.py](https://github.com/google-deepmind/concordia/blob/main/concordia/components/game_master/event_resolution.py)

**Tabletop clocks and fronts**
- Blades in the Dark progress clocks: a complex obstacle is a 4-segment clock, a more complicated one 6 segments and a daunting one 8 segments, and a basic long-term project is 8 segments. A danger clock ticks 1–3 segments according to the consequence level, and the danger takes effect when it is full. The other types are racing clocks (two opposed clocks, and if both fill at once the PCs escape but the hunters are still near), linked clocks (filling one unlocks the next), mission/countdown clocks ("If the countdown runs out, the mission is scrubbed or changes"), tug-of-war clocks (events tick them up or down), and faction clocks ("When the PCs have downtime, the GM ticks forward the faction clocks that they're interested in") — [Roll20 BitD SRD: Progress clocks](https://roll20.net/compendium/BITD/Rules:Progress%20clocks)
- Clocks can be advanced by actions, consequences, fortune rolls and "the natural evolution of the game state" — [The Alexandrian](https://thealexandrian.net/?p=40424)
- Apocalypse World fronts move forward whether or not the PCs get involved, and the PCs' involvement can redirect or halt them. "Grim portents" are the steps toward a front's doom, and the sequence of them is the countdown — [Sly Flourish, Fronts](https://slyflourish.com/fronts_in_dnd.html)
- Clocks let the MC prepare possible futures without declaring them by fiat. They advance during play and can be scratched out if circumstances change — [Daily Apocalypse: threat countdown clocks](https://daily-apocalypse.com/daily-apocalypse/85-threat-countdown-clocks)
- Apocalypse World 2nd edition replaced Fronts with a revised Threats system — [The Alexandrian](https://thealexandrian.net/wordpress/tag/apocalypse-world)

**LLM GM evidence**
- RPGBench (arXiv 2502.00595) concludes that state-of-the-art LLMs can write engaging stories but "often struggle to implement consistent, verifiable game mechanics," especially in long or complex scenarios. The abstract gives no headline numbers — [RPGBench](https://arxiv.org/abs/2502.00595)
- A 2022 D&D dialogue study found that a finetuned model reached only 58% joint accuracy on full game-state tracking — [arXiv 2210.07109](https://arxiv.org/pdf/2210.07109) (figure taken from the search snippet; not re-verified in the PDF)
- CriticaLLM uses a separate judge LLM to check whether each player action fits the current game state, story and rules before the GM LLM responds, and it gives the GM only the last three phases of play — [CriticaLLM, arXiv 2610.21525](https://arxiv.org/html/2610.21525) (from the search snippet)
- The "Static vs Agentic GM" paper resolves combat with a Battle tool that takes qualitative hit chances (Low/Medium/High) and damage severity, rather than dice or free-text outcomes — [arXiv 2502.19519](https://arxiv.org/html/2502.19519v2)

### Inferences (design for Tiny Society)
- **Add an Adjudicator pass after action proposal and before the applicator.** For each proposed action classed as an *attempt* (search, hunt, investigate, repair, persuade, steal, hide), run a Concordia-style chain that returns structured JSON:
  `{outcome: success|partial|fail|complication, why, concrete_result, clock_ticks, state_deltas[], observers[], reveals_fact_id?}`.
  Keep Concordia's two key constraints: name the specific thing found, never "something", and never decide another character's voluntary action.
- **Make the decision cheaply reproducible: skill + difficulty + randomness in code, with the LLM only narrating.** The LLM labels difficulty (trivial/standard/hard/daunting) and the actor's relevant competence (0–2) from the persona. Code rolls a 2d6 or d100 against those, PbtA style: 10+ success, 7–9 partial success or success with a cost, 6- failure plus a complication. The LLM then writes the concrete result for the band it was given. This moves the "does it succeed" choice out of the LLM, where it tends to say yes to everything or to stall, and makes the outcome seedable. (Inference: PbtA's 2d6 bands are standard published rules, but I did not fetch a source for them in this session.)
- **Turn every multi-day effort into a progress clock that the engine owns.** "Find the missing child" becomes an 8-segment clock. Each attempt adds ticks by outcome band (fail = 0 plus a complication, partial = 1, success = 2, great = 3), and the clock is guaranteed to resolve when full. This directly fixes "efforts repeat for days". It also suits 7 days: an 8-segment clock with one or two efforts a day resolves in about 3–5 days.
- **Bind clocks to the hidden truth from event casting.** Each piece of private knowledge or hidden-truth fact gets a `reveal_condition`, such as "investigation clock reaches 4/8" or "succeeds at searching the mill". When the condition is met, the Adjudicator puts the fact into `concrete_result`, and only the observers receive it. This is how the outcome reaches the right characters, as in Concordia's "Which entities are aware" step.
- **Give the 5-day dynamic event an opposing danger or faction clock instead of a one-liner.** Example: "The storm reaches the village" as a 6-clock that ticks each day whatever the characters do, a racing clock against the cast's repair clock. A front that advances on its own guarantees the event lands.

### Gaps
- I did not find measured evidence comparing "LLM decides success" against "dice decides, LLM narrates" in multi-agent social simulations.
- "Say yes or roll the dice" (Vincent Baker, *Dogs in the Vineyard*) and the exact PbtA 2d6 bands were not fetched or verified here.
- I did not read CriticaLLM's numerical results.

---

## 2. Classic drama managers and experience managers

### Takeaway
Classic drama management uses three levers, and all of them fit around LLM calls. **Façade** picks the next beat whose preconditions hold and whose effects best match a target tension arc. **Glaive/Sabre** only accept actions that a character could plausibly intend, given its goals and its *beliefs*. **Ryan's curationism** argues that you leave the simulation alone and select and frame what happened afterwards. Recent comparisons of LLM experience managers find that no single manager wins on every property.

### Cited Findings
- **Façade's drama manager** "globally sequences beats chosen from a large pool in order to make story tension rise and fall to match an Aristotelian arc" — [Mateas & Stern, TIDSE 2003](https://users.soe.ucsc.edu/~michaelm/tenurereview/publications/mateas-tidse2003.pdf)
- Beats are the smallest units of change in dramatic value, and the values (love, trust, tension) are character and story attributes. The desired value arcs and each beat's declared effects "compute a probability distribution over possible next beats; beats are selected by drawing from this changing distribution" — [Beyond Story Graphs: Story Management in Game Worlds](https://dh-abstracts.library.virginia.edu/works/7908); [IDSwiki: Façade](https://tecfalabs.unige.ch/mediawiki-narrative/index.php/Facade)
- The beat manager looks for authored beats "with preconditions that match the player's current interactions and the story memory," and when several qualify it picks the one that best fits the arc — [Zarf's notes on Mateas talk](https://blog.zarfhome.com/2008/11/michael-mateas-talk-on-facade)
- A Façade beat consists of 10–100 joint dialogue behaviors — [IDSwiki: Façade](https://tecfalabs.unige.ch/mediawiki-narrative/index.php/Facade)
- **Search-based drama management** was applied to the interactive fiction *Anchorhead* (Nelson & Mateas, AIIDE 2005) — [paper](https://eis.ucsc.edu/papers/Nelson_Mateas_-_SBDM_-_AIIDE05.pdf)
- **Glaive** (Ware & Young, AIIDE 2014, Best Student Paper) is a state-space planner that reasons about character intentionality, using Riedl & Young's model, and about conflict, meaning how agents' plans can interfere and fail. It represents alternate worlds to do this — [Glaive project](https://cs.uky.edu/~sgware/projects/glaive); [paper](https://ojs.aaai.org/index.php/AIIDE/article/view/12712)
- **Sabre** (Ware & Siler 2021) succeeds Glaive. It adds a model of character *beliefs* and is "significantly more efficient in both memory and time" — [Sabre project](https://www.cs.uky.edu/~sgware/projects/sabre); [paper](https://cs.uky.edu/~sgware/reading/papers/ware2021sabre.pdf)
- **James Ryan, *Curating Simulated Storyworlds* (UCSC PhD, 2018)** argues that simulations produce stories only once someone selects and frames events ("curationist emergent narrative"). It rejects drama management largely on aesthetic grounds, because intervening changes the simulation's nonfiction-like character. It asks whether a storyworld can curate itself, and covers Talk of the Town, Bad News, Hennepin and Sheldon County — [eScholarship PDF](https://escholarship.org/content/qt1340j5h2/qt1340j5h2.pdf?t=plxqme); [Emily Short review ch.1–3](https://emshort.blog/2019/05/21/curating-simulated-storyworlds-james-ryan/)
- **LLM-era experience managers.** Clerc et al. (arXiv 2611.02807) build managers as swappable modules over a shared symbolic model of facts and operations with explicit preconditions and effects, so each session can be analysed as a plan. They score three managers (open generation, Monte Carlo repair, autonomous characters) on player agency, controllability, author intent and robustness, and find that "no manager dominates on every property". The abstract gives no numbers — [arXiv 2611.02807](https://arxiv.org/abs/2611.02807)
- A "Triangle" framework at AIIDE observes that emergent multi-agent simulations give each character local intelligence but no global view and "often los[e] plot structure". It adds a centralized narrative planner that computes causal sequences — [AIIDE paper](https://ojs.aaai.org/index.php/AIIDE/article/download/36858/38996/40935) (from the search snippet; the full text was blocked)
- StoryVerse (2024) has the author, an LLM character simulation and the player co-create a plot through narrative planning, balancing authorial intent against emergent behaviour — [arXiv 2405.13042](https://arxiv.org/pdf/2405.13042)
- HAMLET (ICLR 2026) separates offline planning, where a director agent builds a narrative blueprint, from online performance, and evaluates plot coherence — [paper](https://proceedings.iclr.cc/paper_files/paper/2026/file/33177752ddc94cc32ea2f46eacf10488-Paper-Conference.pdf)

### Inferences (design for Tiny Society)
- **Turn the 5-day dynamic event into a lightweight Façade-style beat selector.** The director LLM writes or selects 3–5 candidate "beats" from the open-threads list. Each beat has preconditions (which characters, which threads, which facts must be known or unknown) and effects (which tension or story value it moves, which thread it advances or closes). Code filters out beats whose preconditions fail and scores the rest against the target tension for that day (see section 3). The director should also run every day, at low cost, not only every 5 days.
- **Use a Sabre-style intentionality check as a validator, not a planner.** Before accepting a proposed action, check that it is (a) consistent with what that character *believes*, using event casting's per-character private knowledge, and (b) explainable by one of the character's goals. This blocks actions that rely on knowledge the character never received, a common LLM leak that hurts causal coherence.
- **Combine Ryan and the drama manager.** Make the minimum intervention during the run (clocks, an adjudicator, an occasional beat), and spend most of the effort on curation at report time (section 4). Given Clerc et al.'s finding, tune the strength of intervention on a dial, not on a single setting.

### Gaps
- I did not fetch Riedl's narrative mediation or Mimesis (Riedl, Saretto & Young 2003; Riedl & Young 2010 IPOCL). From background knowledge only: mediation precomputes how the plan should react when an agent's action threatens a causal link, by *accommodating* it (replanning) or *intervening* (making the action fail). This maps directly onto the adjudicator choosing "fail with complication", but it is unverified here.
- No quantitative coherence results for the Triangle framework or HAMLET could be retrieved; access to the PDF was blocked.

---

## 3. Emergent narrative in simulation games: pacing and arcs

### Takeaway
RimWorld's storyteller is the most transferable model. It treats the simulation as a story generator, watches the state, and schedules incidents along a rising-and-falling tension curve, with deliberate rests after spikes. It does not try to win against the player.

### Cited Findings
- Tynan Sylvester: being a story generator is "the central pillar of the design, to the point that I deliberately decide every design conflict between 'game' and 'story generator' directions in favor of the latter." He describes the AI storyteller as matching a rising and falling pacing curve rather than "over-brutally murdering" struggling players, and the game's "story watchers" monitor the state, for example wealth and dangers encountered — [PC Gamer via PressReader, 2017](https://www.pressreader.com/usa/pc-gamer-us/20170523/283794263693348)
- Before a storyteller event, the game considers colony wealth, colonist and animal counts, recent deaths or severe wounds, and the time since the last major event. Cassandra Classic produces "a classic increasing curve of challenge and tension", pushing with dangerous events, then giving breathing room, then pushing again. Phoebe uses the same events spaced further apart — [RimWorld Wiki: AI Storytellers](https://rimworldwiki.com/wiki/AI_storyteller)
- The exact raid-point and wealth formulas exist only in fan guides and are unverified, for example "up to 4,200 raid points" — [RimWorldHub guide](https://rimworldhub.com/post/brutal_rimworld_taming_your_storytellers_madness) (low reliability)

### Inferences (design for Tiny Society)
- **Set a 7-day target tension curve**, for example Day 1: 2, Day 2: 3, Day 3: 5, Day 4: 4 (breather), Day 5: 7, Day 6: 9 (climax), Day 7: 5 (resolution). Each day a "story watcher" scores current tension from state: number of open clocks near full, relationship hostility, unresolved accusations. The director then picks beats or advances fronts to close the gap, like Cassandra, and *withholds* events when tension is above target, like Phoebe's spacing.
- **Force convergence in the last act.** From Day 5 on, the director stops opening new threads and only picks beats that close existing ones. All clocks get a hard deadline at Day 7 (mission clocks), so every thread reaches *some* resolution.

### Gaps
- No primary sources were fetched for Dwarf Fortress legends mode, Crusader Kings or The Sims' narrative systems. Claims about them would be unsupported, so I omit them.
- No official formula for Cassandra's threat curve was found.

---

## 4. Causality tracking and a faithful final narrative

### Takeaway
Keep a structured event log in which every event has an ID, causes (links to prior event IDs), participants, observers, and thread or clock IDs. Run story sifting (pattern queries plus a "select the unexpected" salience ranking) over that log *before* narration, and make the narrator cite event IDs so that a cheap check can reject claims nobody can trace. Concordia's causal-statement rewrite ("Because of that…", no hedging) is a ready-made way to produce log entries that state cause and effect.

### Cited Findings
- **Story sifting** selects a compelling story from a larger chronicle of events. Ryan introduced the term and framed it as a major open problem in emergent narrative — [Kreminski thesis (eScholarship)](https://escholarship.org/content/qt4vj649w6/qt4vj649w6.pdf?t=rkavv2); [Felt paper](https://mkremins.github.io/publications/Felt_SimpleStorySifter)
- **Felt** (Kreminski, Dickinson & Wardrip-Fruin, ICIDS 2019) is a query-based sifter in which authors hand-specify patterns for interesting event sequences — [Felt](https://mkremins.github.io/publications/Felt_SimpleStorySifter); [Springer](https://link.springer.com/doi/10.1007/978-3-030-33894-7_27)
- **Winnow** (Kreminski, Dickinson & Mateas, AIIDE 2021) is a declarative DSL for *incremental* sifting while a simulation runs. It can flag partial matches, meaning sequences that have started but not yet completed, and it compiles to Felt — [AIIDE](https://ojs.aaai.org/index.php/AIIDE/article/view/18903); [GitHub](https://github.com/mkremins/winnow)
- **"Select the Unexpected"** (Kreminski et al., ICIDS 2022) is a statistical heuristic that ranks sifted results by how unexpected they are — [PDF](https://mkremins.github.io/publications/StU_ICIDS2022.pdf)
- "Authoring for Story Sifters" gives practical guidance for writing sifting patterns — [PDF](https://mkremins.github.io/publications/AuthoringSifters_TAP.pdf)
- An ICCC 2023 study tested whether ChatGPT could choose a subset of simulation events that, once narrated, makes a better story than the full set — [ICCC 2023 paper 124](https://computationalcreativity.net/iccc23/papers/ICCC-2023_paper_124.pdf)
- Lessard et al. (PCG workshop 2026, "Narrative Gold Digging") sift and narrate stories from the Chroniqueur procedural simulation, building on "select the unexpected". They note it would not scale to Chroniqueur's very large event space in its current form — [PDF](https://www.pcgworkshop.com/archive/lessard2026narrative.pdf)
- Concordia's `result_to_causal_statement` turns each outcome into "{event} Because of that, {effect}" and then into a single sentence with no hedging. `result_to_who_what_where` rewrites events around who, what, where and the result, quoting speech verbatim — [event_resolution.py](https://github.com/google-deepmind/concordia/blob/main/concordia/components/game_master/event_resolution.py)
- The SWAG system uses a generator-evaluator loop that scores candidate next narrative actions for relevance and coherence before committing to prose — [Narrative Theory-Driven LLM Methods survey, arXiv 2602.15851](https://arxiv.org/pdf/2602.15851) (from the search snippet)
- Ware et al. also have a 2023 paper on causal structure in narrative planning — [ware2023causal.pdf](https://www.cs.uky.edu/~sgware/reading/papers/ware2023causal.pdf) (found but not read)

### Inferences (design for Tiny Society)
- **Event log schema** (append-only; the engine already logs actions):
  `{id, day, actor, action, outcome_band, concrete_result, caused_by:[event_ids], observers:[...], thread_ids:[...], clock_deltas:{...}, facts_revealed:[fact_ids]}`.
  The adjudicator fills `caused_by` by choosing from the last N events plus the open-thread list. Pick from IDs; do not free-text the causes.
- **Open-threads ledger (Chekhov ledger).** Every setup (hidden truth, private knowledge, an accusation, a promise, an object introduced, the dynamic event) becomes a thread with `status: open|advancing|resolved|abandoned`, a linked clock, and a `setup_event_id`. A payoff must cite the setup ID. The director's beat selection favours threads that are open and stale. At report time, any thread still open is either resolved in the epilogue from logged facts or explicitly named as unresolved, never silently dropped.
- **Incremental sifting with Winnow-style partial matches.** A few hand-written patterns over the log ("A betrays B after B helped A", "secret revealed to the person it concerns", "effort fails twice, then succeeds", "rivalry escalates over 3+ events") report partial matches each day to the director, which can choose a beat that *completes* a pattern. This gives arcs without scripting them.
- **Faithful final report pipeline:** (1) sift by pattern matches and thread payoffs, rank them with a select-the-unexpected surprise score, and choose 3–5 throughlines; (2) give the narrator only the chosen event records plus the thread ledger; (3) require an `[E123]` citation after every factual sentence; (4) validate in code that every cited ID exists and that the sentence's actor appears among the event's participants, plus an optional cheap LLM entailment check per sentence against the cited event; (5) strip citations for display. This follows the 2502.19519 finding that structured state beats prose-in-context (next section).

### Gaps
- I found no published measurement of citation-constrained narration of simulation logs. The design is inferred from general RAG-attribution practice and is not sourced here.
- I did not read the ICCC 2023 ChatGPT-sifting results or the Lessard 2026 evaluation in detail.

---

## 5. LLM-era evidence (2023–2026) on coherence in interactive and multi-agent fiction

### Takeaway
The measured evidence is thin, but it points the same way throughout. Explicit structured world state, kept by a separate archivist or GM pass, together with explicit mechanics, improves perceived coherence. Plain LLM narration drifts and handles mechanics poorly.

### Cited Findings
- **Static vs Agentic GM (arXiv 2502.19519).** v1 was a single prompt with the whole state as a text string, and the authors observed that early details were lost as the context filled. v2 used two ReAct agents: a Narrator, and an Archivist that records new or changed characters and locations through UpdateCharacter and UpdateEnvironment tools into a database. In a within-subjects study with n=12, v2 scored higher on all 14 constructs. Significant results (p<0.05) included Coherent story (p=0.040), Story interesting (p=0.0187), Goals and rules (p=0.018), Mastery (p=0.004) and Immersion (p=0.034). The sample is small, and the paper's claim of "nine significant" counts a p=0.050 result — [arXiv 2502.19519](https://arxiv.org/html/2502.19519v2)
- The same paper describes AI Dungeon (GPT-2) as a pure text interface with no world-state tracking, combat or health mechanics — [arXiv 2502.19519](https://arxiv.org/html/2502.19519v2)
- RPGBench: LLMs struggle to keep mechanics consistent and verifiable, especially over long or complex play — [arXiv 2502.00595](https://arxiv.org/abs/2502.00595)
- "Orchestrated Reality" (arXiv 2606.16014) reports that LLM systems often fail to keep a coherent world state, and proposes a validated JSON world state with a plan → diff → validate → apply pipeline — [arXiv 2606.16014](https://arxiv.org/pdf/2606.16014) (from the search snippet)
- The 2024 survey "Large Language Models and Games" covers LLMs as game masters, including AI Dungeon — [arXiv 2402.18659](https://arxiv.org/pdf/2402.18659)
- "Orchestrating Emergent Storytelling with Embodied Multi-Agent Systems" uses a scheduler that balances pre-designed plot structure against emergent complexity — [OpenReview PDF](https://openreview.net/pdf/1aac484305a0d3733799ad46cc29fd951bd46fa7.pdf) (from the search snippet)

### Inferences (design for Tiny Society)
- **Proposed per-day loop**, about +2–4 LLM calls per action and +1–2 per day:
  1. **Director** (daily): read the tension target and the threads ledger, maybe pick one beat or tick one front.
  2. **Characters** propose actions (unchanged), with the beat injected as an observation for the relevant characters only.
  3. **Validator:** a belief/intentionality check and a grounding check, Sabre and CriticaLLM style.
  4. **Adjudicator:** a difficulty and competence label from the LLM, a seeded roll in code, a concrete result from the LLM under Concordia's constraints, then a causal statement, clock ticks, observers and fact reveals.
  5. **Archivist:** apply the JSON deltas to the world state, event log and threads ledger, with plan → diff → validate → apply.
  6. **Observation routing:** only the observers get the event text, and private-knowledge reveals go only to the characters that earned them.
  7. **End of run:** sift, pick throughlines, narrate with citations, validate.
- **Expected effect on the judge's scores.** Progression should rise because clocks guarantee resolution and the fronts and dynamic event advance on their own. Causal coherence should rise because the `caused_by` links, the Chekhov ledger and cited narration make every report claim traceable. These are inferences; there is no direct measurement.
- **Measure it.** Re-run the existing LLM judge before and after on fixed seeds, and add cheap automatic metrics: % of threads resolved, mean days an effort stays unresolved, % of report sentences with valid citations, and the number of "knowledge leaks" (actions using facts the actor never observed).

### Gaps
- I found no controlled study of LLM multi-agent *social* simulations (Smallville or Concordia style) that measures story progression or causal coherence with and without a drama manager or adjudicator. Everything that quantifies the benefit comes from single-player GM settings (n=12) or from benchmarks without headline numbers.
- Several relevant papers (Triangle/AIIDE, Clerc et al. 2611.02807, HAMLET, CriticaLLM) could only be read as abstracts or snippets, so their quantitative results are not captured here.
