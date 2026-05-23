"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Forecast, ProphecyVerdict, Vignette, VignetteKind, Verdict } from "@/lib/types";

// ── shared bits ───────────────────────────────────────────────────────────────

function PanelLabel({ children, color = "var(--accent)" }: { children: React.ReactNode; color?: string }) {
  return (
    <div className="font-pixel" style={{ fontSize: 8, color, letterSpacing: "0.1em", marginBottom: 10, display: "flex", alignItems: "center", gap: 8 }}>
      {children}
    </div>
  );
}

// ── Prophecy input ──────────────────────────────────────────────────────────
// Free-text prediction the player makes before / during a run.

export function ProphecyInput({ worldId, initial, onSaved }: {
  worldId: string; initial?: string | null; onSaved?: (prophecy: string) => void;
}) {
  const [text, setText] = useState(initial ?? "");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(!!initial);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    const p = text.trim();
    if (!p || busy) return;
    setBusy(true); setErr(null);
    try {
      await api.setProphecy(worldId, p);
      setSaved(true);
      onSaved?.(p);
    } catch (e: any) { setErr(e?.message ?? "Failed to save prophecy."); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <div className="font-pixel" style={{ fontSize: 8, color: "var(--purple, var(--accent))", marginBottom: 8, letterSpacing: "0.1em" }}>
        ✦ YOUR PROPHECY (OPTIONAL)
      </div>
      <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace", marginBottom: 8, lineHeight: 1.5 }}>
        Predict how this plays out — e.g. &ldquo;Maya and Theo end up together&rdquo;. After the run, the AI delivers a verdict.
      </div>
      <textarea
        rows={2}
        value={text}
        onChange={e => { setText(e.target.value); setSaved(false); }}
        placeholder="write a free-text prediction about the outcome..."
        style={{ borderColor: "rgba(121,80,242,0.35)", color: "var(--accent)" }}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
        <button className="btn-ghost" onClick={save} disabled={busy || !text.trim()}
          style={{ fontSize: 8, padding: "6px 12px" }}>
          {busy ? "SAVING..." : saved ? "✓ PROPHECY SET" : "SET PROPHECY"}
        </button>
        {saved && <span style={{ fontSize: 9, color: "var(--accent)", fontFamily: "ui-monospace", fontStyle: "italic" }}>The swarm will be judged against this.</span>}
      </div>
      {err && <div style={{ fontSize: 9, color: "var(--red)", fontFamily: "ui-monospace", marginTop: 6 }}>✖ {err}</div>}
    </div>
  );
}

// ── Inject event ──────────────────────────────────────────────────────────────
// Queues an event to fire on the next simulated day / continue.

export function InjectEvent({ worldId, pending, onInjected }: {
  worldId: string; pending?: string | null; onInjected?: (event: string) => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [queued, setQueued] = useState<string | null>(pending ?? null);
  const [err, setErr] = useState<string | null>(null);

  async function inject() {
    const ev = text.trim();
    if (!ev || busy) return;
    setBusy(true); setErr(null);
    try {
      const w = await api.injectEvent(worldId, ev);
      setQueued(w.pending_event ?? ev);
      setText("");
      onInjected?.(ev);
    } catch (e: any) { setErr(e?.message ?? "Failed to inject event."); }
    finally { setBusy(false); }
  }

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid rgba(255,215,0,0.3)",
      padding: "10px 14px",
    }}>
      <PanelLabel color="var(--gold)">⚡ INJECT AN EVENT</PanelLabel>
      <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace", marginBottom: 8, lineHeight: 1.5 }}>
        Drop a twist into the world. It takes effect on the next simulated day (when you continue).
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => e.key === "Enter" && inject()}
          placeholder="a surprise event for the next day..."
          style={{ flex: 1, fontSize: 11, color: "var(--gold)", borderColor: "rgba(255,215,0,0.3)" }}
        />
        <button onClick={inject} disabled={busy || !text.trim()} className="btn"
          style={{ padding: "5px 14px", fontSize: 8 }}>
          {busy ? "..." : "QUEUE"}
        </button>
      </div>
      {queued && (
        <div style={{ fontSize: 9, color: "var(--gold)", fontFamily: "ui-monospace", marginTop: 8, fontStyle: "italic" }}>
          ⚡ Queued for the next day: &ldquo;{queued}&rdquo;
        </div>
      )}
      {err && <div style={{ fontSize: 9, color: "var(--red)", fontFamily: "ui-monospace", marginTop: 6 }}>✖ {err}</div>}
    </div>
  );
}

// ── Forecast panel ────────────────────────────────────────────────────────────
// Renders topic leanings (mean in [-1,1]) as labeled bars + confidence + pivotal days.

function topicLabel(k: string) {
  return k.replace(/_/g, " ").toUpperCase();
}

function TopicBar({ label, mean, uncertainty }: { label: string; mean: number; uncertainty?: number }) {
  const m = Math.max(-1, Math.min(1, mean));
  const pct = (m + 1) / 2 * 100; // 0..100, 50 = neutral
  const pos = m >= 0;
  const color = pos ? "#22c55e" : "var(--red)";
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace" }}>{label}</span>
        <span className="font-pixel" style={{ fontSize: 7, color }}>{m >= 0 ? "+" : ""}{m.toFixed(2)}</span>
      </div>
      <div style={{ position: "relative", height: 6, background: "#ebe8f8", border: "1px solid var(--border)" }}>
        {/* center line */}
        <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--border)" }} />
        <div style={{
          position: "absolute", top: 0, bottom: 0,
          left: pos ? "50%" : `${pct}%`,
          width: `${Math.abs(pct - 50)}%`,
          background: color, boxShadow: `0 0 4px ${color}`,
        }} />
      </div>
      {uncertainty != null && (
        <div style={{ fontSize: 7, color: "var(--text-muted)", fontFamily: "ui-monospace", marginTop: 1 }}>
          ± {uncertainty.toFixed(2)} uncertainty
        </div>
      )}
    </div>
  );
}

function ConfidenceMeter({ confidence }: { confidence: number }) {
  const c = Math.max(0, Math.min(1, confidence));
  const color = c > 0.66 ? "#22c55e" : c > 0.33 ? "var(--gold)" : "var(--red)";
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", letterSpacing: "0.08em" }}>SWARM CONFIDENCE</span>
        <span className="font-pixel" style={{ fontSize: 7, color }}>{Math.round(c * 100)}%</span>
      </div>
      <div style={{ height: 6, background: "#ebe8f8", border: "1px solid var(--border)", overflow: "hidden" }}>
        <div style={{ width: `${c * 100}%`, height: "100%", background: color, boxShadow: `0 0 6px ${color}` }} />
      </div>
    </div>
  );
}

export function ForecastPanel({ forecast, topicMeans, topicUncertainty, beliefConfidence }: {
  forecast?: Forecast | null;
  topicMeans?: Record<string, number>;
  topicUncertainty?: Record<string, number>;
  beliefConfidence?: number;
}) {
  // Prefer the full forecast object; otherwise fall back to per-day belief metrics.
  const means = forecast?.topic_means ?? topicMeans;
  const uncertainty = forecast?.topic_uncertainty ?? topicUncertainty;
  const confidence = forecast?.confidence ?? beliefConfidence;
  const keys = means ? Object.keys(means) : [];

  if (!forecast && keys.length === 0 && confidence == null) return null;

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--accent-dim)",
      padding: "12px 16px",
    }}>
      <PanelLabel color="var(--accent)">
        ◇ SWARM FORECAST
        {forecast?.question && <span style={{ color: "var(--text-dim)", fontWeight: 400 }}>{forecast.question}</span>}
      </PanelLabel>

      {confidence != null && <ConfidenceMeter confidence={confidence} />}

      {keys.length > 0 && (
        <div style={{ marginBottom: forecast?.narrative ? 12 : 0 }}>
          {keys.map(k => (
            <TopicBar key={k} label={topicLabel(k)} mean={means![k]} uncertainty={uncertainty?.[k]} />
          ))}
        </div>
      )}

      {forecast?.pivotal_days && forecast.pivotal_days.length > 0 && (
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
          <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", letterSpacing: "0.08em" }}>PIVOTAL DAYS</span>
          {forecast.pivotal_days.map(d => (
            <span key={d} className="font-pixel" style={{
              fontSize: 7, padding: "2px 6px", color: "var(--gold)",
              background: "rgba(255,215,0,0.06)", border: "1px solid rgba(255,215,0,0.3)",
            }}>D{d}</span>
          ))}
        </div>
      )}

      {forecast?.narrative && (
        <div style={{
          fontSize: 10, color: "var(--text)", lineHeight: 1.7, fontFamily: "ui-monospace",
          padding: "8px 10px", background: "var(--surface-2)", borderLeft: "2px solid var(--accent)",
        }}>
          {forecast.narrative}
        </div>
      )}
    </div>
  );
}

// ── Prophecy verdict card ───────────────────────────────────────────────────

const VERDICT_STYLE: Record<Verdict, { color: string; label: string; symbol: string }> = {
  correct:    { color: "#22c55e",      label: "CORRECT",    symbol: "✓" },
  partly:     { color: "var(--gold)",  label: "PARTLY",     symbol: "≈" },
  incorrect:  { color: "var(--red)",   label: "INCORRECT",  symbol: "✖" },
  unresolved: { color: "var(--text-dim)", label: "UNRESOLVED", symbol: "?" },
};

export function VerdictCard({ verdict }: { verdict?: ProphecyVerdict | null }) {
  if (!verdict) return null;
  const s = VERDICT_STYLE[verdict.verdict] ?? VERDICT_STYLE.unresolved;
  return (
    <div style={{
      background: "var(--surface)", border: `1px solid ${s.color}`,
      boxShadow: `0 4px 16px ${s.color}22`, padding: "16px 20px", position: "relative",
    }}>
      <div style={{ position: "absolute", top: -2, left: -2, width: 12, height: 12, borderTop: `2px solid ${s.color}`, borderLeft: `2px solid ${s.color}` }} />
      <PanelLabel color={s.color}>✦ THE PROPHECY — VERDICT</PanelLabel>

      <div style={{
        fontSize: 11, color: "var(--text-dim)", fontFamily: "ui-monospace",
        fontStyle: "italic", marginBottom: 12, lineHeight: 1.6,
        padding: "8px 10px", background: "var(--surface-2)", borderLeft: "2px solid var(--accent-dim)",
      }}>
        &ldquo;{verdict.prediction}&rdquo;
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span className="font-pixel" style={{
          fontSize: 11, color: s.color, padding: "5px 12px",
          background: `${s.color}14`, border: `1px solid ${s.color}`, letterSpacing: "0.08em",
        }}>
          {s.symbol} {s.label}
        </span>
        <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", letterSpacing: "0.06em" }}>
          {Math.round(Math.max(0, Math.min(1, verdict.confidence)) * 100)}% CONFIDENCE
        </span>
      </div>

      {verdict.explanation && (
        <div style={{ fontSize: 11, color: "var(--text)", lineHeight: 1.8, fontFamily: "ui-monospace" }}>
          {verdict.explanation}
        </div>
      )}
    </div>
  );
}

// ── Vignette / digest feed ──────────────────────────────────────────────────

const KIND_STYLE: Record<VignetteKind, { color: string; label: string; symbol: string }> = {
  dream:        { color: "var(--purple, #a855f7)", label: "DREAM",        symbol: "☁" },
  catchphrase:  { color: "var(--cyan)",            label: "CATCHPHRASE",  symbol: "❝" },
  announcement: { color: "var(--gold)",            label: "ANNOUNCEMENT", symbol: "📣" },
};

export function VignetteFeed({ vignettes, day }: { vignettes?: Vignette[]; day: number }) {
  const items = (vignettes ?? []).slice(0, 5);
  if (items.length === 0) return null;
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)", padding: "10px 14px",
    }}>
      <div className="font-pixel" style={{
        fontSize: 7, color: "var(--gold)", letterSpacing: "0.1em", marginBottom: 10,
        display: "flex", alignItems: "center", gap: 8,
      }}>
        ✶ DAY {day} — WHAT HAPPENED
        <span style={{ color: "var(--text-dim)" }}>{items.length} VIGNETTE{items.length === 1 ? "" : "S"}</span>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {items.map((v, i) => {
          const s = KIND_STYLE[v.kind] ?? KIND_STYLE.announcement;
          return (
            <div key={i} style={{
              flex: "1 1 200px", minWidth: 180,
              background: "var(--surface-2)", border: `1px solid ${s.color}40`,
              borderTop: `2px solid ${s.color}`, padding: "9px 11px",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
                <span style={{ fontSize: 11 }}>{s.symbol}</span>
                <span className="font-pixel" style={{ fontSize: 7, color: s.color, letterSpacing: "0.06em" }}>{s.label}</span>
                <span style={{ fontSize: 8, color: "var(--text-dim)", fontFamily: "ui-monospace", marginLeft: "auto" }}>{v.agent}</span>
              </div>
              <div style={{ fontSize: 10, color: "var(--text)", lineHeight: 1.6, fontFamily: "ui-monospace", fontStyle: v.kind === "catchphrase" ? "italic" : "normal" }}>
                {v.text}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
