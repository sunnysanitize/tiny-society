"use client";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Agent, MacroMetrics, RelationshipType, Mood } from "@/lib/types";
import { memText } from "@/lib/types";
import { PixelAvatar, isEmojiAvatar } from "./PixelAvatar";

const REL_COLOR: Record<RelationshipType, string> = {
  friendship: "#22c55e", romance: "#f472b6", rivalry: "#ef4444",
  trust: "#3b82f6", influence: "#a855f7", alliance: "#06b6d4",
  conflict: "#f97316", group_membership: "#eab308",
};

const MOOD_COLOR: Record<Mood, string> = {
  calm: "#6b7785", excited: "#f59e0b", frustrated: "#ef4444",
  heartbroken: "#ec4899", ambitious: "#a855f7", anxious: "#f97316",
  content: "#22c55e", angry: "#dc2626", hopeful: "#06b6d4",
  lonely: "#475569", confident: "#2563eb",
};

const MOOD_DESC: Record<Mood, string> = {
  calm: "settled and composed", excited: "buzzing with energy",
  frustrated: "wound tight", heartbroken: "quietly devastated",
  ambitious: "hungry and driven", anxious: "on edge",
  content: "at ease", angry: "simmering",
  hopeful: "cautiously optimistic", lonely: "drifting",
  confident: "assured and decisive",
};

function buildNarrative(agent: Agent): string {
  const traitStr = agent.traits.slice(0, 3).join(", ") || "unremarkable";
  const moodLine = MOOD_DESC[agent.mood] || agent.mood;
  const topRel = Object.entries(agent.relationships).sort((a, b) => Math.abs(b[1].strength) - Math.abs(a[1].strength))[0];
  let s = `${agent.name} is a ${agent.role} — ${traitStr}. Right now they're ${moodLine}.`;
  if (agent.goals.length) s += ` Their drive: to ${agent.goals[0]}.`;
  if (topRel) s += ` Key connection: ${topRel[0]} (${topRel[1].type}).`;
  if (agent.long_term_memory.length) s += ` "${memText(agent.long_term_memory[agent.long_term_memory.length - 1])}"`;
  return s;
}

function buildEdgeNarrative(a: Agent, b: Agent, rel: RelationshipType, strength: number): string {
  const descs: Record<RelationshipType, string> = {
    friendship: `${a.name} and ${b.name} are friends${strength > 0.7 ? " — the real kind" : ""}.`,
    romance: `There's a romantic thread between ${a.name} and ${b.name}${strength > 0.6 ? " — hard to ignore now" : " — still uncertain"}.`,
    rivalry: `${a.name} and ${b.name} are rivals. They keep score.`,
    trust: `${a.name} trusts ${b.name}${strength > 0.6 ? " deeply" : " to a degree"}.`,
    conflict: `${a.name} and ${b.name} are in conflict${strength > 0.6 ? " — something specific happened" : " — low-grade friction"}.`,
    influence: `${a.name} has influence over ${b.name}.`,
    alliance: `${a.name} and ${b.name} are strategically aligned.`,
    group_membership: `${a.name} and ${b.name} share a group — structural connection.`,
  };
  return descs[rel] ?? "";
}

// ── sub-components ─────────────────────────────────────────────────────────────

function Divider() {
  return <div style={{ height: 1, background: "var(--border)", margin: "12px 0" }} />;
}

function Label({ children, color = "var(--text-dim)" }: { children: React.ReactNode; color?: string }) {
  return (
    <div className="font-pixel" style={{ fontSize: 7, color, letterSpacing: "0.12em", marginBottom: 6, textTransform: "uppercase" }}>
      {children}
    </div>
  );
}

function Tag({ label, color }: { label: string; color?: string }) {
  return (
    <span style={{
      display: "inline-block", fontSize: 8, padding: "2px 7px",
      background: color ? `${color}14` : "rgba(78,197,240,0.1)",
      color: color ?? "var(--cyan)",
      border: `1px solid ${color ? `${color}35` : "rgba(78,197,240,0.28)"}`,
      marginRight: 4, marginBottom: 4,
      fontFamily: "var(--font-pixel, monospace)", textTransform: "uppercase",
    }}>{label}</span>
  );
}

function HpBar({ value, color, max = 1 }: { value: number; color: string; max?: number }) {
  const pct = Math.min(100, (Math.abs(value) / max) * 100);
  return (
    <div style={{ height: 5, background: "#ebe8f8", border: "1px solid var(--border)", overflow: "hidden" }}>
      <div style={{
        width: `${pct}%`, height: "100%",
        background: color, boxShadow: `0 0 4px ${color}`,
        transition: "width 0.3s ease",
      }} />
    </div>
  );
}

// A signed stance bar: a center line with the fill growing left (against, red) or
// right (for, green) — so a belief reads as a position on an axis, not a magnitude.
function StanceBar({ topic, value }: { topic: string; value: number }) {
  const v = Math.max(-1, Math.min(1, value));
  const positive = v >= 0;
  const halfPct = Math.abs(v) * 50;
  return (
    <div style={{ marginBottom: 7 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 3 }}>
        <span style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace" }}>{topic}</span>
        <span className="font-pixel" style={{ fontSize: 7, color: positive ? "#22c55e" : "var(--red)" }}>
          {v >= 0 ? "+" : ""}{v.toFixed(2)}
        </span>
      </div>
      <div style={{ position: "relative", height: 5, background: "#ebe8f8", border: "1px solid var(--border)" }}>
        <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--text-muted)" }} />
        <div style={{
          position: "absolute", top: 0, bottom: 0,
          left: positive ? "50%" : `${50 - halfPct}%`, width: `${halfPct}%`,
          background: positive ? "#22c55e" : "var(--red)", opacity: 0.8,
        }} />
      </div>
    </div>
  );
}

// ── Agent Chat ─────────────────────────────────────────────────────────────────

function AgentChat({ worldId, agentId, agentName, currentDay }: {
  worldId: string; agentId: string; agentName: string; currentDay: number;
}) {
  const [messages, setMessages] = useState<{ role: "user" | "agent"; text: string }[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function send() {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    setMessages(m => [...m, { role: "user", text: msg }]);
    setLoading(true);
    try {
      const { reply } = await api.agentChat(worldId, agentId, msg, currentDay);
      setMessages(m => [...m, { role: "agent", text: reply }]);
    } catch {
      setMessages(m => [...m, { role: "agent", text: "(No response — check LLM provider.)" }]);
    } finally {
      setLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  return (
    <div>
      <Label color="var(--purple)">◌ DIALOGUE — {agentName}</Label>
      <div style={{
        background: "var(--surface-2)", border: "1px solid var(--border)",
        padding: 10, minHeight: 70, maxHeight: 200, overflowY: "auto",
        marginBottom: 7, display: "flex", flexDirection: "column", gap: 7,
      }}>
        {messages.length === 0 && (
          <div style={{ fontSize: 9, color: "var(--text-dim)", fontStyle: "italic", fontFamily: "ui-monospace" }}>
            {agentName} is ready. Ask anything.
            <span className="blink" style={{ color: "var(--accent)", marginLeft: 2 }}>█</span>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
            <span className="font-pixel" style={{
              fontSize: 6, color: m.role === "user" ? "var(--cyan)" : "var(--purple)",
              flexShrink: 0, paddingTop: 2, letterSpacing: "0.05em",
            }}>
              {m.role === "user" ? "YOU" : agentName.slice(0, 6).toUpperCase()}
            </span>
            <span style={{ fontSize: 10, color: m.role === "user" ? "var(--text-dim)" : "var(--text)", lineHeight: 1.5, fontFamily: "ui-monospace" }}>
              {m.text}
            </span>
          </div>
        ))}
        {loading && (
          <div style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace" }}>
            {agentName} is thinking
            <span className="blink" style={{ color: "var(--accent)" }}>█</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div style={{ display: "flex", gap: 5 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
          placeholder={`message ${agentName}...`}
          style={{ flex: 1, fontSize: 11 }}
        />
        <button onClick={send} disabled={loading || !input.trim()} className="btn"
          style={{ padding: "5px 12px", fontSize: 8 }}>
          SEND
        </button>
      </div>
    </div>
  );
}

// ── Whisper advice ───────────────────────────────────────────────────────────

function WhisperAdvice({ worldId, agentId, agentName }: {
  worldId: string; agentId: string; agentName: string;
}) {
  const [advice, setAdvice] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);

  async function send() {
    const a = advice.trim();
    if (!a || busy) return;
    setBusy(true); setConfirm(null);
    try {
      await api.advise(worldId, agentId, a);
      setAdvice("");
      setConfirm(`${agentName} will remember that.`);
    } catch {
      setConfirm("Couldn't deliver that whisper — try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Label color="var(--gold)">✦ WHISPER ADVICE — {agentName}</Label>
      <div style={{ display: "flex", gap: 5 }}>
        <input
          value={advice}
          onChange={e => setAdvice(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
          placeholder={`whisper to ${agentName}...`}
          style={{ flex: 1, fontSize: 11 }}
        />
        <button onClick={send} disabled={busy || !advice.trim()} className="btn"
          style={{ padding: "5px 12px", fontSize: 8 }}>
          {busy ? "..." : "WHISPER"}
        </button>
      </div>
      {confirm && (
        <div style={{ fontSize: 9, color: "var(--gold)", fontFamily: "ui-monospace", marginTop: 6, fontStyle: "italic" }}>
          ✦ {confirm}
        </div>
      )}
    </div>
  );
}

// ── Agent panel ────────────────────────────────────────────────────────────────

function AgentInspector({ agent, allAgents, worldId, currentDay, compact = false, onExpand }: {
  agent: Agent; allAgents: Agent[]; worldId: string | null; currentDay: number;
  compact?: boolean; onExpand?: () => void;
}) {
  const moodColor = MOOD_COLOR[agent.mood] || "#6b7785";
  const rels = Object.entries(agent.relationships).sort((a, b) => Math.abs(b[1].strength) - Math.abs(a[1].strength));

  // COMPACT (Story screen): a quick glance — header, traits, top ties, and a jump to the
  // full profile in the Network tab. Keeps the panel short so it doesn't grow the page.
  if (compact) {
    return (
      <div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
          <div style={{
            width: 40, height: 40, flexShrink: 0,
            background: `radial-gradient(circle at 35% 35%, ${moodColor}25, #f8f6ff)`,
            border: `2px solid ${moodColor}`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            {isEmojiAvatar(agent.avatar)
              ? <span style={{ fontSize: 22, lineHeight: 1 }}>{agent.avatar}</span>
              : <PixelAvatar seed={agent.id} avatar={agent.avatar} mood={agent.mood} size={34} title={agent.name} />}
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="font-pixel" style={{ fontSize: 10, color: "var(--text)", marginBottom: 3, letterSpacing: "0.05em" }}>{agent.name}</div>
            <div style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace", marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{agent.role}</div>
            <div style={{ display: "flex", gap: 5 }}>
              <span style={{ fontSize: 8, padding: "2px 7px", background: `${moodColor}12`, color: moodColor, border: `1px solid ${moodColor}35`, fontFamily: "var(--font-pixel)", textTransform: "uppercase" }}>{agent.mood}</span>
              <span style={{ fontSize: 8, padding: "2px 7px", background: "rgba(121,80,242,0.08)", color: "var(--accent)", border: "1px solid rgba(121,80,242,0.22)", fontFamily: "var(--font-pixel)" }}>
                {agent.influence_score >= 0 ? "+" : ""}{agent.influence_score.toFixed(1)} INF
              </span>
            </div>
          </div>
        </div>

        {agent.traits.length > 0 && (
          <div style={{ marginBottom: 10 }}>{agent.traits.slice(0, 5).map(t => <Tag key={t} label={t} />)}</div>
        )}

        {rels.length > 0 && (
          <>
            <Label>TOP TIES</Label>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 12 }}>
              {rels.slice(0, 3).map(([name, r]) => {
                const color = REL_COLOR[r.type] || "#6b7785";
                return (
                  <div key={name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 10, color: "var(--text)", fontFamily: "ui-monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</span>
                    <span style={{ fontSize: 7, padding: "1px 5px", background: `${color}12`, color, border: `1px solid ${color}28`, fontFamily: "var(--font-pixel)", textTransform: "uppercase", flexShrink: 0 }}>{r.type}</span>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {onExpand && (
          <button onClick={onExpand} className="font-pixel" style={{
            width: "100%", fontSize: 7, padding: "7px 0", cursor: "pointer", letterSpacing: "0.08em",
            background: "transparent", color: "var(--accent)", border: "1px solid var(--accent)", textTransform: "uppercase",
          }}>
            VIEW FULL PROFILE IN NETWORK →
          </button>
        )}
      </div>
    );
  }

  return (
    <div>
      {/* Character header */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 14 }}>
        <div style={{
          width: 48, height: 48, flexShrink: 0,
          background: `radial-gradient(circle at 35% 35%, ${moodColor}25, #f8f6ff)`,
          border: `2px solid ${moodColor}`,
          boxShadow: `0 0 14px ${moodColor}50`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          {isEmojiAvatar(agent.avatar) ? (
            <span style={{ fontSize: 26, lineHeight: 1 }}>{agent.avatar}</span>
          ) : (
            <PixelAvatar seed={agent.id} avatar={agent.avatar} mood={agent.mood} size={40} title={agent.name} />
          )}
        </div>
        <div>
          <div className="font-pixel" style={{ fontSize: 10, color: "var(--text)", marginBottom: 4, letterSpacing: "0.05em" }}>{agent.name}</div>
          <div style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace", marginBottom: 5 }}>
            {agent.role}
            {agent.based_on && <span style={{ color: "var(--gold)" }}> · based on {agent.based_on}</span>}
          </div>
          <div style={{ display: "flex", gap: 5 }}>
            <span style={{
              fontSize: 8, padding: "2px 7px",
              background: `${moodColor}12`, color: moodColor, border: `1px solid ${moodColor}35`,
              fontFamily: "var(--font-pixel)", textTransform: "uppercase",
            }}>{agent.mood}</span>
            <span style={{
              fontSize: 8, padding: "2px 7px",
              background: "rgba(121,80,242,0.08)", color: "var(--accent)", border: "1px solid rgba(121,80,242,0.22)",
              fontFamily: "var(--font-pixel)",
            }}>
              {agent.influence_score >= 0 ? "+" : ""}{agent.influence_score.toFixed(1)} INF
            </span>
          </div>
        </div>
      </div>

      {/* narrative */}
      <div style={{
        fontSize: 12, color: "var(--text-dim)", lineHeight: 1.7,
        padding: "8px 10px", background: "var(--surface-2)",
        border: "1px solid var(--border)", marginBottom: 14, fontFamily: "ui-monospace",
      }}>
        {buildNarrative(agent)}
      </div>

      <Divider />

      {agent.traits.length > 0 && (
        <><Label>TRAITS</Label>
        <div style={{ marginBottom: 12 }}>{agent.traits.map(t => <Tag key={t} label={t} />)}</div></>
      )}

      {agent.goals.length > 0 && (
        <><Label>OBJECTIVES</Label>
        <div style={{ marginBottom: 12 }}>
          {agent.goals.map((g, i) => (
            <div key={i} style={{
              fontSize: 10, color: "var(--text-dim)", padding: "5px 8px",
              background: "var(--surface-2)", marginBottom: 3, borderLeft: "2px solid var(--accent-dim)",
              fontFamily: "ui-monospace",
            }}>{g}</div>
          ))}
        </div></>
      )}

      {agent.groups.length > 0 && (
        <><Label>FACTIONS</Label>
        <div style={{ marginBottom: 12 }}>{agent.groups.map(g => <Tag key={g} label={g} color="var(--cyan)" />)}</div></>
      )}

      {rels.length > 0 && (
        <>
          <Divider />
          <Label>RELATIONSHIPS [{rels.length}]</Label>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {rels.map(([name, r]) => {
              const color = REL_COLOR[r.type] || "#6b7785";
              const other = allAgents.find(a => a.name === name);
              return (
                <div key={name}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div style={{
                        width: 22, height: 22, background: "var(--surface-2)",
                        border: `1px solid ${color}50`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        flexShrink: 0,
                      }}>
                        {other && isEmojiAvatar(other.avatar) ? (
                          <span style={{ fontSize: 12, lineHeight: 1 }}>{other.avatar}</span>
                        ) : (
                          <PixelAvatar
                            seed={other?.id ?? name}
                            avatar={other?.avatar}
                            mood={other?.mood}
                            size={20}
                            title={name}
                          />
                        )}
                      </div>
                      <span style={{ fontSize: 10, color: "var(--text)", fontFamily: "ui-monospace" }}>{name}</span>
                      {other && <span style={{ fontSize: 8, color: "var(--text-dim)", fontFamily: "ui-monospace" }}>{other.role}</span>}
                    </div>
                    <span style={{
                      fontSize: 7, padding: "1px 5px",
                      background: `${color}12`, color, border: `1px solid ${color}28`,
                      fontFamily: "var(--font-pixel)", textTransform: "uppercase",
                    }}>{r.type}</span>
                  </div>
                  <HpBar value={r.strength} color={color} />
                </div>
              );
            })}
          </div>
        </>
      )}

      {(agent.long_term_memory.length > 0 || agent.short_term_memory.length > 0) && (
        <>
          <Divider />
          <Label>MEMORY LOG</Label>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 12 }}>
            {agent.short_term_memory.slice(-3).map((m, i) => (
              <div key={`st-${i}`} style={{
                fontSize: 9, color: "var(--text-dim)", padding: "5px 8px",
                background: "var(--surface-2)", borderLeft: "2px solid var(--accent-dim)", fontFamily: "ui-monospace",
              }}>
                <span className="font-pixel" style={{ fontSize: 6, color: "var(--accent-dim)", display: "block", marginBottom: 2 }}>TODAY</span>
                {memText(m)}
              </div>
            ))}
            {agent.long_term_memory.slice(-4).map((m, i) => (
              <div key={`lt-${i}`} style={{
                fontSize: 9, color: "var(--text-dim)", padding: "5px 8px",
                background: "var(--surface-2)", borderLeft: "2px solid var(--border)", fontFamily: "ui-monospace",
              }}>
                <span className="font-pixel" style={{ fontSize: 6, color: "var(--text-muted)", display: "block", marginBottom: 2 }}>PAST</span>
                {memText(m)}
              </div>
            ))}
          </div>
        </>
      )}

      {agent.stance && Object.keys(agent.stance).length > 0 && (
        <>
          <Divider />
          <Label color="var(--accent)">BELIEFS</Label>
          <div style={{ marginBottom: 4 }}>
            {Object.entries(agent.stance).map(([t, v]) => <StanceBar key={t} topic={t} value={v} />)}
          </div>
        </>
      )}

      {agent.feed && agent.feed.length > 0 && (
        <>
          <Divider />
          <Label color="var(--cyan)">◌ WHAT THEY SEE</Label>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 12 }}>
            {[...agent.feed].slice(-6).reverse().map((f, i) => (
              <div key={i} style={{
                fontSize: 9, color: "var(--text-dim)", padding: "5px 8px",
                background: "var(--surface-2)", borderLeft: "2px solid rgba(59,130,246,0.4)", fontFamily: "ui-monospace",
              }}>
                {f.text}
              </div>
            ))}
          </div>
        </>
      )}

      {worldId && (
        <>
          <Divider />
          <WhisperAdvice worldId={worldId} agentId={agent.id} agentName={agent.name} />
          <Divider />
          <AgentChat worldId={worldId} agentId={agent.id} agentName={agent.name} currentDay={currentDay} />
        </>
      )}
    </div>
  );
}

// ── Edge panel ─────────────────────────────────────────────────────────────────

function EdgeInspector({ edgeKey, allAgents, compact = false, onExpand }: {
  edgeKey: string; allAgents: Agent[]; compact?: boolean; onExpand?: () => void;
}) {
  const parts = edgeKey.split("|");
  const agentA = allAgents.find(a => a.id === parts[0]);
  const agentB = allAgents.find(a => a.id === parts[1]);

  if (!agentA || !agentB) return <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace" }}>Data unavailable.</div>;

  const relAB = agentA.relationships[agentB.name];
  const relBA = agentB.relationships[agentA.name];
  // The edge key no longer encodes a type (edges are deduped per unordered pair, and a
  // bond can be asymmetric). Derive the headline type from the direction with the
  // stronger |affinity| as the representative.
  const dominant = Math.abs(relAB?.strength ?? 0) >= Math.abs(relBA?.strength ?? 0) ? relAB : relBA;
  const relType = (dominant?.type ?? "trust") as RelationshipType;
  const color = REL_COLOR[relType] || "#6b7785";
  const strength = dominant?.strength ?? 0;
  const mag = Math.abs(strength);

  const header = (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
      <div className="font-pixel" style={{
        fontSize: 8, color: "var(--text)", padding: "5px 10px",
        background: "var(--surface-2)", border: "1px solid var(--border)",
      }}>{agentA.name}</div>
      <div style={{ flex: 1, textAlign: "center" }}>
        <div style={{ height: 2, background: color, opacity: 0.6, marginBottom: 4 }} />
        <Tag label={relType} color={color} />
      </div>
      <div className="font-pixel" style={{
        fontSize: 8, color: "var(--text)", padding: "5px 10px",
        background: "var(--surface-2)", border: "1px solid var(--border)",
      }}>{agentB.name}</div>
    </div>
  );

  // COMPACT (Story screen): header + bond strength + jump to full detail in the Network tab.
  if (compact) {
    return (
      <div>
        {header}
        <Label>BOND STRENGTH</Label>
        <div style={{ marginBottom: 4 }}><HpBar value={strength} color={color} /></div>
        <div className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", marginBottom: 12, letterSpacing: "0.06em" }}>
          {(mag * 100).toFixed(0)}% — {mag > 0.7 ? "STRONG" : mag > 0.4 ? "MODERATE" : "WEAK"}
        </div>
        {onExpand && (
          <button onClick={onExpand} className="font-pixel" style={{
            width: "100%", fontSize: 7, padding: "7px 0", cursor: "pointer", letterSpacing: "0.08em",
            background: "transparent", color: "var(--accent)", border: "1px solid var(--accent)", textTransform: "uppercase",
          }}>
            VIEW FULL DETAIL IN NETWORK →
          </button>
        )}
      </div>
    );
  }

  return (
    <div>
      {header}

      <div style={{
        fontSize: 10, color: "var(--text-dim)", lineHeight: 1.7,
        padding: "8px 10px", background: "var(--surface-2)", border: "1px solid var(--border)", marginBottom: 14,
        fontFamily: "ui-monospace",
      }}>
        {buildEdgeNarrative(agentA, agentB, relType, strength)}
      </div>

      <Divider />
      <Label>BOND STRENGTH</Label>
      <div style={{ marginBottom: 4 }}><HpBar value={strength} color={color} /></div>
      <div className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", marginBottom: 14, letterSpacing: "0.06em" }}>
        {(mag * 100).toFixed(0)}% — {mag > 0.7 ? "STRONG" : mag > 0.4 ? "MODERATE" : "WEAK"}
      </div>

      <Label>{agentA.name}'s VIEW</Label>
      <div style={{ fontSize: 10, color: "var(--text-dim)", padding: "6px 8px", background: "var(--surface-2)", marginBottom: 8, fontFamily: "ui-monospace" }}>
        {relAB ? `${relAB.type} (${relAB.strength.toFixed(2)})` : "No record."}
      </div>
      <Label>{agentB.name}'s VIEW</Label>
      <div style={{ fontSize: 10, color: "var(--text-dim)", padding: "6px 8px", background: "var(--surface-2)", marginBottom: 12, fontFamily: "ui-monospace" }}>
        {relBA ? `${relBA.type} (${relBA.strength.toFixed(2)})` : "No record."}
      </div>

      {agentA.groups.filter(g => agentB.groups.includes(g)).length > 0 && (
        <>
          <Label>SHARED FACTIONS</Label>
          <div>{agentA.groups.filter(g => agentB.groups.includes(g)).map(g => <Tag key={g} label={g} color="var(--cyan)" />)}</div>
        </>
      )}
    </div>
  );
}

// ── Metrics overview ───────────────────────────────────────────────────────────

function MetricsSummary({ initial, current, day }: { initial: MacroMetrics; current: MacroMetrics; day: number }) {
  function Row({ a, b, label, color }: { a: number; b: number; label: string; color: string }) {
    const d = b - a;
    const fmt = (v: number) => Number.isInteger(v) ? String(v) : v.toFixed(2);
    return (
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "5px 0", borderBottom: "1px solid var(--border)",
      }}>
        <span style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace" }}>{label}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="font-pixel" style={{ fontSize: 8, color: "var(--text)" }}>{fmt(b)}</span>
          {d !== 0 && (
            <span className="font-pixel" style={{
              fontSize: 7, padding: "1px 5px",
              background: d > 0 ? "rgba(34,197,94,0.1)" : "rgba(255,68,68,0.1)",
              color: d > 0 ? "#22c55e" : "var(--red)",
              border: `1px solid ${d > 0 ? "rgba(34,197,94,0.3)" : "rgba(255,68,68,0.3)"}`,
            }}>
              {d > 0 ? "+" : ""}{fmt(d)}
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Row a={initial.friendship_count} b={current.friendship_count} label="Friendships" color="#22c55e" />
        <Row a={initial.rivalry_count} b={current.rivalry_count} label="Rivalries" color="var(--red)" />
        <Row a={initial.romance_count} b={current.romance_count} label="Romances" color="var(--pink)" />
        <Row a={initial.conflict_count} b={current.conflict_count} label="Conflicts" color="var(--orange)" />
        <Row a={initial.alliance_count} b={current.alliance_count} label="Alliances" color="var(--cyan)" />
        <Row a={initial.average_relationship_strength} b={current.average_relationship_strength} label="Avg strength" color="var(--accent)" />
        <Row a={initial.social_fragmentation} b={current.social_fragmentation} label="Fragmentation" color="var(--text-dim)" />
      </div>

      {current.most_connected.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <Label>MOST CONNECTED</Label>
          <div>{current.most_connected.map(n => <Tag key={n} label={n} />)}</div>
        </div>
      )}
      {current.influence_gainers.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <Label>RISING</Label>
          <div>{current.influence_gainers.map(n => <Tag key={n} label={n} color="var(--accent)" />)}</div>
        </div>
      )}
      {current.influence_losers.length > 0 && (
        <div>
          <Label>LOSING GROUND</Label>
          <div>{current.influence_losers.map(n => <Tag key={n} label={n} color="var(--red)" />)}</div>
        </div>
      )}
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────────────────

type Selection = { kind: "node"; id: string } | { kind: "edge"; key: string } | null;

export function Inspector({ selection, snap, initialMetrics, worldId, stacked = false, compact = false, onExpand }: {
  selection: Selection;
  snap: { agents: Agent[]; metrics: MacroMetrics; day: number; highlights: any[] };
  initialMetrics: MacroMetrics;
  worldId: string | null;
  stacked?: boolean;
  // compact: condensed profiles (Story screen) — depth lives in the Network tab.
  compact?: boolean;
  onExpand?: () => void;
}) {
  const selectedAgent = selection?.kind === "node" ? snap.agents.find(a => a.id === selection.id) ?? null : null;
  const title = selection?.kind === "node" ? selectedAgent?.name ?? "CHARACTER" : selection?.kind === "edge" ? "RELATIONSHIP" : `DAY ${snap.day}`;
  const subtitle = selection?.kind === "node" ? "CHARACTER" : selection?.kind === "edge" ? "EDGE" : "OVERVIEW";

  return (
    <div style={{
      width: stacked ? "100%" : 300, flexShrink: 0, display: "flex", flexDirection: "column",
      background: "var(--surface-2)",
      borderLeft: stacked ? "none" : "1px solid var(--border)",
      borderTop: stacked ? "1px solid var(--border)" : "none",
      height: "100%",
    }}>
      {/* header */}
      <div style={{
        padding: "9px 14px", borderBottom: "1px solid var(--border)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        flexShrink: 0, background: "var(--surface)",
      }}>
        <span className="font-pixel" style={{ fontSize: 8, color: "var(--accent)", letterSpacing: "0.08em" }}>{title}</span>
        <span className="font-pixel" style={{ fontSize: 6, color: "var(--text-dim)", letterSpacing: "0.1em" }}>{subtitle}</span>
      </div>

      {/* body */}
      <div style={{ flex: 1, overflowY: "auto", padding: "14px 14px" }}>
        {!selection && (
          <>
            <div style={{ fontSize: 9, color: "var(--text-dim)", marginBottom: 14, lineHeight: 1.7, fontFamily: "ui-monospace" }}>
              Click a node to inspect a character, or click an edge to read about a relationship.
            </div>
            {compact ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {([
                  ["Friendships", snap.metrics.friendship_count, "#22c55e"],
                  ["Romances", snap.metrics.romance_count, "var(--pink)"],
                  ["Tensions", snap.metrics.rivalry_count + snap.metrics.conflict_count, "var(--red)"],
                  ["Alliances", snap.metrics.alliance_count, "var(--cyan)"],
                ] as [string, number, string][]).map(([label, val, color]) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace" }}>{label}</span>
                    <span className="font-pixel" style={{ fontSize: 9, color }}>{val}</span>
                  </div>
                ))}
              </div>
            ) : (
              <>
                <MetricsSummary initial={initialMetrics} current={snap.metrics} day={snap.day} />

                {snap.highlights.length > 0 && (
                  <>
                    <Divider />
                    <Label color="var(--gold)">TODAY'S EVENTS</Label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {snap.highlights.slice(0, 6).map((h, i) => (
                        <div key={i} style={{
                          padding: "7px 9px", background: "var(--surface-2)",
                          borderLeft: "2px solid var(--gold)",
                        }}>
                          <div className="font-pixel" style={{ fontSize: 7, color: "var(--gold)", marginBottom: 3, letterSpacing: "0.05em" }}>
                            {h.agent}
                          </div>
                          <div style={{ fontSize: 12, color: "var(--text-dim)", lineHeight: 1.6, fontFamily: "ui-monospace" }}>
                            {h.summary}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </>
        )}

        {selection?.kind === "node" && selectedAgent && (
          <AgentInspector agent={selectedAgent} allAgents={snap.agents} worldId={worldId} currentDay={snap.day} compact={compact} onExpand={onExpand} />
        )}
        {selection?.kind === "edge" && (
          <EdgeInspector edgeKey={selection.key} allAgents={snap.agents} compact={compact} onExpand={onExpand} />
        )}
      </div>
    </div>
  );
}
