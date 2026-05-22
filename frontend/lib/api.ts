import type {
  World, Agent, CharacterInput, SimulationResult, StreamEvent, SaveMeta,
} from "./types";
import { getToken } from "./supabase";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function setAuthToken(_token: string | null) {
  // kept for backwards compat — token is now fetched fresh per-request
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

async function* streamReq(path: string, body: unknown): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop()!;
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            yield JSON.parse(line.slice(6)) as StreamEvent;
          } catch { /* skip malformed */ }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
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

  simulate: (wid: string, days: number, reasoning_agents_per_day = 8, seed = 42) =>
    req<SimulationResult>(`/world/${wid}/simulate`, {
      method: "POST",
      body: JSON.stringify({ days, reasoning_agents_per_day, seed }),
    }),

  simulateStream: (wid: string, days: number, perDay = 8, seed = 42) =>
    streamReq(`/world/${wid}/simulate/stream`, { days, reasoning_agents_per_day: perDay, seed }),

  continueStream: (wid: string, days: number, perDay = 8, seed = 42) =>
    streamReq(`/world/${wid}/simulate/continue/stream`, { days, reasoning_agents_per_day: perDay, seed }),

  getResult: (wid: string) =>
    req<SimulationResult>(`/world/${wid}/result`),

  agentChat: (wid: string, agentId: string, message: string, day = 1) =>
    req<{ reply: string; agent_name: string }>(`/world/${wid}/agent/${agentId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, day }),
    }),

  // ── Save files ────────────────────────────────────────────────────────────

  listSaves: () =>
    req<SaveMeta[]>("/saves"),

  createSave: (name: string, world: World, result: SimulationResult | null) =>
    req<SaveMeta>("/saves", {
      method: "POST",
      body: JSON.stringify({ name, world_data: world, result_data: result ?? undefined }),
    }),

  overwriteSave: (saveId: string, name: string, world: World, result: SimulationResult | null) =>
    req<SaveMeta>(`/saves/${saveId}`, {
      method: "PUT",
      body: JSON.stringify({ name, world_data: world, result_data: result ?? undefined }),
    }),

  deleteSave: (saveId: string) =>
    req<{ ok: boolean }>(`/saves/${saveId}`, { method: "DELETE" }),

  loadSave: (saveId: string) =>
    req<{ world_id: string; world: World; result: SimulationResult | null }>(
      `/saves/${saveId}/load`,
      { method: "POST" },
    ),
};
