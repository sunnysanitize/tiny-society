export type RelationshipType =
  | "friendship" | "rivalry" | "romance" | "trust"
  | "influence" | "alliance" | "conflict" | "group_membership";

export type Mood =
  | "calm" | "excited" | "frustrated" | "heartbroken" | "ambitious"
  | "anxious" | "content" | "angry" | "hopeful" | "lonely" | "confident";

export interface Relationship {
  type: RelationshipType;
  strength: number;
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  traits: string[];
  goals: string[];
  mood: Mood;
  influence_score: number;
  groups: string[];
  relationships: Record<string, Relationship>;
  short_term_memory: string[];
  long_term_memory: string[];
  is_custom: boolean;
}

export interface World {
  prompt: string;
  target_population: number;
  agents: Agent[];
  starting_event: string | null;
}

export interface DayHighlight {
  agent: string;
  summary: string;
}

export interface MacroMetrics {
  friendship_count: number;
  rivalry_count: number;
  conflict_count: number;
  romance_count: number;
  alliance_count: number;
  average_relationship_strength: number;
  average_trust_score: number;
  most_connected: string[];
  influence_gainers: string[];
  influence_losers: string[];
  relationship_volatility: number;
  social_fragmentation: number;
  group_centrality: Record<string, number>;
}

export interface DaySnapshot {
  day: number;
  agents: Agent[];
  event_log: string[];
  highlights: DayHighlight[];
  metrics: MacroMetrics;
  active_event?: string | null;
}

export interface SimulationResult {
  days: number;
  snapshots: DaySnapshot[];
  initial_metrics: MacroMetrics;
  final_metrics: MacroMetrics;
  final_report: string;
  dynamic_events?: Record<string, string>;
}

export interface CharacterInput {
  name: string;
  role: string;
  traits: string[];
  goals: string[];
  mood: Mood;
  groups: string[];
  starting_memories: string[];
  starting_relationships: Record<string, Relationship>;
}

export interface SaveMeta {
  id: string;
  name: string;
  day_count: number;
  agent_count: number;
  world_prompt: string;
  created_at: string;
  updated_at: string;
}

export type StreamEvent =
  | { type: "day"; snapshot: DaySnapshot }
  | { type: "done"; result: SimulationResult }
  | { type: "error"; message: string };
