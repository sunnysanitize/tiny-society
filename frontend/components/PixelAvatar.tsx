"use client";
import { useMemo } from "react";
import type { Mood } from "@/lib/types";

/**
 * PixelAvatar — a deterministic, code-generated pixel-art humanoid sprite.
 *
 * No external image assets: the sprite is built from inline SVG <rect> cells on a
 * 12x12 grid. Every visual feature (skin tone, hairstyle, hair color, shirt color,
 * accessory) is derived from a stable seed (agent.id or agent.name) via a small hash,
 * so a given character always looks the same everywhere in the app. Mood subtly
 * shifts the facial expression (eyes/mouth) and a faint tint behind the head.
 *
 * The `avatar` string field stays a plain string for backend compatibility. If it
 * holds a "pixel:N" variant override, that N nudges the seed so players can re-roll
 * a look. If it holds an emoji (legacy/explicit pick), the caller decides whether to
 * show that instead — PixelAvatar always renders a sprite and never blanks out.
 */

const GRID = 12;

// ── curated pastel palettes (on-theme, readable on light panels) ──────────────
const SKIN = ["#f6d3b3", "#e8b894", "#c98b63", "#9c6b4a", "#f3c9a8", "#7a4f37"];
const HAIR = ["#3a2a1e", "#6b4226", "#a86b3c", "#d7a86e", "#2b2b3a", "#b54b4b", "#8e5fb0", "#c9c9d6", "#e8b84b"];
const SHIRT = ["#7950f2", "#4ec5f0", "#ffd166", "#ef476f", "#06d6a0", "#f78c6b", "#5f8bff", "#b388eb", "#2ec4b6"];
const ACCENT = ["#ffd700", "#ff6b6b", "#4ec5f0", "#a3e635", "#f472b6"];

// hairstyle: which top/side cells are hair (relative to a centered head)
type Style = { top: boolean; sides: boolean; bangs: boolean; long: boolean };
const STYLES: Style[] = [
  { top: true, sides: false, bangs: true, long: false }, // short bangs
  { top: true, sides: true, bangs: false, long: false }, // bowl
  { top: true, sides: true, bangs: false, long: true }, // long
  { top: true, sides: false, bangs: false, long: false }, // buzz
  { top: true, sides: true, bangs: true, long: true }, // full
];

// accessory: 0 none, 1 glasses, 2 hat band, 3 earring/dot, 4 freckles
const ACCESSORIES = 5;

function hashSeed(seed: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

interface Features {
  skin: string;
  hair: string;
  shirt: string;
  accent: string;
  style: Style;
  accessory: number;
}

function deriveFeatures(seed: string, variant: number | null): Features {
  let h = hashSeed(seed);
  if (variant != null) h = (h ^ Math.imul(variant + 1, 2654435761)) >>> 0;
  // pull successive feature indices off the hash deterministically
  const pick = <T,>(arr: T[], salt: number) =>
    arr[(Math.imul(h ^ salt, 2246822519) >>> 0) % arr.length];
  return {
    skin: pick(SKIN, 0x11),
    hair: pick(HAIR, 0x22),
    shirt: pick(SHIRT, 0x33),
    accent: pick(ACCENT, 0x44),
    style: pick(STYLES, 0x55),
    accessory: (Math.imul(h ^ 0x66, 2246822519) >>> 0) % ACCESSORIES,
  };
}

// Eyes/mouth per mood. Returns the eye row "look" and mouth shape.
type Face = { eye: "open" | "happy" | "sad" | "narrow" | "wide"; mouth: "smile" | "flat" | "frown" | "open" };
function moodFace(mood?: Mood): Face {
  switch (mood) {
    case "excited": return { eye: "wide", mouth: "open" };
    case "content": return { eye: "happy", mouth: "smile" };
    case "confident": return { eye: "narrow", mouth: "smile" };
    case "hopeful": return { eye: "open", mouth: "smile" };
    case "ambitious": return { eye: "narrow", mouth: "flat" };
    case "calm": return { eye: "open", mouth: "flat" };
    case "anxious": return { eye: "wide", mouth: "flat" };
    case "frustrated": return { eye: "narrow", mouth: "frown" };
    case "angry": return { eye: "narrow", mouth: "frown" };
    case "lonely": return { eye: "sad", mouth: "flat" };
    case "heartbroken": return { eye: "sad", mouth: "frown" };
    default: return { eye: "open", mouth: "smile" };
  }
}

const MOOD_TINT: Partial<Record<Mood, string>> = {
  excited: "#f59e0b", frustrated: "#ef4444", heartbroken: "#ec4899",
  ambitious: "#a855f7", anxious: "#f97316", angry: "#dc2626",
  hopeful: "#06b6d4", lonely: "#475569", confident: "#2563eb",
};

interface Cell { x: number; y: number; c: string }

function buildCells(f: Features, face: Face): Cell[] {
  const cells: Cell[] = [];
  const put = (x: number, y: number, c: string) => cells.push({ x, y, c });

  const { skin, hair, shirt, accent, style, accessory } = f;
  const hairDark = shade(hair, -18);

  // Head occupies cols 3..8, rows 2..7. Body/shirt rows 8..11.
  // ── hair top (row 1-2) ──
  if (style.top) {
    for (let x = 3; x <= 8; x++) put(x, 1, hair);
    for (let x = 2; x <= 9; x++) put(x, 2, x === 2 || x === 9 ? (style.sides ? hair : skin) : hair);
  }
  // ── face block (rows 3-7) ──
  for (let y = 3; y <= 7; y++) {
    for (let x = 3; x <= 8; x++) put(x, y, skin);
  }
  // side hair
  if (style.sides) {
    for (let y = 3; y <= (style.long ? 7 : 4); y++) {
      put(2, y, hair); put(9, y, hair);
    }
  }
  if (style.long) {
    put(2, 8, hairDark); put(9, 8, hairDark);
  }
  // bangs over forehead
  if (style.bangs) {
    for (let x = 3; x <= 8; x++) put(x, 3, hair);
  }

  // ── eyes (row 4-5) ── left eye cols 4, right eye col 7
  const eyeC = "#2b2533";
  const drawEye = (x: number) => {
    switch (face.eye) {
      case "wide":
        put(x, 4, "#ffffff"); put(x, 5, eyeC); break;
      case "happy":
        put(x, 5, eyeC); break; // single low pixel = ^ curve feel
      case "sad":
        put(x, 4, eyeC); break; // high pixel droop
      case "narrow":
        put(x, 5, eyeC); break;
      case "open":
      default:
        put(x, 4, eyeC); put(x, 5, eyeC); break;
    }
  };
  drawEye(4);
  drawEye(7);

  // ── mouth (row 6-7) ──
  const mouthC = shade(skin, -32);
  switch (face.mouth) {
    case "smile":
      put(4, 7, mouthC); put(5, 7, mouthC); put(6, 7, mouthC); put(7, 7, mouthC); break;
    case "open":
      put(5, 6, mouthC); put(6, 6, mouthC); put(5, 7, "#7a2e2e"); put(6, 7, "#7a2e2e"); break;
    case "frown":
      put(4, 7, mouthC); put(7, 7, mouthC); put(5, 6, mouthC); put(6, 6, mouthC); break;
    case "flat":
    default:
      put(5, 7, mouthC); put(6, 7, mouthC); break;
  }

  // ── body / shirt (rows 8-11) ──
  for (let y = 8; y <= 11; y++) {
    for (let x = 2; x <= 9; x++) put(x, y, shirt);
  }
  // shoulders rounding
  put(2, 8, "transparent"); put(9, 8, "transparent");
  // collar / accent stripe
  put(5, 8, shade(shirt, 22)); put(6, 8, shade(shirt, 22));

  // neck
  put(5, 8, accessory === 1 ? shirt : shade(skin, -10));
  put(6, 8, shade(skin, -10));

  // ── accessories ──
  switch (accessory) {
    case 1: // glasses bridge
      put(5, 4, "#2b2533"); put(6, 4, "#2b2533");
      break;
    case 2: // hat band
      for (let x = 3; x <= 8; x++) put(x, 2, accent);
      put(2, 2, accent); put(9, 2, accent);
      break;
    case 3: // earring dot
      put(9, 5, accent);
      break;
    case 4: // freckles
      put(3, 5, shade(skin, -22)); put(8, 5, shade(skin, -22));
      break;
    default:
      break;
  }

  return cells;
}

// lighten/darken a hex color by an amount (-100..100-ish on each channel)
function shade(hex: string, amt: number): string {
  const m = hex.replace("#", "");
  const n = m.length === 3 ? m.split("").map(c => c + c).join("") : m;
  const r = clamp(parseInt(n.slice(0, 2), 16) + amt);
  const g = clamp(parseInt(n.slice(2, 4), 16) + amt);
  const b = clamp(parseInt(n.slice(4, 6), 16) + amt);
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}
function clamp(v: number) { return Math.max(0, Math.min(255, Math.round(v))); }

/** Parse a "pixel:N" override out of the avatar string, else null. */
export function pixelVariant(avatar?: string | null): number | null {
  if (!avatar) return null;
  const m = /^pixel:(\d+)$/.exec(avatar.trim());
  return m ? parseInt(m[1], 10) : null;
}

/** True when the avatar string is an explicit emoji pick (not a pixel variant / empty). */
export function isEmojiAvatar(avatar?: string | null): boolean {
  if (!avatar) return false;
  const a = avatar.trim();
  return a.length > 0 && !/^pixel:\d+$/.test(a);
}

export function PixelAvatar({
  seed,
  avatar,
  mood,
  size = 32,
  variant,
  rounded = false,
  title,
}: {
  /** Stable identity seed — pass agent.id (preferred) or agent.name. */
  seed: string;
  /** The character's avatar string (may carry a "pixel:N" variant override). */
  avatar?: string | null;
  mood?: Mood;
  size?: number;
  /** Explicit variant override (takes precedence over avatar's pixel:N). */
  variant?: number | null;
  rounded?: boolean;
  title?: string;
}) {
  const v = variant ?? pixelVariant(avatar);
  const face = useMemo(() => moodFace(mood), [mood]);
  const cells = useMemo(() => {
    const f = deriveFeatures(seed || "?", v);
    return buildCells(f, face);
  }, [seed, v, face]);

  const tint = mood ? MOOD_TINT[mood] : undefined;
  const cell = size / GRID;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${GRID} ${GRID}`}
      shapeRendering="crispEdges"
      style={{ display: "block", borderRadius: rounded ? "50%" : 0 }}
      role="img"
      aria-label={title ?? "character avatar"}
    >
      {title ? <title>{title}</title> : null}
      {/* subtle mood-tinted backdrop behind head */}
      {tint && <rect x={0} y={0} width={GRID} height={GRID} fill={tint} opacity={0.1} />}
      {cells.map((c, i) =>
        c.c === "transparent" ? null : (
          <rect key={i} x={c.x} y={c.y} width={1.02} height={1.02} fill={c.c} />
        )
      )}
    </svg>
  );
}

export default PixelAvatar;
