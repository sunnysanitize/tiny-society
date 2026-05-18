import type {
  World, Agent, CharacterInput, SimulationResult,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  health: () => req<{ ok: boolean; llm_provider: string }>("/health"),

  createWorld: (prompt: string, target_population: number) =>
    req<{ world_id: string; world: World }>("/world", {
      method: "POST",
      body: JSON.stringify({ prompt, target_population }),
    }),

  getWorld: (wid: string) => req<World>(`/world/${wid}`),

  addCharacter: (wid: string, c: CharacterInput) =>
    req<Agent>(`/world/${wid}/character`, {
      method: "POST",
      body: JSON.stringify(c),
    }),

  removeCharacter: (wid: string, agentId: string) =>
    req<{ ok: boolean }>(`/world/${wid}/character/${agentId}`, {
      method: "DELETE",
    }),

  generateFillers: (wid: string, count?: number) =>
    req<World>(`/world/${wid}/generate-fillers`, {
      method: "POST",
      body: JSON.stringify({ count: count ?? null }),
    }),

  setEvent: (wid: string, starting_event: string) =>
    req<World>(`/world/${wid}/event`, {
      method: "POST",
      body: JSON.stringify({ starting_event }),
    }),

  simulate: (wid: string, days: 7 | 30, reasoning_agents_per_day = 8, seed = 42) =>
    req<SimulationResult>(`/world/${wid}/simulate`, {
      method: "POST",
      body: JSON.stringify({ days, reasoning_agents_per_day, seed }),
    }),

  agentChat: (wid: string, agentId: string, message: string, day = 1) =>
    req<{ reply: string; agent_name: string }>(`/world/${wid}/agent/${agentId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, day }),
    }),
};
