"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World, SimulationResult } from "@/lib/types";

export function EventAndRun({
  worldId,
  world,
  onWorldChange,
  onResult,
}: {
  worldId: string;
  world: World;
  onWorldChange: (w: World) => void;
  onResult: (r: SimulationResult) => void;
}) {
  const [event, setEvent] = useState(
    world.starting_event || "A new entrepreneurship club launches with only 12 spots."
  );
  const [days, setDays] = useState<7 | 30>(7);
  const [perDay, setPerDay] = useState(8);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setErr(null);
    try {
      const w = await api.setEvent(worldId, event);
      onWorldChange(w);
      const result = await api.simulate(worldId, days, perDay);
      onResult(result);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="panel p-5 space-y-3">
      <div className="text-sm text-muted">Step 3 — Inject event & run simulation</div>
      <textarea
        rows={2}
        value={event}
        onChange={(e) => setEvent(e.target.value)}
        placeholder="A new club opens with only 12 spots..."
      />
      <div className="flex items-center gap-4 flex-wrap">
        <label className="text-sm text-muted">Simulation length</label>
        <div className="flex gap-2">
          <button
            className={days === 7 ? "btn" : "btn-ghost"}
            onClick={() => setDays(7)}
          >7 days (quick)</button>
          <button
            className={days === 30 ? "btn" : "btn-ghost"}
            onClick={() => setDays(30)}
          >30 days (default)</button>
        </div>
        <label className="text-sm text-muted ml-4">AI agents/day</label>
        <input
          className="w-20"
          type="number"
          min={1}
          max={20}
          value={perDay}
          onChange={(e) => setPerDay(parseInt(e.target.value) || 8)}
        />
        <button className="btn ml-auto" onClick={run} disabled={running || world.agents.length === 0}>
          {running ? `Running ${days}-day simulation...` : "Run simulation"}
        </button>
      </div>
      {err && <div className="text-red-400 text-sm">{err}</div>}
      {running && (
        <div className="text-xs text-muted">
          This calls the LLM once per selected agent per day. With mock provider this finishes in seconds.
          With a real provider it can take longer depending on rate limits.
        </div>
      )}
    </div>
  );
}
