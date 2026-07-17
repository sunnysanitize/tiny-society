"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World, Mood } from "@/lib/types";
import { PixelAvatar, isEmojiAvatar, pixelVariant } from "./PixelAvatar";

const MOODS: Mood[] = ["calm","excited","frustrated","ambitious","anxious","content","hopeful","confident","lonely","angry","heartbroken"];

const MOOD_COLOR: Record<Mood, string> = {
  calm: "#6b7785", excited: "#f59e0b", frustrated: "#ef4444",
  heartbroken: "#ec4899", ambitious: "#a855f7", anxious: "#f97316",
  content: "#22c55e", angry: "#dc2626", hopeful: "#06b6d4",
  lonely: "#475569", confident: "#2563eb",
};

// Tomodachi-style pixel/emoji avatar set: faces plus a few animals/symbols.
const AVATARS = [
  "😀","😎","🥰","😈","🤓","😭","😡","🤔",
  "🐱","🐶","🦊","🐼","🐸","🦄","🐙","🦉",
  "👑","🎭","🌟","🔥","💀","🌸",
];

// Curated pools that the "Surprise" button rolls a plausible character from, so
// building a roster is one click per character instead of eight fields.
const RANDOM = {
  names: [
    "Maya","Theo","Ren","Iris","Kai","Nova","Leo","Suki","Jonas","Priya",
    "Marco","Elena","Dara","Otis","Lena","Finn","Nadia","Cyrus","Mika","Rosa",
    "Hugo","Yara","Bram","Sana","Nico","Wren","Dev","Talia",
  ],
  roles: [
    "student","teacher","club president","barista","librarian","artist","athlete",
    "journalist","coder","musician","chef","gardener","photographer","tutor",
  ],
  traits: [
    "ambitious","social","shy","curious","bold","loyal","sarcastic","kind",
    "competitive","dreamy","stubborn","playful","anxious","charismatic","analytical","reckless",
  ],
  goals: [
    "become club president","win the talent show","make a best friend","start a band",
    "top the class","find true love","expose a secret","launch a business",
    "get over a breakup","find where they belong","beat their rival","throw the best party",
  ],
  groups: [
    "Cooking Club","Dorm A","Dorm B","Drama Club","Robotics Team","Student Council",
    "Chess Club","Track Team","Art Studio","Debate Team","Music Society","Garden Club",
  ],
};

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}
// Pick n distinct items from arr (or fewer if the pool is smaller).
function sample<T>(arr: T[], n: number): T[] {
  const copy = [...arr];
  const out: T[] = [];
  for (let i = 0; i < n && copy.length; i++) {
    out.push(copy.splice(Math.floor(Math.random() * copy.length), 1)[0]);
  }
  return out;
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", letterSpacing: "0.1em", marginBottom: 5 }}>
      {children}
    </div>
  );
}

// Light one-line description shown beneath an input.
function FieldHint({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.5, marginTop: 4 }}>
      {children}
    </div>
  );
}

export function CharacterEditor({ worldId, world, onWorldChange }: {
  worldId: string; world: World; onWorldChange: (w: World) => void;
}) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [traits, setTraits] = useState("");
  const [goals, setGoals] = useState("");
  const [mood, setMood] = useState<Mood>("calm");
  const [groups, setGroups] = useState("");
  const [memory, setMemory] = useState("");
  const [avatar, setAvatar] = useState<string | null>(null);
  const [basedOn, setBasedOn] = useState("");
  const [busy, setBusy] = useState(false);
  const [genBusy, setGenBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // Optional fields (memory, look, based-on) stay hidden until asked for.
  const [showMore, setShowMore] = useState(false);

  function splitCsv(s: string): string[] {
    return s.split(",").map(x => x.trim()).filter(Boolean);
  }

  // Fill the core fields with a random plausible character. Avoids names already
  // on the roster so repeated clicks build a varied cast, not duplicates.
  function surprise() {
    const used = new Set(world.agents.map(a => a.name.toLowerCase()));
    const avail = RANDOM.names.filter(n => !used.has(n.toLowerCase()));
    setName(avail.length ? pick(avail) : `${pick(RANDOM.names)} ${Math.floor(Math.random() * 90) + 10}`);
    setRole(pick(RANDOM.roles));
    setTraits(sample(RANDOM.traits, 2 + Math.floor(Math.random() * 2)).join(", "));
    setGoals(pick(RANDOM.goals));
    setMood(pick(MOODS));
    setGroups(sample(RANDOM.groups, 1 + Math.floor(Math.random() * 2)).join(", "));
    setErr(null);
  }

  async function addCharacter() {
    if (!name.trim()) return;
    setBusy(true); setErr(null);
    try {
      await api.addCharacter(worldId, {
        name: name.trim(), role: role.trim() || "citizen",
        traits: splitCsv(traits), goals: splitCsv(goals),
        mood, groups: splitCsv(groups),
        starting_memories: memory.trim() ? [memory.trim()] : [],
        starting_relationships: {},
        ...(avatar ? { avatar } : {}),
        ...(basedOn.trim() ? { based_on: basedOn.trim() } : {}),
      });
      const w = await api.getWorld(worldId);
      onWorldChange(w);
      setName(""); setMemory(""); setAvatar(null); setBasedOn("");
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  }

  async function removeCharacter(id: string) {
    await api.removeCharacter(worldId, id);
    const w = await api.getWorld(worldId);
    onWorldChange(w);
  }

  async function generateFillers() {
    setGenBusy(true); setErr(null);
    try {
      const w = await api.generateFillers(worldId);
      onWorldChange(w);
    } catch (e: any) { setErr(e.message); }
    finally { setGenBusy(false); }
  }

  const needed = Math.max(0, world.target_population - world.agents.length);
  const rosterPct = Math.round((world.agents.length / world.target_population) * 100);

  return (
    <div className="panel" style={{ padding: "20px 24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "var(--accent)", fontSize: 12 }}>◈</span>
          <span className="font-pixel" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.1em" }}>
            CHARACTER ROSTER
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)" }}>
            {world.agents.length} / {world.target_population}
          </span>
          {/* roster fill bar */}
          <div style={{ width: 80, height: 6, background: "#ebe8f8", border: "1px solid var(--border)", overflow: "hidden" }}>
            <div style={{
              width: `${rosterPct}%`, height: "100%",
              background: "var(--accent)",
              opacity: rosterPct >= 100 ? 1 : 0.55,
              transition: "width 0.4s ease",
            }} />
          </div>
        </div>
      </div>

      <div style={{ height: 1, background: "linear-gradient(90deg, transparent, var(--border), transparent)", marginBottom: 16 }} />

      {/* Recruit form */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.1em" }}>
          ▸ RECRUIT NEW CHARACTER
        </div>
        <button
          type="button"
          onClick={surprise}
          title="Roll a random character into the form"
          style={{
            marginLeft: "auto", fontSize: 8, padding: "6px 12px", cursor: "pointer",
            background: "transparent", color: "var(--accent)",
            border: "1px solid var(--accent)", fontFamily: "var(--font-pixel)",
            textTransform: "uppercase", letterSpacing: "0.06em",
          }}
        >
          🎲 SURPRISE
        </button>
      </div>
      <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "ui-monospace, monospace", lineHeight: 1.6, marginBottom: 14 }}>
        The cast of your world. Roll a random character with Surprise, add people by hand, or auto-fill the rest up to your target population. Every character thinks and acts on their own once the simulation runs.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 10 }}>
        <div>
          <FieldLabel>NAME</FieldLabel>
          <input placeholder="character name" value={name} onChange={e => setName(e.target.value)} />
          <FieldHint>What this character is called.</FieldHint>
        </div>
        <div>
          <FieldLabel>ROLE</FieldLabel>
          <input placeholder="student / teacher..." value={role} onChange={e => setRole(e.target.value)} />
          <FieldHint>Their place in the world, like student or teacher.</FieldHint>
        </div>
        <div>
          <FieldLabel>TRAITS</FieldLabel>
          <input placeholder="ambitious, social, ..." value={traits} onChange={e => setTraits(e.target.value)} />
          <FieldHint>Comma-separated personality traits.</FieldHint>
        </div>
        <div>
          <FieldLabel>GOALS</FieldLabel>
          <input placeholder="become club president, ..." value={goals} onChange={e => setGoals(e.target.value)} />
          <FieldHint>What they are trying to achieve.</FieldHint>
        </div>
        <div>
          <FieldLabel>MOOD</FieldLabel>
          <select value={mood} onChange={e => setMood(e.target.value as Mood)}>
            {MOODS.map(m => <option key={m} value={m}>{m.toUpperCase()}</option>)}
          </select>
          <FieldHint>How they feel on day one.</FieldHint>
        </div>
        <div>
          <FieldLabel>GROUPS</FieldLabel>
          <input placeholder="Dorm A, Cooking Club, ..." value={groups} onChange={e => setGroups(e.target.value)} />
          <FieldHint>Clubs, dorms, or factions they belong to.</FieldHint>
        </div>

        <div style={{ gridColumn: "1 / -1" }}>
          <button
            type="button"
            onClick={() => setShowMore(s => !s)}
            style={{
              fontSize: 8, padding: "4px 0", cursor: "pointer",
              background: "none", border: "none", color: "var(--text-dim)",
              fontFamily: "var(--font-pixel)", letterSpacing: "0.06em",
            }}
          >
            {showMore ? "▾ FEWER OPTIONS" : "▸ MORE OPTIONS (MEMORY, LOOK, BASED-ON)"}
          </button>
        </div>

        {showMore && (
          <>
        <div style={{ gridColumn: "span 2" }}>
          <FieldLabel>STARTING MEMORY (OPTIONAL)</FieldLabel>
          <input placeholder="a memory this character starts with..." value={memory} onChange={e => setMemory(e.target.value)} />
          <FieldHint>An experience they carry in from before the story starts.</FieldHint>
        </div>
        <div style={{ gridColumn: "span 2" }}>
          <FieldLabel>PIXEL LOOK (OPTIONAL, AUTO BY DEFAULT)</FieldLabel>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 8 }}>
            {Array.from({ length: 8 }).map((_, i) => {
              const tag = `pixel:${i}`;
              const sel = pixelVariant(avatar) === i;
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => setAvatar(sel ? null : tag)}
                  title={sel ? "click to use auto look" : "use this look"}
                  style={{
                    width: 34, height: 34, cursor: "pointer", padding: 2,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    background: sel ? "rgba(121,80,242,0.12)" : "var(--surface-2)",
                    border: `1px solid ${sel ? "var(--accent)" : "var(--border)"}`,
                    boxShadow: sel ? "0 0 6px rgba(121,80,242,0.4)" : "none",
                  }}
                >
                  <PixelAvatar seed={name.trim() || "preview"} variant={i} mood={mood} size={28} />
                </button>
              );
            })}
          </div>
          <FieldLabel>OR PICK AN EMOJI</FieldLabel>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {AVATARS.map(emo => {
              const sel = avatar === emo;
              return (
                <button
                  key={emo}
                  type="button"
                  onClick={() => setAvatar(sel ? null : emo)}
                  title={sel ? "click to clear" : "pick avatar"}
                  style={{
                    width: 28, height: 28, fontSize: 15, lineHeight: "26px",
                    cursor: "pointer", textAlign: "center", padding: 0,
                    background: sel ? "rgba(121,80,242,0.12)" : "var(--surface-2)",
                    border: `1px solid ${sel ? "var(--accent)" : "var(--border)"}`,
                    boxShadow: sel ? "0 0 6px rgba(121,80,242,0.4)" : "none",
                  }}
                >{emo}</button>
              );
            })}
          </div>
        </div>
        <div style={{ gridColumn: "span 2" }}>
          <FieldLabel>BASED ON A REAL PERSON (OPTIONAL)</FieldLabel>
          <input placeholder="e.g. my friend Maya, a coworker..." value={basedOn} onChange={e => setBasedOn(e.target.value)} />
          <FieldHint>Loosely model this character on someone you know.</FieldHint>
        </div>
          </>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button className="btn" onClick={addCharacter} disabled={busy || !name.trim()}>
          {busy ? "ADDING..." : "▶ ADD CHARACTER"}
        </button>
        <button className="btn-ghost" onClick={generateFillers} disabled={genBusy || needed === 0}>
          {genBusy ? "GENERATING..." : `AUTO-FILL ${needed} CHARACTER${needed === 1 ? "" : "S"}`}
        </button>
      </div>

      {err && (
        <div style={{ fontSize: 10, color: "var(--red)", fontFamily: "ui-monospace", marginBottom: 8, letterSpacing: "0.04em" }}>
          ✖ {err}
        </div>
      )}

      {/* Roster list */}
      {world.agents.length > 0 && (
        <>
          <div style={{ height: 1, background: "var(--border)", marginBottom: 10 }} />
          <div className="font-pixel" style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 8, letterSpacing: "0.08em" }}>
            ▸ CURRENT ROSTER
          </div>
          <div style={{ maxHeight: 260, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
            {world.agents.map((a) => {
              const moodColor = MOOD_COLOR[a.mood] || "#6b7785";
              return (
                <div key={a.id} style={{
                  display: "flex", alignItems: "flex-start", gap: 10,
                  padding: "8px 10px",
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  transition: "border-color 0.1s",
                }}>
                  {/* avatar: pixel sprite by default; explicit emoji pick overrides */}
                  {isEmojiAvatar(a.avatar) ? (
                    <span style={{ fontSize: 16, lineHeight: "20px", flexShrink: 0, marginTop: 2 }}>{a.avatar}</span>
                  ) : (
                    <div style={{ flexShrink: 0, marginTop: 2 }}>
                      <PixelAvatar seed={a.id} avatar={a.avatar} mood={a.mood} size={22} title={a.name} />
                    </div>
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span className="font-pixel" style={{ fontSize: 8, color: "var(--text)" }}>{a.name}</span>
                      <span style={{ fontSize: 9, color: "var(--text-dim)" }}>· {a.role}</span>
                      {a.is_custom && (
                        <span style={{
                          fontSize: 7, padding: "1px 5px",
                          border: "1px solid var(--border)", color: "var(--text-dim)",
                          background: "var(--surface)", fontFamily: "var(--font-pixel)",
                        }}>CUSTOM</span>
                      )}
                    </div>
                    <div>{a.traits.map(t => <span key={t} className="tag">{t}</span>)}</div>
                    <div style={{ fontSize: 8, color: "var(--text-dim)", marginTop: 2, fontFamily: "ui-monospace" }}>
                      {a.groups.join(" · ") || "no groups"} &nbsp;|&nbsp; mood:{" "}
                      <span style={{
                        display: "inline-block", width: 6, height: 6, borderRadius: "50%",
                        background: moodColor, marginRight: 4, verticalAlign: "middle",
                      }} />
                      <span style={{ color: "var(--text-dim)" }}>{a.mood}</span>
                      {a.based_on && <> &nbsp;|&nbsp; based on <span style={{ color: "var(--text-dim)" }}>{a.based_on}</span></>}
                    </div>
                  </div>
                  <button
                    onClick={() => removeCharacter(a.id)}
                    style={{
                      fontSize: 8, padding: "4px 8px", cursor: "pointer",
                      background: "transparent", color: "var(--text-dim)",
                      border: "1px solid var(--border)", fontFamily: "var(--font-pixel)",
                      textTransform: "uppercase", letterSpacing: "0.05em",
                      transition: "border-color 0.1s, color 0.1s", flexShrink: 0,
                    }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "var(--red)"; (e.currentTarget as HTMLElement).style.color = "var(--red)"; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border)"; (e.currentTarget as HTMLElement).style.color = "var(--text-dim)"; }}
                  >
                    REMOVE
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
