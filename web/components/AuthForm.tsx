"use client";
import { useState } from "react";
import { supabase } from "@/lib/supabase";
import { normalizeUsername, usernameToEmail, validateUsername } from "@/lib/auth";

interface Props {
  // Called after a successful login/signup. The global onAuthStateChange in
  // page.tsx remains the source of truth for session state; this is only a UI
  // hook so callers (e.g. a modal) can react to a completed sign-in.
  onSuccess?: () => void;
  // Slightly tightens spacing/labels when embedded in a modal vs. full screen.
  compact?: boolean;
}

export function AuthForm({ onSuccess, compact }: Props) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [username, setUsername] = useState("");
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
          options: { data: { username: normalizeUsername(username) } },
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
      onSuccess?.();
    } catch (err: any) {
      setError(err.message ?? "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="font-pixel" style={{
        fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.1em",
        marginBottom: compact ? 14 : 20, textAlign: "center",
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

      <div style={{ marginTop: compact ? 14 : 20, textAlign: "center" }}>
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
    </>
  );
}
