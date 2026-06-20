"use client";
import { useMemo } from "react";
import type { Agent, DayHighlight, Vignette, VignetteKind, Mood, Forecast, PerceptionNote } from "@/lib/types";
import { PixelAvatar, isEmojiAvatar } from "./PixelAvatar";

/**
 * StoryChapter — turns one day's raw data (highlights + vignettes + event_log)
 * into a single, followable "chapter" of the town's unfolding saga.
 *
 * Each beat leads with a human-readable line and carries the character's pixel
 * avatar + name, so a day reads like a story rather than a terse log. Vignettes
 * (dreams / catchphrases / announcements) and any leftover event-log lines are
 * folded into the same feed. A short chapter header frames the day's mood, and
 * the active event is surfaced as the day's inciting moment.
 *
 * Fully defensive: missing highlights / vignettes / event_log / agents must not
 * crash, and older saves (which may lack vignettes) render fine.
 */

const MOOD_COLOR: Record<Mood, string> = {
  calm: "#6b7785", excited: "#f59e0b", frustrated: "#ef4444",
  heartbroken: "#ec4899", ambitious: "#a855f7", anxious: "#f97316",
  content: "#22c55e", angry: "#dc2626", hopeful: "#06b6d4",
  lonely: "#475569", confident: "#2563eb",
};

const KIND_STYLE: Record<VignetteKind, { color: string; label: string; symbol: string }> = {
  dream:        { color: "var(--purple)", label: "DREAM",        symbol: "☁" },
  catchphrase:  { color: "var(--cyan)",   label: "CATCHPHRASE",  symbol: "❝" },
  announcement: { color: "var(--gold)",   label: "ANNOUNCEMENT", symbol: "📣" },
};

// A unified story beat the chapter renders.
type Beat =
  | { kind: "highlight"; agent: string; text: string }
  | { kind: "vignette"; agent: string; text: string; vk: VignetteKind }
  | { kind: "event"; text: string };

// Strip the leading "[Name] " bracket tag from a raw event-log line, returning
// the name (if any) and the cleaned, readable remainder.
function parseLogLine(line: string): { name: string | null; text: string } {
  const m = /^\s*\[([^\]]+)\]\s*(.*)$/.exec(line);
  if (m) {
    const text = m[2].trim();
    // Capitalise the first letter so it reads as a sentence about the person.
    return { name: m[1].trim(), text: text.charAt(0).toUpperCase() + text.slice(1) };
  }
  return { name: null, text: line.trim() };
}

// Derive a short, evocative chapter subtitle from the day's mood mix + activity.
function chapterMood(agents: Agent[], beatCount: number, hasEvent: boolean): string {
  if (hasEvent) return "a turn of events";
  const moods = agents.map(a => a.mood);
  const tense = moods.filter(m => ["frustrated", "angry", "anxious", "heartbroken", "lonely"].includes(m)).length;
  const bright = moods.filter(m => ["excited", "content", "hopeful", "confident"].includes(m)).length;
  const total = moods.length || 1;
  if (tense / total > 0.45) return "tensions rise";
  if (bright / total > 0.55) return "spirits lift";
  if (beatCount === 0) return "a quiet day";
  if (beatCount > 6) return "a busy day in town";
  return "the town stirs";
}

function findAgent(agents: Agent[], name: string): Agent | undefined {
  if (!name) return undefined;
  const lower = name.toLowerCase();
  return agents.find(a => a.name?.toLowerCase() === lower);
}

function Face({ agent, name, size }: { agent?: Agent; name: string; size: number }) {
  const moodColor = agent ? (MOOD_COLOR[agent.mood] || "#6b7785") : "var(--border)";
  return (
    <div style={{
      width: size + 8, height: size + 8, flexShrink: 0,
      background: agent ? `radial-gradient(circle at 35% 35%, ${moodColor}22, var(--surface-2))` : "var(--surface-2)",
      border: `2px solid ${agent ? moodColor : "var(--border)"}`,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {agent && isEmojiAvatar(agent.avatar) ? (
        <span style={{ fontSize: size - 4, lineHeight: 1 }}>{agent.avatar}</span>
      ) : (
        <PixelAvatar seed={agent?.id ?? name} avatar={agent?.avatar} mood={agent?.mood} size={size} title={name} />
      )}
    </div>
  );
}

export function StoryChapter({
  agents, highlights, vignettes, eventLog, milestones, perceptionNotes, day, totalDays, activeEvent, isStartEvent, forecast, fillHeight = false,
}: {
  agents: Agent[];
  highlights?: DayHighlight[];
  vignettes?: Vignette[];
  eventLog?: string[];
  milestones?: string[];
  perceptionNotes?: PerceptionNote[];
  day: number;
  totalDays: number;
  activeEvent?: string | null;
  isStartEvent: boolean;
  forecast?: Forecast | null;
  // When true (desktop Story tab), the card fills its column's fixed height and the
  // whole chapter scrolls as one — so it matches the interactive panel's length instead
  // of dictating it. The inner beats list drops its own cap to avoid a nested scrollbar.
  fillHeight?: boolean;
}) {
  const safeAgents = agents ?? [];
  const turningPoints = (milestones ?? []).filter(m => (m ?? "").trim());
  // Subjective reinterpretations worth showing: only those where perception meaningfully
  // diverged from the raw signal (otherwise it's just "they took it at face value").
  const perceptions = (perceptionNotes ?? []).filter(
    p => (p?.narrative ?? "").trim() && Math.abs((p.perceived_delta ?? 0) - (p.raw_delta ?? 0)) >= 0.05
  );

  const beats = useMemo<Beat[]>(() => {
    const out: Beat[] = [];
    const seen = new Set<string>();

    // 1) Lead with the human-readable highlights (best summaries available).
    for (const h of highlights ?? []) {
      const text = (h?.summary ?? "").trim();
      if (!text) continue;
      out.push({ kind: "highlight", agent: h.agent ?? "", text });
      seen.add(text.toLowerCase());
    }

    // 2) Fold in vignettes (dreams / catchphrases / announcements).
    for (const v of vignettes ?? []) {
      const text = (v?.text ?? "").trim();
      if (!text) continue;
      out.push({ kind: "vignette", agent: v.agent ?? "", text, vk: v.kind });
    }

    // 3) Backfill with cleaned event-log lines the highlights didn't already cover,
    //    so nothing is lost but the feed stays digestible.
    for (const raw of eventLog ?? []) {
      const { name, text } = parseLogLine(raw ?? "");
      if (!text) continue;
      if (seen.has(text.toLowerCase())) continue;
      if (name) out.push({ kind: "highlight", agent: name, text });
      else out.push({ kind: "event", text });
    }

    return out;
  }, [highlights, vignettes, eventLog]);

  const subtitle = chapterMood(safeAgents, beats.length, !!activeEvent && !isStartEvent);

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--accent-dim)",
      boxShadow: "0 6px 24px rgba(100,80,200,0.09)",
      padding: "16px 18px", position: "relative",
      ...(fillHeight ? { height: "100%", minHeight: 0, overflowY: "auto" as const, width: "100%" } : null),
    }}>
      <div style={{ position: "absolute", top: -2, left: -2, width: 12, height: 12, borderTop: "2px solid var(--accent)", borderLeft: "2px solid var(--accent)" }} />

      {/* ── Chapter header ───────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap", marginBottom: 4 }}>
        <span className="font-pixel" style={{ fontSize: 9, color: "var(--accent)", letterSpacing: "0.12em" }}>
          CHAPTER {day}
        </span>
        <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-muted)", letterSpacing: "0.1em" }}>
          OF {totalDays}
        </span>
      </div>
      <h3 style={{
        fontSize: 16, color: "var(--text)", fontWeight: 700, margin: 0, lineHeight: 1.3,
        fontFamily: "ui-monospace, monospace",
      }}>
        Day {day} — {subtitle}
      </h3>

      {/* Inciting moment: the active/starting event for the day. */}
      {activeEvent && (
        <div style={{
          marginTop: 12, padding: "10px 12px",
          background: "var(--surface-2)", borderLeft: "3px solid var(--gold)",
        }}>
          <div className="font-pixel" style={{ fontSize: 7, color: "var(--gold)", letterSpacing: "0.1em", marginBottom: 5 }}>
            {isStartEvent ? "✶ HOW IT BEGAN" : "✶ TODAY'S INCITING MOMENT"}
          </div>
          <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.6, fontFamily: "ui-monospace, monospace" }}>
            {activeEvent}
          </div>
        </div>
      )}

      {/* Turning points: relationship milestones that moved the story this day. */}
      {turningPoints.length > 0 && (
        <div style={{
          marginTop: 12, padding: "10px 12px",
          background: "rgba(204,93,232,0.06)", borderLeft: "3px solid var(--purple)",
        }}>
          <div className="font-pixel" style={{ fontSize: 7, color: "var(--purple)", letterSpacing: "0.1em", marginBottom: 6 }}>
            ✦ TURNING POINTS
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {turningPoints.slice(0, 6).map((m, i) => (
              <div key={i} style={{ fontSize: 12.5, color: "var(--text)", lineHeight: 1.5, fontFamily: "ui-monospace, monospace" }}>
                <span style={{ color: "var(--purple)", marginRight: 6 }}>↳</span>{m}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Narrative beats ──────────────────────────────────────────── */}
      <div style={{ marginTop: 14 }}>
        {beats.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.6, fontStyle: "italic", fontFamily: "ui-monospace, monospace" }}>
            A calm day in town — nothing of note was recorded.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: fillHeight ? undefined : 340, overflowY: fillHeight ? "visible" : "auto" }}>
            {beats.map((b, i) => {
              if (b.kind === "event") {
                return (
                  <div key={i} style={{
                    fontSize: 12.5, color: "var(--text-dim)", lineHeight: 1.6,
                    fontFamily: "ui-monospace, monospace", paddingLeft: 50,
                  }}>
                    <span style={{ color: "var(--accent-dim)", marginRight: 6 }}>•</span>{b.text}
                  </div>
                );
              }
              const agent = findAgent(safeAgents, b.agent);
              const vk = b.kind === "vignette" ? b.vk : null;
              const ks = vk ? KIND_STYLE[vk] : null;
              const accent = ks ? ks.color : (agent ? (MOOD_COLOR[agent.mood] || "var(--accent)") : "var(--accent)");
              return (
                <div key={i} style={{
                  display: "flex", gap: 10, alignItems: "flex-start",
                  padding: "9px 11px", background: "var(--surface-2)",
                  borderLeft: `3px solid ${accent}`,
                }}>
                  <Face agent={agent} name={b.agent} size={28} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 3, flexWrap: "wrap" }}>
                      <span className="font-pixel" style={{ fontSize: 9, color: "var(--text)", letterSpacing: "0.04em" }}>
                        {b.agent || "The town"}
                      </span>
                      {agent && (
                        <span style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace" }}>
                          {agent.role}
                        </span>
                      )}
                      {ks && (
                        <span className="font-pixel" style={{
                          fontSize: 7, color: ks.color, letterSpacing: "0.06em", marginLeft: "auto",
                        }}>
                          {ks.symbol} {ks.label}
                        </span>
                      )}
                    </div>
                    <div style={{
                      fontSize: 13, color: "var(--text)", lineHeight: 1.6,
                      fontFamily: "ui-monospace, monospace",
                      fontStyle: vk === "catchphrase" ? "italic" : "normal",
                    }}>
                      {b.text}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── How they took it: subjective perception (information asymmetry) ── */}
      {perceptions.length > 0 && (
        <div style={{
          marginTop: 14, padding: "10px 12px",
          background: "rgba(59,130,246,0.05)", borderLeft: "3px solid var(--cyan)",
        }}>
          <div className="font-pixel" style={{ fontSize: 7, color: "var(--cyan)", letterSpacing: "0.1em", marginBottom: 6 }}>
            ◌ HOW THEY TOOK IT
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {perceptions.slice(0, 5).map((p, i) => {
              const amplified = Math.abs(p.perceived_delta) > Math.abs(p.raw_delta);
              const agent = findAgent(safeAgents, p.perceiver);
              return (
                <div key={i} style={{ display: "flex", gap: 9, alignItems: "flex-start" }}>
                  <Face agent={agent} name={p.perceiver} size={22} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2, flexWrap: "wrap" }}>
                      <span className="font-pixel" style={{ fontSize: 8, color: "var(--text)", letterSpacing: "0.04em" }}>
                        {p.perceiver}
                      </span>
                      <span className="font-pixel" style={{
                        fontSize: 6, letterSpacing: "0.06em",
                        color: amplified ? "var(--pink)" : "var(--text-muted)",
                      }}>
                        {amplified ? "▲ FELT STRONGER" : "▼ LANDED SOFTER"}
                      </span>
                      {p.revealed_trait && (
                        <span className="font-pixel" style={{ fontSize: 6, color: "var(--gold)", letterSpacing: "0.04em", marginLeft: "auto" }}>
                          ✦ {p.revealed_trait}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-dim)", lineHeight: 1.55, fontFamily: "ui-monospace, monospace", fontStyle: "italic" }}>
                      {p.narrative}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── The stakes: where the town is heading ────────────────────── */}
      {forecast?.narrative && (
        <div style={{
          marginTop: 14, padding: "10px 12px",
          background: "var(--surface-2)", borderLeft: "3px solid var(--accent)",
        }}>
          <div className="font-pixel" style={{ fontSize: 7, color: "var(--accent)", letterSpacing: "0.1em", marginBottom: 5 }}>
            ◇ WHERE THE TOWN IS HEADING
          </div>
          <div style={{ fontSize: 12.5, color: "var(--text-dim)", lineHeight: 1.7, fontFamily: "ui-monospace, monospace", fontStyle: "italic" }}>
            {forecast.narrative}
          </div>
        </div>
      )}
    </div>
  );
}

export default StoryChapter;
