"use client";
import type { MacroMetrics } from "@/lib/types";

function Row({ label, before, after }: { label: string; before: number; after: number }) {
  const delta = after - before;
  const sign = delta > 0 ? "+" : "";
  const color = delta === 0 ? "text-muted" : delta > 0 ? "text-green-400" : "text-red-400";
  return (
    <tr>
      <td className="py-1 text-muted">{label}</td>
      <td className="py-1 text-right">{Number.isInteger(before) ? before : before.toFixed(2)}</td>
      <td className="py-1 text-right">{Number.isInteger(after) ? after : after.toFixed(2)}</td>
      <td className={`py-1 text-right ${color}`}>{sign}{Number.isInteger(delta) ? delta : delta.toFixed(2)}</td>
    </tr>
  );
}

export function MetricsPanel({
  initial,
  final,
}: {
  initial: MacroMetrics;
  final: MacroMetrics;
}) {
  return (
    <div className="panel p-4 text-sm">
      <div className="text-xs text-muted mb-2">Macro metrics — Day 0 vs final day</div>
      <table className="w-full text-xs">
        <thead className="text-muted">
          <tr>
            <th className="text-left">Metric</th>
            <th className="text-right">Day 0</th>
            <th className="text-right">Final</th>
            <th className="text-right">Δ</th>
          </tr>
        </thead>
        <tbody>
          <Row label="Friendships" before={initial.friendship_count} after={final.friendship_count} />
          <Row label="Rivalries" before={initial.rivalry_count} after={final.rivalry_count} />
          <Row label="Conflicts" before={initial.conflict_count} after={final.conflict_count} />
          <Row label="Romances" before={initial.romance_count} after={final.romance_count} />
          <Row label="Alliances" before={initial.alliance_count} after={final.alliance_count} />
          <Row label="Avg rel strength" before={initial.average_relationship_strength} after={final.average_relationship_strength} />
          <Row label="Avg trust" before={initial.average_trust_score} after={final.average_trust_score} />
          <Row label="Social fragmentation" before={initial.social_fragmentation} after={final.social_fragmentation} />
          <Row label="Volatility (final day)" before={initial.relationship_volatility} after={final.relationship_volatility} />
        </tbody>
      </table>
      <div className="mt-3 grid grid-cols-1 gap-2 text-xs">
        <div>
          <span className="text-muted">Most connected: </span>
          {final.most_connected.join(", ") || "(none)"}
        </div>
        <div>
          <span className="text-muted">Influence gainers: </span>
          <span className="text-green-400">{final.influence_gainers.join(", ") || "(none)"}</span>
        </div>
        <div>
          <span className="text-muted">Influence losers: </span>
          <span className="text-red-400">{final.influence_losers.join(", ") || "(none)"}</span>
        </div>
      </div>
    </div>
  );
}
