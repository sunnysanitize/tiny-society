"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World } from "@/lib/types";

const DAY_OPTIONS = [7, 14, 30, 60];

export function EventAndRun({
  worldId,
  world,
  onWorldChange,
  onRun,
}: {
  worldId: string;
  world: World;
  onWorldChange: (w: World) => void;
  onRun: (days: number, perDay: number) => void;
}) {
  const [event, setEvent] = useState(
    world.starting_event || "A new entrepreneurship club launches with only 12 spots."
  );
  const [days, setDays] = useState(30);
  const [perDay, setPerDay] = useState(8);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    setSaving(true);
    setErr(null);
    try {
      const w = await api.setEvent(worldId, event);
      onWorldChange(w);
      onRun(days, perDay);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  }

  const canRun = world.agents.length > 0 && !saving;

  return (
    <div className="panel p-5 space-y-3">
      <div className="text-sm text-muted">Step 3 — Set the starting event & run</div>

      <textarea
        rows={2}
        value={event}
        onChange={(e) => setEvent(e.target.value)}
        placeholder="A new club opens with only 12 spots…"
      />

      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "#4b5563" }}>Days</span>
          <div style={{ display: "flex", gap: 4 }}>
            {DAY_OPTIONS.map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                style={{
                  padding: "4px 10px", borderRadius: 6, fontSize: 11, cursor: "pointer",
                  background: days === d ? "#1e3a5f" : "transparent",
                  color: days === d ? "#60a5fa" : "#4b5563",
                  border: `1px solid ${days === d ? "#2563eb" : "#1a2030"}`,
                }}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "#4b5563" }}>AI agents/day</span>
          <input
            type="number" min={1} max={20} value={perDay}
            onChange={(e) => setPerDay(parseInt(e.target.value) || 8)}
            style={{ width: 56 }}
          />
        </div>

        <button
          className="btn"
          onClick={run}
          disabled={!canRun}
          style={{ marginLeft: "auto" }}
        >
          {saving ? "Saving…" : `Run ${days}-day simulation`}
        </button>
      </div>

      {world.agents.length === 0 && (
        <div style={{ fontSize: 11, color: "#6b7280" }}>
          Add at least one agent above before running.
        </div>
      )}
      {err && <div className="text-red-400 text-sm">{err}</div>}
    </div>
  );
}
