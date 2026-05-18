"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World, Mood } from "@/lib/types";

const MOODS: Mood[] = ["calm", "excited", "frustrated", "ambitious", "anxious", "content", "hopeful", "confident", "lonely", "angry", "heartbroken"];

export function CharacterEditor({
  worldId,
  world,
  onWorldChange,
}: {
  worldId: string;
  world: World;
  onWorldChange: (w: World) => void;
}) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("student");
  const [traits, setTraits] = useState("ambitious, social");
  const [goals, setGoals] = useState("become club president");
  const [mood, setMood] = useState<Mood>("calm");
  const [groups, setGroups] = useState("Cooking Club");
  const [memory, setMemory] = useState("");
  const [busy, setBusy] = useState(false);
  const [genBusy, setGenBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function splitCsv(s: string): string[] {
    return s.split(",").map((x) => x.trim()).filter(Boolean);
  }

  async function addCharacter() {
    if (!name.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api.addCharacter(worldId, {
        name: name.trim(),
        role: role.trim() || "citizen",
        traits: splitCsv(traits),
        goals: splitCsv(goals),
        mood,
        groups: splitCsv(groups),
        starting_memories: memory.trim() ? [memory.trim()] : [],
        starting_relationships: {},
      });
      const w = await api.getWorld(worldId);
      onWorldChange(w);
      setName("");
      setMemory("");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeCharacter(id: string) {
    await api.removeCharacter(worldId, id);
    const w = await api.getWorld(worldId);
    onWorldChange(w);
  }

  async function generateFillers() {
    setGenBusy(true);
    setErr(null);
    try {
      const w = await api.generateFillers(worldId);
      onWorldChange(w);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setGenBusy(false);
    }
  }

  const needed = Math.max(0, world.target_population - world.agents.length);

  return (
    <div className="panel p-5 space-y-4">
      <div className="text-sm text-muted">
        Step 2 — Add custom characters ({world.agents.length} / {world.target_population})
      </div>

      <div className="grid grid-cols-2 gap-3">
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="Role" value={role} onChange={(e) => setRole(e.target.value)} />
        <input placeholder="Traits (comma separated)" value={traits} onChange={(e) => setTraits(e.target.value)} />
        <input placeholder="Goals (comma separated)" value={goals} onChange={(e) => setGoals(e.target.value)} />
        <select value={mood} onChange={(e) => setMood(e.target.value as Mood)}>
          {MOODS.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <input placeholder="Groups (comma separated)" value={groups} onChange={(e) => setGroups(e.target.value)} />
        <input className="col-span-2" placeholder="Optional starting memory" value={memory} onChange={(e) => setMemory(e.target.value)} />
      </div>

      <div className="flex gap-2">
        <button className="btn" onClick={addCharacter} disabled={busy || !name.trim()}>
          {busy ? "Adding..." : "Add character"}
        </button>
        <button className="btn-ghost" onClick={generateFillers} disabled={genBusy || needed === 0}>
          {genBusy ? "Generating..." : `Auto-generate ${needed} filler agent${needed === 1 ? "" : "s"}`}
        </button>
      </div>

      {err && <div className="text-red-400 text-sm">{err}</div>}

      {world.agents.length > 0 && (
        <div className="space-y-2 max-h-72 overflow-auto pr-2">
          {world.agents.map((a) => (
            <div key={a.id} className="flex items-start gap-3 border border-line rounded p-2">
              <div className="flex-1">
                <div className="text-sm">
                  <span className="font-semibold">{a.name}</span>
                  <span className="text-muted"> — {a.role}</span>
                  {a.is_custom && <span className="tag ml-2">custom</span>}
                </div>
                <div className="mt-1">
                  {a.traits.map((t) => <span key={t} className="tag">{t}</span>)}
                </div>
                <div className="text-xs text-muted mt-1">
                  groups: {a.groups.join(", ") || "(none)"} · mood: {a.mood}
                </div>
              </div>
              <button className="btn-ghost text-xs" onClick={() => removeCharacter(a.id)}>remove</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
