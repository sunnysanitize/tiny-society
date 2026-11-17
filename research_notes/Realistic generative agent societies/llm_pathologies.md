# Behavioral pathologies of LLM-driven characters in social simulation and role-play, with evidence-backed mitigations

Context: Tiny Society runs 5–7 characters, each an independent LLM call (Gemini 2.5 Flash via OpenRouter, T=0.8). Each call gets a persona, memories, relationships and observations, and returns a JSON action. Observed symptoms: convergent behavior, loops across days, out-of-character (OOC) turns, too much politeness in some worlds and manufactured drama in others, knowledge leakage, invented backstory, mood swings, over-articulate "explainer" speech, and drift toward a generic helpful voice.

Source note: most sources are arXiv preprints. Where I read only an abstract or a search snippet, the finding says so. Two well-known papers (Park et al. 2023/2024) are cited from prior knowledge and were not re-fetched in this session; they are marked [prior knowledge].

---

## 1. Sycophancy, agreeableness, positivity bias and conflict avoidance

### Takeaway
Many studies find that aligned LLM agents under-produce disagreement, conflict and uncooperative behavior. Biasing prompts that say "disagree more" or "you are hostile" do not reliably fix this. The cause appears to be alignment and preference tuning, so model choice and structural mechanisms (stance state, protocol constraints, world pressure) matter more than adjectives in the prompt. When a model does try to play a negative character, it tends to replace subtle negativity with crude aggression. That fits the project's "too polite in some worlds, manufactured drama in others" pattern.

### Cited Findings
- **Agents with opposing preferences rarely disagree outright, even at the maximum preference gap.** Biasing prompts meant to counter sycophancy did not restore principled disagreement. At the largest gap, biased pairs agreed *more* than baseline, and the lowest-openness pairs had the *highest* agreement, the opposite of the hypothesis. The study tested 9 open models (Qwen3, Llama-3.x, Gemma-3), and each passed only 0–3 of 6 behavioral-coherence tests. Agents "produce the appearance of coherent social behavior" while failing deeper checks. — [Are LLM Agents Behaviorally Coherent? (arXiv 2509.03736)](https://arxiv.org/html/2509.03736v2)
- **Safety-tuned agents tend to suppress partisan or conflictual behavior, which pushes simulations toward agreeable consensus.** The authors warn that researchers may mistake this for realism. (Search snippet only.) — [Opportunities and Pitfalls of LLMs in Social Simulation (arXiv 2507.19364)](https://arxiv.org/pdf/2507.19364)
- **Negotiating agents sometimes reach deals by being overly agreeable rather than genuinely negotiating.** (Snippet.) — [EMNLP 2024, "Is this the real life? Is this just fantasy?"](https://aclanthology.org/2024.emnlp-main.1208.pdf)
- **Cooperative bias in multi-agent social dilemmas may come from fine-tuning for human values.** Cooperative and neutral prompts performed similarly, so the baseline is already cooperative. (Snippet.) — [Will Systems of LLM Agents Cooperate (arXiv 2501.16173)](https://arxiv.org/html/2501.16173)
- **Competing LLM agents spontaneously drift into cooperation.** — [Shall We Team Up (arXiv 2402.12327)](https://arxiv.org/pdf/2402.12327)
- **Vanilla-prompted LLM conversations contain far fewer inconsistent and uncollaborative behaviors than human conversations.** Neither prompt engineering nor SFT provided reliable control of these behaviors. (Snippet.) — [COCOEVAL (arXiv 2603.17094)](https://arxiv.org/pdf/2603.17094)
- **LLM user simulators show "atypical levels of patience" and unrealistically encyclopedic knowledge.** A trained discriminator identified nearly all simulated conversations as synthetic. — [Google Research, ConvApparel](https://research.google/blog/convapparel-measuring-and-bridging-the-realism-gap-in-user-simulators/)
- **Role-play fidelity falls as character morality falls ("Too Good to be Bad", Moral RolePlay benchmark, 800 characters).** Mean fidelity by moral level: Paragons 3.21, Flawed-but-Good 3.14, Egoists 2.71, Villains 2.62. The biggest drop (-0.43) comes between flawed-but-good and egoist. The most penalized traits were Hypocritical, Deceitful and Selfish. Models "substitute nuanced malevolence with superficial aggression": for example, claude-opus-4.1-thinking has characters resort to "open insults" and explosions of rage, while glm-4.6 sustains a "tense battle of wits". — [arXiv 2511.04962](https://arxiv.org/html/2511.04962v2) (ACL Findings 2026)
- **Villain RolePlay leaderboard.** glm-4.6 2.96 (1st); deepseek-v3.1-thinking 2.82; gemini-2.5-pro 2.75; o3 2.70; chatgpt-4o-latest 2.65; claude-sonnet-4.5 2.56; claude-opus-4.1 2.48; qwen3-max 2.33 (last). Arena rank is a poor predictor of villain role-play, and highly safety-aligned models are "disproportionately affected". — [arXiv 2511.04962](https://arxiv.org/html/2511.04962v2)
- **Agreeableness composition drives outcomes.** In 1,010 simulated conversations, the dyad's agreeableness composition strongly predicts shared-goal achievement, partly through the choice between cooperative and confrontational strategies. (Snippet.) — [Personality Anchoring for Social Simulation (arXiv 2606.06936)](https://arxiv.org/html/2606.06936v1)
- **"Echoing": agents drop their assigned role and mirror their partner.** Rates in agent-to-agent conversations range from 5% to 70% (2,500+ conversations, 66 configurations). Reasoning models still echo at an average of 32.8%, and more reasoning effort does not reduce it. Echoing tends to appear after 7 or more turns. A protocol-level fix (structured responses) cut it to about 9%, while prompt engineering reduced it without eliminating it. (Abstract and snippet.) — [Echoing: Identity Failures when LLM Agents Talk to Each Other (arXiv 2511.09710)](https://arxiv.org/abs/2511.09710), ICLR 2026 workshop

### Inferences
- The "volatile character offers a measured truce" symptom matches three documented effects: sycophantic reconciliation, echoing toward a calmer partner, and the alignment pull toward prosocial resolution. Adding more adjectives to the persona is unlikely to fix it, given the 2509.03736 null result for biasing prompts.
- "Manufactured drama" in other worlds is probably the flip side of the same problem: when a model is pushed to be negative, it produces overt, theatrical aggression instead of grounded friction (2511.04962). Both failures suggest grounding conflict in **explicit state** (grievances, stakes, resources and a stance variable the engine tracks) instead of asking the LLM to *feel* conflict.
- Structured-response protocols (echoing reduced to about 9%) support the engine's existing JSON-action design. A schema field such as `stance_toward_target: oppose|neutral|support`, carried forward by the engine and changed only with a cited reason, would apply the same idea.
- Gemini 2.5 Pro sits mid-pack on villain fidelity (2.75), and Flash was not tested. Less safety-heavy models such as GLM-4.6 and DeepSeek-v3.1 scored higher on negative roles, so it is worth A/B testing a GLM or DeepSeek model for the antagonistic characters.

### Gaps
- I found no study that directly measures reconciliation or truce-offering rates for OOC volatile personas, and no study that quantifies "drama inflation" as a pathology.
- I found no measured result for "conflict-forcing" prompt techniques beyond the null result for biasing prompts.
- Gemini 2.5 Flash specifically was not covered by any benchmark I found.

---

## 2. Homogeneity, persona collapse and mode collapse across agents

### Takeaway
Distinct personas often collapse to the same model judgment. Neither model size, nor thinking mode, nor role-play fine-tuning reliably fixes this. Fine-tuning and RL for role-play can *reduce* population coverage while increasing caricature. Temperature alone is a blunt tool. More promising options are verbalized sampling, personas grounded in heterogeneous real data, and engine-level diversification (assignment, scheduling, differential information).

### Cited Findings
- **"The Chameleon's Limit" tested 10 LLMs on 1,144 personas (BFI-44, against 2,058 human respondents) and 131 moral scenarios, and found persona collapse in every model.**
  - Coverage of human archetypes: Qwen3-4B 0.80, Qwen3-32B 0.64, CoSER-Llama-8B 0.16, MiniMax-M2-Her 0.06.
  - Effective Likert vocabulary: humans 3.69; CoSER-Llama-8B 1.36, with 83.7% of answers at the midpoint.
  - Every model with fidelity above 0.9 produced High-vs-Low trait differences above d=6, against a "very large" threshold of d=2. MiniMax-M2 reached d=15.7. In other words, high persona adherence came with caricature.
  - About 29% of self-introductions shared an identical template skeleton.
  - Thinking mode had no meaningful effect (coverage 0.626–0.658). Role-play SFT (Llama-3.1-8B to CoSER-Llama-8B) cut coverage sharply. RL (MiniMax-M2 to M2-Her) raised complexity from 6.5 to 22.3 but cut coverage from 0.55 to 0.06 and fidelity from 0.95 to 0.41.
  - The authors conclude the collapse "lies in the model weights."
  - Source: [arXiv 2604.24698](https://arxiv.org/html/2604.24698v1)
- **Caricature produces homogeneous narratives that miss within-persona diversity.** — [Characterizing and Evaluating Caricature in LLM Simulations (EMNLP 2023)](https://aclanthology.org/2023.emnlp-main.669.pdf)
- **LLMs "flatten" identity groups compared with 3,200 human participants across 16 demographic identities.** Assigning personas only partly approximates human differences between groups. (Cited via search snippets of follow-up papers; the primary is Wang et al. 2025.) — [Population-Aligned Persona Generation (arXiv 2509.10127)](https://arxiv.org/pdf/2509.10127); [Restoring Heterogeneity (arXiv 2604.06663)](https://arxiv.org/html/2604.06663)
- **Simulations default to an "average persona" that hides heterogeneity.** Population-aligned persona sets outperform widely used persona sets in alignment and behavioral realism. — [arXiv 2509.10127](https://arxiv.org/html/2509.10127v1)
- **Mode collapse comes from "typicality bias" in human preference data.** Verbalized Sampling, which asks the model to output several candidates with probabilities and then samples among them, is training-free and stacks with temperature and top-p. In persuasion-dialogue simulation it produced donation distributions closer to human ones and more linguistic diversity. — [Verbalized Sampling (arXiv 2510.01171, ICML 2026)](https://icml.cc/virtual/2026/poster/60489)
- **Temperature flattens the distribution indiscriminately.** At the entropy needed to break consensus, incoherent tokens appear. (Snippet.) — [Beyond the Hivemind (arXiv 2608.02618)](https://arxiv.org/pdf/2608.02618)
- **The same persona asked the same question returns the same answer on more than half of items, regardless of standard decoding temperature.** The logit gap is too large. (Snippet.) — [Instruction-Tuned Language Models Cannot Sample (arXiv 2607.25292)](https://www.alphaxiv.org/abs/2607.25292.md)
- **LLM populations develop shared conventions and collective biases through interaction.** This is a mechanism for convergence in multi-agent settings. — [Emergent social conventions and collective bias in LLM populations (Science Advances)](https://www.science.org/doi/10.1126/sciadv.adu9368)

### Inferences
- "Everyone interrogates the same bystander" is probably a mix of model-level collapse (every character computes the same "most salient" action from near-identical context) and shared context (every agent sees the same observation feed). Engine-side fixes are likely to beat prompt fixes:
  - give each agent differentiated information (only what it perceived);
  - add an engine-side "target crowding" penalty or soft constraint that tells later agents who is already engaging whom;
  - use per-character action priors or goals that point at different targets;
  - use Verbalized-Sampling-style generation (k candidate actions with probabilities, sampled by the engine).
- Raising temperature above 0.8 is unlikely to help and may damage JSON validity and coherence.
- Do not adopt role-play fine-tuned models expecting diversity. The Chameleon's Limit shows they can collapse *more*.

### Gaps
- I found no study measuring action-target convergence in small (5–7 agent) societies.
- I found no measured comparison of Verbalized Sampling for agent *action selection*, as opposed to text responses.

---

## 3. Persona drift and inconsistency over long interactions

### Takeaway
Persona fidelity measurably decays within about 8 turns in self-chat, and over 100+ round dialogues, especially goal-directed ones. Personas regress toward the model's default assistant behavior. Local turn-to-turn coherence stays high while global persona adherence fails, so turn-level checks miss drift. Mitigations with measured effects: re-anchoring (attention-level split-softmax), multi-turn RL with consistency rewards (more than 55% less inconsistency), and structured protocols.

### Cited Findings
- **Significant instruction or persona drift within 8 rounds of self-chat for LLaMA2-chat-70B and GPT-3.5.** The authors attribute it partly to attention decay over the system prompt. Split-softmax, an attention-level fix, "compares favorably against two strong baselines". (Abstract only; no exact numbers retrieved.) — [Measuring and Controlling Persona Drift (arXiv 2402.10962)](https://arxiv.org/abs/2402.10962)
- **Across 7 open and closed LLMs and dialogues of over 100 rounds, "persona fidelity degrades over the course of dialogues, especially in goal-oriented conversations".** As fidelity fades, persona responses converge toward non-persona baseline responses, which is drift toward the generic assistant. (Abstract only.) — [Persistent Personas? (arXiv 2512.12775)](https://arxiv.org/abs/2512.12775)
- **Off-the-shelf LLM persona simulators drift, contradict earlier statements, or abandon role-appropriate behavior.**
  - Line-to-line consistency was uniformly high, while prompt-to-line and Q&A consistency revealed persistent global failures.
  - Multi-turn RL (PPO) with these consistency metrics as reward reduced inconsistency by more than 55%. It beat SFT and KTO, and stayed stable as dialogues got longer.
  - Source: [Consistently Simulating Human Personas with Multi-Turn RL (NeurIPS 2025, arXiv 2511.00222)](https://arxiv.org/abs/2511.00222v1)
- **SPASM measures drift by comparing per-turn answers to persona probes against a pre-conversation baseline, using embedding distance.** (Snippet.) — [arXiv 2604.09212](https://arxiv.org/pdf/2604.09212)
- **A 2026 survey describes character personality drift or collapse in long conversations as an open problem.** — [Role-Playing Agents Driven by LLMs survey (arXiv 2601.10122)](https://arxiv.org/pdf/2601.10122)
- **Echoing (Section 1) is a persona-drift mechanism specific to agent-to-agent conversation.** It appears after 7 or more turns. — [arXiv 2511.09710](https://arxiv.org/abs/2511.09710)

### Inferences
- The "generic helpful voice" drift is the documented regression toward non-persona baseline (2512.12775). Mitigations available at inference time:
  - re-inject a compact persona anchor (voice and speech samples, not only trait adjectives) close to the generation point, at the end of the prompt, to counter attention decay;
  - keep raw dialogue history short and summarize it;
  - score each candidate action against the persona with a cheap judge ("prompt-to-line" style) and resample on failure.
- Mood swings are partly a missing-state problem. If mood is regenerated freely each turn, drift is guaranteed. Make mood an engine-owned variable with bounded per-turn deltas, and let the LLM only *propose* changes, justified by events.

### Gaps
- I did not obtain split-softmax effect sizes or exact per-model decay curves; only the abstracts were read.
- I found no drift data for Gemini 2.5 Flash specifically.

---

## 4. Hallucinated knowledge and knowledge leakage (characters knowing what they shouldn't, invented backstory)

### Takeaway
Character hallucination is well documented. Even GPT-4-class models answer "future" or unwitnessed-event questions correctly only about 51% of the time or less. Retrieval restricted to what the character could know (RAG-cutoff, narrative experts) and "protective experiences" (training or prompting the character to express ignorance) are the evidenced mitigations. Refusal-style protection can hurt storytelling quality.

### Cited Findings
- **TimeChara (ACL Findings 2024): 10,895 instances, 14 characters, point-in-time knowledge.** GPT-4 and GPT-4 Turbo struggle with point-in-time hallucination, and baselines reach 51% or less on "future" questions.
  - Mitigation: NARRATIVE-EXPERTS, which decomposes reasoning into temporal and spatial experts. Its RAG-cutoff variant, which retrieves only events up to the character's point in time, consistently outperformed baselines across query types.
  - The LLM judge tended to penalize correct expressions of unawareness and preferred "omniscient", verbose portrayals. This is a caution for using LLM judges in this setting.
  - Sources: [TimeChara project](https://ahnjaewoo.github.io/timechara/); [ACL Anthology](https://aclanthology.org/2024.findings-acl.197/); [arXiv 2405.18027](https://arxiv.org/pdf/2405.18027)
- **Character-LLM (Shao et al. 2023): fewer than 100 "protective" scenes per character (examples of the character declining knowledge it shouldn't have) effectively reduce hallucination without hurting other portrayal abilities.** — [arXiv 2310.10158](https://arxiv.org/pdf/2310.10158)
- **RoleBreak: query sparsity and role-query conflict are the main drivers of character hallucination.** Refusal-based defenses such as Character-LLM's often hamper storytelling quality. — [arXiv 2409.16727](https://arxiv.org/pdf/2409.16727)
- **RoleFact modulates the influence of parametric knowledge using a pre-calibrated confidence threshold.** (Snippet.) — [Mitigating Hallucination in Fictional Character Role-Play (arXiv 2406.17260)](https://emergentmind.com/papers/2406.17260)
- **LLM simulators show "unrealistic, sometimes encyclopedic knowledge".** — [Google Research ConvApparel](https://research.google/blog/convapparel-measuring-and-bridging-the-realism-gap-in-user-simulators/)

### Inferences
- In Tiny Society the analogue of "future knowledge" is knowledge of events the character did not witness. RAG-cutoff maps directly onto two engine rules: retrieve memories only from the agent's own perception log, and never place the global event feed in its prompt.
- Add a schema field such as `knowledge_basis` (seen / told_by:X / inferred) for claims made in speech. A cheap validator can then reject statements that reference events not in the agent's perceived set.
- For invented family ties and backstory, put an explicit "facts not in your profile are unknown; do not invent relatives or history" clause in the prompt, plus a few protective examples (Character-LLM). Better still, have the engine maintain a canonical fact sheet, and require that any new backstory fact be committed to it so it stays consistent afterwards.

### Gaps
- I found no measured study of hallucinated *relationships* or backstory in multi-agent sandbox simulations specifically.

---

## 5. Drama inflation vs flatness; repetition loops; over-explaining

### Takeaway
The evidence is indirect but consistent. LLM dialogue is longer per turn and less human-like than real dialogue. Reasoning or chain-of-thought text leaks a formal, structured "explainer" style into role-play. Simulators show excessive patience and continuation bias. I found no paper that directly measures cross-day repetition loops in agent societies.

### Cited Findings
- **Chain-of-thought degraded role-play on 4 of 6 benchmarks (CroSS-MR, HPD, SocialBench, CharacterEval) across 24 LLMs, and helped on InCharacter and RoleBench.** The causes were *attention diversion* and *linguistic style drift* (reasoning is structured and formal). Reasoning-distilled models role-played worse than their base models. — [Reasoning Does Not Necessarily Improve Role-Playing Ability (ACL Findings 2025, arXiv 2502.16940)](https://aclanthology.org/2025.findings-acl.537)
- **Thinking mode slightly lowered villain fidelity at every non-paragon level.** Without and with reasoning: L2 3.14 to 3.09, L3 2.74 to 2.69, L4 2.59 to 2.57. — [arXiv 2511.04962](https://arxiv.org/html/2511.04962v2)
- **LLM agents use fewer turns but significantly longer responses per turn than humans.** — [Human vs. Agent in Task-Oriented Conversations (arXiv 2509.17619)](https://arxiv.org/pdf/2509.17619)
- **LLMs predicted that a conversation continues 87.1–98.6% of the time, regardless of whether the human actually ended it.** They capture semantics but struggle with syntactic and stylistic components of human turns. (Snippet.) — [Real or Robotic? (arXiv 2409.08330)](https://alphaxiv.org/overview/2409.08330v2)
- **Modern simulators are "identified nearly all" as synthetic by a discriminator using statistics such as words per turn.** — [ConvApparel](https://research.google/blog/convapparel-measuring-and-bridging-the-realism-gap-in-user-simulators/)
- **Role-play models substitute "superficial aggression" for nuanced negativity.** This is a drama-inflation mechanism. — [arXiv 2511.04962](https://arxiv.org/html/2511.04962v2)

### Inferences
- The over-articulate "explanation" speech is consistent with style drift from reasoning fields. If the JSON schema puts a `reasoning` field *before* `speech`, the reasoning register may bleed into the dialogue. The fix is to keep private reasoning short and in character (see Section 6, Thinking in Character), and to give speech its own constraints: maximum word count, register examples, and permission to be curt, evasive or ungrammatical.
- Repetition loops across days are likely to come from the same context producing the same action (collapse) plus memory retrieval surfacing the same salient items. Engine-side novelty checks (embedding similarity of the action against the agent's last N actions, with a resample above a threshold) are the standard remedy. I found no paper quantifying it in this setting.

### Gaps
- I found no study that directly measures repetition loops in multi-day agent societies, or "drama level" calibration.

---

## 6. Techniques: private reasoning, critics, best-of-n, belief state, sampling, model choice, fine-tuning

### Takeaway
- **Private reasoning:** helps only when it is *in character*. Generic chain-of-thought hurts (Section 5). Role-Aware Reasoning (profile-anchored, style-matched reasoning) and "inner thoughts plus motivations" are evidenced improvements.
- **Critics and rewards:** consistency metrics used as reward or filter give large measured gains (more than 55% less inconsistency with RL). The same metrics can serve as a best-of-n scorer at inference time, but I found no paper measuring that directly.
- **Structured protocols:** these cut identity failures (echoing about 9%).
- **Model choice:** general capability does not predict role-play quality, and leaderboards conflict.
- **Fine-tuned role-play models:** better fidelity on literary characters, but they can collapse population diversity.

### Cited Findings
- **Role-Aware Reasoning (RAR, NeurIPS 2025) has two stages.** Role Identity Activation keeps the profile (emotion, experience, standpoint, motivation) explicitly in the reasoning, which counters attention diversion. Reasoning Style Optimization distills in-character reasoning style, which counters style drift. Ablating any of the four elements hurt persona and emotional consistency. The authors report significant gains over SFT, RAG, Neeko and CharacterGLM on LLaMA-3-8B with LoRA. (Exact numbers not retrieved.) — [Thinking in Character (arXiv 2506.01748)](https://arxiv.org/html/2506.01748v1)
- **CoSER (ICML 2025) uses "given-circumstance acting" over 29,798 conversations from 771 books.**
  - CoSER-70B (Llama-3.1) matched or surpassed GPT-4o, with 75.80% on InCharacter and 93.47% on LifeChoice.
  - Enabling *inner thoughts* and providing *motivations* improved role-play agents at test time.
  - Sources: [arXiv 2502.09082](https://arxiv.org/abs/2502.09082v3); [ICML slides](https://icml.cc/media/icml-2025/Slides/46115.pdf)
- **Caution: the same CoSER fine-tunes showed the worst persona-population collapse (coverage 0.16 for CoSER-Llama-8B).** — [arXiv 2604.24698](https://arxiv.org/html/2604.24698v1)
- **Consistency metrics (prompt-to-line, line-to-line, Q&A probing) were validated against human annotations and used as RL reward: more than 55% less inconsistency.** The same metrics work as an LLM-judge filter. — [arXiv 2511.00222](https://arxiv.org/abs/2511.00222v1)
- **Structured response protocols reduced agent-to-agent echoing to about 9%; prompt engineering reduced it only partly.** — [arXiv 2511.09710](https://arxiv.org/abs/2511.09710)
- **Sampling.** Verbalized Sampling stacks with temperature and top-p. High temperature alone harms coherence before it restores diversity. — [arXiv 2510.01171](https://icml.cc/virtual/2026/poster/60489); [arXiv 2608.02618](https://arxiv.org/pdf/2608.02618)
- **Thinking or reasoning mode** did not improve persona diversity (Qwen3-32B) and slightly reduced villain fidelity. — [arXiv 2604.24698](https://arxiv.org/html/2604.24698v1); [arXiv 2511.04962](https://arxiv.org/html/2511.04962v2)
- **Model choice: Arena rank does not predict villain role-play.** GLM-4.6 and DeepSeek-v3.1-thinking led; Gemini-2.5-pro placed 4th; the Claude models ranked lower; Qwen3-max was last. — [arXiv 2511.04962](https://arxiv.org/html/2511.04962v2)
- **Model choice: role-play leaderboards disagree as of late 2026.**
  - RP-Bench composite (May 2026): Claude Opus 4.6 1st, Sonnet 4.5 2nd, Gemini 3.1 Pro 15th.
  - lmmarketcap: Claude Opus 4.6 1st, Gemini 3.1 Pro Preview 2nd.
  - BenchLM (Nov 2026): Qwen3.5-27B 1st.
  - MiniMax role-play-bench (older): gpt-5.1 3rd, gemini-3-pro 5th, claude-opus-4.5 6th.
  - These are mostly community or aggregator leaderboards with opaque methods, so they are weak evidence. Sources: [RP-Bench GitHub](https://github.com/LeviTheWeasel/rp-benchmark); [lmmarketcap](https://lmmarketcap.com/leaderboards/best-roleplay); [BenchLM](https://benchlm.ai/best/roleplay); [MiniMax role-play-bench (HF)](https://huggingface.co/datasets/MiniMaxAI/role-play-bench)
- **Explicit memory, reflection and planning.** [prior knowledge] In Generative Agents (Park et al. 2023), ablating memory, reflection or planning each reduced human-rated believability, and the full architecture scored highest. Rich interview-based personas (Park et al. 2024, 1,052 people) replicated participants' General Social Survey answers at about 85% of the participants' own two-week test-retest consistency. — [arXiv 2304.03442](https://arxiv.org/abs/2304.03442); [arXiv 2411.10109](https://arxiv.org/abs/2411.10109)

### Inferences (recommended stack for Tiny Society, ordered by expected value and cost)
1. **Engine-owned state over LLM-generated state.** Mood, stance and grudges, known facts and perceived events, and the backstory fact sheet are all engine variables with bounded deltas. The LLM proposes changes with justifications. This addresses mood swings, invented backstory and knowledge leakage. (By analogy to RAG-cutoff, structured protocols and Park's memory and reflection.)
2. **Split private in-character thought from public action,** with the thought written in the character's voice and anchored to profile elements (RAR, CoSER "inner thoughts plus motivations"). Keep it short. Avoid generic analytic chain-of-thought; the evidence says it hurts.
3. **Persona-consistency critic plus resample (best-of-2 or 3).** A cheap judge scores prompt-to-line consistency, knowledge validity and novelty against the last N actions. This is an inference-time version of the 2511.00222 reward. Caveat from TimeChara: LLM judges favor verbose, omniscient answers, so tell the judge to reward terseness and in-character ignorance.
4. **Diversity at the engine level.** Use per-agent differentiated observations, target-crowding awareness, and verbalized k-candidate action proposals sampled by the engine, rather than raising temperature.
5. **Voice anchors.** Use 2–4 short speech samples per character placed late in the prompt, plus speech length limits. This counters the drift toward the assistant voice and the explainer style.
6. **Model trial.** A/B test against GLM-4.6 or newer and DeepSeek-V3.x, which are strong on negative roles, and against Claude or Gemini Pro-tier models, which rank high on several general role-play leaderboards. Measure on project-specific metrics: OOC rate, target convergence, repetition. Avoid reasoning-distilled models for the speech step.
7. **Fine-tuning** (CoSER or RAR-style) is the highest-cost option and can reduce population diversity, so it is not recommended as a first step.

### Gaps
- I found no paper directly measuring best-of-n with a persona scorer at inference time; the evidence is the RL-reward version.
- I found no peer-reviewed 2025–2026 benchmark that includes Gemini 2.5 Flash for role-play consistency.
- The community leaderboards conflict and list some model names I could not verify, so treat model rankings as provisional.
- The split-softmax and RAR exact effect sizes were not retrieved; only abstracts and summaries were read.
