"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World, Mood } from "@/lib/types";

const MOODS: Mood[] = ["calm","excited","frustrated","ambitious","anxious","content","hopeful","confident","lonely","angry","heartbroken"];

const MOOD_COLOR: Record<Mood, string> = {
  calm: "#6b7785", excited: "#f59e0b", frustrated: "#ef4444",
  heartbroken: "#ec4899", ambitious: "#a855f7", anxious: "#f97316",
  content: "#22c55e", angry: "#dc2626", hopeful: "#06b6d4",
  lonely: "#475569", confident: "#2563eb",
};

// Tomodachi-style pixel/emoji avatar set — faces + a few animals/symbols.
const AVATARS = [
  "😀","😎","🥰","😈","🤓","😭","😡","🤔",
  "🐱","🐶","🦊","🐼","🐸","🦄","🐙","🦉",
  "👑","🎭","🌟","🔥","💀","🌸",
];

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", letterSpacing: "0.1em", marginBottom: 5 }}>
      {children}
    </div>
  );
}

export function CharacterEditor({ worldId, world, onWorldChange }: {
  worldId: string; world: World; onWorldChange: (w: World) => void;
}) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("student");
  const [traits, setTraits] = useState("ambitious, social");
  const [goals, setGoals] = useState("become club president");
  const [mood, setMood] = useState<Mood>("calm");
  const [groups, setGroups] = useState("Cooking Club");
  const [memory, setMemory] = useState("");
  const [avatar, setAvatar] = useState<string | null>(null);
  const [basedOn, setBasedOn] = useState("");
  const [busy, setBusy] = useState(false);
  const [genBusy, setGenBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function splitCsv(s: string): string[] {
    return s.split(",").map(x => x.trim()).filter(Boolean);
  }

  async function addCharacter() {
    if (!name.trim()) return;
    setBusy(true); setErr(null);
    try {
      await api.addCharacter(worldId, {
        name: name.trim(), role: role.trim() || "citizen",
        traits: splitCsv(traits), goals: splitCsv(goals),
        mood, groups: splitCsv(groups),
        starting_memories: memory.trim() ? [memory.trim()] : [],
        starting_relationships: {},
        ...(avatar ? { avatar } : {}),
        ...(basedOn.trim() ? { based_on: basedOn.trim() } : {}),
      });
      const w = await api.getWorld(worldId);
      onWorldChange(w);
      setName(""); setMemory(""); setAvatar(null); setBasedOn("");
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  }

  async function removeCharacter(id: string) {
    await api.removeCharacter(worldId, id);
    const w = await api.getWorld(worldId);
    onWorldChange(w);
  }

  async function generateFillers() {
    setGenBusy(true); setErr(null);
    try {
      const w = await api.generateFillers(worldId);
      onWorldChange(w);
    } catch (e: any) { setErr(e.message); }
    finally { setGenBusy(false); }
  }

  const needed = Math.max(0, world.target_population - world.agents.length);
  const rosterPct = Math.round((world.agents.length / world.target_population) * 100);

  return (
    <div className="panel" style={{ padding: "20px 24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "var(--cyan)", fontSize: 12 }}>◈</span>
          <span className="font-pixel" style={{ fontSize: 10, color: "var(--cyan)", letterSpacing: "0.1em" }}>
            CHARACTER ROSTER
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)" }}>
            {world.agents.length} / {world.target_population}
          </span>
          {/* roster fill bar */}
          <div style={{ width: 80, height: 6, background: "#ebe8f8", border: "1px solid var(--border)", overflow: "hidden" }}>
            <div style={{
              width: `${rosterPct}%`, height: "100%",
              background: rosterPct >= 100 ? "var(--accent)" : "var(--cyan)",
              boxShadow: `0 0 6px ${rosterPct >= 100 ? "var(--accent)" : "var(--cyan)"}`,
              transition: "width 0.4s ease",
            }} />
          </div>
        </div>
      </div>

      <div style={{ height: 1, background: "linear-gradient(90deg, transparent, var(--cyan), transparent)", marginBottom: 16 }} />

      {/* Recruit form */}
      <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.1em", marginBottom: 12 }}>
        ▸ RECRUIT NEW CHARACTER
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
        <div>
          <FieldLabel>NAME</FieldLabel>
          <input placeholder="character name" value={name} onChange={e => setName(e.target.value)} />
        </div>
        <div>
          <FieldLabel>ROLE</FieldLabel>
          <input placeholder="student / teacher..." value={role} onChange={e => setRole(e.target.value)} />
        </div>
        <div>
          <FieldLabel>TRAITS</FieldLabel>
          <input placeholder="ambitious, social, ..." value={traits} onChange={e => setTraits(e.target.value)} />
        </div>
        <div>
          <FieldLabel>GOALS</FieldLabel>
          <input placeholder="become club president, ..." value={goals} onChange={e => setGoals(e.target.value)} />
        </div>
        <div>
          <FieldLabel>MOOD</FieldLabel>
          <select value={mood} onChange={e => setMood(e.target.value as Mood)}
            style={{ color: MOOD_COLOR[mood] }}>
            {MOODS.map(m => <option key={m} value={m} style={{ color: MOOD_COLOR[m] }}>{m.toUpperCase()}</option>)}
          </select>
        </div>
        <div>
          <FieldLabel>GROUPS</FieldLabel>
          <input placeholder="Dorm A, Cooking Club, ..." value={groups} onChange={e => setGroups(e.target.value)} />
        </div>
        <div style={{ gridColumn: "span 2" }}>
          <FieldLabel>STARTING MEMORY (OPTIONAL)</FieldLabel>
          <input placeholder="a memory this character starts with..." value={memory} onChange={e => setMemory(e.target.value)} />
        </div>
        <div style={{ gridColumn: "span 2" }}>
          <FieldLabel>AVATAR (OPTIONAL)</FieldLabel>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {AVATARS.map(emo => {
              const sel = avatar === emo;
              return (
                <button
                  key={emo}
                  type="button"
                  onClick={() => setAvatar(sel ? null : emo)}
                  title={sel ? "click to clear" : "pick avatar"}
                  style={{
                    width: 28, height: 28, fontSize: 15, lineHeight: "26px",
                    cursor: "pointer", textAlign: "center", padding: 0,
                    background: sel ? "rgba(78,197,240,0.12)" : "var(--surface-2)",
                    border: `1px solid ${sel ? "var(--cyan)" : "var(--border)"}`,
                    boxShadow: sel ? "0 0 6px rgba(78,197,240,0.4)" : "none",
                  }}
                >{emo}</button>
              );
            })}
          </div>
        </div>
        <div style={{ gridColumn: "span 2" }}>
          <FieldLabel>BASED ON A REAL PERSON (OPTIONAL)</FieldLabel>
          <input placeholder="e.g. my friend Maya, a coworker..." value={basedOn} onChange={e => setBasedOn(e.target.value)} />
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button className="btn" onClick={addCharacter} disabled={busy || !name.trim()}>
          {busy ? "ADDING..." : "▶ ADD CHARACTER"}
        </button>
        <button className="btn-ghost" onClick={generateFillers} disabled={genBusy || needed === 0}>
          {genBusy ? "GENERATING..." : `AUTO-FILL ${needed} CHARACTER${needed === 1 ? "" : "S"}`}
        </button>
      </div>

      {err && (
        <div style={{ fontSize: 10, color: "var(--red)", fontFamily: "ui-monospace", marginBottom: 8, letterSpacing: "0.04em" }}>
          ✖ {err}
        </div>
      )}

      {/* Roster list */}
      {world.agents.length > 0 && (
        <>
          <div style={{ height: 1, background: "var(--border)", marginBottom: 10 }} />
          <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 8, letterSpacing: "0.08em" }}>
            ▸ CURRENT ROSTER
          </div>
          <div style={{ maxHeight: 260, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
            {world.agents.map((a) => {
              const moodColor = MOOD_COLOR[a.mood] || "#6b7785";
              return (
                <div key={a.id} style={{
                  display: "flex", alignItems: "flex-start", gap: 10,
                  padding: "8px 10px",
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  transition: "border-color 0.1s",
                }}>
                  {/* avatar or mood dot */}
                  {a.avatar ? (
                    <span style={{ fontSize: 16, lineHeight: "20px", flexShrink: 0, marginTop: 2 }}>{a.avatar}</span>
                  ) : (
                    <div style={{
                      width: 8, height: 8, borderRadius: "50%",
                      background: moodColor, flexShrink: 0, marginTop: 4,
                      boxShadow: `0 0 4px ${moodColor}`,
                    }} />
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span className="font-pixel" style={{ fontSize: 8, color: "var(--text)" }}>{a.name}</span>
                      <span style={{ fontSize: 9, color: "var(--text-dim)" }}>— {a.role}</span>
                      {a.is_custom && (
                        <span style={{
                          fontSize: 7, padding: "1px 5px",
                          border: "1px solid var(--gold)", color: "var(--gold)",
                          background: "rgba(255,215,0,0.06)", fontFamily: "var(--font-pixel)",
                        }}>CUSTOM</span>
                      )}
                    </div>
                    <div>{a.traits.map(t => <span key={t} className="tag">{t}</span>)}</div>
                    <div style={{ fontSize: 8, color: "var(--text-dim)", marginTop: 2, fontFamily: "ui-monospace" }}>
                      {a.groups.join(" · ") || "no groups"} &nbsp;|&nbsp; mood:{" "}
                      <span style={{ color: moodColor }}>{a.mood}</span>
                      {a.based_on && <> &nbsp;|&nbsp; based on <span style={{ color: "var(--gold)" }}>{a.based_on}</span></>}
                    </div>
                  </div>
                  <button
                    onClick={() => removeCharacter(a.id)}
                    style={{
                      fontSize: 8, padding: "4px 8px", cursor: "pointer",
                      background: "transparent", color: "var(--text-dim)",
                      border: "1px solid var(--border)", fontFamily: "var(--font-pixel)",
                      textTransform: "uppercase", letterSpacing: "0.05em",
                      transition: "border-color 0.1s, color 0.1s", flexShrink: 0,
                    }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "var(--red)"; (e.currentTarget as HTMLElement).style.color = "var(--red)"; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border)"; (e.currentTarget as HTMLElement).style.color = "var(--text-dim)"; }}
                  >
                    REMOVE
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
