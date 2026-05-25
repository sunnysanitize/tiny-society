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

export interface Memory {
  text: string;
  importance: number;
  day: number;
  last_accessed_day: number;
}

/** Memories are rich objects now, but legacy saves may hold plain strings. */
export type MemoryEntry = Memory | string;

/** One ranked-feed observation an agent witnessed (information asymmetry). */
export interface FeedEntry {
  text: string;
  author: string;
  author_influence: number;
  day: number;
  action_kind: string;
}

/** Safely read a memory's text whether it's a Memory object or a legacy string. */
export function memText(m: MemoryEntry): string {
  return typeof m === "string" ? m : m?.text ?? "";
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
  short_term_memory: MemoryEntry[];
  long_term_memory: MemoryEntry[];
  is_custom: boolean;
  // ── Engagement (Slice F) — optional so older saves still type-check ──
  avatar?: string | null;
  based_on?: string | null;
  // ── earlier slices (defensive optionals) ──
  stance?: Record<string, number>;
  plan?: string | null;
  feed?: FeedEntry[];
  observations?: string[];
}

export interface World {
  prompt: string;
  target_population: number;
  agents: Agent[];
  starting_event: string | null;
  // ── Engagement (Slice F) ──
  prophecy?: string | null;
  question?: string | null;
  pending_event?: string | null;
}

export type VignetteKind = "dream" | "catchphrase" | "announcement";

export interface Vignette {
  agent: string;
  kind: VignetteKind;
  text: string;
}

export interface Forecast {
  question: string | null;
  topic_means: Record<string, number>;
  topic_uncertainty: Record<string, number>;
  confidence: number;
  pivotal_days: number[];
  narrative: string;
}

export type Verdict = "correct" | "partly" | "incorrect" | "unresolved";

export interface ProphecyVerdict {
  prediction: string;
  verdict: Verdict;
  confidence: number;
  explanation: string;
}

export interface DayHighlight {
  agent: string;
  summary: string;
}

/** How a character subjectively internalized an incoming event (perception layer).
 * `narrative` is the readable, in-character reinterpretation; the deltas show how much
 * the raw social signal was amplified or dampened by who they are. */
export interface PerceptionNote {
  perceiver: string;
  actor: string;
  raw_delta: number;
  perceived_delta: number;
  relationship_type: string;
  narrative: string;
  revealed_trait?: string | null;
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
  // ── Slice B belief state (optional/defensive) ──
  topic_means?: Record<string, number>;
  topic_uncertainty?: Record<string, number>;
  belief_confidence?: number;
}

export interface DaySnapshot {
  day: number;
  agents: Agent[];
  event_log: string[];
  highlights: DayHighlight[];
  metrics: MacroMetrics;
  active_event?: string | null;
  vignettes?: Vignette[];
  milestones?: string[];
  perception_notes?: PerceptionNote[];
}

export interface SimulationResult {
  days: number;
  snapshots: DaySnapshot[];
  initial_metrics: MacroMetrics;
  final_metrics: MacroMetrics;
  final_report: string;
  dynamic_events?: Record<string, string>;
  forecast?: Forecast | null;
  prophecy_verdict?: ProphecyVerdict | null;
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
  avatar?: string;
  based_on?: string;
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
