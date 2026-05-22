"use client";
import { useState } from "react";
import { supabase } from "@/lib/supabase";

export function AuthScreen() {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setInfo("Check your email for a confirmation link.");
      }
    } catch (err: any) {
      setError(err.message ?? "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      padding: 24,
    }}>
      <div style={{ width: "100%", maxWidth: 400 }}>
        {/* title */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginBottom: 8 }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%",
              background: "var(--accent)", boxShadow: "0 0 10px var(--accent)",
              animation: "neon-pulse 2s ease-in-out infinite",
            }} />
            <span className="font-pixel" style={{ fontSize: 14, color: "var(--accent)", letterSpacing: "0.05em" }}>
              TINY SOCIETY AI
            </span>
          </div>
          <div style={{ fontSize: 10, color: "var(--text-dim)", letterSpacing: "0.08em" }}>
            multi-agent social simulation
          </div>
        </div>

        {/* card */}
        <div className="panel" style={{ padding: "28px 28px" }}>
          <div className="font-pixel" style={{
            fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.1em",
            marginBottom: 20, textAlign: "center",
          }}>
            {mode === "login" ? "── CONTINUE ──" : "── NEW ACCOUNT ──"}
          </div>

          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.08em", display: "block", marginBottom: 6 }}>
                EMAIL
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="player@example.com"
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.08em", display: "block", marginBottom: 6 }}>
                PASSWORD
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
              />
            </div>

            {error && (
              <div style={{
                padding: "8px 12px", background: "rgba(255,68,68,0.06)",
                border: "1px solid var(--red)", fontSize: 11, color: "var(--red)",
                fontFamily: "ui-monospace, monospace", letterSpacing: "0.03em",
              }}>
                ✖ {error}
              </div>
            )}

            {info && (
              <div style={{
                padding: "8px 12px", background: "rgba(81,207,102,0.06)",
                border: "1px solid var(--green)", fontSize: 11, color: "var(--green)",
                fontFamily: "ui-monospace, monospace", letterSpacing: "0.03em",
              }}>
                ✔ {info}
              </div>
            )}

            <button type="submit" className="btn" disabled={loading} style={{ marginTop: 4 }}>
              {loading ? "..." : mode === "login" ? "SIGN IN" : "CREATE ACCOUNT"}
            </button>
          </form>

          <div style={{ marginTop: 20, textAlign: "center" }}>
            <button
              onClick={() => { setMode(m => m === "login" ? "signup" : "login"); setError(null); setInfo(null); }}
              className="font-pixel"
              style={{
                background: "none", border: "none", cursor: "pointer",
                fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.08em",
                textDecoration: "underline",
              }}
            >
              {mode === "login" ? "NO ACCOUNT? REGISTER" : "HAVE AN ACCOUNT? SIGN IN"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
