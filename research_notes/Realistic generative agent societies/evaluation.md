# Evaluating the realism / believability of LLM multi-agent social simulations

Context: Tiny Society runs about 16 simulations across 8 worlds. A Sonnet judge scores each story 1–10 on 7 dimensions and lists errors. Scores cluster at 6–8 with run-to-run noise of about ±0.5, and each run costs about $0.10–0.15.

## Q1. What evaluation methods have generative-agent papers used?

### Takeaway
The main papers use four kinds of evaluation:
- **Interviewing agents and ranking the results against each other**, done by humans with TrueSkill (Park 2023).
- **Counting things that come out of a run**, such as how far information spread, how network density changed, and hallucination rates (Park 2023).
- **Scoring each dimension on a 0–10 scale with an LLM judge**, which matches humans well only on some dimensions (Sotopia-Eval).
- **Checking predictions against real human data**: survey answers in Park 2024, real social experiments in AgentSociety.

A critical review finds that most of the field still relies only on subjective "believability" judgments and a single run.

### Cited Findings
**Park et al. 2023, "Generative Agents" (Smallville, 25 agents)**
- **Interviews.** Each agent was "interviewed" with 25 questions, five in each of five areas: self-knowledge, memory, plans, reactions and reflections. [arXiv 2304.03442](https://arxiv.org/html/2304.03442v2)
- **Raters.** 100 Prolific participants (within-subjects design) watched a replay of an agent and ranked five conditions by believability. The rankings were turned into TrueSkill ratings. [arXiv 2304.03442](https://arxiv.org/html/2304.03442v2)
- **TrueSkill results (μ, σ).** [arXiv 2304.03442](https://arxiv.org/html/2304.03442v2)

  | Condition | μ | σ |
  |---|---|---|
  | Full architecture | 29.89 | 0.72 |
  | No reflection | 26.88 | 0.69 |
  | No reflection or planning | 25.64 | 0.68 |
  | Human crowdworker | 22.95 | 0.69 |
  | No memory, planning or reflection | 21.21 | 0.70 |

- **Statistics.** A Kruskal-Wallis test gave H(4)=150.29, p<0.001. Dunn post-hoc tests with Holm-Bonferroni correction found every pair significantly different except crowdworker vs. the fully ablated condition. The full architecture vs. the prior-work condition gave d=8.16. [arXiv 2304.03442](https://arxiv.org/html/2304.03442v2)
  - Note: these are large ablations. Ranking the conditions against each other gave clear separation; scoring each one on its own scale was not used.
- **End-to-end countable measures over 2 game days.** [arXiv 2304.03442](https://arxiv.org/html/2304.03442v2)
  - Knowledge of Sam's candidacy spread from 1 agent (4%) to 8 (32%).
  - Knowledge of Isabella's party spread from 1 agent (4%) to 13 (52%).
  - Network density rose from 0.167 to 0.74.
  - 5 of 12 invited agents attended the party.
  - 1.3% (6 of 453) of agent statements about knowing others were hallucinated.
- **Failure modes they catalogued.** [arXiv 2304.03442](https://arxiv.org/html/2304.03442v2)
  - Embellishment, e.g. adding that Sam "is going to make an announcement tomorrow".
  - Leakage of world knowledge from the model's training (Adam Smith the economist).
  - Memory-retrieval failures, e.g. Rajiv saying he hadn't followed the election even though he knew of the candidacy.
  - Overly formal speech.
  - These map directly onto things Tiny Society can count.

**Sotopia / Sotopia-Eval (Zhou et al. 2023)**
- **Seven dimensions and their ranges.** [arXiv 2310.11667](https://arxiv.org/html/2310.11667v2)
  - Goal completion: 0 to 10
  - Believability: 0 to 10
  - Knowledge: 0 to 10
  - Secret: -10 to 0
  - Relationship: -5 to 5
  - Social rules: -10 to 0
  - Financial/material: -5 to 5
- **Agreement between the GPT-4 judge and humans (Pearson r, model role-play).** It was high only for Goal, Fin and Rel. [arXiv 2310.11667](https://arxiv.org/html/2310.11667v2)

  | Dimension | r |
  |---|---|
  | Goal | 0.71 |
  | Fin | 0.62 |
  | Rel | 0.56 |
  | Bel | 0.45 |
  | Kno | 0.33 |
  | Soc | 0.33 |
  | Sec | 0.22 |

- **Judge bias and human reliability.** GPT-4 rated Social rules and Secret higher than humans did. Agreement among human annotators was only moderate (Randolph's κ=0.503, MTurk, 200 episodes). [arXiv 2310.11667](https://arxiv.org/html/2310.11667v2)

**Humanoid Agents (Wang et al., EMNLP 2023 demo)**
- **Method.** Three human annotators labelled one simulated day using the same instructions the LLM had. The system's per-step predictions were scored against the majority vote with micro-F1. [arXiv 2310.05418](https://arxiv.org/pdf/2310.05418)
- **Results.** [arXiv 2310.05418](https://arxiv.org/pdf/2310.05418)
  - Fullness F1 = 0.972; closeness F1 = 0.9.
  - Weaker on fun (0.66), health (0.694) and social (0.743), driven by over-prediction. For example, "fun" was tagged on 44.4% of activities vs. 10.4% by humans.
  - Fleiss' κ ranged from 0.556 to 0.972.
- This is a model for checking cheap state annotations against a small human-labelled sample.

**Park et al. 2024, "Generative Agent Simulations of 1,000 People"**
- **Agents.** Built from 2-hour interviews with 1,052 real people. [arXiv 2411.10109](https://arxiv.org/abs/2411.10109)
- **Result.** The agents reproduced participants' General Social Survey answers 85% as accurately as the participants reproduced their own answers two weeks later. [arXiv 2411.10109](https://arxiv.org/abs/2411.10109)
  - The key methodological move is normalizing by how consistent humans are with themselves over time.
- **Other checks.** Big Five, economic games and replications of five social-science experiments. [arXiv 2411.10109](https://arxiv.org/abs/2411.10109)
- **Caution.** Press coverage reported this loosely as "85% similar". [eWeek](https://www.eweek.com/news/ai-simulation-mimics-humans-with-high-accuracy/)

**AgentSociety (Tsinghua, arXiv 2502.08691)**
- Validated by reproducing patterns from real-world social experiments: polarization, spread of inflammatory messages, effects of universal basic income, and responses to hurricane shocks. [arXiv 2502.08691](https://arxiv.org/html/2502.08691v2)
- I did not verify the specific metrics for each experiment. The UBI and polarization details come only from secondary summaries. [emergentmind](https://www.emergentmind.com/papers/2502.08691)

**Concordia**
- The NeurIPS 2024 Concordia Contest scored agents' zero-shot generalization in held-out mixed-motive scenarios. [arXiv 2512.03318](https://arxiv.org/abs/2512.03318v1)
  - Agents were ranked with Elo, then the top five met in a cross-play round.
  - Voting methods (Maximal Lotteries, Copeland, Ranked Pairs) were robustness checks for cases where rankings are non-transitive.
  - The final winner was not in the Elo top 5, a sign that the ranking was unstable.

**SimulateBench**
- Proposes **consistency** and **robustness** as believability dimensions measured through character profiles. [arXiv 2312.17115](https://arxiv.org/pdf/2312.17115)

**Critical reviews**
- **Larooij & Törnberg 2025** reviewed 35 papers on LLM-driven agent-based models. [arXiv 2504.03274](https://arxiv.org/html/2504.03274v1)
  - 15 (~43%) were validated *only* subjectively.
  - Believability judged by researchers, crowds or LLMs was the main criterion.
  - "None" ran sensitivity analyses, and most relied on a single run.
  - Using an LLM to rate its own believability is called the "worst" form of validation.
  - Untrained humans are poor at spotting AI text, so "human or AI?" tests mislead.
- **PIMMUR (arXiv 2509.18052)** is a pre-registered audit of more than 40 LLM-society papers. It lists six recurring methodological flaws, such as homogeneous agents and discarded memory. [PIMMUR](https://www.opentrain.ai/papers/the-pimmur-principles-ensuring-validity-in-collective-behavior-of-llm-societies--arxiv-2509.18052/)
- **TrustSim** found that LLMs give different answers to the same question when it is asked in different formats. [arXiv 2410.23426](https://arxiv.org/html/2410.23426v1)

### Inferences
- **Park 2023 used a pairwise/ranking design.** Raters ranked conditions side by side, which is more sensitive than absolute scores. Its countable measures (diffusion %, density, hallucination rate) are the cheapest way to get variance that is not a judge's opinion.
- **Tiny Society's 7 dimensions resemble Sotopia-Eval.** In Sotopia the judge was weakest on "believability"/"knowledge"-like dimensions (r≈0.3–0.45). That suggests "character consistency" and "relationship plausibility" may be the noisiest of the current dimensions.
- **Park 2024 suggests a noise-ceiling normalization.** Express the gap between two arms relative to the gap between two identical-config runs (test–retest).

### Gaps
- I did not check Park 2023's interview-level coding details, or how many runs the end-to-end measures were based on (it appears to be one).
- I did not verify AgentSociety's quantitative validation statistics.
- I found no paper that evaluates 5–7-agent, multi-day narrative simulations with a validated metric suite.

## Q2. How reliable are LLM judges of narrative and social realism, and how can they be fixed?

### Takeaway
LLM judges reach roughly human-level agreement on pairwise preferences in general chat. On stories they are much weaker at the level of a single item than at the level of a whole system. They show biases for position, verbosity and their own outputs.

The best-supported fixes are:
- pairwise comparison with the order swapped;
- breaking the rubric into binary checklist items;
- permuting the order of rubric options;
- using a judge from a different model family than the one that generated the stories;
- calibrating against a small human-labelled set.

### Cited Findings
- **Zheng et al. 2023 (MT-Bench/Chatbot Arena).** [arXiv 2306.05685](https://arxiv.org/abs/2306.05685)
  - GPT-4 judges reach >80% agreement with human preferences, the same level as agreement between humans.
  - The paper documents position bias (GPT-3.5 and Claude-v1 strongly favored the first position), verbosity bias and self-enhancement bias.
  - Mitigation: swap positions and count a win only when the judgment is consistent across both orders.
- **Panickssery, Bowman & Feng (NeurIPS 2024).** [arXiv 2404.13076](https://arxiv.org/abs/2404.13076v1)
  - LLM judges score their own outputs higher even when humans rate them equal.
  - The strength of this self-preference correlates linearly with the model's ability to recognize its own text. Fine-tuning to improve self-recognition increased self-preference, which suggests a causal link.
- **Chhun et al., TACL 2024, on story evaluation by LLMs.** [arXiv 2405.13769](https://arxiv.org/abs/2405.13769); [TACL](https://aclanthology.org/2024.tacl-1.62.pdf)
  - Item-level correlation with humans is moderate to weak, but system-level correlation is very high.
  - LLMs beat earlier automatic metrics at system-level evaluation, but their explanations are unsatisfactory.
- **CheckEval (Lee et al., arXiv 2403.18771, v3 Oct 2025).** [arXiv 2403.18771](https://arxiv.org/html/2403.18771v2)
  - Breaks criteria into Boolean checklist questions and aggregates the answers.
  - Raises average agreement across evaluator models by 0.45, reduces score variance and lessens sensitivity to which judge is used (12 evaluator models tested).
  - The often-cited κ≈0.72 figure comes from a secondary source and is unverified.
- **Rubric position bias (arXiv 2602.02219, Feb 2026).** [arXiv 2602.02219](https://arxiv.org/html/2602.02219v1)
  - Pointwise rubric scoring has position bias toward score options listed in certain orders.
  - Aggregating over balanced permutations of the rubric order exposes the bias and improves correlation with humans.
- **Practitioner guidance (non-peer-reviewed).** [OneUptime blog 2026](https://oneuptime.com/blog/post/2026-08-31-pointwise-vs-pairwise-llm-evaluation/view)
  - Pointwise scores suffer scale drift, central tendency (clumping), and drift between runs.
  - Recommended pattern: deterministic and pointwise floors first, then counterbalanced pairwise comparisons for relative change.
  - Include identical-response controls (A vs. A should tie) and length-controlled pairs.
- **Critiques of LLM-judged believability.** Larooij & Törnberg question claims that LLM evaluators "match humans" in simulation papers. [arXiv 2504.03274](https://arxiv.org/html/2504.03274v1)
- **Sotopia-Eval agreement varies by dimension.** It ranged from r=0.22 to r=0.71, and the judge was more lenient than humans on norm and secret violations. [arXiv 2310.11667](https://arxiv.org/html/2310.11667v2)

### Inferences
- **The 6–8 clustering is the documented central-tendency failure of pointwise 1–10 scoring.** It throws away resolution. Tiny Society should move to the following:
  1. **Pairwise A/B judging.** Compare two stories from the same world, baseline arm vs. treatment arm, judged in both orders. Report win rate, or a Bradley–Terry/TrueSkill rating across many pairs, as Park 2023 did.
  2. **Checklist items.** Use binary or count-based questions per dimension, e.g. "Does any character act on information they never observed? List each instance". Report counts per 1,000 words or per event.
  3. **A judge from a different family than the generator.** If characters are generated by Claude, judging with Sonnet risks self-preference. Add a cheap second judge (a GPT- or Gemini-class model) and average, or at least check agreement.
- **Chhun's result suggests LLM judges are adequate for comparing configurations even when noisy per story.** It supports aggregating many cheap judgments over relying on any single story score.
- **Calibration set.** Hand-label about 20–30 stories or story pairs once. Use them to measure judge–human agreement per dimension and to drop dimensions where agreement is poor.

### Gaps
- I found no study of LLM-judge reliability specifically for multi-agent simulation transcripts longer than about 10k tokens; long-context judging bias is untested here.
- I found no quantitative sample-efficiency comparison of pairwise vs. pointwise judging, i.e. how many judgments each needs to detect the same effect.

## Q3. Fine-grained, countable metrics

### Takeaway
The literature gives ready-made recipes:
- **Atomic-claim decomposition with a support check** (FActScore) for checking the final report against the event log.
- **NLI checks within sentences and between sentences** (SummaC; the Abdulhai consistency metrics) for checking persona and action consistency.
- **Asymmetric-information controls** for detecting knowledge leaks.

Because Tiny Society has a ground-truth event log and a ground-truth record of who perceived what, it can check claims against the record instead of relying on judge opinion.

### Cited Findings
- **FActScore (Min et al. 2023).** [arXiv 2305.14251](https://arxiv.org/pdf/2305.14251)
  - Splits generations into atomic facts and reports the fraction supported by a knowledge source, using retrieval plus an LLM.
  - It measures precision only, not recall.
  - Sentences often mix supported and unsupported facts (about 40% of ChatGPT cases), which is why checking whole sentences is too coarse.
- **SummaC (Laban et al.).** [arXiv 2111.09525](https://arxiv.org/pdf/2111.09525)
  - Earlier NLI-based inconsistency detection failed because NLI is trained on sentence pairs while summaries are checked against whole documents.
  - Fix: split into sentences and aggregate a sentence × sentence NLI matrix.
  - The SummaC-Conv variant reaches 74.4% balanced accuracy on the six-dataset SummaC benchmark.
- **FIZZ.** Checking at the sentence level misses details inside sentences and is confused by pronouns; it proposes NLI at the level of atomic facts. [arXiv 2404.11184](https://arxiv.org/html/2404.11184v2)
- **Abdulhai et al., NeurIPS 2025, "Consistently Simulating Human Personas with Multi-Turn RL".** [arXiv 2511.00222](https://arxiv.org/html/2511.00222v1); [NeurIPS](https://proceedings.nips.cc/paper_files/paper/2025/hash/4c91443877f8388d8190c938ac5a4d4d-Abstract-Conference.html)
  - Defines three automatic consistency metrics, each validated against human annotations:
    - **prompt-to-line:** does each utterance match the persona?
    - **line-to-line:** contradictions within a conversation.
    - **Q&A consistency.**
  - Line-to-line was uniformly high across models. Prompt-to-line and Q&A were lower and more variable, so they discriminate better.
  - RL training on these metrics cut inconsistency by more than 55%.
- **Zhou et al., "Is this the real life? Is this just fantasy?" (EMNLP 2024).** [arXiv 2403.05020](https://arxiv.org/abs/2403.05020)
  - Compares SCRIPT mode (one omniscient LLM writes all characters) with AGENTS mode (separate private information).
  - Omniscient simulation overestimates success at social goals, leaks information in cooperative scenarios, and produces overly agreeable characters.
  - A MINDREADERS control (agents given others' private information) performs close to SCRIPT, which isolates leakage as the cause.
- **Sotopia-ToM (arXiv 2605.02307, 2026).** [arXiv 2605.02307](https://arxiv.org/html/2605.02307v1)
  - Scores information management under explicit asymmetry: sharing what is needed without oversharing, and asking the right stakeholder.
  - Models tend to exchange either most of their knowledge or none of it.
- **Park 2023 as a precedent for countable errors.** It reported a hallucination rate (6 of 453), embellishment and retrieval failures. [arXiv 2304.03442](https://arxiv.org/html/2304.03442v2)

### Inferences (concrete metric menu for Tiny Society; my design, not from a source)
1. **Knowledge-leak rate**
   - For each action or utterance, extract the facts it relies on.
   - Check each fact against that character's perception or memory log, i.e. whether the character observed it or was told it.
   - Report leaks per 100 actions.
   - This is deterministic plus a small LLM extraction, and directly sensitive to memory and perception changes.
2. **Memory-retrieval recall probe** (Park-style interview, automated)
   - At the end of each day, ask each character 3–5 questions whose answers are in its own memory log. Score exact or LLM match against ground truth.
   - Gives a binary per question, i.e. many Bernoulli trials per run.
   - This is the most direct test of a memory-retrieval improvement.
3. **Contradiction counts**
   - Line-to-line: pairs of a character's statements that contradict, flagged by NLI or an LLM over sampled pairs.
   - Persona-to-action: prompt-to-line.
   - Per Abdulhai, prompt-to-line discriminates better.
4. **Report faithfulness**
   - Split the final report into atomic claims and check each against the event log.
   - Report unsupported-claim precision, as in FActScore.
   - Also report recall: the share of key logged events mentioned. FActScore lacks recall, so add it.
5. **Repetition and staleness**
   - Distinct-n or self-BLEU over each character's utterances.
   - Fraction of near-duplicate actions (embedding cosine above a threshold). The repo already has `engine/simulation/embeddings.py`.
6. **Event grounding**
   - The fraction of story sentences that cite or align to a logged event, using NLI entailment against the event log.

All of these produce many binary or count observations per run (hundreds of actions). That gives far more statistical power than one 1–10 score per dimension per run.

### Gaps
- I found no established, published "knowledge-leak" metric for multi-agent social simulation beyond the SCRIPT-vs-AGENTS comparison and Sotopia-ToM. The design above is extrapolated.
- I did not verify the exact formulas behind the Abdulhai metrics (only abstract and summary).
- I did not find benchmark numbers for QAGS in this session.

## Q4. Statistical design: number of runs, paired designs, variance reduction, confidence intervals

### Takeaway
Treat the evaluation as an experiment:
- Compute standard errors that are clustered by world and run.
- Pair the two arms on world, character set and seed.
- Analyze differences within each pair.
- Do a power analysis before running.

Miller (2024) gives the formulas. Paired designs, plus many binary sub-measurements per run, are the main levers for detecting small effects cheaply.

### Cited Findings
- **Miller, "Adding Error Bars to Evals" (Anthropic, arXiv 2411.00640).** [arXiv 2411.00640](https://arxiv.org/abs/2411.00640); [PDF](https://arxiv.org/pdf/2411.00640)
  - Treats eval items as drawn from a larger super-population and reports a standard error with each score.
  - Recommends analyzing paired differences at the question level when comparing two models.
  - Variance reduction: resample answers per item, and use clustered standard errors when items are grouped.
  - Recommends power analysis to decide whether an eval can test the hypothesis.
  - Argues bootstrapping is often unnecessary when the central limit theorem holds.
- **Simulation papers are weak on this.** Larooij & Törnberg note that most LLM-ABM studies use one run and none do sensitivity analysis. [arXiv 2504.03274](https://arxiv.org/html/2504.03274v1)
- **Park 2023 used rank-based tests on a within-subjects ranking.** Kruskal-Wallis with Dunn/Holm post-hoc. [arXiv 2304.03442](https://arxiv.org/html/2304.03442v2)

### Inferences (worked numbers; my arithmetic, standard formulas)
- **Unpaired sample size.** n per arm ≈ 2·(z₁₋α/₂+z₁₋β)²·σ²/δ² ≈ 15.7·σ²/δ² for α=0.05 and 80% power.
  - With a run-level SD of σ≈0.5 on a 1–10 dimension, a δ=0.25 improvement needs about 63 runs per arm. That is roughly $15–20 total, but noisy.
  - Detecting δ=0.5 needs about 16 per arm.
- **Paired sample size.** The variance of the difference is 2σ²(1−ρ). If run scores within a world correlate at ρ=0.5, the required n halves. At ρ=0.75, it quarters.
  - So always run baseline and treatment on the same world list (and the same seed, character set and event script where the engine allows). Analyze differences within each world.
- **Many binary sub-measurements per run shrink the SE far more than adding runs.** For example, 200 actions checked for leaks, or 30 memory probes per run.
  - Caveat: these observations are clustered within a run, so compute cluster-robust SEs at the run level (Miller) or bootstrap whole runs, not individual actions.
- **Pairwise judging converts each matched pair into a win/loss/tie.** A sign or binomial test then applies.
  - With a true win rate of 60%, about 200 non-tied pairs are needed for 80% power.
  - With a 70% win rate, about 45 pairs.
  - Judging each pair in both orders and over several judge samples reduces the noise added by the judge.
- **Separate simulation noise from judge noise.** Judge each story K=3 times (or with permuted rubric order) to estimate judge variance.
  - If judge variance dominates, spend on more judging (cheap) instead of more runs.
  - If simulation variance dominates, spend on more paired runs.
- **Test–retest baseline.** Run the *same* config twice per world and measure the difference distribution (an A/A test). That is the empirical noise floor and also catches a judge biased toward position or toward A/B labels.
- **Sequential testing.** Run in batches, e.g. 8 worlds × 2 runs, and use a pre-registered stopping rule (O'Brien–Fleming or SPRT-style). This lets clear wins or losses stop early. Do not peek at fixed-n p-values repeatedly.
- **Bootstrap.** With small n of worlds, use a cluster bootstrap over worlds (resample worlds, then runs within each world) for confidence intervals on the paired difference.
- **Use common random numbers where the engine allows.**
  - Fix event-casting seeds and initial states.
  - Use temperature 0 or a seeded sampler for non-agent components (event casting, the world interpreter), so only the changed component varies.
  - This raises ρ.

### Gaps
- I did not retrieve a peer-reviewed source specific to sequential testing for LLM evals. The sequential-testing advice is standard clinical/A-B practice, not taken from an LLM-eval paper.
- Tiny Society's actual ρ between paired runs is unknown and must be measured with a pilot A/A run.

## Q5. Validation against real human data or stylized social facts for small groups

### Takeaway
Large-scale validation against real data exists (Park 2024 against the General Social Survey; AgentSociety against field experiments). For small-group, multi-day narratives, the practical options are:
- comparing against stylized patterns that are known qualitatively (information diffusion, network densification, attendance vs. invitations);
- normalizing by human test–retest consistency.

The literature warns that matching qualitative patterns is a weak form of validation.

### Cited Findings
- **Park 2023 measured emergent diffusion and relationship formation as outcome statistics.** Diffusion 4%→32% and 4%→52%; density 0.167→0.74 over 2 days with 25 agents. [arXiv 2304.03442](https://arxiv.org/html/2304.03442v2)
- **Park 2024 normalized agent accuracy by human self-consistency over two weeks.** 85% of human test–retest accuracy. [arXiv 2411.10109](https://arxiv.org/abs/2411.10109)
- **AgentSociety reproduced qualitative patterns from real experiments.** Polarization, spread of inflammatory messages, UBI, hurricane response. [arXiv 2502.08691](https://arxiv.org/html/2502.08691v2)
- **Validation against "well-known patterns" is often qualitative** and argued with varying rigor. Quantitative comparisons show LLM text is longer, more polite and more articulate than human text. [arXiv 2504.03274](https://arxiv.org/html/2504.03274v1)
- **Simulations written by one omniscient model produce overly agreeable characters.** A marker of unrealism that can be measured, e.g. the conflict or refusal rate. [arXiv 2403.05020](https://arxiv.org/abs/2403.05020)
- **PIMMUR flags homogeneous agents and discarded memory** as methodological flaws that undermine claims about collective behavior. [PIMMUR](https://www.opentrain.ai/papers/the-pimmur-principles-ensuring-validity-in-collective-behavior-of-llm-societies--arxiv-2509.18052/)

### Inferences
- **Cheap stylized-fact checks for Tiny Society.** Per run, compute:
  - **Information diffusion curves:** the fraction of characters who know a seeded secret or rumor, by day.
  - **Relationship-change trajectories:** how far the relationship graph moves per day.
  - **Agreeableness and conflict rates:** the share of interactions with disagreement, refusal or negative sentiment.
  - **Behavioral diversity across characters.**
- **Flag degenerate patterns** rather than assert a "correct" value:
  - instant universal diffusion, which signals a knowledge leak;
  - monotonic relationship warming, which signals over-agreeableness;
  - zero conflict;
  - identical daily routines.
- These are useful as guardrails and sanity checks, not as a realism score, because no small-group human baseline for user-written fictional worlds exists.

### Gaps
- I found no human dataset of 5–7-person groups over about a week that would give quantitative baselines (e.g. gossip spread rates or relationship-formation timelines) usable as targets for fictional worlds. Classic social-psychology findings (e.g. homophily and propinquity effects in friendship formation) exist, but I did not retrieve sources in this session.
- I did not find published human-rated datasets of multi-agent simulation stories that could serve as a calibration set; one would have to be built by hand.
