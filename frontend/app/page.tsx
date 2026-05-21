"use client";
import { useRef, useState } from "react";
import type { World, SimulationResult, DaySnapshot } from "@/lib/types";
import { api } from "@/lib/api";
import { WorldSetup } from "@/components/WorldSetup";
import { CharacterEditor } from "@/components/CharacterEditor";
import { EventAndRun } from "@/components/EventAndRun";
import { SimulationView } from "@/components/SimulationView";

type Phase = "setup" | "running" | "result";

export default function Page() {
  const [worldId, setWorldId] = useState<string | null>(null);
  const [world, setWorld] = useState<World | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [phase, setPhase] = useState<Phase>("setup");
  const [liveSnaps, setLiveSnaps] = useState<DaySnapshot[]>([]);
  const [totalDays, setTotalDays] = useState(0);
  const [runError, setRunError] = useState<string | null>(null);
  const abortRef = useRef(false);

  function reset() {
    setWorldId(null);
    setWorld(null);
    setResult(null);
    setPhase("setup");
    setLiveSnaps([]);
    setRunError(null);
  }

  async function runStream(
    wid: string,
    w: World,
    days: number,
    perDay: number,
    isContin = false,
  ) {
    abortRef.current = false;
    setPhase("running");
    setRunError(null);
    if (!isContin) setLiveSnaps([]);
    setTotalDays((isContin ? (result?.days ?? 0) : 0) + days);
    setWorld(w);

    const stream = isContin
      ? api.continueStream(wid, days, perDay)
      : api.simulateStream(wid, days, perDay);

    try {
      for await (const event of stream) {
        if (abortRef.current) break;
        if (event.type === "day") {
          setLiveSnaps((prev) => {
            const next = isContin ? prev : [];
            return [...next, event.snapshot];
          });
        } else if (event.type === "done") {
          setResult(event.result);
          setPhase("result");
          return;
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }
    } catch (e: any) {
      setRunError(e.message ?? "Simulation failed");
      setPhase(result ? "result" : "setup");
    }
  }

  function handleRun(days: number, perDay: number) {
    if (!worldId || !world) return;
    runStream(worldId, world, days, perDay, false);
  }

  function handleContinue(days: number, perDay: number) {
    if (!worldId || !world) return;
    runStream(worldId, world, days, perDay, true);
  }

  // Build a partial "live result" during streaming so SimulationView renders
  const liveResult: SimulationResult | null = (() => {
    if (liveSnaps.length === 0) return null;
    const firstMetrics = liveSnaps[0].metrics;
    const lastMetrics = liveSnaps[liveSnaps.length - 1].metrics;
    return {
      days: totalDays,
      snapshots: liveSnaps,
      initial_metrics: result?.initial_metrics ?? firstMetrics,
      final_metrics: lastMetrics,
      final_report: "",
      dynamic_events: {},
    };
  })();

  const viewResult = phase === "result" ? result : liveResult ?? result;

  return (
    <main style={{ maxWidth: 1400, margin: "0 auto", padding: "20px 24px" }}>
      <header style={{
        display: "flex", alignItems: "flex-end", justifyContent: "space-between",
        marginBottom: 24,
      }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>
            Tiny Society AI
          </h1>
          <p style={{ fontSize: 12, color: "#374151", margin: "4px 0 0" }}>
            Multi-agent social simulation · agents reason via LLM · watch society evolve
          </p>
        </div>
        {worldId && (
          <button
            onClick={reset}
            style={{
              fontSize: 11, padding: "5px 14px", borderRadius: 6, cursor: "pointer",
              background: "transparent", color: "#374151",
              border: "1px solid #1a2030",
            }}
          >
            New world
          </button>
        )}
      </header>

      {/* Setup flow */}
      {phase === "setup" && !worldId && (
        <WorldSetup onCreated={(wid, w) => { setWorldId(wid); setWorld(w); }} />
      )}

      {phase === "setup" && worldId && world && (
        <>
          <CharacterEditor worldId={worldId} world={world} onWorldChange={setWorld} />
          <div style={{ marginTop: 16 }}>
            <EventAndRun
              worldId={worldId}
              world={world}
              onWorldChange={setWorld}
              onRun={handleRun}
            />
          </div>
          {runError && (
            <div style={{
              marginTop: 12, padding: "10px 14px", background: "#1a0a0a",
              border: "1px solid #7f1d1d", borderRadius: 8,
              fontSize: 12, color: "#f87171",
            }}>
              {runError}
            </div>
          )}
        </>
      )}

      {/* Live simulation view during streaming */}
      {phase === "running" && (
        <div style={{ marginBottom: 16 }}>
          <LiveProgress
            currentDay={liveSnaps.length > 0 ? liveSnaps[liveSnaps.length - 1].day : 0}
            totalDays={totalDays}
            latestLog={liveSnaps.length > 0 ? liveSnaps[liveSnaps.length - 1].event_log : []}
          />
        </div>
      )}

      {/* Graph + inspector during streaming or after */}
      {viewResult && worldId && world && (
        <SimulationView
          result={viewResult}
          world={world}
          worldId={worldId}
          isLive={phase === "running"}
          onContinue={phase === "result" ? handleContinue : undefined}
        />
      )}

      {/* Error overlay on result page */}
      {phase === "result" && runError && (
        <div style={{
          marginTop: 12, padding: "10px 14px", background: "#1a0a0a",
          border: "1px solid #7f1d1d", borderRadius: 8,
          fontSize: 12, color: "#f87171",
        }}>
          Continue failed: {runError}
        </div>
      )}
    </main>
  );
}

function LiveProgress({
  currentDay, totalDays, latestLog,
}: {
  currentDay: number; totalDays: number; latestLog: string[];
}) {
  const pct = totalDays > 0 ? Math.round((currentDay / totalDays) * 100) : 0;
  return (
    <div style={{
      background: "#0d1117", border: "1px solid #1a2030", borderRadius: 10,
      padding: "14px 18px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
        <div style={{
          width: 8, height: 8, borderRadius: "50%", background: "#22c55e",
          boxShadow: "0 0 8px #22c55e", flexShrink: 0,
          animation: "pulse 1.5s ease-in-out infinite",
        }} />
        <span style={{ fontSize: 13, color: "#f1f5f9", fontWeight: 600 }}>
          {currentDay === 0 ? "Starting simulation…" : `Day ${currentDay} of ${totalDays}`}
        </span>
        <span style={{ fontSize: 11, color: "#374151", marginLeft: "auto" }}>
          {pct}%
        </span>
      </div>
      <div style={{
        height: 3, background: "#111827", borderRadius: 2, overflow: "hidden", marginBottom: 12,
      }}>
        <div style={{
          height: "100%", width: `${pct}%`,
          background: "linear-gradient(90deg, #1e3a5f, #2563eb)",
          borderRadius: 2, transition: "width 0.6s ease",
        }} />
      </div>
      {latestLog.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {latestLog.slice(-4).map((line, i) => (
            <div key={i} style={{
              fontSize: 11, color: i === latestLog.slice(-4).length - 1 ? "#94a3b8" : "#374151",
              lineHeight: 1.5,
              opacity: 0.4 + (i / latestLog.slice(-4).length) * 0.6,
            }}>
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
