"use client";
import { AuthForm } from "@/components/AuthForm";

interface Props {
  onClose: () => void;
  // Fired after a successful sign-in/register. Caller hands off to SaveModal;
  // the in-progress world stays in server RAM under the same world_id.
  onSuccess: () => void;
}

export function SaveSignInModal({ onClose, onSuccess }: Props) {
  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.35)", backdropFilter: "blur(2px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 24,
    }} onClick={onClose}>
      <div
        className="panel"
        style={{ width: "100%", maxWidth: 420, padding: "24px 24px" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <span className="font-pixel" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.06em" }}>
            SIGN IN TO SAVE
          </span>
          <button
            onClick={onClose}
            className="font-pixel"
            style={{
              background: "none", border: "none", cursor: "pointer",
              fontSize: 12, color: "var(--text-dim)",
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ marginBottom: 16, fontSize: 11, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.5 }}>
          Your simulation stays open — sign in or create an account and we'll save
          it right away.
        </div>

        <AuthForm compact onSuccess={onSuccess} />
      </div>
    </div>
  );
}
