"use client";
import { useEffect, useState } from "react";
import type { SaveMeta, World, SimulationResult } from "@/lib/types";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";

interface Props {
  onNewGame: () => void;
  onLoad: (worldId: string, world: World, result: SimulationResult | null) => void;
  // When true the visitor has no account: skip the (auth-gated) saves fetch and
  // surface a sign-in affordance instead of sign-out.
  guest?: boolean;
  onSignIn?: () => void;
}

function timeAgo(iso: string) {
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

export function SavesScreen({ onNewGame, onLoad, guest, onSignIn }: Props) {
  const [saves, setSaves] = useState<SaveMeta[]>([]);
  const [loading, setLoading] = useState(!guest);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Guests have no token; listing saves would 401. Show the empty state.
    if (guest) return;
    api.listSaves()
      .then(setSaves)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [guest]);

  async function handleLoad(id: string) {
    setLoadingId(id);
    setError(null);
    try {
      const { world_id, world, result } = await api.loadSave(id);
      onLoad(world_id, world, result);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingId(null);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this save file?")) return;
    setDeletingId(id);
    try {
      await api.deleteSave(id);
      setSaves(prev => prev.filter(s => s.id !== id));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
  }

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "20px 24px" }}>
      {/* header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 20px", background: "var(--surface)",
        border: "1px solid var(--accent-dim)",
        boxShadow: "0 6px 24px rgba(100,80,200,0.09)",
        marginBottom: 24, position: "relative",
      }}>
        <div style={{ position: "absolute", top: -2, left: -2, width: 14, height: 14, borderTop: "2px solid var(--accent)", borderLeft: "2px solid var(--accent)" }} />
        <div style={{ position: "absolute", bottom: -2, right: -2, width: 14, height: 14, borderBottom: "2px solid var(--accent)", borderRight: "2px solid var(--accent)" }} />

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)", boxShadow: "0 0 10px var(--accent)", animation: "neon-pulse 2s ease-in-out infinite" }} />
          <span className="font-pixel" style={{ fontSize: 12, color: "var(--accent)", letterSpacing: "0.05em" }}>
            SELECT FILE
          </span>
        </div>
        <button
          onClick={guest ? onSignIn : handleSignOut}
          className="font-pixel"
          style={{
            fontSize: 8, padding: "5px 12px", cursor: "pointer",
            background: "transparent", color: guest ? "var(--accent)" : "var(--text-dim)",
            border: `1px solid ${guest ? "var(--accent)" : "var(--border)"}`, letterSpacing: "0.08em",
          }}
        >
          {guest ? "SIGN IN" : "SIGN OUT"}
        </button>
      </div>

      <div style={{ height: 1, background: "linear-gradient(90deg, transparent, var(--accent-dim), transparent)", marginBottom: 24 }} />

      {error && (
        <div style={{
          marginBottom: 16, padding: "8px 12px", background: "rgba(255,68,68,0.06)",
          border: "1px solid var(--red)", fontSize: 11, color: "var(--red)",
          fontFamily: "ui-monospace, monospace",
        }}>
          ✖ {error}
        </div>
      )}

      {/* save slots */}
      {loading ? (
        <div className="font-pixel" style={{ textAlign: "center", fontSize: 9, color: "var(--text-dim)", padding: 40 }}>
          LOADING SAVES<span className="blink">_</span>
        </div>
      ) : saves.length === 0 ? (
        <div className="panel" style={{ padding: "28px 24px", textAlign: "center", marginBottom: 16 }}>
          <div className="font-pixel" style={{ fontSize: 9, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
            — NO SAVE FILES —
          </div>
          <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 8 }}>
            {guest
              ? "Playing as guest — sign in to save your progress."
              : "Start a new simulation to create your first save."}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
          {saves.map((save, i) => (
            <div key={save.id} className="panel" style={{ padding: "16px 20px" }}>
              {/* slot header */}
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 8 }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span className="font-pixel" style={{ fontSize: 8, color: "var(--text-muted)", letterSpacing: "0.06em" }}>
                      SLOT {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="font-pixel" style={{ fontSize: 10, color: "var(--text)", letterSpacing: "0.04em" }}>
                      {save.name}
                    </span>
                  </div>
                  {save.world_prompt && (
                    <div style={{
                      fontSize: 11, color: "var(--text-dim)", lineHeight: 1.5,
                      maxWidth: 340, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {save.world_prompt}
                    </div>
                  )}
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div className="font-pixel" style={{ fontSize: 8, color: "var(--accent)", letterSpacing: "0.04em" }}>
                    {save.day_count > 0 ? `DAY ${save.day_count}` : "NOT RUN"}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 2 }}>
                    {save.agent_count} characters
                  </div>
                </div>
              </div>

              {/* footer */}
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                paddingTop: 10, borderTop: "1px solid var(--border)",
              }}>
                <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
                  {timeAgo(save.updated_at)}
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="btn"
                    onClick={() => handleLoad(save.id)}
                    disabled={loadingId === save.id}
                    style={{ fontSize: 8, padding: "6px 14px" }}
                  >
                    {loadingId === save.id ? "..." : "LOAD"}
                  </button>
                  <button
                    onClick={() => handleDelete(save.id)}
                    disabled={deletingId === save.id}
                    className="font-pixel"
                    style={{
                      fontSize: 8, padding: "6px 10px", cursor: "pointer",
                      background: "transparent", color: "var(--red)",
                      border: "1px solid var(--red)", letterSpacing: "0.06em",
                    }}
                  >
                    {deletingId === save.id ? "..." : "DEL"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* new game */}
      <button className="btn-ghost" onClick={onNewGame} style={{ width: "100%", fontSize: 9, padding: "12px 20px" }}>
        + NEW SIMULATION
      </button>
    </div>
  );
}
