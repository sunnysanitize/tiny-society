"use client";
import { useState } from "react";
import { supabase } from "@/lib/supabase";
import { normalizeUsername, usernameToEmail, validateUsername } from "@/lib/auth";

export function AuthScreen() {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [recoveryEmail, setRecoveryEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const usernameError = validateUsername(username);
      if (usernameError) throw new Error(usernameError);

      const email = usernameToEmail(username);

      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw new Error("Incorrect username or password");
      } else {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { username: normalizeUsername(username), recovery_email: recoveryEmail.trim() || null } },
        });
        if (error) {
          if (/already registered|already exists/i.test(error.message)) {
            throw new Error("That username is already taken");
          }
          throw error;
        }
        // With email confirmation disabled, signUp returns a session and the
        // onAuthStateChange listener takes over. If confirmation is still on,
        // no session comes back — sign in explicitly so the user isn't stuck.
        if (!data.session) {
          const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
          if (signInError) throw signInError;
        }
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
              THE TINY SOCIETY GAME
            </span>
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
                USERNAME
              </label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="pixelfish"
                required
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
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

            {mode === "signup" && (
              <div>
                <label className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.08em", display: "block", marginBottom: 6 }}>
                  RECOVERY EMAIL <span style={{ opacity: 0.6 }}>(OPTIONAL)</span>
                </label>
                <input
                  type="email"
                  value={recoveryEmail}
                  onChange={e => setRecoveryEmail(e.target.value)}
                  placeholder="player@example.com"
                  autoComplete="email"
                />
                <div style={{ marginTop: 6, fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", opacity: 0.7 }}>
                  Used only to reset a forgotten password. Leave blank to skip.
                </div>
              </div>
            )}

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
