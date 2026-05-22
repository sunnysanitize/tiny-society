"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World } from "@/lib/types";

export function WorldSetup({ onCreated }: { onCreated: (wid: string, world: World) => void }) {
  const [prompt, setPrompt] = useState(
    "A small fictional university island with 25 students, a few clubs, two rival dorms, and casual campus drama."
  );
  const [pop, setPop] = useState(25);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setLoading(true); setErr(null);
    try {
      const { world_id, world } = await api.createWorld(prompt, pop);
      onCreated(world_id, world);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* Title screen header */}
      <div style={{ textAlign: "center", marginBottom: 32, padding: "20px 0" }}>
        <div className="font-pixel" style={{
          fontSize: 10, color: "var(--text-dim)", letterSpacing: "0.2em",
          marginBottom: 12, textTransform: "uppercase",
        }}>
          ─── SELECT YOUR WORLD ───
        </div>
        <div style={{ fontSize: 10, color: "var(--text-dim)", lineHeight: 2, fontFamily: "ui-monospace, monospace" }}>
          Define a fictional society · populate it with agents<br />
          inject a starting event · watch society evolve
        </div>
      </div>

      {/* Main panel */}
      <div className="panel" style={{ padding: "24px 28px" }}>
        {/* Panel header */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <span style={{ color: "var(--accent)", fontSize: 12 }}>◆</span>
          <span className="font-pixel" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.1em" }}>
            WORLD CONFIGURATION
          </span>
        </div>
        <div className="game-divider" />

        {/* World prompt */}
        <div style={{ marginBottom: 20 }}>
          <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 8, letterSpacing: "0.1em" }}>
            WORLD DESCRIPTION
          </div>
          <div style={{ position: "relative" }}>
            <span style={{
              position: "absolute", left: 12, top: 10,
              fontSize: 12, color: "var(--accent-dim)",
              fontFamily: "ui-monospace, monospace", zIndex: 1, pointerEvents: "none",
            }}>›</span>
            <textarea
              rows={4}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="describe your fictional world..."
              style={{ paddingLeft: 28, lineHeight: 1.7 }}
            />
          </div>
        </div>

        {/* Population */}
        <div style={{ marginBottom: 24, display: "flex", alignItems: "center", gap: 16 }}>
          <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.1em", flexShrink: 0 }}>
            TARGET POPULATION
          </div>
          <input
            type="number" min={5} max={60} value={pop}
            onChange={(e) => setPop(parseInt(e.target.value) || 25)}
            style={{ width: 80 }}
          />
          <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
            {[5, 10, 25, 50].map(n => (
              <button key={n} onClick={() => setPop(n)} style={{
                padding: "4px 10px", cursor: "pointer", fontSize: 9,
                fontFamily: "var(--font-pixel, monospace)", textTransform: "uppercase",
                border: `1px solid ${pop === n ? "var(--accent)" : "var(--border)"}`,
                background: pop === n ? "rgba(121,80,242,0.1)" : "transparent",
                color: pop === n ? "var(--accent)" : "var(--text-dim)",
                boxShadow: pop === n ? "0 2px 0 var(--accent-dim)" : "none",
              }}>{n}</button>
            ))}
          </div>
        </div>

        <div className="game-divider" />

        {/* Submit */}
        <button
          className="btn"
          disabled={loading}
          onClick={submit}
          style={{ width: "100%", padding: "14px", fontSize: 10, letterSpacing: "0.15em", marginTop: 16 }}
        >
          {loading ? "INITIALIZING..." : "▶  BEGIN NEW GAME"}
        </button>

        {err && (
          <div style={{
            marginTop: 12, padding: "8px 12px", fontSize: 10,
            color: "var(--red)", border: "1px solid var(--red)",
            background: "rgba(255,68,68,0.05)", letterSpacing: "0.05em",
            fontFamily: "ui-monospace, monospace",
          }}>
            ✖ {err}
          </div>
        )}
      </div>

      {/* Footer hint */}
      <div style={{ textAlign: "center", marginTop: 16 }}>
        <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-muted)", letterSpacing: "0.1em" }}>
          ALL CHARACTERS ARE FICTIONAL · POWERED BY LLM AGENT REASONING
        </span>
      </div>
    </div>
  );
}
