"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World } from "@/lib/types";
import { ProphecyInput, QuestionInput } from "./Engagement";

const DAY_OPTIONS = [7, 14, 30, 60];

export function EventAndRun({ worldId, world, onWorldChange, onRun, onBegin }: {
  worldId: string; world: World; onWorldChange: (w: World) => void;
  onRun: (days: number, perDay: number) => void;
  onBegin: (perDay: number) => void;
}) {
  const [event, setEvent] = useState(world.starting_event || "A new entrepreneurship club launches with only 12 spots.");
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
        <span style={{ color: "var(--gold)", fontSize: 12 }}>◉</span>
        <span className="font-pixel" style={{ fontSize: 10, color: "var(--gold)", letterSpacing: "0.1em" }}>
          MISSION BRIEFING
        </span>
      </div>
      <div style={{ height: 1, background: "linear-gradient(90deg, transparent, var(--gold), transparent)", marginBottom: 20 }} />

      {/* Event input */}
      <div style={{ marginBottom: 20 }}>
        <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 8, letterSpacing: "0.1em" }}>
          STARTING EVENT
        </div>
        <div style={{ position: "relative" }}>
          <span style={{
            position: "absolute", left: 12, top: 10,
            fontSize: 12, color: "var(--gold)",
            fontFamily: "ui-monospace, monospace", zIndex: 1, pointerEvents: "none",
          }}>!</span>
          <textarea
            rows={2}
            value={event}
            onChange={e => setEvent(e.target.value)}
            placeholder="describe the event that kicks off your simulation..."
            style={{ paddingLeft: 30, borderColor: "rgba(255,215,0,0.3)", color: "var(--gold)" }}
          />
        </div>
      </div>

      {/* Prediction question — anchors the forecast */}
      <QuestionInput worldId={worldId} initial={world.question}
        onSaved={q => onWorldChange({ ...world, question: q })} />

      {/* Prophecy */}
      <ProphecyInput worldId={worldId} initial={world.prophecy} />

      {/* Options row */}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "wrap", marginBottom: 20 }}>
        {/* Duration */}
        <div>
          <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 8, letterSpacing: "0.1em" }}>
            FAST-FORWARD (DAYS)
          </div>
          <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
            {DAY_OPTIONS.map(d => (
              <button key={d} onClick={() => setDays(d)} style={{
                padding: "7px 12px", cursor: "pointer",
                fontFamily: "var(--font-pixel, monospace)", fontSize: 9,
                textTransform: "uppercase", letterSpacing: "0.05em",
                border: `1px solid ${days === d ? "var(--gold)" : "var(--border)"}`,
                background: days === d ? "rgba(255,215,0,0.08)" : "transparent",
                color: days === d ? "var(--gold)" : "var(--text-dim)",
                boxShadow: days === d ? "0 0 8px rgba(255,215,0,0.2)" : "none",
                transition: "all 0.1s",
              }}>
                {d}D
              </button>
            ))}
            {/* Free duration: type any number of days (clamped 1..1000). Highlights when
                the value isn't one of the presets, so a custom run is visibly selected. */}
            <input
              type="number" min={1} max={1000} value={days}
              onChange={e => setDays(Math.max(1, Math.min(1000, parseInt(e.target.value) || 1)))}
              aria-label="custom number of days"
              style={{
                width: 64, marginLeft: 3, fontSize: 11, textAlign: "center",
                borderColor: DAY_OPTIONS.includes(days) ? "var(--border)" : "var(--gold)",
                color: DAY_OPTIONS.includes(days) ? "var(--text-dim)" : "var(--gold)",
              }}
            />
          </div>
        </div>

        {/* AI per day */}
        <div>
          <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 8, letterSpacing: "0.1em" }}>
            AI CHARACTERS / DAY
          </div>
          <input
            type="number" min={1} max={20} value={perDay}
            onChange={e => setPerDay(parseInt(e.target.value) || 8)}
            style={{ width: 72 }}
          />
        </div>

        {/* Agent count indicator */}
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 4, letterSpacing: "0.1em" }}>
            CHARACTERS LOADED
          </div>
          <div className="font-pixel" style={{
            fontSize: 18, color: world.agents.length > 0 ? "var(--accent)" : "var(--red)",
            textShadow: "none",
          }}>
            {world.agents.length}
          </div>
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

      {/* Primary: begin day-by-day. The town advances one day at a time, and you can
          nudge / inject events / add characters / set a prophecy between days. */}
      <button
        className="btn"
        onClick={begin}
        disabled={!canRun}
        style={{ width: "100%", padding: "14px", fontSize: 10, letterSpacing: "0.15em" }}
      >
        {saving ? "SAVING EVENT..." : "▶  BEGIN — DAY BY DAY"}
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
