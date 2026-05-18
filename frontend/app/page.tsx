"use client";
import { useState } from "react";
import type { World, SimulationResult } from "@/lib/types";
import { WorldSetup } from "@/components/WorldSetup";
import { CharacterEditor } from "@/components/CharacterEditor";
import { EventAndRun } from "@/components/EventAndRun";
import { SimulationView } from "@/components/SimulationView";

export default function Page() {
  const [worldId, setWorldId] = useState<string | null>(null);
  const [world, setWorld] = useState<World | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);

  function reset() {
    setWorldId(null);
    setWorld(null);
    setResult(null);
  }

  return (
    <main className="max-w-7xl mx-auto p-6 space-y-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Tiny Society AI</h1>
          <p className="text-sm text-muted">
            MiroFish-inspired multi-agent social simulation. Agents reason via LLM; the engine applies structured updates.
          </p>
        </div>
        {worldId && (
          <button className="btn-ghost text-xs" onClick={reset}>Start over</button>
        )}
      </header>

      {!worldId && (
        <WorldSetup
          onCreated={(wid, w) => {
            setWorldId(wid);
            setWorld(w);
          }}
        />
      )}

      {worldId && world && !result && (
        <>
          <CharacterEditor worldId={worldId} world={world} onWorldChange={setWorld} />
          <EventAndRun
            worldId={worldId}
            world={world}
            onWorldChange={setWorld}
            onResult={setResult}
          />
        </>
      )}

      {result && world && worldId && (
        <SimulationView result={result} world={world} worldId={worldId} />
      )}
    </main>
  );
}
