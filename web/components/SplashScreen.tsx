"use client";
import { useEffect, useState } from "react";

/**
 * Full-screen landing image shown on every fresh page load. Holds briefly, then
 * fades out to reveal whatever screen rendered underneath (login, or the user's
 * saves if already signed in). Auto-only — there's no skip; it's gone in ~1.6s.
 */
export function SplashScreen() {
  // hold → covering the app · fading → opacity transition running · done → unmounted
  const [phase, setPhase] = useState<"hold" | "fading" | "done">("hold");

  useEffect(() => {
    const HOLD_MS = 600;
    const FADE_MS = 450;
    const toFade = setTimeout(() => setPhase("fading"), HOLD_MS);
    const toDone = setTimeout(() => setPhase("done"), HOLD_MS + FADE_MS);
    return () => { clearTimeout(toFade); clearTimeout(toDone); };
  }, []);

  if (phase === "done") return null;

  return (
    <div
      aria-hidden
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "var(--bg, #eef0ff)",
        display: "flex", alignItems: "center", justifyContent: "center",
        opacity: phase === "fading" ? 0 : 1,
        transition: "opacity 450ms ease-out",
        // Once fading, let clicks pass through to the screen underneath.
        pointerEvents: phase === "fading" ? "none" : "auto",
      }}
    >
      <img
        src="/tinysocietylanding.png"
        alt="Tiny Society"
        style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
      />
    </div>
  );
}
