"use client";
import { useEffect, useRef, useState } from "react";
import { AuthForm } from "@/components/AuthForm";
import { PixelAvatar } from "@/components/PixelAvatar";

/**
 * TitleScreen — the game's front door (replaces the bare sign-in card).
 *
 * A living town: the town art (town-cutout.png, its sky cut away) sits in a fixed 2:1
 * "stage" that covers the viewport (anchored to the bottom, so the grass and paths
 * always show). Behind it a sky runs day -> sunset -> night -> dawn with a square sun,
 * moon and stars; the town and villagers are tinted to match (all driven by one CSS
 * animation, ts-cycle). PixelAvatar villagers walk across the grass, now and then saying
 * something. Positions are percentages of the art, so they hold at any screen size.
 * "Press start" (click, Enter or Space) opens the menu: play now as a guest, or sign in.
 */

interface Props {
  onGuest: () => void;
}

// lane = feet position as % of stage height; dur = seconds per crossing; delay < 0 starts mid-walk
const VILLAGERS = [
  { seed: "Mabel", lane: 91.5, dur: 38, delay: -4, dir: 1 },
  { seed: "Otto", lane: 94.5, dur: 46, delay: -27, dir: -1 },
  { seed: "Priya", lane: 97.5, dur: 34, delay: -15, dir: 1 },
  { seed: "Jun", lane: 91.5, dur: 52, delay: -40, dir: -1 },
  { seed: "Rosa", lane: 97.5, dur: 42, delay: -33, dir: -1 },
  { seed: "Felix", lane: 94.5, dur: 36, delay: -9, dir: 1 },
  { seed: "Agnes", lane: 86.5, dur: 60, delay: -22, dir: 1 },
];

// The kind of thing people in a tiny town say — what the game is about, without explaining it.
const LINES = [
  "Did you hear about the mill?",
  "Who keeps leaving the gate open?",
  "I'm not speaking to Otto today.",
  "Something's off about the new baker.",
  "Don't tell anyone I told you.",
  "The mayor is hiding something.",
  "Pie at the fountain, three o'clock.",
  "Lovely weather. Suspicious, really.",
  "She said WHAT about me?",
  "I'd keep an eye on Felix.",
];

// Fixed pseudo-random star field in the upper sky (same on server and client).
const STARS = Array.from({ length: 48 }, (_, i) => ({
  x: (i * 37.7 + 11) % 100,
  y: (i * 23.3 + 5) % 52,
  big: i % 7 === 0,
}));

const SPARKLES = [
  { x: 6, y: 64 }, { x: 14, y: 67 }, { x: 21, y: 63 }, { x: 3, y: 70 },
  { x: 84, y: 88 }, { x: 91, y: 92 }, { x: 97, y: 86 }, { x: 88, y: 96 },
];

export function TitleScreen({ onGuest }: Props) {
  const [menu, setMenu] = useState<"closed" | "main" | "signin">("closed");
  const [talk, setTalk] = useState<{ who: number; line: string } | null>(null);
  const walkers = useRef<(HTMLDivElement | null)[]>([]);

  // One villager speaks at a time, picked from those well inside the screen so the
  // bubble isn't cut off; the line stays up long enough to read.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let i = 0;
    const speak = () => {
      const margin = Math.min(160, window.innerWidth / 4);
      const onScreen = walkers.current.flatMap((el, k) => {
        const r = el?.getBoundingClientRect();
        return r && r.left > margin && r.right < window.innerWidth - margin ? [k] : [];
      });
      if (!onScreen.length) return;
      i = (i + 1 + Math.floor(Math.random() * 3)) % LINES.length;
      setTalk({ who: onScreen[Math.floor(Math.random() * onScreen.length)], line: LINES[i] });
    };
    const t0 = setTimeout(speak, 1400);
    const id = setInterval(speak, 3600);
    return () => { clearTimeout(t0); clearInterval(id); };
  }, []);

  // Enter / Space anywhere presses start, like a console title screen.
  useEffect(() => {
    if (menu !== "closed") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setMenu("main"); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menu]);

  return (
    <div className="ts-title">
      <div className="ts-sky" aria-hidden="true" />
      <div className="ts-stage" aria-hidden="true">
        {STARS.map((s, i) => (
          <span key={i} className={`ts-star ${s.big ? "ts-star-big" : ""}`}
                style={{ left: `${s.x}%`, top: `${s.y}%`, animationDelay: `${(i % 9) * 0.45}s` }} />
        ))}
        <div className="ts-sun" />
        <div className="ts-moon" />
        <div className="ts-cloud ts-cloud-a" />
        <div className="ts-cloud ts-cloud-b" />
        <div className="ts-cloud ts-cloud-c" />
        <div className="ts-town" />
        <div className="ts-town-tint" />
        {SPARKLES.map((s, i) => (
          <span key={i} className="ts-sparkle" style={{ left: `${s.x}%`, top: `${s.y}%`, animationDelay: `${i * 0.37}s` }} />
        ))}
        {VILLAGERS.map((v, i) => (
          <div
            key={v.seed}
            ref={el => { walkers.current[i] = el; }}
            className={`ts-walker ${v.dir < 0 ? "ts-walker-rtl" : ""}`}
            style={{ top: `${v.lane}%`, animationDuration: `${v.dur}s`, animationDelay: `${v.delay}s`, zIndex: Math.round(v.lane) }}
          >
            {talk?.who === i && <div key={talk.line} className="ts-bubble">{talk.line}</div>}
            <div className="ts-body">
              <PixelAvatar seed={v.seed} size={48} />
              <div className="ts-legs"><span /><span /></div>
            </div>
          </div>
        ))}
      </div>

      <div className={`ts-front ${menu !== "closed" ? "ts-front-open" : ""}`}>
        <h1 className="ts-logo" aria-label="Tiny Society">
          {"Tiny Society".split("").map((ch, i) => (
            <span key={i} style={{ animationDelay: `${0.15 + i * 0.05}s` }}>{ch === " " ? " " : ch}</span>
          ))}
        </h1>
        <p className="ts-tagline">Build a little town, stir up some trouble, and watch what everyone does.</p>

        {menu === "closed" && (
          <button className="ts-start" onClick={() => setMenu("main")}>
            <span className="ts-caret">▶</span> Press start
          </button>
        )}

        {menu === "main" && (
          <div className="panel ts-menu">
            <button className="btn ts-menu-btn" onClick={onGuest} autoFocus>Play now</button>
            <button className="btn-secondary ts-menu-btn" onClick={() => setMenu("signin")}>Sign in</button>
          </div>
        )}

        {menu === "signin" && (
          <div className="panel ts-menu">
            <AuthForm compact />
            <button className="ts-back" onClick={() => setMenu("main")}>Back</button>
          </div>
        )}
      </div>
    </div>
  );
}
