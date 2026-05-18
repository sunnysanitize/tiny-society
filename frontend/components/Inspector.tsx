"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Agent, MacroMetrics, RelationshipType, Mood } from "@/lib/types";

// ─── palette ─────────────────────────────────────────────────────────────────

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
  frustrated: "wound tight and irritable", heartbroken: "quietly devastated",
  ambitious: "hungry and driven", anxious: "on edge, overthinking",
  content: "at ease with where things stand", angry: "simmering and reactive",
  hopeful: "looking forward with cautious optimism", lonely: "drifting at the edges",
  confident: "assured and decisive",
};

// ─── helpers ─────────────────────────────────────────────────────────────────

function buildNarrative(agent: Agent): string {
  const traitStr = agent.traits.length
    ? agent.traits.slice(0, 3).join(", ")
    : "unremarkable";
  const goalStr = agent.goals.length
    ? agent.goals[0]
    : "no clear direction";
  const relCount = Object.keys(agent.relationships).length;
  const topRel = Object.entries(agent.relationships).sort(
    (a, b) => Math.abs(b[1].strength) - Math.abs(a[1].strength)
  )[0];
  const moodLine = MOOD_DESC[agent.mood] || agent.mood;

  let narrative = `${agent.name} is a ${agent.role} — ${traitStr}. Right now they're ${moodLine}.`;

  if (agent.goals.length) {
    narrative += ` Their main drive is to ${goalStr}.`;
  }
  if (topRel) {
    const [name, rel] = topRel;
    narrative += ` Their most significant connection is with ${name} — a ${rel.type} that runs ${rel.strength > 0.6 ? "deep" : rel.strength < 0.2 ? "shallow" : "somewhere in the middle"}.`;
  } else if (relCount === 0) {
    narrative += " They haven't formed any meaningful connections yet.";
  }
  if (agent.long_term_memory.length) {
    narrative += ` One thing that stuck: "${agent.long_term_memory[agent.long_term_memory.length - 1]}"`;
  }
  return narrative;
}

function buildEdgeNarrative(
  agentA: Agent, agentB: Agent, relType: RelationshipType, strength: number
): string {
  const descriptions: Record<RelationshipType, (a: string, b: string, s: number) => string> = {
    friendship: (a, b, s) => `${a} and ${b} are friends${s > 0.7 ? " — the kind that actually show up for each other" : s < 0.3 ? ", though it's still early and fragile" : ""}. `,
    romance: (a, b, s) => `There's a romantic thread between ${a} and ${b}${s > 0.6 ? " that's become hard to ignore" : " — still uncertain, still charged"}. `,
    rivalry: (a, b, s) => `${a} and ${b} are rivals${s > 0.7 ? ". The tension between them is a defining feature of this social world" : ". They keep score, even if quietly"}. `,
    trust: (a, b, s) => `${a} trusts ${b}${s > 0.6 ? " deeply — more than most" : " to a degree, though it hasn't been fully tested yet"}. `,
    conflict: (a, b, s) => `${a} and ${b} are in conflict${s > 0.6 ? ". Something specific happened that hasn't been resolved" : " — a low-grade friction that colors their interactions"}. `,
    influence: (a, b, s) => `${a} has influence over ${b}${s > 0.6 ? " — enough to shift decisions and moods" : ", though ${b} doesn't always realize it"}. `,
    alliance: (a, b, s) => `${a} and ${b} are aligned. They've found enough common ground to move together. `,
    group_membership: (a, b, s) => `${a} and ${b} share a group — a structural connection that shapes how often they interact. `,
  };
  const desc = descriptions[relType]?.(agentA.name, agentB.name, strength) ?? "";
  const sharedGroups = agentA.groups.filter(g => agentB.groups.includes(g));
  const suffix = sharedGroups.length
    ? `They're both part of: ${sharedGroups.join(", ")}.`
    : "";
  return (desc + suffix).trim();
}

// ─── sub-components ───────────────────────────────────────────────────────────

function Divider() {
  return <div style={{ height: 1, background: "#1a2030", margin: "16px 0" }} />;
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 10, color: "#4b5563", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>
      {children}
    </div>
  );
}

function Tag({ label, color }: { label: string; color?: string }) {
  return (
    <span style={{
      display: "inline-block", fontSize: 11, padding: "2px 8px", borderRadius: 999,
      background: color ? `${color}1a` : "#111827",
      color: color || "#6b7785",
      border: `1px solid ${color ? `${color}35` : "#1e2b3a"}`,
      marginRight: 4, marginBottom: 4,
    }}>{label}</span>
  );
}

function StrengthBar({ value, color }: { value: number; color: string }) {
  const pct = Math.min(100, Math.abs(value) * 100);
  return (
    <div style={{ height: 3, background: "#111827", borderRadius: 2, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2 }} />
    </div>
  );
}

// ─── Agent Chat ───────────────────────────────────────────────────────────────

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
      setMessages(m => [...m, { role: "agent", text: "(No response — check backend and LLM provider.)" }]);
    } finally {
      setLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  return (
    <div>
      <Label>Talk to {agentName}</Label>
      <div style={{
        background: "#080d13", borderRadius: 8, border: "1px solid #1a2030",
        padding: 10, minHeight: 80, maxHeight: 220, overflowY: "auto",
        marginBottom: 8, display: "flex", flexDirection: "column", gap: 8,
      }}>
        {messages.length === 0 && (
          <div style={{ fontSize: 11, color: "#374151", fontStyle: "italic" }}>
            Ask {agentName} anything. They'll respond in character.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
            <span style={{
              fontSize: 10, color: m.role === "user" ? "#60a5fa" : "#a855f7",
              flexShrink: 0, paddingTop: 1, fontWeight: 600,
            }}>
              {m.role === "user" ? "You" : agentName}
            </span>
            <span style={{ fontSize: 12, color: m.role === "user" ? "#94a3b8" : "#e2e8f0", lineHeight: 1.5 }}>
              {m.text}
            </span>
          </div>
        ))}
        {loading && (
          <div style={{ fontSize: 11, color: "#374151", fontStyle: "italic" }}>
            {agentName} is thinking...
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
          placeholder={`Message ${agentName}...`}
          style={{
            flex: 1, background: "#0e1420", border: "1px solid #1e2b3a",
            borderRadius: 6, padding: "5px 9px", fontSize: 12, color: "#e2e8f0",
          }}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          style={{
            background: loading || !input.trim() ? "#111827" : "#1e3a5f",
            color: loading || !input.trim() ? "#374151" : "#60a5fa",
            border: "1px solid #1e2b3a", borderRadius: 6,
            padding: "5px 12px", fontSize: 12, cursor: "pointer",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

// ─── Agent Inspector ──────────────────────────────────────────────────────────

function AgentInspector({ agent, allAgents, worldId, currentDay }: {
  agent: Agent; allAgents: Agent[]; worldId: string | null; currentDay: number;
}) {
  const moodColor = MOOD_COLOR[agent.mood] || "#6b7785";
  const narrative = buildNarrative(agent);
  const rels = Object.entries(agent.relationships).sort(
    (a, b) => Math.abs(b[1].strength) - Math.abs(a[1].strength)
  );

  return (
    <div>
      {/* avatar + header */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 14 }}>
        <div style={{
          width: 52, height: 52, borderRadius: "50%", flexShrink: 0,
          background: `radial-gradient(circle at 35% 35%, ${moodColor}30, #0e1420)`,
          border: `2px solid ${moodColor}`,
          boxShadow: `0 0 16px ${moodColor}40`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 17, fontWeight: 700, color: "#f1f5f9",
        }}>
          {agent.name.trim().split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase()}
        </div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9" }}>{agent.name}</div>
          <div style={{ fontSize: 12, color: "#475569", marginTop: 1 }}>{agent.role}</div>
          <div style={{ display: "flex", gap: 6, marginTop: 5 }}>
            <span style={{
              fontSize: 11, padding: "2px 8px", borderRadius: 999,
              background: `${moodColor}1a`, color: moodColor, border: `1px solid ${moodColor}35`,
            }}>{agent.mood}</span>
            <span style={{
              fontSize: 11, padding: "2px 8px", borderRadius: 999,
              background: "#111827", color: "#475569", border: "1px solid #1e2b3a",
            }}>
              {agent.influence_score >= 0 ? "+" : ""}{agent.influence_score.toFixed(1)} influence
            </span>
          </div>
        </div>
      </div>

      {/* narrative summary */}
      <div style={{
        fontSize: 12, color: "#94a3b8", lineHeight: 1.65,
        padding: "10px 12px", background: "#080d13",
        borderRadius: 8, border: "1px solid #111827", marginBottom: 16,
      }}>
        {narrative}
      </div>

      <Divider />

      {/* traits */}
      {agent.traits.length > 0 && (
        <>
          <Label>Personality</Label>
          <div style={{ marginBottom: 14 }}>
            {agent.traits.map(t => <Tag key={t} label={t} />)}
          </div>
        </>
      )}

      {/* goals */}
      {agent.goals.length > 0 && (
        <>
          <Label>Wants</Label>
          <div style={{ marginBottom: 14 }}>
            {agent.goals.map((g, i) => (
              <div key={i} style={{
                fontSize: 12, color: "#94a3b8", padding: "5px 10px",
                background: "#080d13", borderRadius: 6, marginBottom: 4,
                borderLeft: "2px solid #1e3a5f",
              }}>
                {g}
              </div>
            ))}
          </div>
        </>
      )}

      {/* groups */}
      {agent.groups.length > 0 && (
        <>
          <Label>Groups</Label>
          <div style={{ marginBottom: 14 }}>
            {agent.groups.map(g => <Tag key={g} label={g} color="#06b6d4" />)}
          </div>
        </>
      )}

      {/* relationships */}
      {rels.length > 0 && (
        <>
          <Divider />
          <Label>Relationships ({rels.length})</Label>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 14 }}>
            {rels.map(([name, r]) => {
              const color = REL_COLOR[r.type] || "#6b7785";
              const other = allAgents.find(a => a.name === name);
              return (
                <div key={name}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div style={{
                        width: 24, height: 24, borderRadius: "50%", background: "#0e1420",
                        border: `1px solid ${color}60`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 9, color: "#94a3b8", flexShrink: 0,
                      }}>
                        {name.slice(0, 2).toUpperCase()}
                      </div>
                      <span style={{ fontSize: 12, color: "#e2e8f0" }}>{name}</span>
                      {other && (
                        <span style={{ fontSize: 10, color: "#374151" }}>{other.role}</span>
                      )}
                    </div>
                    <span style={{
                      fontSize: 10, padding: "1px 6px", borderRadius: 999,
                      background: `${color}18`, color, border: `1px solid ${color}30`,
                    }}>{r.type}</span>
                  </div>
                  <StrengthBar value={r.strength} color={color} />
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* memories */}
      {(agent.long_term_memory.length > 0 || agent.short_term_memory.length > 0) && (
        <>
          <Divider />
          <Label>Memory</Label>
          <div style={{ display: "flex", flexDirection: "column", gap: 5, marginBottom: 14 }}>
            {agent.short_term_memory.slice(-3).map((m, i) => (
              <div key={`st-${i}`} style={{
                fontSize: 11, color: "#94a3b8", padding: "6px 10px",
                background: "#080d13", borderRadius: 6,
                borderLeft: "2px solid #1e3a5f",
              }}>
                <span style={{ fontSize: 9, color: "#1e3a5f", display: "block", marginBottom: 2 }}>TODAY</span>
                {m}
              </div>
            ))}
            {agent.long_term_memory.slice(-4).map((m, i) => (
              <div key={`lt-${i}`} style={{
                fontSize: 11, color: "#64748b", padding: "6px 10px",
                background: "#080d13", borderRadius: 6,
                borderLeft: "2px solid #111827",
              }}>
                <span style={{ fontSize: 9, color: "#1a2535", display: "block", marginBottom: 2 }}>PAST</span>
                {m}
              </div>
            ))}
          </div>
        </>
      )}

      {/* agent chat */}
      {worldId && (
        <>
          <Divider />
          <AgentChat
            worldId={worldId}
            agentId={agent.id}
            agentName={agent.name}
            currentDay={currentDay}
          />
        </>
      )}
    </div>
  );
}

// ─── Edge Inspector ───────────────────────────────────────────────────────────

function EdgeInspector({ edgeKey, allAgents }: {
  edgeKey: string; allAgents: Agent[];
}) {
  const parts = edgeKey.split("|");
  const relType = (parts[2] || "trust") as RelationshipType;
  const color = REL_COLOR[relType] || "#6b7785";
  const agentA = allAgents.find(a => a.id === parts[0]);
  const agentB = allAgents.find(a => a.id === parts[1]);

  if (!agentA || !agentB) {
    return <div style={{ fontSize: 12, color: "#374151" }}>Relationship data unavailable.</div>;
  }

  const relAB = agentA.relationships[agentB.name];
  const relBA = agentB.relationships[agentA.name];
  const strength = relAB?.strength ?? relBA?.strength ?? 0;
  const narrative = buildEdgeNarrative(agentA, agentB, relType, strength);

  return (
    <div>
      {/* header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <div style={{
          fontSize: 13, fontWeight: 600, color: "#f1f5f9",
          padding: "6px 10px", background: "#0e1420",
          borderRadius: 7, border: "1px solid #1e2b3a",
        }}>{agentA.name}</div>
        <div style={{ flex: 1, textAlign: "center" }}>
          <div style={{ height: 2, background: color, opacity: 0.5, marginBottom: 4 }} />
          <Tag label={relType} color={color} />
        </div>
        <div style={{
          fontSize: 13, fontWeight: 600, color: "#f1f5f9",
          padding: "6px 10px", background: "#0e1420",
          borderRadius: 7, border: "1px solid #1e2b3a",
        }}>{agentB.name}</div>
      </div>

      {/* narrative */}
      <div style={{
        fontSize: 12, color: "#94a3b8", lineHeight: 1.65,
        padding: "10px 12px", background: "#080d13",
        borderRadius: 8, border: "1px solid #111827", marginBottom: 16,
      }}>
        {narrative}
      </div>

      <Divider />

      <Label>Bond strength</Label>
      <div style={{ marginBottom: 4 }}><StrengthBar value={strength} color={color} /></div>
      <div style={{ fontSize: 11, color: "#374151", marginBottom: 16 }}>
        {(strength * 100).toFixed(0)}% — {strength > 0.7 ? "strong" : strength > 0.4 ? "moderate" : "weak"}
      </div>

      <Label>{agentA.name}'s perspective</Label>
      <div style={{
        fontSize: 12, color: "#64748b", padding: "8px 10px",
        background: "#080d13", borderRadius: 6, marginBottom: 10,
      }}>
        {relAB
          ? `Views this as ${relAB.type} (${relAB.strength.toFixed(2)})`
          : "No direct record of this connection."}
      </div>

      <Label>{agentB.name}'s perspective</Label>
      <div style={{
        fontSize: 12, color: "#64748b", padding: "8px 10px",
        background: "#080d13", borderRadius: 6, marginBottom: 14,
      }}>
        {relBA
          ? `Views this as ${relBA.type} (${relBA.strength.toFixed(2)})`
          : "No direct record of this connection."}
      </div>

      {agentA.groups.filter(g => agentB.groups.includes(g)).length > 0 && (
        <>
          <Label>Shared groups</Label>
          <div>
            {agentA.groups.filter(g => agentB.groups.includes(g)).map(g => (
              <Tag key={g} label={g} color="#06b6d4" />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Metrics summary (default state) ─────────────────────────────────────────

function MetricsSummary({ initial, current, day }: {
  initial: MacroMetrics; current: MacroMetrics; day: number;
}) {
  function Delta({ a, b, label, color }: { a: number; b: number; label: string; color: string }) {
    const d = b - a;
    const fmt = (v: number) => Number.isInteger(v) ? String(v) : v.toFixed(2);
    return (
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "5px 0", borderBottom: "1px solid #111827",
      }}>
        <span style={{ fontSize: 11, color: "#475569" }}>{label}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: "#f1f5f9", fontWeight: 500 }}>{fmt(b)}</span>
          {d !== 0 && (
            <span style={{
              fontSize: 10, padding: "1px 5px", borderRadius: 4,
              background: d > 0 ? "#14321a" : "#320a0a",
              color: d > 0 ? "#22c55e" : "#ef4444",
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
      <div style={{ marginBottom: 14 }}>
        <Delta label="Friendships" a={initial.friendship_count} b={current.friendship_count} color="#22c55e" />
        <Delta label="Rivalries" a={initial.rivalry_count} b={current.rivalry_count} color="#ef4444" />
        <Delta label="Romances" a={initial.romance_count} b={current.romance_count} color="#f472b6" />
        <Delta label="Conflicts" a={initial.conflict_count} b={current.conflict_count} color="#f97316" />
        <Delta label="Alliances" a={initial.alliance_count} b={current.alliance_count} color="#06b6d4" />
        <Delta label="Avg strength" a={initial.average_relationship_strength} b={current.average_relationship_strength} color="#3b82f6" />
        <Delta label="Fragmentation" a={initial.social_fragmentation} b={current.social_fragmentation} color="#6b7785" />
      </div>

      {current.most_connected.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <Label>Most connected</Label>
          <div>{current.most_connected.map(n => <Tag key={n} label={n} />)}</div>
        </div>
      )}
      {current.influence_gainers.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <Label>Rising influence</Label>
          <div>{current.influence_gainers.map(n => <Tag key={n} label={n} color="#22c55e" />)}</div>
        </div>
      )}
      {current.influence_losers.length > 0 && (
        <div>
          <Label>Losing ground</Label>
          <div>{current.influence_losers.map(n => <Tag key={n} label={n} color="#ef4444" />)}</div>
        </div>
      )}
    </div>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────────

type Selection = { kind: "node"; id: string } | { kind: "edge"; key: string } | null;

export function Inspector({
  selection,
  snap,
  initialMetrics,
  worldId,
}: {
  selection: Selection;
  snap: { agents: Agent[]; metrics: MacroMetrics; day: number; highlights: any[] };
  initialMetrics: MacroMetrics;
  worldId: string | null;
}) {
  const selectedAgent = selection?.kind === "node"
    ? snap.agents.find(a => a.id === selection.id) ?? null
    : null;

  const title = selection?.kind === "node"
    ? selectedAgent?.name ?? "Character"
    : selection?.kind === "edge"
    ? "Relationship"
    : `Day ${snap.day}`;

  return (
    <div style={{
      width: 300, flexShrink: 0, display: "flex", flexDirection: "column",
      background: "#090c10", borderLeft: "1px solid #141b24", height: "100%",
    }}>
      {/* header */}
      <div style={{
        padding: "10px 14px", borderBottom: "1px solid #141b24",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8" }}>{title}</span>
        <span style={{ fontSize: 10, color: "#374151" }}>
          {selection?.kind === "node" ? "character" : selection?.kind === "edge" ? "edge" : "overview"}
        </span>
      </div>

      {/* body */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 14px" }}>
        {!selection && (
          <>
            <div style={{ fontSize: 11, color: "#374151", marginBottom: 16, lineHeight: 1.6 }}>
              Click any node to inspect a character, or click an edge to read about a relationship.
            </div>
            <MetricsSummary initial={initialMetrics} current={snap.metrics} day={snap.day} />

            {snap.highlights.length > 0 && (
              <>
                <Divider />
                <Label>What happened today</Label>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {snap.highlights.slice(0, 6).map((h, i) => (
                    <div key={i} style={{
                      padding: "8px 10px", background: "#080d13",
                      borderRadius: 7, borderLeft: "2px solid #1e3a5f",
                    }}>
                      <div style={{ fontSize: 11, color: "#60a5fa", fontWeight: 600, marginBottom: 3 }}>
                        {h.agent}
                      </div>
                      <div style={{ fontSize: 11, color: "#475569", lineHeight: 1.5 }}>
                        {h.summary}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}

        {selection?.kind === "node" && selectedAgent && (
          <AgentInspector
            agent={selectedAgent}
            allAgents={snap.agents}
            worldId={worldId}
            currentDay={snap.day}
          />
        )}

        {selection?.kind === "edge" && (
          <EdgeInspector edgeKey={selection.key} allAgents={snap.agents} />
        )}
      </div>
    </div>
  );
}
