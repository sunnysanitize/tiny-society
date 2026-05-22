"use client";
import { useEffect, useRef, useState } from "react";
import type { SaveMeta, World, SimulationResult } from "@/lib/types";
import { api } from "@/lib/api";

interface Props {
  world: World;
  result: SimulationResult | null;
  onClose: () => void;
  onSaved: (save: SaveMeta) => void;
}

export function SaveModal({ world, result, onClose, onSaved }: Props) {
  const [saves, setSaves] = useState<SaveMeta[]>([]);
  const [name, setName] = useState("Untitled World");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.listSaves().then(setSaves).catch(() => {});
    setTimeout(() => inputRef.current?.focus(), 50);
  }, []);

  async function saveNew() {
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const save = await api.createSave(name.trim(), world, result);
      setSaves(prev => [save, ...prev]);
      onSaved(save);
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function overwrite(save: SaveMeta) {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.overwriteSave(save.id, save.name, world, result);
      onSaved(updated);
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.35)", backdropFilter: "blur(2px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 24,
    }} onClick={onClose}>
      <div
        className="panel"
        style={{ width: "100%", maxWidth: 420, padding: "24px 24px" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <span className="font-pixel" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.06em" }}>
            SAVE GAME
          </span>
          <button
            onClick={onClose}
            className="font-pixel"
            style={{
              background: "none", border: "none", cursor: "pointer",
              fontSize: 12, color: "var(--text-dim)",
            }}
          >
            ✕
          </button>
        </div>

        {/* new save */}
        <div style={{ marginBottom: 20 }}>
          <label className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.08em", display: "block", marginBottom: 6 }}>
            SAVE AS NEW
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              ref={inputRef}
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && saveNew()}
              placeholder="Name your save..."
              style={{ flex: 1 }}
            />
            <button
              className="btn"
              onClick={saveNew}
              disabled={saving || !name.trim()}
              style={{ fontSize: 8, padding: "8px 14px", whiteSpace: "nowrap" }}
            >
              {saving ? "..." : "SAVE"}
            </button>
          </div>
        </div>

        {/* overwrite existing */}
        {saves.length > 0 && (
          <>
            <div style={{ height: 1, background: "var(--border)", marginBottom: 14 }} />
            <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.08em", marginBottom: 10 }}>
              OVERWRITE EXISTING
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 200, overflowY: "auto" }}>
              {saves.map(s => (
                <div key={s.id} style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "8px 12px", border: "1px solid var(--border)",
                  background: "var(--surface-2)",
                }}>
                  <div>
                    <div className="font-pixel" style={{ fontSize: 9, color: "var(--text)" }}>{s.name}</div>
                    <div style={{ fontSize: 10, color: "var(--text-dim)" }}>
                      {s.day_count > 0 ? `Day ${s.day_count}` : "not run"} · {s.agent_count} agents
                    </div>
                  </div>
                  <button
                    onClick={() => overwrite(s)}
                    disabled={saving}
                    className="font-pixel"
                    style={{
                      fontSize: 8, padding: "4px 10px", cursor: "pointer",
                      background: "transparent", color: "var(--text-dim)",
                      border: "1px solid var(--border)", letterSpacing: "0.06em",
                    }}
                  >
                    OVERWRITE
                  </button>
                </div>
              ))}
            </div>
          </>
        )}

        {error && (
          <div style={{
            marginTop: 12, padding: "6px 10px", background: "rgba(255,68,68,0.06)",
            border: "1px solid var(--red)", fontSize: 11, color: "var(--red)",
            fontFamily: "ui-monospace, monospace",
          }}>
            ✖ {error}
          </div>
        )}
      </div>
    </div>
  );
}
