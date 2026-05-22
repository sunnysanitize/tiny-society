"use client";
import { useRef, useState } from "react";
import type { World, SimulationResult, DaySnapshot } from "@/lib/types";
import { api } from "@/lib/api";
import { WorldSetup } from "@/components/WorldSetup";
import { CharacterEditor } from "@/components/CharacterEditor";
import { EventAndRun } from "@/components/EventAndRun";
import { SimulationView } from "@/components/SimulationView";

type Phase = "setup" | "running" | "result";

const SCANLINE_BG: React.CSSProperties = {
  position: "fixed", inset: 0, pointerEvents: "none", zIndex: -1,
  background:
    "radial-gradient(ellipse at 20% 30%, rgba(121,80,242,0.05) 0%, transparent 55%)," +
    "radial-gradient(ellipse at 80% 70%, rgba(78,197,240,0.04) 0%, transparent 55%)",
};

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
    setWorldId(null); setWorld(null); setResult(null);
    setPhase("setup"); setLiveSnaps([]); setRunError(null);
  }

  async function runStream(wid: string, w: World, days: number, perDay: number, isContin = false) {
    abortRef.current = false;
    setPhase("running"); setRunError(null);
    if (!isContin) setLiveSnaps([]);
    setTotalDays((isContin ? (result?.days ?? 0) : 0) + days);
    setWorld(w);
    const stream = isContin ? api.continueStream(wid, days, perDay) : api.simulateStream(wid, days, perDay);
    try {
      for await (const event of stream) {
        if (abortRef.current) break;
        if (event.type === "day") {
          setLiveSnaps((prev) => [...(isContin ? prev : []), event.snapshot]);
        } else if (event.type === "done") {
          setResult(event.result); setPhase("result"); return;
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

  const liveResult: SimulationResult | null = (() => {
    if (liveSnaps.length === 0) return null;
    const first = liveSnaps[0].metrics;
    const last = liveSnaps[liveSnaps.length - 1].metrics;
    return { days: totalDays, snapshots: liveSnaps, initial_metrics: result?.initial_metrics ?? first, final_metrics: last, final_report: "", dynamic_events: {} };
  })();
  const viewResult = phase === "result" ? result : liveResult ?? result;

  return (
    <>
      {/* ambient background glow */}
      <div style={SCANLINE_BG} />

      <main className="page-enter" style={{ maxWidth: 1400, margin: "0 auto", padding: "20px 24px" }}>

        {/* ── Title Bar ───────────────────────────────────────────────────── */}
        <header style={{ marginBottom: 28 }}>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "14px 20px",
            background: "var(--surface)",
            border: "1px solid var(--accent-dim)",
            boxShadow: "0 6px 24px rgba(100,80,200,0.09)",
            position: "relative",
          }}>
            {/* corner brackets */}
            <div style={{ position: "absolute", top: -2, left: -2, width: 14, height: 14, borderTop: "2px solid var(--accent)", borderLeft: "2px solid var(--accent)" }} />
            <div style={{ position: "absolute", bottom: -2, right: -2, width: 14, height: 14, borderBottom: "2px solid var(--accent)", borderRight: "2px solid var(--accent)" }} />

            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
                <div style={{
                  width: 8, height: 8, borderRadius: "50%", background: "var(--accent)",
                  boxShadow: "0 0 10px var(--accent)",
                  animation: "neon-pulse 2s ease-in-out infinite",
                }} />
                <h1 className="font-pixel" style={{
                  fontSize: 14, color: "var(--accent)", margin: 0,
                  textShadow: "none",
                  animation: "title-flicker 10s infinite",
                  letterSpacing: "0.05em",
                }}>
                  TINY SOCIETY AI
                </h1>
                <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", padding: "2px 6px", border: "1px solid var(--border)" }}>
                  v1.0
                </span>
              </div>
              <div style={{ fontSize: 10, color: "var(--text-dim)", letterSpacing: "0.08em", paddingLeft: 20 }}>
                multi-agent social simulation · llm-powered agent reasoning
              </div>
            </div>

            {worldId && (
              <button
                onClick={reset}
                className="font-pixel"
                style={{
                  fontSize: 8, padding: "7px 14px", cursor: "pointer",
                  background: "transparent", color: "var(--text-dim)",
                  border: "1px solid var(--border)", letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  transition: "border-color 0.1s, color 0.1s",
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "var(--red)"; (e.currentTarget as HTMLElement).style.color = "var(--red)"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border)"; (e.currentTarget as HTMLElement).style.color = "var(--text-dim)"; }}
              >
                ← QUIT
              </button>
            )}
          </div>

          {/* separator line */}
          <div style={{ height: 1, background: "linear-gradient(90deg, transparent, var(--accent-dim), transparent)" }} />
        </header>

        {/* ── Setup: world creation ─────────────────────────────────────── */}
        {phase === "setup" && !worldId && (
          <div className="stagger-in" style={{ maxWidth: 680, margin: "0 auto" }}>
            <WorldSetup onCreated={(wid, w) => { setWorldId(wid); setWorld(w); }} />
          </div>
        )}

        {/* ── Setup: characters + event ─────────────────────────────────── */}
        {phase === "setup" && worldId && world && (
          <div className="stagger-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <CharacterEditor worldId={worldId} world={world} onWorldChange={setWorld} />
            <EventAndRun worldId={worldId} world={world} onWorldChange={setWorld} onRun={handleRun} />
            {runError && <GameError message={runError} />}
          </div>
        )}

        {/* ── Live progress ─────────────────────────────────────────────── */}
        {phase === "running" && (
          <div style={{ marginBottom: 16 }}>
            <LiveProgress
              currentDay={liveSnaps.length > 0 ? liveSnaps[liveSnaps.length - 1].day : 0}
              totalDays={totalDays}
              latestLog={liveSnaps.length > 0 ? liveSnaps[liveSnaps.length - 1].event_log : []}
            />
          </div>
        )}

        {/* ── Simulation view ───────────────────────────────────────────── */}
        {viewResult && worldId && world && (
          <SimulationView
            result={viewResult}
            world={world}
            worldId={worldId}
            isLive={phase === "running"}
            onContinue={phase === "result" ? handleContinue : undefined}
          />
        )}

        {phase === "result" && runError && <GameError message={`CONTINUE FAILED: ${runError}`} />}
      </main>
    </>
  );
}

function GameError({ message }: { message: string }) {
  return (
    <div style={{
      marginTop: 12, padding: "10px 16px",
      background: "rgba(255,68,68,0.06)", border: "1px solid var(--red)",
      boxShadow: "0 0 12px rgba(255,68,68,0.2)",
      fontSize: 11, color: "var(--red)", fontFamily: "ui-monospace, monospace",
      letterSpacing: "0.05em",
    }}>
      ✖ {message}
    </div>
  );
}

function LiveProgress({ currentDay, totalDays, latestLog }: {
  currentDay: number; totalDays: number; latestLog: string[];
}) {
  const pct = totalDays > 0 ? Math.round((currentDay / totalDays) * 100) : 0;
  const barFilled = Math.floor(pct / 2);
  const barEmpty = 50 - barFilled;

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--accent-dim)",
      boxShadow: "0 6px 24px rgba(100,80,200,0.09)",
      padding: "16px 20px", position: "relative",
    }}>
      <div style={{ position: "absolute", top: -2, left: -2, width: 12, height: 12, borderTop: "2px solid var(--accent)", borderLeft: "2px solid var(--accent)" }} />
      <div style={{ position: "absolute", bottom: -2, right: -2, width: 12, height: 12, borderBottom: "2px solid var(--accent)", borderRight: "2px solid var(--accent)" }} />

      {/* header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div style={{
          width: 8, height: 8, borderRadius: "50%", background: "var(--accent)",
          boxShadow: "0 0 8px var(--accent)", animation: "pulse 1.2s ease-in-out infinite",
        }} />
        <span className="font-pixel" style={{ fontSize: 9, color: "var(--accent)", letterSpacing: "0.1em" }}>
          {currentDay === 0 ? "INITIALIZING SIMULATION..." : `SIMULATING — DAY ${currentDay} / ${totalDays}`}
        </span>
        <span className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", marginLeft: "auto" }}>
          {pct}%
        </span>
      </div>

      {/* pixel progress bar */}
      <div className="font-pixel" style={{
        fontSize: 8, letterSpacing: "0px",
        color: "var(--accent)", marginBottom: 12,
        fontFamily: "ui-monospace, monospace",
        textShadow: "none",
        overflowX: "hidden", whiteSpace: "nowrap",
      }}>
        {"▓".repeat(barFilled)}
        <span style={{ color: "var(--text-muted)" }}>{"░".repeat(barEmpty)}</span>
      </div>

      {/* log */}
      {latestLog.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 3, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
          {latestLog.slice(-4).map((line, i, arr) => (
            <div key={i} style={{
              fontSize: 10, color: i === arr.length - 1 ? "var(--text)" : "var(--text-dim)",
              lineHeight: 1.5, fontFamily: "ui-monospace, monospace",
              opacity: 0.3 + (i / arr.length) * 0.7,
            }}>
              <span style={{ color: "var(--accent-dim)", marginRight: 6 }}>›</span>{line}
            </div>
          ))}
          <span className="blink" style={{ fontSize: 10, color: "var(--accent)", marginTop: 2 }}>█</span>
        </div>
      )}
    </div>
  );
}
