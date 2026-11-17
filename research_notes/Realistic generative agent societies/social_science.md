# Social-science and psychology models for a small LLM-driven social simulation ("Tiny Society")

Notation: sources marked (†) are canonical papers cited by DOI from the researcher's background knowledge and were **not re-fetched in this session**; their numbers should be spot-checked before being quoted in user-facing text. Unmarked sources were surfaced and checked through search this session. "Sim mapping" bullets under Inferences are design suggestions, not findings.

Engine context: 5–7 characters, up to 7 days, signed directional affinity in [-1,1] updated by intent-verb bids, threshold-derived relationship types, 0.01/day decay, perception step, a single volatile mood label, audience-limited observations, no retelling, per-topic stances drifting to group mean.

---

## 1. Gossip and information diffusion in small groups

### Takeaway
Talk about absent people is the default content of conversation (about 2/3 of conversation time, and about 85% in a 2025 replication), so in a realistic tiny society nearly every observed social event should be a candidate for retelling. A deterministic layer can do this with a per-dyad independent-cascade retelling probability, a "spreader → stifler" stop rule (Maki–Thompson), and retelling distortion that drops detail and sharpens valence (Allport & Postman leveling/sharpening/assimilation). Social and negative information spreads further and more faithfully than neutral information.

### Cited Findings
**How much talk is gossip**
- Dunbar, Marriott & Duncan (1997, *Human Nature* 8(3)) coded 45 casual conversations in public settings. Social and personal topics, loosely "gossip", took about two-thirds of conversation time, with little variation by age or sex — [Szala et al. 2025 revisit, Cambridge](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/61BF5C91583F04053BE9471ED96FAE1D/S1866980824000541a.pdf/how-much-conversation-content-is-actually-social-human-conversational-behaviour-revisited.pdf); [Scribd copy of original](https://es.scribd.com/document/235689769/Dunbar-Duncan-And-Marriot-1997-Human-Conversational-Behavior)
- A 2025 replication (Szala et al.) found about 85% of conversation content was social. Its authors note that the 1997 sample was small and limited in composition — [Oxford Psych listing](https://www.psy.ox.ac.uk/publications/publication_modal/2080635)
- Where the 1997 study found sex differences, the authors read them as women's concern with networking and men's concern with self-display — [UPEI intro psych summary](https://pressbooks.library.upei.ca/upeiintropsychology/?p=921)
- Robbins & Karan (2020, *Soc. Psych. & Personality Sci.*) used EAR audio sampling of 467 people. They found about 52 minutes of gossip per day, mostly neutral in valence. Negative gossip (about 15%) outnumbered positive (about 9%), and most gossip was about acquaintances rather than celebrities (†) — [doi:10.1177/1948550619837000](https://doi.org/10.1177/1948550619837000)

**Who passes on what, and why**
- Kniffin & Wilson (2005, *Human Nature* 16(3):278–292) argue from multilevel selection that gossip enforces group-beneficial norms (for example, against free-riders). This holds when rewards are shared at the group level and the group is small enough for members to monitor each other. Self-interested gossip predominates when those conditions fail — [abstract record](https://data.zhenzhi.com/details/1/860457736); DOI 10.1007/s12110-005-1011-6. *The case-study details (a collegiate rowing team) could not be confirmed from the fetched abstract.*
- Feinberg, Willer, Stellar & Keltner (2012, *JPSP*) studied "prosocial gossip". People who watched someone behave unfairly spent their own money to warn the next partner, and doing so reduced their frustration. Higher-prosociality people gossiped more (†) — [doi:10.1037/a0026650](https://doi.org/10.1037/a0026650)
- Mesoudi, Whiten & Dunbar (2006, *Brit. J. Psych.*) found that in transmission chains, social-gossip content was transmitted more accurately and in greater quantity than equivalent non-social content (†) — [doi:10.1348/000712605X85871](https://doi.org/10.1348/000712605X85871)
- Secrets: the average person currently keeps about 13 secrets from a 38-category list (Common Secrets Questionnaire, Slepian et al. 2017). Separately, people keep about 15 secrets for others. More shame about a secret meant more frequent recurrent thoughts about it (about +2 times/month per scale point) — [Slepian & Kalokerinos PDF](https://www.columbia.edu/~ms4992/Pubs/in-press_Slepian-Kalokerinos_SPPC.pdf); [Columbia Business School](https://business.columbia.edu/insights/business-society/game-secrets). *A widely repeated "about 5 secrets never told to anyone" figure could not be confirmed.*

**Distortion in retelling**
- Allport & Postman (1947, *The Psychology of Rumor*) named three serial-reproduction processes. **Leveling**: the story gets shorter and simpler, quickly. **Sharpening**: a few retained details are selected and often exaggerated. **Assimilation**: the content is distorted toward the teller's expectations, motives and prejudices — [Wikipedia: Rumor](https://en.wikipedia.org/wiki/Rumor); [Encyclopedia.com](https://www.encyclopedia.com/social-sciences/applied-and-social-sciences-magazines/rumor)
- Field (non-lab) studies show much less distortion than Allport & Postman's lab chains. In the lab, recipients could not ask questions and had no stake in accuracy — [Wikipedia: Rumor](https://en.wikipedia.org/wiki/Rumor). *Contested: the often-quoted figure of "about 70% of details lost in the first 5–6 transmissions" could not be confirmed in any fetched source and should be treated as unverified.*

**Computational diffusion models**
- **Daley–Kendall (DK)** and **Maki–Thompson (MT)** rumor models use ignorant/spreader/stifler states (≈ SIR). In MT, a spreader who contacts someone who already knows becomes a stifler; in DK, both parties become stiflers. In the large-N limit of MT, the fraction who never hear the rumor converges to about 0.203, i.e. about 20% never hear it — [arXiv 2002.06821](https://arxiv.org/pdf/2002.06821); [arXiv 1004.1391](https://ar5iv.arxiv.org/html/1004.1391)
- **Independent cascade** (Kempe, Kleinberg & Tardos 2003): when node u becomes active, it gets one chance to activate each neighbor v, with probability p_uv (†) — [doi:10.1145/956750.956769](https://doi.org/10.1145/956750.956769)
- Valence and arousal predict sharing. Berger & Milkman (2012, *J. Marketing Research*) found that high-arousal content (awe, anger, anxiety) is shared more than low-arousal content (sadness), and that positive content is shared slightly more than negative content in news articles (†) — [doi:10.1509/jmr.10.0353](https://doi.org/10.1509/jmr.10.0353)

### Inferences
- **Sim mapping: add a "knowledge item" object.** Each witnessed event becomes a fact `{id, subject(s), about, valence, arousal, secrecy∈{public, private, secret}, source, fidelity=1.0, hops=0}` stored per character. This is what is missing today.
- **Retelling probability per encounter (independent cascade).** When A interacts with B and A holds fact f about subject S (where S ≠ B):
  `p_tell = base × novelty(B doesn't know) × juiciness × trust(A→B) × (1 − secrecy_penalty) × norm_bonus`.
  Reasonable defaults: base ≈ 0.3–0.5 per relevant conversation (gossip fills about 2/3 of talk); juiciness = 0.5 + 0.5·|valence|·arousal; trust = sigmoid(affinity A→B); secrecy_penalty = 0 (public), 0.5 (private), 0.85 (explicitly secret); norm_bonus = 1.5 when S broke a group norm (Kniffin & Wilson, Feinberg).
  If S is a close friend of A, multiply by about 0.5 for negative facts, since people protect allies. If S is a rival, multiply by about 1.5 for negative facts. The ally/rival multipliers are design guesses, not sourced numbers.
- **Stop rule (Maki–Thompson):** if A tries to tell B and B already knows, A becomes a stifler for f with probability about 0.5–1.0. This stops a 6-person group from re-telling the same item forever, and it naturally leaves some people out of the loop.
- **Distortion on each hop:** fidelity *= 0.8–0.9. Then (a) drop the lowest-salience detail (leveling); (b) push valence away from 0 by 10–20% (sharpening); (c) let the teller's affinity toward S bias the valence (assimilation). An LLM can do the actual rewording, constrained by these deterministic deltas. The per-hop retention is a design value, because the 70% figure is unverified.
- **Confession case:** a confession to one person should create a `secret` fact. It still leaks with about 0.15 × (other modifiers) per opportunity, and leaks much faster if the confidant's affinity toward the confessor drops or if the confidant is low in Agreeableness or Honesty-Humility.
- **Learning about yourself:** when the subject learns they were gossiped about, apply a betrayal bid to subject→teller that is larger than the original act's effect, as justified by the negativity bias in Section 3.

### Gaps
- No verified per-hop retention rate for naturalistic retelling; the "70% lost" figure is unconfirmed.
- No empirical per-dyad transmission probability for small face-to-face groups was found; the values above are design parameters.
- The Kniffin & Wilson case-study specifics were not retrievable.

---

## 2. Emotion: appraisal, dimensions, decay/inertia, contagion, and computational agents

### Takeaway
Represent affect in three layers with different time constants, as in ALMA. **Emotions** are short-lived appraisal outputs. **Mood** is a slowly moving PAD (pleasure-arousal-dominance) vector, pulled by emotions and decaying toward a personality-derived baseline. **Personality** is fixed. Emotion durations vary over orders of magnitude, from shame at about 30 minutes to sadness at about 120 hours, mainly driven by rumination and event importance. That variation argues for per-emotion half-lives rather than "overwrite mood every action".

### Cited Findings
**Appraisal theories**
- OCC (Ortony, Clore & Collins 1988, *The Cognitive Structure of Emotions*) defines 22 emotion types from three appraisal branches: consequences of events (desirability for self or for others), actions of agents (praiseworthiness), and aspects of objects (appealingness). Examples: joy/distress, hope/fear, pride/shame, admiration/reproach, gratitude/anger, happy-for/resentment, gloating/pity (†) — [doi:10.1017/CBO9780511571299](https://doi.org/10.1017/CBO9780511571299)
- Scherer's Component Process Model: a sequence of stimulus evaluation checks (relevance, implications, coping potential, normative significance) (†) — [Scherer 2009, doi:10.1080/02699930902928969](https://doi.org/10.1080/02699930902928969)
- EMA (Marsella & Gratch 2009) is a computational appraisal model. Appraisal variables (desirability, likelihood, causal attribution, controllability, changeability) are re-computed as the agent's interpretation of events changes, and the agent selects coping strategies (problem-focused vs emotion-focused such as denial or shifting blame) (†) — [doi:10.1016/j.cogsys.2008.03.005](https://doi.org/10.1016/j.cogsys.2008.03.005)

**Dimensional models and the ALMA layered model**
- PAD (Mehrabian 1996): pleasure, arousal and dominance, each in [-1,1]. Mehrabian also gave regressions from Big Five to PAD temperament (†) — [doi:10.1007/BF02686918](https://doi.org/10.1007/BF02686918)
- ALMA (Gebhard 2005, AAMAS) combines short-term emotions (24 OCC-based types), medium-term mood (a PAD point; the 8 octants are named mood types such as Exuberant, Bored, Anxious, Hostile, Relaxed, Dependent, Disdainful, Docile; intensity is the distance from the origin), and long-term personality (Big Five). The default mood is derived from Big Five via PAD correlations, and personality regulates emotion intensity and decay — [ALMA project page](https://alma.dfki.de/); [slides](https://sambuz.com/doc/alma-a-layered-model-of-affect-ppt-presentation-664816); [paper PDF](https://cs.huji.ac.il/course/2005/aisemin/articles2006/docs/pa1a3_29.pdf)
- ALMA mood update (†, from the paper): active emotions are mapped to PAD and their centroid acts as a "virtual emotion center". If the current mood lies between the origin and that center, mood is pulled toward the center ("pull"). If the mood is beyond the center, it is pushed further out ("push"; reinforcement). Without emotions, mood decays back to the default mood over time. In ALMA's default configuration the return takes on the order of minutes, but the decay time is configurable. Separately, Gebhard & Kipp (2006) found that users rated the generated emotions and moods as plausible — [paper PDF](https://cs.huji.ac.il/course/2005/aisemin/articles2006/docs/pa1a3_29.pdf); [Springer chapter](https://www.springerprofessional.de/are-computer-generated-emotions-and-moods-plausible-to-humans/1232988)
- Mehrabian's Big Five → PAD temperament mapping, as used in ALMA (†, from the paper):
  P = 0.21·E + 0.59·A + 0.19·N
  A = 0.15·O + 0.30·A − 0.57·N
  D = 0.25·O + 0.17·C + 0.60·E − 0.32·A
  Here N is coded as *emotional stability* in Mehrabian's formulation. Verify the sign convention before use — [paper PDF](https://cs.huji.ac.il/course/2005/aisemin/articles2006/docs/pa1a3_29.pdf)

**Duration, decay and inertia**
- Verduyn & Lavrijsen (2015, *Motivation & Emotion*, DOI 10.1007/s11031-014-9445-y): 233 students reported the durations of recent episodes of 27 emotions. Sadness lasted longest (mean about 120 h), shame shortest (about 30 min). Surprise, fear, disgust, boredom, irritation and relief were also short. Hope, exhaustion, pride and anger lasted relatively long. Rumination was the main driver of duration, along with event importance. The study relied on retrospective recall, and the "240× longer" headline is a ratio derived from those averages — [ScienceDaily](https://www.sciencedaily.com/releases/2014/10/141030133119.htm); [BPS Research Digest](https://www.bps.org.uk/research-digest/why-sadness-lasts-longer-other-emotions)
- Emotional inertia means current affect is predicted by prior affect, i.e. a lag-1 autoregressive coefficient. Kuppens, Allen & Sheeber (2010, *Psychological Science*) found higher inertia of both positive and negative affect in people with low self-esteem and in people with depression. Inertia prospectively predicted depression onset 2.5 years later in adolescents (Kuppens et al. 2012). Inertia is higher with higher neuroticism (Brose et al. 2015) — [PMC2901421](https://pmc.ncbi.nlm.nih.gov/articles/PMC2901421); [Unimelb record](https://findanexpert.unimelb.edu.au/scholarlywork/323690-emotional-inertia-and-psychological-maladjustment)
- Houben, Van den Noortgate & Kuppens (2015, *Psych. Bulletin*) meta-analysed 79 studies. Psychological well-being was associated with lower emotional variability, lower instability and lower inertia (†) — [doi:10.1037/a0038822](https://doi.org/10.1037/a0038822)

**Contagion**
- Hatfield, Cacioppo & Rapson (1993) define primitive emotional contagion as automatic mimicry of expressions and posture, followed by afferent feedback that produces convergent emotion (†) — [doi:10.1111/1467-8721.ep10770953](https://doi.org/10.1111/1467-8721.ep10770953)
- Kramer, Guillory & Hancock (2014, *PNAS*) reduced positive or negative posts in feeds for about 689,000 Facebook users. Users' own posts shifted in the same direction, but the effect size was very small (d ≈ 0.001–0.02). The study is ethically contested (†) — [doi:10.1073/pnas.1320040111](https://doi.org/10.1073/pnas.1320040111)
- Barsade (2002, *ASQ*): in work groups, a confederate's pleasant or unpleasant mood spread to group members and changed cooperation and conflict (†) — [doi:10.2307/3094912](https://doi.org/10.2307/3094912)

**Agent architectures**
- FAtiMA is OCC-based appraisal with an emotional state plus mood and with emotion-specific decay. ALMA (above) is the canonical PAD layering. EMA is appraisal plus coping. All three implement emotions as decaying intensities rather than replaced labels (†) — [FAtiMA Modular, Dias, Mascarenhas & Paiva 2014, doi:10.1007/978-3-319-12973-0_3](https://doi.org/10.1007/978-3-319-12973-0_3)
- Humanoid Agents (Wang et al., EMNLP 2023 demo) gives each agent an emotion label and a relationship-closeness value updated after conversations, alongside basic needs — [arXiv 2310.05418](https://arxiv.org/abs/2310.05418v1); [GitHub](https://github.com/HumanoidAgents/HumanoidAgents)

### Inferences
- **Sim mapping: replace the single overwritten mood label with this:**
  - `emotions[]`: each `{type (OCC), intensity 0–1, target, t0}` with intensity(t) = I0·exp(−ln2·Δt/h_type). Suggested half-lives scaled from Verduyn: shame, surprise, disgust, fear, irritation ≈ 0.5–2 h; anger, pride, hope ≈ 6–12 h; sadness or grief ≈ 1–3 days. Rumination extends the half-life: ×(1 + 0.5·Neuroticism + importance).
  - `mood` = PAD vector. At each tick, `mood ← baseline + ρ·(mood − baseline) + κ·Σ(PAD(emotion_i)·intensity_i)`. ρ is the inertia: about 0.6–0.8 per half-day tick, and higher for high-N characters. κ is about 0.2–0.4. The baseline comes from the Big Five via the Mehrabian mapping.
  - Overnight reset: apply 2–3 extra decay steps toward baseline (sleep), so day-to-day mood is mostly baseline plus a carried residue of high-importance negative events.
  - The LLM receives a mood *label* derived from the PAD octant and intensity, but the label is computed, not written by the LLM. This directly fixes "mood swings implausibly".
- **Appraisal via LLM, numbers via code.** Ask the LLM to output OCC appraisal variables for the receiver (desirability for self, praiseworthiness of the actor's act, likelihood). Code then maps them to an emotion type and intensity. This fits the existing perception step.
- **Contagion:** each co-present tick, nudge P and A toward the co-present group mean by about 0.05·(1 + affinity)·susceptibility, where susceptibility is higher for high A and N. Keep the nudge small, consistent with the small effect sizes in the Kramer and Barsade findings.

### Gaps
- No empirically fitted day-to-day AR coefficient for a "typical" person was extracted this session; Kuppens 2010 reports inertia comparatively, not as a portable constant.
- ALMA's exact default decay constants were not verified from the full text.

---

## 3. Relationship formation, maintenance, decay, balance, and conflict

### Takeaway
Friendship is driven by **accumulated shared time, weighted toward leisure and talk over joint work**: about 40–60 h for casual friendship, 80–100 h for friendship, and over 200 h for close friendship (Hall 2018). Ties decay without contact, and friendships decay faster than kin ties. Negative events weigh several times more than positive ones (Gottman's roughly 5:1 ratio). Over 7 simulated days with roughly 2 waking hours together per dyad per day, a realistic ceiling is "casual friend → friend", not close friendship. Fast, intense bonds should need a special cause such as high self-disclosure, shared crisis or romance.

### Cited Findings
**Hours to friendship**
- Hall (2018/2019, *J. Social & Personal Relationships*, "How many hours does it take to make a friend?") ran two studies, including 112 University of Kansas freshmen tracked after moving. Combined estimates: about 40–60 h to casual friend, 80–100 h to friend, and over 200 h to good or close friend. The 50% transition probabilities were about 50 h (acquaintance → casual), about 90 h, and about 219 h (→ close friend). The figures differ by sample: adults about 94 h vs students about 43 h for acquaintance → casual — [KU News](https://news.ku.edu/2018/03/06/study-reveals-number-hours-it-takes-make-friend); [Simply Psychology](https://www.simplypsychology.org/news/how-many-hours-does-it-take-to-make-a-friend/); [Greater Good](https://greatergood.berkeley.edu/article/item/how_long_does_it_take_to_make_a_friend)
- Type of time matters. Leisure such as hanging out, joking around and playing games increased closeness, while time working together contributed much less. Hall stresses the numbers are averages, not thresholds. The study only included relationships that persisted, so it says little about ties that fade — [Futurity](https://www.futurity.org/friends-time-1718952-2/); [KU News](https://news.ku.edu/2018/03/06/study-reveals-number-hours-it-takes-make-friend)

**Decay without contact**
- Roberts & Dunbar (2011, *Evolution & Human Behavior*, "The costs of family and friends") followed 25 students over 18 months, from school to university. Emotional closeness to friends was more sensitive than closeness to kin to drops in contact frequency and in shared activities — [Oxford record](https://www.neuroscience.ox.ac.uk/publications/572905); [CORE PDF](https://core.ac.uk/download/131226437.pdf)
- Roberts & Dunbar (2015, *Human Nature*, "Managing relationship decay") found that effort mitigated the decline in friendship quality. For women, talking more prevented decline. For men, doing more activities together did — [LJMU repository](https://researchonline.ljmu.ac.uk/id/eprint/7521/)
- *No fetched source gives a numeric per-day closeness decay rate.*

**Self-disclosure and social penetration**
- Social penetration theory (Altman & Taylor 1973): intimacy grows as disclosure increases in **breadth** (topics) and **depth** (layers), gradually and reciprocally. De-penetration accompanies dissolution (†) — Altman & Taylor, *Social Penetration*, Holt 1973
- Collins & Miller (1994, *Psych. Bulletin*), a meta-analysis: people who disclose are liked more; people disclose more to those they like; and disclosing to someone makes you like them more (†) — [doi:10.1037/0033-2909.116.3.457](https://doi.org/10.1037/0033-2909.116.3.457)
- Aron et al. (1997, *PSPB*): 45 minutes of escalating reciprocal self-disclosure between strangers produced closeness comparable to some existing relationships (†) — [doi:10.1177/0146167297234003](https://doi.org/10.1177/0146167297234003)

**Interdependence and commitment**
- Rusbult's investment model (1980, 1998): **Commitment = Satisfaction − Quality of alternatives + Investment size**. Satisfaction = rewards − costs relative to a comparison level (CL). Commitment predicts staying, accommodation and willingness to sacrifice (†) — [Rusbult, Martz & Agnew 1998, doi:10.1111/j.1475-6811.1998.tb00177.x](https://doi.org/10.1111/j.1475-6811.1998.tb00177.x)

**Structural balance, homophily, reciprocity**
- Heider (1946) balance theory: a triad is balanced when the product of the three signs is positive ("friend of my friend is my friend; enemy of my enemy is my friend"). People are pressured to resolve imbalance by changing a sentiment (†) — [doi:10.1080/00223980.1946.9917275](https://doi.org/10.1080/00223980.1946.9917275); formalized by Cartwright & Harary 1956 [doi:10.1037/h0046049](https://doi.org/10.1037/h0046049)
- McPherson, Smith-Lovin & Cook (2001, *Ann. Rev. Sociology*): homophily on race/ethnicity, age, religion, education, occupation and values strongly structures ties. It operates both through baseline opportunity and through choice (†) — [doi:10.1146/annurev.soc.27.1.415](https://doi.org/10.1146/annurev.soc.27.1.415)
- Reciprocity of liking: people like those who like them. Montoya & Insko (2008) and related work in reciprocal liking (†) — [Montoya & Insko 2008, doi:10.1002/ejsp.472](https://doi.org/10.1002/ejsp.472)

**Negativity bias, ratios, conflict**
- Gottman: stable couples show roughly 5 positive to 1 negative interaction *during conflict*. Couples headed for divorce show about 0.8:1. This comes from Gottman & Levenson's observational work (73 couples in the early studies). The "over 90% divorce prediction" accuracy is Gottman's own claim and should be read cautiously — [Gottman Institute](https://gottman.com/blog/the-magic-relationship-ratio-according-science/); [Psychology Today, "Marriage Math"](https://www.psychologytoday.com/us/articles/200403/marriage-math)
- Baumeister, Bratslavsky, Finkenauer & Vohs (2001, *Rev. Gen. Psych.*), "Bad is stronger than good": across domains, negative events have larger and longer-lasting effects than equivalent positive ones (†) — [doi:10.1037/1089-2680.5.4.323](https://doi.org/10.1037/1089-2680.5.4.323)
- Gottman's "Four Horsemen" (criticism, contempt, defensiveness, stonewalling) predict relationship breakdown. Contempt is the strongest single predictor in his work — [Big Think summary](https://bigthink.com/?p=597249)
- Conflict escalation and de-escalation: Glasl's 9-stage model (hardening → debate → actions not words → images/coalitions → loss of face → threat strategies → limited destruction → fragmentation → together into the abyss) is widely used in mediation but is descriptive rather than quantified (†) — Glasl, *Confronting Conflict*, 1999. Tit-for-tat with forgiveness (generous TFT) sustains cooperation under noise (Nowak & Sigmund 1992) (†) — [doi:10.1038/355250a0](https://doi.org/10.1038/355250a0)

### Inferences
- **Sim mapping: separate *closeness* (slow, accumulated) from *affinity/valence* (fast, signed).** Currently a single affinity value moves on every bid, which explains "too fast or too slow".
  - `hours_together[a][b]` accumulates weighted shared time: leisure or talk ×1.0, joint work ×0.3, conflict ×0. Closeness tier = f(weighted hours), using Hall's logistic transitions. With 7 days in the sim, compress time with a world-config factor (for example, 1 simulated hour of intense co-living ≈ 3–5 "Hall hours" in total institutions such as a Mars base or monastery). Then friendship ≈ 15–30 scene-hours and close friendship is rarely reached in 7 days.
  - Self-disclosure accelerator: an intimate disclosure that is reciprocated within the same or next scene adds a one-off bonus (for example +3–5 Hall-hours equivalent) to both sides, per Aron and Collins & Miller. An unreciprocated disclosure gives a smaller gain and a vulnerability flag.
- **Asymmetric bids:** scale negative bids 2–5× relative to positive ones (Baumeister, Gottman). Give negative events a slower decay of their effect. Keep the existing damping. This lets one betrayal outweigh several kindnesses.
- **Decay:** decay closeness only when there is *no contact* that day, by about 1–3% of the gap above the baseline. Friends decay faster than family or bonded roles (Roberts & Dunbar). Affinity drifts back toward the closeness-implied level rather than toward 0.
- **Balance pressure:** once a day, for each unbalanced triad with strong ties (|aff| > 0.3), nudge the weakest edge toward balance by about 0.02–0.05. Also surface the imbalance to the LLM as a felt tension ("Mara likes Jon, whom you distrust").
- **Homophily prior:** initial affinity += 0.05–0.15 × similarity of stated values or roles.
- **Reciprocity:** perceived affinity of B toward A feeds A→B (+0.3× the perceived value per day), gated by perception accuracy.
- **Conflict state machine:** track `conflict_level[a][b]` from 0 to 4 (tension → open disagreement → hostile acts → coalition-seeking/gossip → rupture). An escalation step happens when a negative bid lands while the level is above 0. De-escalation requires an apology or repair *accepted* by the other party, with acceptance probability rising with Agreeableness, closeness and time elapsed. Coalition-seeking (level 3) triggers gossip about the opponent, which connects Sections 1 and 3.
- **Romance gate:** keep the mutual-affinity, signal and interaction gates, but add a closeness tier requirement plus a reciprocated disclosure, to avoid "romance by day 2" unless the world premise says otherwise.

### Gaps
- No verified per-day decay rate for friendship closeness without contact.
- Hall's hours are for real-world adults and students; no source calibrates them to intense co-residence (total institutions), so the compression factor is a design choice.
- Glasl's stages are qualitative, with no empirical transition rates.

---

## 4. Opinion dynamics and conformity in tiny groups

### Takeaway
For 5–7 agents, plain averaging (DeGroot) collapses everyone to consensus unrealistically quickly. Bounded-confidence models (Deffuant pairwise; Hegselmann–Krause group) preserve stable factions: with confidence radius d, the number of surviving opinion clusters is about ⌊1/(2d)⌋. Weighting influence by affinity and closeness, and having opinions resist change in proportion to stake and to public commitment, gives more realistic drift than "drift toward the group mean".

### Cited Findings
- **Deffuant–Weisbuch model:** a random pair (i, j) interacts. If |x_i − x_j| < d, then x_i += μ(x_j − x_i) and x_j += μ(x_i − x_j). The number of final clusters ≈ ⌊1/(2d)⌋ (the "1/2d rule"). μ ∈ (0, 0.5] sets convergence speed but not the final cluster count. The original runs used μ = 0.5 — [Weisbuch et al., arXiv cond-mat/0111494](https://arxiv.org/pdf/cond-mat/0111494); [JASSS 11/2/4](https://jasss.soc.surrey.ac.uk/11/2/4.html)
- **Hegselmann–Krause:** each agent moves to the mean of all opinions within its confidence bound. On complete graphs the consensus threshold is about 0.2; with finite degree it is 1/2. The Deffuant consensus threshold is 1/2 on any graph — [arXiv 2102.10910](https://arxiv.org/pdf/2102.10910.pdf); [Castellano, Fortunato & Loreto, "Statistical physics of social dynamics", arXiv 0710.3256](https://arxiv.org/pdf/0710.3256)
- **DeGroot (1974):** x(t+1) = W·x(t) with a row-stochastic trust matrix W. A strongly connected aperiodic W converges to a consensus weighted by each agent's eigenvector centrality (†) — [doi:10.1080/01621459.1974.10480137](https://doi.org/10.1080/01621459.1974.10480137). Friedkin–Johnsen adds stubbornness: x(t+1) = Λ·W·x(t) + (I−Λ)·x(0), which keeps persistent disagreement (†) — [Friedkin & Johnsen 1990, doi:10.1080/0022250X.1990.9990069](https://doi.org/10.1080/0022250X.1990.9990069)
- **Social impact theory (Latané 1981):** impact = f(S·I·N), with S = strength or status, I = immediacy and N = number of sources. Impact grows as a power of N with exponent below 1 (about 0.5), so each additional source adds less (†) — [doi:10.1037/0003-066X.36.4.343](https://doi.org/10.1037/0003-066X.36.4.343)
- **Asch conformity:** about 37% of critical-trial responses conformed to an obviously wrong unanimous majority; about 75% of participants conformed at least once. A single dissenting ally cut conformity sharply, and majority size effects plateaued around 3–4 confederates (†) — [Asch 1956, doi:10.1037/h0093718](https://doi.org/10.1037/h0093718). Bond & Smith's (1996) meta-analysis found that conformity has declined over time in the US and is higher in collectivist cultures (†) — [doi:10.1037/0033-2909.119.1.111](https://doi.org/10.1037/0033-2909.119.1.111)

### Inferences
- **Sim mapping, per topic:** at each conversation where topic T comes up between i and j, apply `Δx_i = μ·w_ij·(x_j − x_i)` only if |x_j − x_i| < d_i. Use w_ij = sigmoid(affinity i→j) × status_j. Use d_i = 0.2 + 0.3·Openness, and μ ≈ 0.1–0.2 per exchange, so movement is slow over 7 days. Hostile pairs (affinity < −0.25) can push opinions apart (repulsion, a common extension) instead of converging. This yields factions that align with relationships.
- **Stubbornness anchor (Friedkin–Johnsen):** keep x(0) and λ_i = 0.5–0.8 for core-value topics and lower for trivia. A publicly stated stance should raise λ, since public commitment increases consistency pressure.
- **Public conformity vs private belief:** in group scenes, compute the public expressed stance as private stance pulled toward the unanimous majority with probability about 0.3–0.4 (Asch). That probability drops to about 0.1 if any one other person shares the dissent. Then let private stance drift only slightly. This produces the realistic gap between "said in the meeting" and "said in private", which is good gossip fuel.

### Gaps
- No empirical μ for face-to-face small-group attitude change was found; the parameters are design values.
- Repulsive extensions are theoretically motivated; evidence for backfire or polarization from contact is contested, and it was not reviewed here.

---

## 5. Motivation, needs and time-use realism

### Takeaway
Everyday behavior is better driven by a small set of decaying homeostatic needs scored with nonlinear urgency curves (The Sims' utility AI; Humanoid Agents' five needs on 0–10), plus stable "desire profiles" for character (Reiss; self-determination theory). Real time-use data show socializing is a small slice of a day (about 34–35 min/day on average in the US; about 2 h on days people do socialize). Most of the day is routine. In a society sim that compresses only interesting scenes, routine should still be represented as off-screen background that consumes time and restores needs.

### Cited Findings
**Game AI: The Sims**
- The Sims uses "motives" (8 needs in the final game, cut down from more) with meters from −100 to 100. Objects "advertise" the motive gains they offer, an idea derived from SimAnt's pheromones. Characters score actions by weighted motive deltas through **nonlinear curves**: hunger utility is near zero when full and very high when starving, while fun/social/comfort weights behave differently. Characters pick randomly among the top-scoring options rather than strictly the argmax. The design was influenced by Maslow — [GMTK, "The Genius AI Behind The Sims" (Game Industry Library)](https://gameindustrylibrary.com/documents/gmtk-the-genius-ai-behind-the-sims); [Will Wright history](https://will-wright.com/willshistory12.php). *Exact decay rates are not officially documented; hobbyist figures should not be cited.*

**LLM agents: Humanoid Agents**
- Humanoid Agents (Wang, Chiu & Chiu, EMNLP 2023) adds "System 1" state to generative agents: five basic needs (fullness, fun, health, social, energy), each 0–10, decaying at predefined rates. Needs start at 5, except energy at 10. Emotion and relationship closeness are also tracked — [arXiv 2310.05418](https://arxiv.org/abs/2310.05418v1); [ACL Anthology](https://aclanthology.org/2023.emnlp-demo.15)
- When needs were critically low, time spent on health, energy and fullness rose about +156%, +56% and +35% respectively, while social (+12%) and fun (−9%) barely responded. The LLM predicted fullness effects well (F1 0.972) and energy fairly well (0.861), but fun (0.66) and health (0.694) poorly, often over-predicting them. Needs are configurable — [arXiv 2310.05418](https://arxiv.org/abs/2310.05418v1); [GitHub](https://github.com/HumanoidAgents/HumanoidAgents)

**Psychological theories of motive**
- Self-determination theory (Deci & Ryan 2000): three basic psychological needs (autonomy, competence, relatedness). Satisfying them predicts well-being and intrinsic motivation; frustrating them predicts ill-being (†) — [Ryan & Deci 2000, doi:10.1037/0003-066X.55.1.68](https://doi.org/10.1037/0003-066X.55.1.68)
- Reiss's 16 basic desires (power, independence, curiosity, acceptance, order, saving, honor, idealism, social contact, family, status, vengeance, romance, eating, physical activity, tranquility) are measured as stable individual *intensities* that shape what satiates a person. Psychometric support comes from Reiss & Havercamp (1998), but the instrument is commercial and less independently replicated (†) — [doi:10.1037/1040-3590.10.2.97](https://doi.org/10.1037/1040-3590.10.2.97)
- Maslow's hierarchy is widely used in games, but empirical support for a strict ordering is weak. Tay & Diener (2011) found needs were satisfied largely independently across 123 countries (†) — [doi:10.1037/a0023779](https://doi.org/10.1037/a0023779)
- Belongingness as a fundamental need (Baumeister & Leary 1995): deprivation produces ill effects, and people seek a minimum of frequent, positive interactions within stable relationships (†) — [doi:10.1037/0033-2909.117.3.497](https://doi.org/10.1037/0033-2909.117.3.497)
- Hall's "communicate bond belong" theory: social energy is finite. After social interaction people need recovery, and being alone after social contact recovers it (†) — [Hall & Davis 2017, doi:10.1177/1088868316631066](https://doi.org/10.1177/1088868316631066)

**Time use**
- ATUS 2023 (US, ages 15+): socializing and communicating averaged 34 min/day (25 min on weekdays, 55 min on weekend days). Among people who socialized that day, the average was about 1.96 h. TV was the top leisure activity at 2.7 h/day. ATUS 2024 gave 35 min/day — [BLS ATUS 2023 release](https://www.bls.gov/news.release/archives/atus_06272024.htm); [BLS current release](https://www.bls.gov/news.release/atus.nr0.htm)
- Note that ATUS "socializing" excludes talk embedded in work, meals and household activities, so total social contact is higher than 34 min. Mehl et al. (2007, *Science*) estimated about 16,000 spoken words per day for both sexes using EAR (†) — [doi:10.1126/science.1139940](https://doi.org/10.1126/science.1139940)

### Inferences
- **Sim mapping: add 4–6 needs per character on a 0–1 scale,** for example energy, hunger/fullness, social, solitude/recovery, fun/leisure, and purpose/competence, plus 0–2 world-specific needs (faith in a monastery, oxygen/safety on a Mars base, pack status for wolves). Each decays linearly per tick at a character-specific rate scaled by trait: social decays faster for high-Extraversion characters, and solitude builds faster after social scenes for low-Extraversion characters (Hall).
- **Urgency curve:** `urgency = w_need × (1 − level)^k` with k ≈ 2–3, so a need is ignorable until it is low and then dominates (Sims curve). Pass the top 1–2 urgent needs to the LLM as "what you feel like doing" and let it choose an action. Code then credits need restoration by action category. This keeps the LLM inventive while code supplies the pressure.
- **Stable desire profile:** give each character 3–4 high-intensity Reiss desires (or SDT emphases) as persona fields. Map each desire to the intent verbs it rewards: status → confront or show off; acceptance → befriend; vengeance → retaliate. Use the mapping to weight intent selection, which adds variety across characters.
- **Routine background:** per simulated day, mark 60–80% of waking time as role routine (work, chores, meals, prayer) that the narrator summarizes. Within it, incidental co-presence still accrues small amounts of Hall-hours (weighted ×0.3 for work) and occasional gossip opportunities. Foreground scenes cover the remaining 20–40%. Without this, characters socialize at implausible intensity.
- **Lesson from Humanoid Agents:** LLMs handle physical needs well and fun/social poorly. The deterministic layer should therefore own social and fun accounting rather than asking the LLM whether the need was satisfied.

### Gaps
- No authoritative Sims decay constants exist publicly.
- Humanoid Agents' exact per-need decay rates are configurable and were not extracted from the paper.
- No time-use data was found for the specific settings (monastery, Mars base), so the routine share is an extrapolation.

---

## 6. Personality: Big Five / HEXACO and social behavior; persona consistency

### Takeaway
Big Five and HEXACO traits predict social behavior modestly but reliably: correlations of about 0.1–0.4 with aggregated behavior, and higher than that with aggregates than with single acts. Within-person variability is large, since people's moment-to-moment state levels span most of the population range (Fleeson). Realistic consistency therefore means keeping each character's *distribution* of behavior stable, not making every act prototypical. Traits should parameterize the deterministic layer (baselines, rates, thresholds) rather than live only in prompt text.

### Cited Findings
- Fleeson (2001, *JPSP*), density distributions: within-person variability in state-level trait expression (e.g. momentary extraversion) is as large as or larger than between-person variability. Individual means are highly stable across weeks (r ≈ 0.8–0.9 for aggregated means) (†) — [doi:10.1037/0022-3514.80.6.1011](https://doi.org/10.1037/0022-3514.80.6.1011)
- Big Five → social outcomes (Ozer & Benet-Martínez 2006 review). Extraversion predicts more social interaction and positive affect. Agreeableness predicts less conflict and more cooperation and forgiveness. Neuroticism predicts negative affect, relationship dissatisfaction and conflict. Conscientiousness predicts reliability and norm adherence. Openness predicts receptivity to new ideas (†) — [doi:10.1146/annurev.psych.57.102904.190127](https://doi.org/10.1146/annurev.psych.57.102904.190127)
- HEXACO (Ashton & Lee 2007) adds Honesty-Humility, which predicts lower exploitation, cheating, manipulative gossip and dark-triad behaviors, and higher cooperation in economic games. HEXACO Agreeableness is specifically forgiveness/patience vs anger, and Emotionality covers fear, anxiety, dependence and sentimentality (†) — [doi:10.1177/1088868306294907](https://doi.org/10.1177/1088868306294907)
- Big Five → PAD temperament regression (Mehrabian 1996) gives personality-dependent mood baselines, as used in ALMA — [ALMA paper PDF](https://cs.huji.ac.il/course/2005/aisemin/articles2006/docs/pa1a3_29.pdf); [ALMA project](https://alma.dfki.de/)
- ALMA uses the Big Five to regulate emotion intensity and decay, and personality sets the weight of mood in emotion intensity — [ALMA slides](https://sambuz.com/doc/alma-a-layered-model-of-affect-ppt-presentation-664816)
- Personality and emotional inertia: higher neuroticism goes with higher inertia of negative affect — [Kuppens et al. 2010, PMC2901421](https://pmc.ncbi.nlm.nih.gov/articles/PMC2901421)

### Inferences
- **Sim mapping: a trait → parameter table, computed once per character from Big Five (+ H) scores in [0,1]:**
  - E → social-need decay rate, initiation probability for befriend/joke, contagion susceptibility (+), and a solitude need that is low.
  - A → size of negative perception bids (dampened), apology-acceptance probability, gossip negativity (−), Deffuant μ (+).
  - N → mood baseline P (−), emotion half-life (+), inertia ρ (+), threat appraisal bias (+), conflict escalation probability (+).
  - O → confidence radius d (+), novelty-seeking needs.
  - C → routine adherence, keeping secrets (+), punctuality of need satisfaction.
  - H (HEXACO) → secret-leak probability (−), strategic or exploitative gossip (−), retaliation (−).
- **Consistency mechanism:** sample a per-scene *state* = trait + N(0, σ≈0.15) (Fleeson). Feed the LLM the state, not only the trait label, and log a rolling mean. If a character's rolling observed behavior (from intent-verb counts) drifts more than about 0.25 from its trait for more than 1 day, add a corrective "you're usually …" line to the prompt. This keeps realistic variance while preventing persona collapse.

### Gaps
- Exact trait–behavior correlations per behavior type (e.g. E → number of conversations) were not extracted this session; the Ozer & Benet-Martínez figures are summarized qualitatively.
- No verified source for the effectiveness of LLM persona-drift correction was reviewed here; that belongs to the agent-architecture literature, outside this scope.
