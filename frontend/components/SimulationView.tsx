"use client";

import { useMemo, useState } from "react";
import type { SimulationResult, World } from "@/lib/types";
import { RelationshipGraph } from "./RelationshipGraph";
import { Inspector } from "./Inspector";

type Selection = { kind: "node"; id: string } | { kind: "edge"; key: string } | null;

export function SimulationView({
  result, world, worldId,
}: {
  result: SimulationResult;
  world: World;
  worldId: string;
}) {
  const [day, setDay] = useState(result.snapshots[result.snapshots.length - 1]?.day ?? 1);
  const [selection, setSelection] = useState<Selection>(null);
  const [showReport, setShowReport] = useState(false);

  const snap = useMemo(
    () => result.snapshots.find((s) => s.day === day) ?? result.snapshots[0],
    [result, day]
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* world context header */}
      <div style={{
        background: "#0d1117", border: "1px solid #1a2030", borderRadius: 10,
        padding: "12px 18px", marginBottom: 10,
      }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 10, color: "#374151", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>
              World
            </div>
            <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.5 }}>
              {world.prompt}
            </div>
          </div>
          {world.starting_event && (
            <div style={{
              borderLeft: "3px solid #f59e0b", paddingLeft: 12,
              maxWidth: 340, flexShrink: 0,
            }}>
              <div style={{ fontSize: 10, color: "#92400e", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>
                Active event
              </div>
              <div style={{ fontSize: 13, color: "#fcd34d", lineHeight: 1.5 }}>
                {world.starting_event}
              </div>
            </div>
          )}
          <div style={{ display: "flex", gap: 16, alignItems: "center", flexShrink: 0 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#60a5fa" }}>
                {snap.agents.length}
              </div>
              <div style={{ fontSize: 10, color: "#374151" }}>agents</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#a78bfa" }}>
                {result.days}d
              </div>
              <div style={{ fontSize: 10, color: "#374151" }}>simulated</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#34d399" }}>
                {snap.metrics.friendship_count}
              </div>
              <div style={{ fontSize: 10, color: "#374151" }}>friendships</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#f87171" }}>
                {snap.metrics.rivalry_count + snap.metrics.conflict_count}
              </div>
              <div style={{ fontSize: 10, color: "#374151" }}>tensions</div>
            </div>
          </div>
        </div>
      </div>

      {/* main body: graph + inspector */}
      <div style={{
        display: "flex", height: "calc(100vh - 260px)", minHeight: 520,
        borderRadius: 12, overflow: "hidden",
        border: "1px solid #1a2030",
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <RelationshipGraph
            agents={snap.agents}
            selection={selection}
            onSelect={setSelection}
          />
        </div>
        <Inspector
          selection={selection}
          snap={snap}
          initialMetrics={result.initial_metrics}
          worldId={worldId}
        />
      </div>

      {/* timeline scrubber */}
      <div style={{
        marginTop: 12,
        background: "#0d1117", border: "1px solid #1a2030", borderRadius: 10,
        padding: "10px 14px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 11, color: "#4b5563", flexShrink: 0 }}>Day</span>
          <div style={{ flex: 1, display: "flex", gap: 4, flexWrap: "wrap" }}>
            {result.snapshots.map((s) => {
              const isActive = s.day === day;
              const hasHighlights = s.highlights.length > 0;
              return (
                <button
                  key={s.day}
                  onClick={() => { setDay(s.day); setSelection(null); }}
                  title={s.highlights[0]?.summary ?? `Day ${s.day}`}
                  style={{
                    width: 32, height: 28, borderRadius: 6, cursor: "pointer",
                    fontSize: 11, fontWeight: isActive ? 600 : 400,
                    background: isActive ? "#1e3a5f" : hasHighlights ? "#0e1a26" : "transparent",
                    color: isActive ? "#60a5fa" : hasHighlights ? "#475569" : "#374151",
                    border: `1px solid ${isActive ? "#2563eb" : hasHighlights ? "#1e2b3a" : "transparent"}`,
                    transition: "all 0.15s",
                    position: "relative",
                  }}
                >
                  {s.day}
                  {hasHighlights && !isActive && (
                    <span style={{
                      position: "absolute", top: 3, right: 3,
                      width: 4, height: 4, borderRadius: "50%", background: "#2563eb",
                    }} />
                  )}
                </button>
              );
            })}
          </div>
          <button
            onClick={() => setShowReport((v) => !v)}
            style={{
              fontSize: 11, padding: "4px 12px", borderRadius: 6, cursor: "pointer", flexShrink: 0,
              background: showReport ? "#1e3a5f" : "transparent",
              color: showReport ? "#60a5fa" : "#4b5563",
              border: `1px solid ${showReport ? "#2563eb" : "#1a2030"}`,
            }}
          >
            Final report
          </button>
        </div>
      </div>

      {/* final report */}
      {showReport && (
        <div style={{
          marginTop: 12, background: "#0d1117",
          border: "1px solid #1a2030", borderRadius: 10, padding: "18px 20px",
        }}>
          <div style={{ fontSize: 10, color: "#4b5563", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>
            Final report — {result.days}-day simulation
          </div>
          <div style={{ fontSize: 13, color: "#94a3b8", whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
            {result.final_report}
          </div>
        </div>
      )}
    </div>
  );
}
