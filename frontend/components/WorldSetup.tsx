"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { World } from "@/lib/types";

export function WorldSetup({
  onCreated,
}: {
  onCreated: (wid: string, world: World) => void;
}) {
  const [prompt, setPrompt] = useState(
    "A small fictional university island with 25 students, a few clubs, two rival dorms, and casual campus drama."
  );
  const [pop, setPop] = useState(25);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setLoading(true);
    setErr(null);
    try {
      const { world_id, world } = await api.createWorld(prompt, pop);
      onCreated(world_id, world);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel p-5 space-y-3">
      <div className="text-sm text-muted">Step 1 — Define your world</div>
      <textarea
        rows={4}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Describe your fictional world..."
      />
      <div className="flex items-center gap-3">
        <label className="text-sm text-muted">Target population</label>
        <input
          className="w-24"
          type="number"
          min={5}
          max={60}
          value={pop}
          onChange={(e) => setPop(parseInt(e.target.value) || 25)}
        />
        <button className="btn ml-auto" disabled={loading} onClick={submit}>
          {loading ? "Creating..." : "Create world"}
        </button>
      </div>
      {err && <div className="text-red-400 text-sm">{err}</div>}
    </div>
  );
}
