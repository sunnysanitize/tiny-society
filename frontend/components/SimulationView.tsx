"use client";
import { useMemo, useState } from "react";
import type { SimulationResult, World } from "@/lib/types";
import { RelationshipGraph } from "./RelationshipGraph";
import { Inspector } from "./Inspector";

type Selection = { kind: "node"; id: string } | { kind: "edge"; key: string } | null;

const CONTINUE_OPTIONS = [7, 14, 30];

const STAT: React.CSSProperties = { textAlign: "center" };

function StatBox({ value, label, color }: { value: number | string; label: string; color: string }) {
  return (
    <div style={STAT}>
      <div className="font-pixel" style={{ fontSize: 16, color, textShadow: `0 0 12px ${color}80` }}>{value}</div>
      <div className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", marginTop: 4, letterSpacing: "0.08em" }}>{label}</div>
    </div>
  );
}

export function SimulationView({ result, world, worldId, isLive = false, onContinue }: {
  result: SimulationResult; world: World; worldId: string;
  isLive?: boolean; onContinue?: (days: number, perDay: number) => void;
}) {
  const lastSnap = result.snapshots[result.snapshots.length - 1];
  const [day, setDay] = useState<number>(lastSnap?.day ?? 1);
  const [selection, setSelection] = useState<Selection>(null);
  const [showReport, setShowReport] = useState(false);
  const [continueDays, setContinueDays] = useState(7);
  const [continuePerDay, setContinuePerDay] = useState(8);
  const [showContinueMenu, setShowContinueMenu] = useState(false);

  const effectiveDay = isLive ? (lastSnap?.day ?? day) : day;
  const snap = useMemo(
    () => result.snapshots.find(s => s.day === effectiveDay) ?? lastSnap,
    [result, effectiveDay, lastSnap]
  );

  if (!snap) return null;

  const activeEvent = snap.active_event ?? world.starting_event;
  const dynamicEvents = result.dynamic_events ?? {};
  const totalDays = result.days;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>

      {/* ── HUD header ─────────────────────────────────────────────────── */}
      <div style={{
        background: "var(--surface)", border: "1px solid var(--accent-dim)",
        boxShadow: "0 6px 24px rgba(100,80,200,0.09)",
        padding: "12px 18px", position: "relative",
      }}>
        <div style={{ position: "absolute", top: -2, left: -2, width: 12, height: 12, borderTop: "2px solid var(--accent)", borderLeft: "2px solid var(--accent)" }} />
        <div style={{ position: "absolute", bottom: -2, right: -2, width: 12, height: 12, borderBottom: "2px solid var(--accent)", borderRight: "2px solid var(--accent)" }} />

        <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
          {/* world description */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", letterSpacing: "0.12em", marginBottom: 5 }}>
              ◆ WORLD
            </div>
            <div style={{ fontSize: 11, color: "var(--text)", lineHeight: 1.6, fontFamily: "ui-monospace, monospace" }}>
              {world.prompt}
            </div>
          </div>

          {/* starting event */}
          {activeEvent && (
            <div style={{
              borderLeft: "2px solid var(--gold)", paddingLeft: 12,
              maxWidth: 280, flexShrink: 0,
            }}>
              <div className="font-pixel" style={{ fontSize: 7, color: "rgba(255,215,0,0.5)", letterSpacing: "0.1em", marginBottom: 5 }}>
                {snap.active_event && snap.active_event !== world.starting_event
                  ? `DAY ${snap.day} EVENT` : "STARTING EVENT"}
              </div>
              <div style={{ fontSize: 11, color: "var(--gold)", lineHeight: 1.5, fontFamily: "ui-monospace" }}>
                {activeEvent}
              </div>
            </div>
          )}

          {/* stats */}
          <div style={{ display: "flex", gap: 18, alignItems: "center", flexShrink: 0 }}>
            <StatBox value={snap.agents.length} label="AGENTS" color="var(--cyan)" />
            <StatBox value={isLive ? `${snap.day}/${totalDays}` : `${totalDays}`} label={isLive ? "RUNNING" : "DAYS"} color="var(--accent)" />
            <StatBox value={snap.metrics.friendship_count} label="FRIENDS" color="#22c55e" />
            <StatBox value={snap.metrics.romance_count} label="ROMANCES" color="var(--pink)" />
            <StatBox value={snap.metrics.rivalry_count + snap.metrics.conflict_count} label="TENSIONS" color="var(--red)" />
          </div>
        </div>
      </div>

      {/* ── Graph + Inspector ──────────────────────────────────────────── */}
      <div style={{
        display: "flex", height: "calc(100vh - 290px)", minHeight: 480,
        overflow: "hidden",
        border: "1px solid var(--accent-dim)",
        boxShadow: "0 4px 16px rgba(100,80,200,0.08)",
      }}>
        <div style={{ flex: 1, minWidth: 0, position: "relative" }}>
          <RelationshipGraph agents={snap.agents} selection={selection} onSelect={setSelection} />
          {isLive && (
            <div style={{
              position: "absolute", top: 10, left: 10,
              display: "flex", alignItems: "center", gap: 6,
              background: "rgba(255,255,255,0.92)", backdropFilter: "blur(6px)",
              border: "1px solid var(--border)",
              padding: "5px 10px",
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: "50%", background: "var(--accent)",
                boxShadow: "0 0 8px var(--accent)", animation: "pulse 1.2s ease-in-out infinite",
              }} />
              <span className="font-pixel" style={{ fontSize: 7, color: "var(--accent)", letterSpacing: "0.08em" }}>
                LIVE · DAY {snap.day}
              </span>
            </div>
          )}
        </div>
        <Inspector selection={selection} snap={snap} initialMetrics={result.initial_metrics} worldId={worldId} />
      </div>

      {/* ── Timeline ──────────────────────────────────────────────────── */}
      <div style={{
        background: "var(--surface)", border: "1px solid var(--border)",
        padding: "10px 14px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", flexShrink: 0, letterSpacing: "0.1em" }}>DAY</span>

          <div style={{ flex: 1, display: "flex", gap: 2, flexWrap: "wrap" }}>
            {result.snapshots.map(s => {
              const isActive = s.day === effectiveDay;
              const hasDynEv = !!dynamicEvents[String(s.day)];
              const hasHL = s.highlights.length > 0;
              return (
                <button key={s.day}
                  onClick={() => { if (!isLive) { setDay(s.day); setSelection(null); } }}
                  title={hasDynEv ? `Day ${s.day}: ${dynamicEvents[String(s.day)]}` : s.highlights[0]?.summary ?? `Day ${s.day}`}
                  className="font-pixel"
                  style={{
                    width: 30, height: 26, cursor: isLive ? "default" : "pointer",
                    fontSize: 7, letterSpacing: 0,
                    background: isActive ? "rgba(121,80,242,0.1)" : hasDynEv ? "rgba(255,212,59,0.08)" : hasHL ? "rgba(78,197,240,0.06)" : "transparent",
                    color: isActive ? "var(--accent)" : hasDynEv ? "var(--gold)" : hasHL ? "var(--cyan)" : "var(--text-muted)",
                    border: `1px solid ${isActive ? "var(--accent)" : hasDynEv ? "rgba(255,212,59,0.35)" : hasHL ? "rgba(78,197,240,0.25)" : "transparent"}`,
                    boxShadow: isActive ? "0 2px 0 var(--accent-dim)" : "none",
                    position: "relative", transition: "all 0.1s",
                  }}>
                  {s.day}
                  {hasDynEv && !isActive && (
                    <span style={{ position: "absolute", top: 2, right: 2, width: 3, height: 3, borderRadius: "50%", background: "var(--gold)" }} />
                  )}
                </button>
              );
            })}
          </div>

          {/* controls */}
          <div style={{ display: "flex", gap: 5, flexShrink: 0 }}>
            {!isLive && (
              <button className="font-pixel"
                onClick={() => setShowReport(v => !v)}
                style={{
                  fontSize: 7, padding: "4px 10px", cursor: "pointer", letterSpacing: "0.08em",
                  background: showReport ? "rgba(0,212,255,0.1)" : "transparent",
                  color: showReport ? "var(--cyan)" : "var(--text-dim)",
                  border: `1px solid ${showReport ? "var(--cyan)" : "var(--border)"}`,
                  textTransform: "uppercase",
                }}>
                REPORT
              </button>
            )}

            {onContinue && !isLive && (
              <div style={{ position: "relative" }}>
                <button className="font-pixel"
                  onClick={() => setShowContinueMenu(v => !v)}
                  style={{
                    fontSize: 7, padding: "4px 10px", cursor: "pointer", letterSpacing: "0.08em",
                    background: showContinueMenu ? "rgba(121,80,242,0.08)" : "transparent",
                    color: showContinueMenu ? "var(--accent)" : "var(--text-dim)",
                    border: `1px solid ${showContinueMenu ? "var(--accent)" : "var(--border)"}`,
                    textTransform: "uppercase",
                  }}>
                  CONTINUE +
                </button>
                {showContinueMenu && (
                  <div style={{
                    position: "absolute", right: 0, bottom: "calc(100% + 6px)",
                    background: "var(--surface)", border: "1px solid var(--accent-dim)",
                    boxShadow: "0 6px 24px rgba(100,80,200,0.12)",
                    padding: "14px 16px", width: 200, zIndex: 10,
                  }}>
                    <div className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", marginBottom: 10, letterSpacing: "0.08em" }}>
                      EXTEND FROM DAY {lastSnap.day}
                    </div>
                    <div style={{ display: "flex", gap: 4, marginBottom: 10 }}>
                      {CONTINUE_OPTIONS.map(d => (
                        <button key={d} onClick={() => setContinueDays(d)} className="font-pixel" style={{
                          flex: 1, padding: "5px 0", fontSize: 7, cursor: "pointer",
                          letterSpacing: "0.05em", textTransform: "uppercase",
                          background: continueDays === d ? "rgba(121,80,242,0.1)" : "transparent",
                          color: continueDays === d ? "var(--accent)" : "var(--text-dim)",
                          border: `1px solid ${continueDays === d ? "var(--accent)" : "var(--border)"}`,
                        }}>{d}D</button>
                      ))}
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
                      <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", flexShrink: 0 }}>AI/DAY</span>
                      <input type="number" min={1} max={20} value={continuePerDay}
                        onChange={e => setContinuePerDay(parseInt(e.target.value) || 8)}
                        style={{ flex: 1, fontSize: 11 }} />
                    </div>
                    <button className="btn" onClick={() => { setShowContinueMenu(false); onContinue(continueDays, continuePerDay); }}
                      style={{ width: "100%", padding: "8px" }}>
                      ▶ RUN {continueDays} DAYS
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* dynamic events legend */}
      {Object.keys(dynamicEvents).length > 0 && !isLive && (
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", letterSpacing: "0.1em" }}>EVENTS</span>
          {Object.entries(dynamicEvents).map(([d, ev]) => (
            <div key={d} style={{
              fontSize: 9, color: "var(--gold)",
              background: "rgba(255,215,0,0.05)", border: "1px solid rgba(255,215,0,0.25)",
              padding: "2px 8px", fontFamily: "ui-monospace",
            }}>
              D{d}: {ev}
            </div>
          ))}
        </div>
      )}

      {/* final report */}
      {showReport && result.final_report && (
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          boxShadow: "0 4px 16px rgba(100,80,200,0.08)",
          padding: "20px 24px", position: "relative",
        }}>
          <div style={{ position: "absolute", top: -2, left: -2, width: 12, height: 12, borderTop: "2px solid var(--cyan)", borderLeft: "2px solid var(--cyan)" }} />
          <div className="font-pixel" style={{ fontSize: 8, color: "var(--cyan)", marginBottom: 14, letterSpacing: "0.1em" }}>
            ◆ MISSION REPORT — {result.days}-DAY SIMULATION
          </div>
          <div style={{ height: 1, background: "linear-gradient(90deg, transparent, var(--cyan), transparent)", marginBottom: 14 }} />
          <div style={{ fontSize: 12, color: "var(--text)", whiteSpace: "pre-wrap", lineHeight: 1.9, fontFamily: "ui-monospace, monospace" }}>
            {result.final_report}
          </div>
        </div>
      )}
    </div>
  );
}
