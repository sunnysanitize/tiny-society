"use client";
import { useEffect, useRef, useState } from "react";
import type { World, SimulationResult, DaySnapshot } from "@/lib/types";
import { api, setAuthToken } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { WorldSetup } from "@/components/WorldSetup";
import { CharacterEditor } from "@/components/CharacterEditor";
import { EventAndRun } from "@/components/EventAndRun";
import { SimulationView } from "@/components/SimulationView";
import { AuthScreen } from "@/components/AuthScreen";
import { SavesScreen } from "@/components/SavesScreen";
import { SaveModal } from "@/components/SaveModal";
import type { Session } from "@supabase/supabase-js";

// "playing" = day-by-day interactive state (a run in progress the player advances one
// day at a time, intervening between days). "result" remains the post-run review state.
type Phase = "auth" | "saves" | "setup" | "running" | "playing" | "result";

const SCANLINE_BG: React.CSSProperties = {
  position: "fixed", inset: 0, pointerEvents: "none", zIndex: -1,
  background:
    "radial-gradient(ellipse at 20% 30%, rgba(121,80,242,0.05) 0%, transparent 55%)," +
    "radial-gradient(ellipse at 80% 70%, rgba(78,197,240,0.04) 0%, transparent 55%)",
};

export default function Page() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [worldId, setWorldId] = useState<string | null>(null);
  const [world, setWorld] = useState<World | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [phase, setPhase] = useState<Phase>("auth");
  const [liveSnaps, setLiveSnaps] = useState<DaySnapshot[]>([]);
  const [totalDays, setTotalDays] = useState(0);
  const [playPerDay, setPlayPerDay] = useState(8);
  const [runError, setRunError] = useState<string | null>(null);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [stopping, setStopping] = useState(false);
  const abortRef = useRef(false);

  // Bootstrap auth session
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const s = data.session;
      setSession(s);
      if (s) {
        setAuthToken(s.access_token);
        setPhase("saves");
      } else {
        setPhase("auth");
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
      if (s) {
        setAuthToken(s.access_token);
        setPhase(prev => prev === "auth" ? "saves" : prev);
      } else {
        setAuthToken(null);
        setPhase("auth");
        reset();
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  // Lighter background scrim on the loading / auth entry screens.
  useEffect(() => {
    const isEntry = session === undefined || phase === "auth";
    document.body.classList.toggle("entry-bg", isEntry);
    return () => document.body.classList.remove("entry-bg");
  }, [session, phase]);

  function reset() {
    setWorldId(null); setWorld(null); setResult(null);
    setPhase(session ? "saves" : "auth");
    setLiveSnaps([]); setRunError(null);
  }

  function handleLoaded(wid: string, w: World, r: SimulationResult | null) {
    setWorldId(wid);
    setWorld(w);
    if (r) {
      setResult(r);
      setLiveSnaps(r.snapshots);
      setTotalDays(r.days);
      setPhase("result");
    } else {
      setPhase("setup");
    }
  }

  // Stop an in-flight run: ask the backend to halt (it finishes the current day, then
  // emits a normal "done" with the partial result, so the stream's done-handler lands the
  // UI on the review screen — no stuck "running" state and the run stays resumable).
  function handleStop() {
    if (!worldId) return;
    setStopping(true);
    api.cancel(worldId).catch(() => {});
  }

  async function runStream(wid: string, w: World, days: number, perDay: number, isContin = false) {
    abortRef.current = false; setStopping(false);
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
          setResult(event.result); setStopping(false); setPhase("result"); return;
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }
    } catch (e: any) {
      setRunError(e.message ?? "Simulation failed");
      setStopping(false);
      setPhase(result ? "result" : "setup");
    }
  }

  function handleRun(days: number, perDay: number) {
    if (!worldId || !world) return;
    // FAST-FORWARD from setup: a fresh batch run if nothing has run yet, otherwise append
    // to the existing run. (Continuing with no prior result hits /simulate, not /continue.)
    runStream(worldId, world, days, perDay, !!result);
  }
  function handleContinue(days: number, perDay: number) {
    if (!worldId || !world) return;
    runStream(worldId, world, days, perDay, true);
  }

  // DAY-BY-DAY: stream a single day. Used for "Begin" (day 1) and every "Next day".
  // Lands in the interactive "playing" phase so the player can intervene before the next.
  async function handleAdvance(perDay: number) {
    if (!worldId || !world) return;
    abortRef.current = false; setRunError(null);
    const hadResult = !!result;
    setPlayPerDay(perDay);
    setPhase("running");
    if (!hadResult) setLiveSnaps([]);
    setTotalDays((result?.days ?? 0) + 1);
    try {
      for await (const event of api.advanceStream(worldId, perDay)) {
        if (abortRef.current) break;
        if (event.type === "day") {
          setLiveSnaps((prev) => [...prev, event.snapshot]);
        } else if (event.type === "done") {
          setResult(event.result);
          setLiveSnaps(event.result.snapshots);
          setTotalDays(event.result.days);
          setPhase("playing");
          return;
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }
    } catch (e: any) {
      setRunError(e.message ?? "Advance failed");
      setPhase(hadResult ? "playing" : "setup");
    }
  }
  function handleBegin(perDay: number) { handleAdvance(perDay); }

  const liveResult: SimulationResult | null = (() => {
    if (liveSnaps.length === 0) return null;
    const first = liveSnaps[0].metrics;
    const last = liveSnaps[liveSnaps.length - 1].metrics;
    return { days: totalDays, snapshots: liveSnaps, initial_metrics: result?.initial_metrics ?? first, final_metrics: last, final_report: "", dynamic_events: {} };
  })();
  const viewResult = (phase === "result" || phase === "playing") ? result : liveResult ?? result;

  // Loading state while auth resolves
  if (session === undefined) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span className="font-pixel" style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.1em" }}>
          LOADING<span className="blink">_</span>
        </span>
      </div>
    );
  }

  if (phase === "auth") return <AuthScreen />;

  if (phase === "saves") {
    return (
      <>
        <div style={SCANLINE_BG} />
        <main className="page-enter">
          <SavesScreen
            onNewGame={() => setPhase("setup")}
            onLoad={handleLoaded}
          />
        </main>
      </>
    );
  }

  return (
    <>
      <div style={SCANLINE_BG} />

      {showSaveModal && world && (
        <SaveModal
          world={world}
          result={result}
          onClose={() => setShowSaveModal(false)}
          onSaved={() => {}}
        />
      )}

      <main className="page-enter" style={{ maxWidth: 1800, margin: "0 auto", padding: "clamp(12px, 3vw, 20px) clamp(10px, 3vw, 24px)" }}>

        {/* ── Title Bar ─────────────────────────────────────────────────── */}
        <header style={{ marginBottom: 28 }}>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            flexWrap: "wrap", gap: 10,
            padding: "14px 20px",
            background: "var(--surface)",
            border: "1px solid var(--accent-dim)",
            boxShadow: "0 6px 24px rgba(100,80,200,0.09)",
            position: "relative",
          }}>
            <div style={{ position: "absolute", top: -2, left: -2, width: 14, height: 14, borderTop: "2px solid var(--accent)", borderLeft: "2px solid var(--accent)" }} />
            <div style={{ position: "absolute", bottom: -2, right: -2, width: 14, height: 14, borderBottom: "2px solid var(--accent)", borderRight: "2px solid var(--accent)" }} />

            <div style={{ minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4, flexWrap: "wrap" }}>
                <div style={{
                  width: 8, height: 8, borderRadius: "50%", background: "var(--accent)",
                  boxShadow: "0 0 10px var(--accent)",
                  animation: "neon-pulse 2s ease-in-out infinite",
                }} />
                <h1 className="font-pixel" style={{
                  fontSize: 14, color: "var(--accent)", margin: 0,
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
                multi-character social simulation · llm-powered character reasoning
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {worldId && (
                <button
                  onClick={() => setShowSaveModal(true)}
                  className="font-pixel"
                  style={{
                    fontSize: 8, padding: "7px 14px", cursor: "pointer",
                    background: "transparent", color: "var(--accent)",
                    border: "1px solid var(--accent)", letterSpacing: "0.08em",
                  }}
                >
                  💾 SAVE
                </button>
              )}
              <button
                onClick={reset}
                className="font-pixel"
                style={{
                  fontSize: 8, padding: "7px 14px", cursor: "pointer",
                  background: "transparent", color: "var(--text-dim)",
                  border: "1px solid var(--border)", letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "var(--red)"; (e.currentTarget as HTMLElement).style.color = "var(--red)"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border)"; (e.currentTarget as HTMLElement).style.color = "var(--text-dim)"; }}
              >
                ← QUIT
              </button>
            </div>
          </div>

          <div style={{ height: 1, background: "linear-gradient(90deg, transparent, var(--accent-dim), transparent)" }} />
        </header>

        {/* ── Setup: world creation ──────────────────────────────────── */}
        {phase === "setup" && !worldId && (
          <div className="stagger-in" style={{ maxWidth: 680, margin: "0 auto" }}>
            <WorldSetup onCreated={(wid, w) => { setWorldId(wid); setWorld(w); }} />
          </div>
        )}

        {/* ── Setup: characters + event ──────────────────────────────── */}
        {phase === "setup" && worldId && world && (
          <div className="stagger-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <CharacterEditor worldId={worldId} world={world} onWorldChange={setWorld} />
            <EventAndRun worldId={worldId} world={world} onWorldChange={setWorld} onRun={handleRun} onBegin={handleBegin} />
            {runError && <GameError message={runError} />}
          </div>
        )}

        {/* ── Live progress ──────────────────────────────────────────── */}
        {phase === "running" && (
          <div style={{ marginBottom: 16 }}>
            <LiveProgress
              currentDay={liveSnaps.length > 0 ? liveSnaps[liveSnaps.length - 1].day : 0}
              totalDays={totalDays}
              latestLog={liveSnaps.length > 0 ? liveSnaps[liveSnaps.length - 1].event_log : []}
            />
            <div style={{ display: "flex", justifyContent: "center", marginTop: 10 }}>
              <button
                onClick={handleStop}
                disabled={stopping}
                className="font-pixel"
                style={{
                  fontSize: 8, padding: "8px 18px", letterSpacing: "0.1em",
                  cursor: stopping ? "default" : "pointer", textTransform: "uppercase",
                  background: "transparent", color: "var(--red)",
                  border: "1px solid var(--red)", opacity: stopping ? 0.5 : 1,
                }}
              >
                {stopping ? "STOPPING — FINISHING CURRENT DAY..." : "■ STOP RUN"}
              </button>
            </div>
          </div>
        )}

        {/* ── Simulation view ────────────────────────────────────────── */}
        {viewResult && worldId && world && (
          <SimulationView
            result={viewResult}
            world={world}
            worldId={worldId}
            isLive={phase === "running"}
            onContinue={(phase === "result" || phase === "playing") ? handleContinue : undefined}
            onAdvance={phase === "playing" ? () => handleAdvance(playPerDay) : undefined}
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

      <div className="font-pixel" style={{
        fontSize: 8, letterSpacing: "0px",
        color: "var(--accent)", marginBottom: 12,
        fontFamily: "ui-monospace, monospace",
        overflowX: "hidden", whiteSpace: "nowrap",
      }}>
        {"▓".repeat(barFilled)}
        <span style={{ color: "var(--text-muted)" }}>{"░".repeat(barEmpty)}</span>
      </div>

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
