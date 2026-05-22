"use client";
import type { Agent } from "@/lib/types";
import { memText } from "@/lib/types";

export function CharacterPanel({ agent }: { agent: Agent | null }) {
  if (!agent) {
    return (
      <div className="panel p-4 text-sm text-muted">
        Click a node in the graph to view a character's traits, memories, and relationships.
      </div>
    );
  }
  const rels = Object.entries(agent.relationships);
  return (
    <div className="panel p-4 space-y-3 text-sm">
      <div>
        <div className="text-lg font-semibold">{agent.name}</div>
        <div className="text-muted">{agent.role}</div>
      </div>
      <div className="flex gap-4 text-xs text-muted">
        <div>mood: <span className="text-white">{agent.mood}</span></div>
        <div>influence: <span className="text-white">{agent.influence_score.toFixed(1)}</span></div>
      </div>
      <div>
        <div className="text-xs text-muted mb-1">Traits</div>
        <div>{agent.traits.map((t) => <span key={t} className="tag">{t}</span>)}</div>
      </div>
      <div>
        <div className="text-xs text-muted mb-1">Goals</div>
        <div>{agent.goals.map((g) => <span key={g} className="tag">{g}</span>) || "(none)"}</div>
      </div>
      <div>
        <div className="text-xs text-muted mb-1">Groups</div>
        <div>{agent.groups.map((g) => <span key={g} className="tag">{g}</span>)}</div>
      </div>

      <div>
        <div className="text-xs text-muted mb-1">Relationships ({rels.length})</div>
        <div className="space-y-1 max-h-40 overflow-auto pr-1">
          {rels.length === 0 && <div className="text-muted text-xs">(none yet)</div>}
          {rels.map(([name, r]) => (
            <div key={name} className="flex items-center gap-2 text-xs">
              <div className="w-24 truncate">{name}</div>
              <div className="w-20 text-muted">{r.type}</div>
              <div className="flex-1 h-1.5 bg-line rounded overflow-hidden">
                <div
                  style={{
                    width: `${Math.abs(r.strength) * 100}%`,
                    background: r.strength >= 0 ? "#22c55e" : "#ef4444",
                    height: "100%",
                  }}
                />
              </div>
              <div className="w-10 text-right">{r.strength.toFixed(2)}</div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="text-xs text-muted mb-1">Short-term memory</div>
        <ul className="text-xs space-y-1 max-h-32 overflow-auto pr-1">
          {agent.short_term_memory.length === 0 && <li className="text-muted">(empty)</li>}
          {agent.short_term_memory.map((m, i) => <li key={i} className="text-gray-300">· {memText(m)}</li>)}
        </ul>
      </div>
      <div>
        <div className="text-xs text-muted mb-1">Long-term memory</div>
        <ul className="text-xs space-y-1 max-h-40 overflow-auto pr-1">
          {agent.long_term_memory.length === 0 && <li className="text-muted">(empty)</li>}
          {agent.long_term_memory.map((m, i) => <li key={i} className="text-gray-300">· {memText(m)}</li>)}
        </ul>
      </div>
    </div>
  );
}
