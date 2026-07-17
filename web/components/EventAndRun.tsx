"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World } from "@/lib/types";
import { ProphecyInput, QuestionInput } from "./Engagement";

export function EventAndRun({ worldId, world, onWorldChange, onRun, onBegin }: {
  worldId: string; world: World; onWorldChange: (w: World) => void;
  onRun: (days: number, perDay: number) => void;
  onBegin: (perDay: number) => void;
}) {
  const [event, setEvent] = useState(world.starting_event || "");
  const [days, setDays] = useState(30);
  const [perDay, setPerDay] = useState(8);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function saveEvent() {
    const w = await api.setEvent(worldId, event);
    onWorldChange(w);
  }
  async function run() {
    setSaving(true); setErr(null);
    try { await saveEvent(); onRun(days, perDay); }
    catch (e: any) { setErr(e.message); }
    finally { setSaving(false); }
  }
  async function begin() {
    setSaving(true); setErr(null);
    try { await saveEvent(); onBegin(perDay); }
    catch (e: any) { setErr(e.message); }
    finally { setSaving(false); }
  }

  const canRun = world.agents.length > 0 && !saving;

  return (
    <div className="panel" style={{ padding: "20px 24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <span style={{ color: "var(--accent)", fontSize: 12 }}>◉</span>
        <span className="font-pixel" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.1em" }}>
          MISSION BRIEFING
        </span>
      </div>
      <div style={{ height: 1, background: "linear-gradient(90deg, transparent, var(--border), transparent)", marginBottom: 16 }} />

      <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.6, marginBottom: 20 }}>
        The spark that sets your world in motion, plus how long it should run. Set the opening event and the pace, then launch.
      </div>

      {/* Event input */}
      <div style={{ marginBottom: 20 }}>
        <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 8, letterSpacing: "0.1em" }}>
          STARTING EVENT
        </div>
        <textarea
          rows={2}
          value={event}
          onChange={e => setEvent(e.target.value)}
          placeholder="describe the event that kicks off your simulation..."
          style={{ lineHeight: 1.7 }}
        />
        <div style={{ marginTop: 12, fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.6 }}>
          What your characters wake up to on day one. Everything that follows grows out of how each of them reacts to it.
        </div>
      </div>

      {/* Prediction question: anchors the forecast */}
      <QuestionInput worldId={worldId} initial={world.question}
        onSaved={q => onWorldChange({ ...world, question: q })} />

      {/* Prophecy */}
      <ProphecyInput worldId={worldId} initial={world.prophecy} />

      {/* Options */}
      <div style={{ display: "flex", flexDirection: "column", gap: 18, marginBottom: 20 }}>
        {/* Duration */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
            <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.1em" }}>
              FAST-FORWARD (DAYS)
            </div>
            <span className="font-pixel" style={{ fontSize: 12, color: "var(--accent)", marginLeft: "auto" }}>{days}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-muted)", flexShrink: 0 }}>1</span>
            <input
              type="range" min={1} max={60} step={1} value={days}
              className="volume-range"
              onChange={e => setDays(parseInt(e.target.value))}
              style={{ ["--fill" as any]: `${((days - 1) / (60 - 1)) * 100}%` }}
            />
            <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-muted)", flexShrink: 0 }}>60</span>
          </div>
          <div style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.5, marginTop: 6 }}>
            How many days to run in one fast-forward.
          </div>
        </div>

        {/* AI per day */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
            <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.1em" }}>
              AI CHARACTERS / DAY
            </div>
            <span className="font-pixel" style={{ fontSize: 12, color: "var(--accent)", marginLeft: "auto" }}>{perDay}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-muted)", flexShrink: 0 }}>1</span>
            <input
              type="range" min={1} max={20} step={1} value={perDay}
              className="volume-range"
              onChange={e => setPerDay(parseInt(e.target.value))}
              style={{ ["--fill" as any]: `${((perDay - 1) / (20 - 1)) * 100}%` }}
            />
            <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-muted)", flexShrink: 0 }}>20</span>
          </div>
          <div style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.5, marginTop: 6 }}>
            How many characters take a turn each day.
          </div>
        </div>

        {/* Agent count indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.1em" }}>
            CHARACTERS LOADED
          </div>
          <span className="font-pixel" style={{
            fontSize: 18, marginLeft: "auto",
            color: world.agents.length > 0 ? "var(--accent)" : "var(--red)",
          }}>
            {world.agents.length}
          </span>
        </div>
      </div>

      {/* Run button */}
      {world.agents.length === 0 && (
        <div className="font-pixel" style={{
          fontSize: 8, color: "var(--red)", marginBottom: 10,
          padding: "8px 12px", border: "1px solid rgba(255,68,68,0.3)",
          background: "rgba(255,68,68,0.05)", letterSpacing: "0.06em",
        }}>
          ✖ ADD CHARACTERS TO ROSTER BEFORE LAUNCHING
        </div>
      )}

      <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.6, marginBottom: 10 }}>
        Begin day by day to watch each day unfold and step in between days, or fast-forward to run straight through and review the outcome.
      </div>

      {/* Primary: begin day-by-day. The town advances one day at a time, and you can
          nudge / inject events / add characters / set a prophecy between days. */}
      <button
        className="btn"
        onClick={begin}
        disabled={!canRun}
        style={{ width: "100%", padding: "14px", fontSize: 10, letterSpacing: "0.15em" }}
      >
        {saving ? "SAVING EVENT..." : "▶  BEGIN DAY BY DAY"}
      </button>

      {/* Secondary: fast-forward straight through N days (the old batch behavior). */}
      <button
        className="btn-ghost"
        onClick={run}
        disabled={!canRun}
        style={{ width: "100%", padding: "11px", fontSize: 9, letterSpacing: "0.12em", marginTop: 8 }}
      >
        ▶▶  FAST-FORWARD {days} DAYS
      </button>

      {err && (
        <div style={{ marginTop: 10, fontSize: 10, color: "var(--red)", fontFamily: "ui-monospace", letterSpacing: "0.04em" }}>
          ✖ {err}
        </div>
      )}
    </div>
  );
}
