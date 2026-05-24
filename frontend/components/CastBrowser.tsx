"use client";
import { useMemo, useState } from "react";
import type { Agent, Mood } from "@/lib/types";
import { PixelAvatar, isEmojiAvatar } from "./PixelAvatar";

const MOOD_COLOR: Record<Mood, string> = {
  calm: "#6b7785", excited: "#f59e0b", frustrated: "#ef4444",
  heartbroken: "#ec4899", ambitious: "#a855f7", anxious: "#f97316",
  content: "#22c55e", angry: "#dc2626", hopeful: "#06b6d4",
  lonely: "#475569", confident: "#2563eb",
};

type SortKey = "name" | "influence" | "connections";

/**
 * CastBrowser — a searchable, sortable grid of every character in the world.
 * Clicking a card selects that agent (the parent switches to the Network tab so the
 * Inspector shows them). This is the missing "see the whole cast" view: in a 25-60
 * agent world you can't reliably hunt for a node in the force graph.
 */
export function CastBrowser({ agents, onSelect, selectedId }: {
  agents: Agent[];
  onSelect: (id: string) => void;
  selectedId?: string | null;
}) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("influence");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matches = (a: Agent) =>
      !q ||
      a.name.toLowerCase().includes(q) ||
      a.role.toLowerCase().includes(q) ||
      a.traits.some(t => t.toLowerCase().includes(q)) ||
      a.groups.some(g => g.toLowerCase().includes(q));
    const relCount = (a: Agent) => Object.keys(a.relationships ?? {}).length;
    return [...agents].filter(matches).sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name);
      if (sort === "connections") return relCount(b) - relCount(a);
      return b.influence_score - a.influence_score;
    });
  }, [agents, query, sort]);

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--accent-dim)",
      boxShadow: "0 4px 16px rgba(100,80,200,0.08)", padding: "14px 16px",
    }}>
      {/* controls */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
        <span className="font-pixel" style={{ fontSize: 8, color: "var(--accent)", letterSpacing: "0.1em" }}>
          ◆ CAST
        </span>
        <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
          {filtered.length}/{agents.length}
        </span>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="search name, role, trait, faction..."
          style={{ flex: 1, minWidth: 160, fontSize: 11 }}
        />
        <div style={{ display: "flex", gap: 4 }}>
          {(["influence", "connections", "name"] as SortKey[]).map(k => (
            <button key={k} onClick={() => setSort(k)} className="font-pixel" style={{
              fontSize: 6, padding: "4px 8px", cursor: "pointer", letterSpacing: "0.06em",
              textTransform: "uppercase",
              background: sort === k ? "rgba(121,80,242,0.1)" : "transparent",
              color: sort === k ? "var(--accent)" : "var(--text-dim)",
              border: `1px solid ${sort === k ? "var(--accent)" : "var(--border)"}`,
            }}>{k}</button>
          ))}
        </div>
      </div>

      {/* grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
        gap: 8,
      }}>
        {filtered.map(a => {
          const moodColor = MOOD_COLOR[a.mood] || "#6b7785";
          const relCount = Object.keys(a.relationships ?? {}).length;
          const selected = a.id === selectedId;
          return (
            <button key={a.id} onClick={() => onSelect(a.id)}
              title={`${a.name} — ${a.role}`}
              style={{
                display: "flex", gap: 10, alignItems: "center", textAlign: "left",
                padding: "8px 10px", cursor: "pointer",
                background: selected ? "rgba(121,80,242,0.08)" : "var(--surface-2)",
                border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}`,
                transition: "border-color 0.1s",
              }}>
              <div style={{
                width: 36, height: 36, flexShrink: 0,
                background: `radial-gradient(circle at 35% 35%, ${moodColor}22, var(--surface))`,
                border: `2px solid ${moodColor}`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                {isEmojiAvatar(a.avatar)
                  ? <span style={{ fontSize: 20, lineHeight: 1 }}>{a.avatar}</span>
                  : <PixelAvatar seed={a.id} avatar={a.avatar} mood={a.mood} size={30} title={a.name} />}
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="font-pixel" style={{ fontSize: 9, color: "var(--text)", letterSpacing: "0.03em", marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {a.name}
                </div>
                <div style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginBottom: 3 }}>
                  {a.role}
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <span style={{ fontSize: 7, color: moodColor, fontFamily: "var(--font-pixel)", textTransform: "uppercase" }}>{a.mood}</span>
                  <span style={{ fontSize: 7, color: "var(--accent)", fontFamily: "var(--font-pixel)" }}>
                    {a.influence_score >= 0 ? "+" : ""}{a.influence_score.toFixed(0)} INF
                  </span>
                  <span style={{ fontSize: 7, color: "var(--text-muted)", fontFamily: "var(--font-pixel)" }}>
                    {relCount} ◆
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
      {filtered.length === 0 && (
        <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace", padding: "12px 0", textAlign: "center" }}>
          No characters match “{query}”.
        </div>
      )}
    </div>
  );
}
