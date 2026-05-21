"use client";

import { useMemo, useState } from "react";
import type { SimulationResult, World } from "@/lib/types";
import { RelationshipGraph } from "./RelationshipGraph";
import { Inspector } from "./Inspector";

type Selection = { kind: "node"; id: string } | { kind: "edge"; key: string } | null;

const CONTINUE_OPTIONS = [7, 14, 30];

export function SimulationView({
  result, world, worldId, isLive = false, onContinue,
}: {
  result: SimulationResult;
  world: World;
  worldId: string;
  isLive?: boolean;
  onContinue?: (days: number, perDay: number) => void;
}) {
  const lastSnap = result.snapshots[result.snapshots.length - 1];
  const [day, setDay] = useState<number>(lastSnap?.day ?? 1);
  const [selection, setSelection] = useState<Selection>(null);
  const [showReport, setShowReport] = useState(false);
  const [continueDays, setContinueDays] = useState(7);
  const [continuePerDay, setContinuePerDay] = useState(8);
  const [showContinueMenu, setShowContinueMenu] = useState(false);

  // When streaming, auto-advance to latest day
  const effectiveDay = isLive ? (lastSnap?.day ?? day) : day;
  const snap = useMemo(
    () => result.snapshots.find((s) => s.day === effectiveDay) ?? lastSnap,
    [result, effectiveDay, lastSnap]
  );

  if (!snap) return null;

  const activeEvent = snap.active_event ?? world.starting_event;
  const dynamicEvents = result.dynamic_events ?? {};
  const totalDays = result.days;

  function handleDayClick(d: number) {
    if (!isLive) {
      setDay(d);
      setSelection(null);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* World context header */}
      <div style={{
        background: "#0a0f18", border: "1px solid #1a2030", borderRadius: 10,
        padding: "12px 18px", marginBottom: 10,
      }}>
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 9, color: "#374151", textTransform: "uppercase",
              letterSpacing: "0.1em", marginBottom: 4,
            }}>
              World
            </div>
            <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.5 }}>
              {world.prompt}
            </div>
          </div>

          {activeEvent && (
            <div style={{
              borderLeft: "2px solid #f59e0b", paddingLeft: 12,
              maxWidth: 300, flexShrink: 0,
            }}>
              <div style={{
                fontSize: 9, color: "#92400e", textTransform: "uppercase",
                letterSpacing: "0.1em", marginBottom: 4,
              }}>
                {snap.active_event && snap.active_event !== world.starting_event
                  ? `Day ${snap.day} event`
                  : "Starting event"}
              </div>
              <div style={{ fontSize: 12, color: "#fcd34d", lineHeight: 1.5 }}>
                {activeEvent}
              </div>
            </div>
          )}

          {/* Stats */}
          <div style={{ display: "flex", gap: 16, alignItems: "center", flexShrink: 0 }}>
            {[
              { v: snap.agents.length, label: "agents", color: "#60a5fa" },
              { v: isLive ? `${snap.day}/${totalDays}d` : `${totalDays}d`, label: isLive ? "running" : "days", color: "#a78bfa" },
              { v: snap.metrics.friendship_count, label: "friends", color: "#34d399" },
              { v: snap.metrics.romance_count, label: "romances", color: "#f472b6" },
              { v: snap.metrics.rivalry_count + snap.metrics.conflict_count, label: "tensions", color: "#f87171" },
            ].map(({ v, label, color }) => (
              <div key={label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 700, color }}>{v}</div>
                <div style={{ fontSize: 9, color: "#374151" }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Graph + Inspector */}
      <div style={{
        display: "flex", height: "calc(100vh - 290px)", minHeight: 480,
        borderRadius: 12, overflow: "hidden", border: "1px solid #1a2030",
      }}>
        <div style={{ flex: 1, minWidth: 0, position: "relative" }}>
          <RelationshipGraph
            agents={snap.agents}
            selection={selection}
            onSelect={setSelection}
          />
          {isLive && (
            <div style={{
              position: "absolute", top: 12, left: 12,
              display: "flex", alignItems: "center", gap: 6,
              background: "#080d1380", backdropFilter: "blur(6px)",
              border: "1px solid #1a2030", borderRadius: 8,
              padding: "6px 12px",
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: "50%", background: "#22c55e",
                boxShadow: "0 0 6px #22c55e",
              }} />
              <span style={{ fontSize: 11, color: "#94a3b8" }}>
                Live · Day {snap.day}
              </span>
            </div>
          )}
        </div>
        <Inspector
          selection={selection}
          snap={snap}
          initialMetrics={result.initial_metrics}
          worldId={worldId}
        />
      </div>

      {/* Timeline + controls */}
      <div style={{
        marginTop: 10,
        background: "#0a0f18", border: "1px solid #1a2030", borderRadius: 10,
        padding: "10px 14px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 10, color: "#4b5563", flexShrink: 0 }}>Day</span>

          <div style={{ flex: 1, display: "flex", gap: 3, flexWrap: "wrap" }}>
            {result.snapshots.map((s) => {
              const isActive = s.day === effectiveDay;
              const hasDynEv = !!dynamicEvents[String(s.day)];
              const hasHighlights = s.highlights.length > 0;
              return (
                <button
                  key={s.day}
                  onClick={() => handleDayClick(s.day)}
                  title={
                    hasDynEv
                      ? `Day ${s.day} event: ${dynamicEvents[String(s.day)]}`
                      : s.highlights[0]?.summary ?? `Day ${s.day}`
                  }
                  style={{
                    width: 30, height: 26, borderRadius: 5, cursor: isLive ? "default" : "pointer",
                    fontSize: 10, fontWeight: isActive ? 600 : 400,
                    background: isActive
                      ? "#1e3a5f"
                      : hasDynEv
                      ? "#1a1400"
                      : hasHighlights
                      ? "#0e1a26"
                      : "transparent",
                    color: isActive ? "#60a5fa" : hasDynEv ? "#f59e0b" : hasHighlights ? "#475569" : "#2a3547",
                    border: `1px solid ${isActive ? "#2563eb" : hasDynEv ? "#78350f" : hasHighlights ? "#1e2b3a" : "transparent"}`,
                    position: "relative",
                    transition: "all 0.1s",
                  }}
                >
                  {s.day}
                  {hasDynEv && !isActive && (
                    <span style={{
                      position: "absolute", top: 2, right: 2,
                      width: 3, height: 3, borderRadius: "50%", background: "#f59e0b",
                    }} />
                  )}
                  {!hasDynEv && hasHighlights && !isActive && (
                    <span style={{
                      position: "absolute", top: 2, right: 2,
                      width: 3, height: 3, borderRadius: "50%", background: "#2563eb",
                    }} />
                  )}
                </button>
              );
            })}
          </div>

          {/* Controls: report + continue */}
          <div style={{ display: "flex", gap: 6, flexShrink: 0, alignItems: "center" }}>
            {!isLive && (
              <button
                onClick={() => setShowReport((v) => !v)}
                style={{
                  fontSize: 11, padding: "4px 12px", borderRadius: 6, cursor: "pointer",
                  background: showReport ? "#1e3a5f" : "transparent",
                  color: showReport ? "#60a5fa" : "#4b5563",
                  border: `1px solid ${showReport ? "#2563eb" : "#1a2030"}`,
                }}
              >
                Report
              </button>
            )}

            {onContinue && !isLive && (
              <div style={{ position: "relative" }}>
                <button
                  onClick={() => setShowContinueMenu((v) => !v)}
                  style={{
                    fontSize: 11, padding: "4px 12px", borderRadius: 6, cursor: "pointer",
                    background: showContinueMenu ? "#14321a" : "transparent",
                    color: showContinueMenu ? "#22c55e" : "#4b5563",
                    border: `1px solid ${showContinueMenu ? "#166534" : "#1a2030"}`,
                  }}
                >
                  Continue +
                </button>
                {showContinueMenu && (
                  <div style={{
                    position: "absolute", right: 0, bottom: "calc(100% + 6px)",
                    background: "#0d1117", border: "1px solid #1a2030", borderRadius: 8,
                    padding: "12px 14px", width: 200, zIndex: 10,
                    boxShadow: "0 8px 32px #00000080",
                  }}>
                    <div style={{ fontSize: 10, color: "#4b5563", marginBottom: 8 }}>
                      Add more days from Day {lastSnap.day}
                    </div>
                    <div style={{ display: "flex", gap: 4, marginBottom: 10 }}>
                      {CONTINUE_OPTIONS.map((d) => (
                        <button
                          key={d}
                          onClick={() => setContinueDays(d)}
                          style={{
                            flex: 1, padding: "4px 0", borderRadius: 5, fontSize: 11, cursor: "pointer",
                            background: continueDays === d ? "#1e3a5f" : "transparent",
                            color: continueDays === d ? "#60a5fa" : "#4b5563",
                            border: `1px solid ${continueDays === d ? "#2563eb" : "#1a2030"}`,
                          }}
                        >
                          {d}d
                        </button>
                      ))}
                    </div>
                    <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 10 }}>
                      <span style={{ fontSize: 10, color: "#4b5563" }}>AI/day</span>
                      <input
                        type="number" min={1} max={20} value={continuePerDay}
                        onChange={(e) => setContinuePerDay(parseInt(e.target.value) || 8)}
                        style={{ flex: 1, fontSize: 11 }}
                      />
                    </div>
                    <button
                      onClick={() => {
                        setShowContinueMenu(false);
                        onContinue(continueDays, continuePerDay);
                      }}
                      style={{
                        width: "100%", padding: "6px 0", borderRadius: 6, cursor: "pointer",
                        background: "#14321a", color: "#22c55e",
                        border: "1px solid #166534", fontSize: 11, fontWeight: 600,
                      }}
                    >
                      Continue {continueDays} days →
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Legend for dynamic events */}
      {Object.keys(dynamicEvents).length > 0 && !isLive && (
        <div style={{
          marginTop: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
        }}>
          <span style={{ fontSize: 9, color: "#374151", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Dynamic events
          </span>
          {Object.entries(dynamicEvents).map(([day, ev]) => (
            <div key={day} style={{
              fontSize: 10, color: "#fcd34d",
              background: "#1a1400", border: "1px solid #78350f",
              borderRadius: 5, padding: "2px 8px",
            }}>
              Day {day}: {ev}
            </div>
          ))}
        </div>
      )}

      {/* Final report */}
      {showReport && result.final_report && (
        <div style={{
          marginTop: 12, background: "#0a0f18",
          border: "1px solid #1a2030", borderRadius: 10, padding: "18px 20px",
        }}>
          <div style={{
            fontSize: 9, color: "#4b5563", textTransform: "uppercase",
            letterSpacing: "0.1em", marginBottom: 12,
          }}>
            Final report — {result.days}-day simulation
          </div>
          <div style={{
            fontSize: 13, color: "#94a3b8", whiteSpace: "pre-wrap", lineHeight: 1.8,
          }}>
            {result.final_report}
          </div>
        </div>
      )}
    </div>
  );
}
