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
    strength: float = Field(ge=-1.0, le=1.0)


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
    short_term_memory: list[str] = []
    long_term_memory: list[str] = []
    is_custom: bool = False


class CharacterInput(BaseModel):
    name: str
    role: str = "citizen"
    traits: list[str] = []
    goals: list[str] = []
    mood: Mood = "calm"
    groups: list[str] = []
    starting_memories: list[str] = []
    starting_relationships: dict[str, Relationship] = {}


class WorldInput(BaseModel):
    prompt: str
    target_population: int = Field(default=25, ge=5, le=60)


class World(BaseModel):
    prompt: str
    target_population: int
    agents: list[Agent] = []
    starting_event: Optional[str] = None


class SimulationConfig(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
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


class AgentAction(BaseModel):
    """Structured output contract returned by the AI reasoning layer."""
    action: str
    target_agents: list[str] = []
    emotional_reaction: Mood = "calm"
    relationship_effects: dict[str, RelationshipEffect] = {}
    influence_effects: dict[str, float] = {}
    new_memory: str
    explanation: str


class DayHighlight(BaseModel):
    agent: str
    summary: str


class DaySnapshot(BaseModel):
    day: int
    agents: list[Agent]
    event_log: list[str]
    highlights: list[DayHighlight]
    metrics: MacroMetrics
    active_event: Optional[str] = None
    perception_notes: list[PerceptionNote] = []


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


class SimulationResult(BaseModel):
    days: int
    snapshots: list[DaySnapshot]
    initial_metrics: MacroMetrics
    final_metrics: MacroMetrics
    final_report: str
    dynamic_events: Dict[str, str] = Field(default_factory=dict)


DaySnapshot.model_rebuild()
