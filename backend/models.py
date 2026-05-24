from __future__ import annotations

from typing import Literal, Optional, Dict
from pydantic import BaseModel, Field

RelationshipType = Literal[
    "friendship",
    "rivalry",
    "romance",
    "trust",
    "influence",
    "alliance",
    "conflict",
    "group_membership",
]

Mood = Literal[
    "calm", "excited", "frustrated", "heartbroken", "ambitious",
    "anxious", "content", "angry", "hopeful", "lonely", "confident",
]


class Relationship(BaseModel):
    type: RelationshipType
    # `strength` is the underlying continuous AFFINITY (signed sentiment) in [-1, 1].
    # The relationship `type` is no longer set by fiat — it is DERIVED from this affinity
    # (plus the fields below) by simulation/consequence.py, so bonds are earned, not asserted.
    strength: float = Field(ge=-1.0, le=1.0)
    # How many meaningful interactions this pair has had — the "dwell time" that gates
    # transitions (e.g. an alliance/romance needs sustained contact, not one moment).
    interactions: int = 0
    # Accumulated ROMANTIC signal (rises only on romantic overtures). Romance requires
    # this to be mutually high — so it can't spring from platonic closeness alone.
    romantic: float = 0.0
    # Accumulated ALLIANCE signal (rises only on strategic/allying overtures). Like
    # `romantic`, this distinguishes a strategic pact from ordinary warm friendship, so
    # close friends aren't mislabeled as allies just for being close.
    allied: float = 0.0


class WorldEntity(BaseModel):
    """A named thing in the world's ground truth (a person-class, place, object,
    institution, resource, or stake) extracted from the world prompt."""
    name: str
    kind: str = "entity"   # e.g. person, place, institution, resource, stake, event
    description: str = ""


class WorldRelationship(BaseModel):
    """A directed/undirected factual relationship between two world entities."""
    source: str
    target: str
    relation: str = "related to"


class WorldGraph(BaseModel):
    """Shared factual ground truth for the world (a lightweight GraphRAG layer).

    Extracted once at simulation start from `World.prompt` (+ `World.question` if set)
    via a single LLM call. Injected compactly into every agent's reasoning prompt so the
    population shares the same facts. `topics` are the 3-6 short stance axes the society
    divides on — these seed and drive `Agent.stance`.
    """
    entities: list[WorldEntity] = []
    relationships: list[WorldRelationship] = []
    power_structures: list[str] = []
    topics: list[str] = []

    def is_empty(self) -> bool:
        return not (self.entities or self.power_structures or self.topics)


class Memory(BaseModel):
    """A single recalled experience.

    Retrieval (see simulation/memory.py) scores memories on relevance + recency +
    importance, modeled on the Stanford "Generative Agents" paper. `day` is the sim
    day the memory was created; `last_accessed_day` is bumped whenever the memory is
    retrieved, feeding the recency term for later reflection/observation features.
    """
    text: str
    importance: float = Field(default=5.0, ge=1.0, le=10.0)
    day: int = 0
    last_accessed_day: int = 0


class FeedEntry(BaseModel):
    """One ranked-feed observation (Phase 2 #4 — interest + hot-score feed).

    Lightweight metadata so each entry can be RANKED per viewer (see
    simulation/observation.rank_feed): the author + their influence at the time, the
    day (recency), the action_kind (reach signal), and the rendered text. `Agent.feed`
    holds these; `Agent.observations` keeps the plain-string back-compat view.
    """
    text: str
    author: str = ""
    author_influence: float = 0.0
    day: int = 0
    action_kind: str = "interact"


class Agent(BaseModel):
    id: str
    name: str
    role: str
    traits: list[str] = []           # declared by the user at setup
    revealed_traits: list[str] = []  # emerged from simulation behavior
    goals: list[str] = []
    mood: Mood = "calm"
    influence_score: float = 0.0
    groups: list[str] = []
    relationships: dict[str, Relationship] = {}
    short_term_memory: list[Memory] = []
    long_term_memory: list[Memory] = []
    # Per-agent observation feed (information asymmetry): recent world events this
    # agent could plausibly witness — actions it took, actions targeting it, actions
    # by group-mates, and "public" actions by high-influence agents. Plain strings
    # (feed entries, not scored memories), capped to a recent window.
    observations: list[str] = []
    # Per-agent RANKED feed (Phase 2 #4): the same witnessed events as `observations`
    # but as structured FeedEntry objects carrying author/influence/day/action_kind so
    # the reasoner can show each agent a feed RANKED by interest-match + hot-score
    # (see simulation/observation.rank_feed). Frontend ignores unknown fields, so this
    # serializes harmlessly. `observations` remains for back-compat string consumers.
    feed: list[FeedEntry] = []
    # Per-agent stance on each world topic (see WorldGraph.topics): topic -> position
    # in [-1, 1]. Initialized mildly-varied at simulation start (see simulation/stance.py)
    # and shifted by `AgentAction.stance_shift` as agents engage. Belief AGGREGATION across
    # agents is a later slice — this field just holds and moves per-agent positions.
    stance: dict[str, float] = {}
    # GOAL-DRIVEN PLANNING (Slice D ④): a short current intention toward a goal,
    # refreshed for selected agents when stale (see simulation/planner.py and
    # PLAN_REFRESH_DAYS in engine.py). Injected into the reasoner prompt so the
    # day's action can pursue it. `plan_day` is the sim day the plan was last set.
    plan: Optional[str] = None
    plan_day: int = 0
    # ANTI-REPETITION (richness fix): a short rolling log of this agent's most recent
    # actions ("day3: confront -> Aria"), surfaced in the reasoner prompt so the model
    # can see its OWN pattern and deliberately vary target/approach instead of looping.
    recent_actions: list[str] = []
    is_custom: bool = False
    # IDENTITY INJECTION (Slice E): an emoji or a preset pixel-avatar id string used by
    # the frontend to render the character. None means the frontend assigns one.
    avatar: Optional[str] = None
    # Free text noting a real person the character is based on (e.g. "my friend Sam").
    based_on: Optional[str] = None


class CharacterInput(BaseModel):
    name: str
    role: str = "citizen"
    traits: list[str] = []
    goals: list[str] = []
    mood: Mood = "calm"
    groups: list[str] = []
    starting_memories: list[str] = []
    starting_relationships: dict[str, Relationship] = {}
    # IDENTITY INJECTION (Slice E): optional emoji/pixel-avatar id + "based on a real
    # person" free text. Both optional so existing callers are unaffected.
    avatar: Optional[str] = None
    based_on: Optional[str] = None


class WorldInput(BaseModel):
    prompt: str
    target_population: int = Field(default=25, ge=5, le=60)


class World(BaseModel):
    prompt: str
    target_population: int
    agents: list[Agent] = []
    starting_event: Optional[str] = None
    # Optional player prediction question (Phase 2). May be None for a pure sandbox run.
    question: Optional[str] = None
    # Shared factual ground truth (entities/relationships/power structures/topics),
    # populated once at simulation start by simulation/worldgraph.py.
    world_graph: WorldGraph = Field(default_factory=WorldGraph)
    # PROPHECY (Slice E): player's free-text prediction, graded by the AI at the end of
    # a run against the actual outcome. None = no prophecy made.
    prophecy: Optional[str] = None
    # INJECT-AN-EVENT nudge (Slice E): a player-authored event queued to become the
    # `active_event` on the NEXT simulated day, taking priority over auto-generated
    # dynamic events. Consumed (cleared) by run_simulation on its first day.
    pending_event: Optional[str] = None


class SimulationConfig(BaseModel):
    days: int = Field(default=30, ge=1, le=1000)
    reasoning_agents_per_day: int = Field(default=8, ge=1, le=30)


class RelationshipEffect(BaseModel):
    type: RelationshipType
    strength_delta: float = Field(ge=-1.0, le=1.0)


class PerceptionNote(BaseModel):
    perceiver: str
    actor: str
    raw_delta: float
    perceived_delta: float
    relationship_type: str
    narrative: str
    revealed_trait: Optional[str] = None


# Real action space (Phase 2 #5, modeled on OASIS's distinct social actions). The
# action_kind drives REACH (who witnesses it) and side-effects, layered on top of the
# free-text `action` verb. Unknown values are clamped to "interact" (current behavior).
#   - post     : public broadcast — witnessed broadly (celebrity/news reach).
#   - direct   : private — only the named target(s) witness it.
#   - amplify  : boost/repost a target — the target gains influence and their standing
#                spreads to the amplifier's own witnesses.
#   - comment  : reply — medium reach (current witness rule).
#   - interact : default — current behavior (actor + targets + group-mates + public-if-high-influence).
ActionKind = Literal["post", "direct", "amplify", "comment", "interact"]
ACTION_KINDS: set[str] = {"post", "direct", "amplify", "comment", "interact"}


def normalize_action_kind(value: object) -> str:
    """Clamp an arbitrary value to a valid ActionKind, defaulting to 'interact'."""
    if isinstance(value, str) and value.strip().lower() in ACTION_KINDS:
        return value.strip().lower()
    return "interact"


class AgentAction(BaseModel):
    """Structured output contract returned by the AI reasoning layer.

    The agent expresses an in-character SOCIAL MOVE — what it does/says and its *intent*
    toward each target — NOT numeric relationship/influence deltas. The consequence layer
    (simulation/consequence.py) translates intents into calibrated, bilateral state changes,
    so bonds are earned rather than asserted. (Stage 2 of the realism re-architecture.)
    """
    action: str
    # Social-action type driving reach + side-effects (see ActionKind above). Safe
    # default "interact" preserves prior behavior for any caller that omits it.
    action_kind: ActionKind = "interact"
    target_agents: list[str] = []
    emotional_reaction: Mood = "calm"
    # Per-target SOCIAL INTENT verb (befriend / confide / flirt / court / ally / confront /
    # undermine / distance / …). The verb — not a number — is what the agent controls; the
    # consequence layer maps it to a calibrated affinity bid. See consequence.INTENT_EFFECTS.
    intents: dict[str, str] = {}
    # What the character actually says or does this turn, in-character (1-2 sentences).
    utterance: str = ""
    # Optional small per-topic stance deltas (topic -> delta, roughly -0.3..0.3) for the
    # world topics this agent actually engaged with today. Applied to the actor's
    # `stance` in applicator.apply_action and clamped to [-1, 1]. (Beliefs are self-owned,
    # so this stays agent-authored — it's not an interpersonal effect.)
    stance_shift: dict[str, float] = {}
    new_memory: str
    explanation: str


class DayHighlight(BaseModel):
    agent: str
    summary: str


class Vignette(BaseModel):
    """A theatrical, flavorful first-person moment (Slice E) — a dream, catchphrase,
    or dramatic announcement — produced occasionally by an agent. Surfaced as charming
    digest cards alongside (not replacing) the day's DayHighlights."""
    agent: str
    kind: str = "announcement"   # "dream" | "catchphrase" | "announcement"
    text: str


class DaySnapshot(BaseModel):
    day: int
    agents: list[Agent]
    event_log: list[str]
    highlights: list[DayHighlight]
    metrics: MacroMetrics
    active_event: Optional[str] = None
    perception_notes: list[PerceptionNote] = []
    # THEATRICAL VIGNETTES (Slice E): bounded per-day charming moments. Default [] so
    # existing snapshots/serialization are unaffected.
    vignettes: list[Vignette] = []
    # RELATIONSHIP MILESTONES (richness fix): human-readable "turning point" beats
    # detected this day — a relationship changed type (friendship→romance, trust→rivalry)
    # or crossed a strength threshold. Fed into the final report and surfaced in the
    # story view so arcs are visible instead of buried in per-day activity. Default [].
    milestones: list[str] = []


class MacroMetrics(BaseModel):
    friendship_count: int
    rivalry_count: int
    conflict_count: int
    romance_count: int
    alliance_count: int
    average_relationship_strength: float
    average_trust_score: float
    most_connected: list[str]
    influence_gainers: list[str]
    influence_losers: list[str]
    relationship_volatility: int
    social_fragmentation: float
    group_centrality: dict[str, int]
    # ── Belief aggregation (Phase 2 #2) ──────────────────────────────────────
    # Aggregated over Agent.stance across the population, per world topic.
    # topic_means[topic]  = population MEAN stance on that axis in [-1, 1]
    #                       (where the population leans on that topic).
    # topic_uncertainty[topic] = population SPREAD (standard deviation) of stances
    #                       on that axis; HIGH spread = high disagreement = LOW
    #                       confidence in any single forecast value.
    # belief_confidence   = single scalar in [0, 1]: 1 - normalized average spread
    #                       across topics (1.0 = full consensus, 0.0 = max disagreement).
    # All default empty/1.0 so existing call sites and serialization are unaffected.
    topic_means: dict[str, float] = {}
    topic_uncertainty: dict[str, float] = {}
    belief_confidence: float = 1.0


class Forecast(BaseModel):
    """Structured prediction output (Phase 2 #3), grounded in the per-day belief
    trajectory. Numeric fields are computed in Python from the daily MacroMetrics;
    `narrative` is the LLM-written prose (single FINAL_REPORT call).

    - question: the player's prediction question (may be None for a sandbox run).
    - topic_means / topic_uncertainty: final-day aggregated stance distribution.
    - confidence: final-day belief_confidence (1 = consensus, 0 = max disagreement).
    - pivotal_days: sim days where the aggregate distribution moved the most
      (largest day-over-day change in mean across topics), most-pivotal first.
    - narrative: prose answer to the question, grounded in the means + confidence
      + the pivotal-day causal chain.
    """
    question: Optional[str] = None
    topic_means: dict[str, float] = {}
    topic_uncertainty: dict[str, float] = {}
    confidence: float = 1.0
    pivotal_days: list[int] = []
    narrative: str = ""


class ProphecyVerdict(BaseModel):
    """AI grading of the player's free-text prophecy against the run's outcome (Slice E).

    - prediction: the player's original free-text prediction.
    - verdict: one of "correct" / "partly" / "incorrect" / "unresolved".
    - confidence: grader confidence in [0, 1].
    - explanation: short prose justifying the verdict against the actual outcome.
    """
    prediction: str
    verdict: str = "unresolved"
    confidence: float = 0.5
    explanation: str = ""


class SimulationResult(BaseModel):
    days: int
    snapshots: list[DaySnapshot]
    initial_metrics: MacroMetrics
    final_metrics: MacroMetrics
    final_report: str
    dynamic_events: Dict[str, str] = Field(default_factory=dict)
    # Structured forecast (Phase 2 #3). None for runs with no question and no topics.
    forecast: Optional[Forecast] = None
    # PROPHECY grading (Slice E). None when the world had no prophecy set.
    prophecy_verdict: Optional[ProphecyVerdict] = None
    # DAY-BY-DAY: the influence scores captured BEFORE day 1, so "gainers/losers" stay
    # measured against day 0 even when the run is advanced one day at a time (each
    # advance is a fresh run_simulation call that would otherwise re-baseline). Carried
    # forward by _merge_results and fed back into run_simulation on each advance.
    baseline_influence: Dict[str, float] = Field(default_factory=dict)


DaySnapshot.model_rebuild()
