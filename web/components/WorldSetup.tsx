"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World } from "@/lib/types";

export function WorldSetup({ onCreated }: { onCreated: (wid: string, world: World) => void }) {
  const [prompt, setPrompt] = useState("");
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
          Define a fictional society · populate it with characters<br />
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
          {/* description */}
          <div style={{ marginTop: 12, fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.6 }}>
            The setting your society grows from. Sketch the place, its groups, and the tensions between them. The AI turns it into characters, relationships, and the drama that unfolds.
          </div>
        </div>

        {/* Population */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
            <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.1em" }}>
              TARGET POPULATION
            </div>
            <span className="font-pixel" style={{ fontSize: 12, color: "var(--accent)", marginLeft: "auto" }}>
              {pop}
            </span>
          </div>

          {/* volume-bar-style slider */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-muted)", flexShrink: 0 }}>5</span>
            <input
              type="range" min={5} max={60} step={1} value={pop}
              className="volume-range"
              onChange={(e) => setPop(parseInt(e.target.value))}
              style={{ ["--fill" as any]: `${((pop - 5) / (60 - 5)) * 100}%` }}
            />
            <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-muted)", flexShrink: 0 }}>60</span>
          </div>

          {/* quick presets */}
          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
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

          {/* description */}
          <div style={{ marginTop: 12, fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.6 }}>
            How many characters live in your world. A larger population means more relationships and richer social drama, but each resident adds simulation time to every day.
          </div>
        </div>

        <div className="game-divider" />

        {/* Submit */}
        <button
          className="btn"
          disabled={loading || !prompt.trim()}
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
          ALL CHARACTERS ARE FICTIONAL · POWERED BY LLM CHARACTER REASONING
        </span>
      </div>
    </div>
  );
}
