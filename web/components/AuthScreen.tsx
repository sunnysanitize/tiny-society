"use client";
import { AuthForm } from "@/components/AuthForm";

interface Props {
  onGuest: () => void;
}

export function AuthScreen({ onGuest }: Props) {
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
          <AuthForm onGuest={onGuest} />
        </div>
      </div>
    </div>
  );
}
