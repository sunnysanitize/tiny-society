"use client";

import {
  useCallback, useEffect, useMemo, useRef, useState, type PointerEvent,
} from "react";
import {
  forceSimulation, forceManyBody, forceLink, forceCenter, forceCollide,
  type SimulationNodeDatum, type SimulationLinkDatum,
} from "d3-force";
import type { Agent, RelationshipType, Mood } from "@/lib/types";

// ─── constants ────────────────────────────────────────────────────────────────

const EDGE: Record<RelationshipType, { color: string; dash: string; label: string; width: number }> = {
  friendship:       { color: "#22c55e", dash: "none",     label: "Friend",     width: 2 },
  romance:          { color: "#f472b6", dash: "10 4",     label: "Romance",    width: 2 },
  rivalry:          { color: "#ef4444", dash: "none",     label: "Rival",      width: 2.5 },
  trust:            { color: "#3b82f6", dash: "none",     label: "Trust",      width: 3 },
  influence:        { color: "#a855f7", dash: "8 3",      label: "Influence",  width: 1.5 },
  alliance:         { color: "#06b6d4", dash: "none",     label: "Alliance",   width: 3 },
  conflict:         { color: "#f97316", dash: "4 3 2 3",  label: "Conflict",   width: 2 },
  group_membership: { color: "#eab308", dash: "2 5",      label: "Group",      width: 1.5 },
};

const MOOD_COLOR: Record<Mood, string> = {
  calm:        "#6b7785",
  excited:     "#f59e0b",
  frustrated:  "#ef4444",
  heartbroken: "#ec4899",
  ambitious:   "#a855f7",
  anxious:     "#f97316",
  content:     "#22c55e",
  angry:       "#dc2626",
  hopeful:     "#06b6d4",
  lonely:      "#475569",
  confident:   "#2563eb",
};

const MOOD_SYMBOL: Record<Mood, string> = {
  calm:        "≈",
  excited:     "★",
  frustrated:  "✖",
  heartbroken: "♡",
  ambitious:   "△",
  anxious:     "?",
  content:     "✓",
  angry:       "!",
  hopeful:     "✦",
  lonely:      "○",
  confident:   "◆",
};

const GROUP_PALETTE = [
  "#818cf8", "#34d399", "#fb923c", "#f472b6", "#38bdf8",
  "#a3e635", "#fbbf24", "#c084fc", "#2dd4bf", "#f87171",
  "#60a5fa", "#e879f9", "#4ade80", "#facc15", "#f97316",
];

function buildGroupColors(agents: Agent[]): Map<string, string> {
  const groups = new Set<string>();
  for (const a of agents) for (const g of a.groups) groups.add(g);
  const map = new Map<string, string>();
  let i = 0;
  for (const g of groups) map.set(g, GROUP_PALETTE[i++ % GROUP_PALETTE.length]);
  return map;
}

const BASE_R = 22;
const GLOW_COLOR: Record<RelationshipType, string> = {
  friendship: "#22c55e80", rivalry: "#ef444480", romance: "#f472b680",
  trust: "#3b82f680", influence: "#a855f780", alliance: "#06b6d480",
  conflict: "#f9731680", group_membership: "#eab30880",
};

// ─── types ────────────────────────────────────────────────────────────────────

interface GraphNode extends SimulationNodeDatum {
  id: string;
  name: string;
  mood: Mood;
  influence: number;
  groups: string[];
  role: string;
  traits: string[];
  goals: string[];
}

interface GraphLink extends SimulationLinkDatum<GraphNode> {
  key: string;
  type: RelationshipType;
  strength: number;
}

interface Transform { x: number; y: number; k: number }
type Selection = { kind: "node"; id: string } | { kind: "edge"; key: string } | null;

// ─── helpers ──────────────────────────────────────────────────────────────────

function initials(name: string) {
  const parts = name.trim().split(/\s+|-/);
  return parts.length >= 2
    ? (parts[0][0] + parts[1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase();
}

function nodeR(influence: number) {
  return BASE_R + Math.max(0, Math.min(influence, 30)) * 0.4;
}

function edgePath(sx: number, sy: number, tx: number, ty: number, curvature = 0.2) {
  const dx = tx - sx, dy = ty - sy;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / dist, uy = dy / dist;
  const rs = nodeR(0) + 2, rt = nodeR(0) + 2;
  const x1 = sx + ux * rs, y1 = sy + uy * rs;
  const x2 = tx - ux * rt, y2 = ty - uy * rt;
  const cx = (sx + tx) / 2 - uy * dist * curvature;
  const cy = (sy + ty) / 2 + ux * dist * curvature;
  return `M ${x1},${y1} Q ${cx},${cy} ${x2},${y2}`;
}

function labelMid(sx: number, sy: number, tx: number, ty: number, curvature = 0.2) {
  const dx = tx - sx, dy = ty - sy;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / dist, uy = dy / dist;
  const cx = (sx + tx) / 2 - uy * dist * curvature;
  const cy = (sy + ty) / 2 + ux * dist * curvature;
  return { x: (sx + tx) / 2 * 0.5 + cx * 0.5, y: (sy + ty) / 2 * 0.5 + cy * 0.5 };
}

function buildGraphData(agents: Agent[]) {
  const nodes: GraphNode[] = agents.map((a, i) => ({
    id: a.id, name: a.name, mood: a.mood,
    influence: a.influence_score, groups: a.groups,
    role: a.role, traits: a.traits, goals: a.goals,
    x: undefined, y: undefined,
  }));
  const byName = new Map(agents.map((a) => [a.name, a.id]));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const links: GraphLink[] = [];
  const seen = new Set<string>();
  for (const a of agents) {
    for (const [name, rel] of Object.entries(a.relationships)) {
      const tid = byName.get(name);
      if (!tid) continue;
      const key = [a.id, tid].sort().join("|") + "|" + rel.type;
      if (seen.has(key)) continue;
      seen.add(key);
      links.push({ key, source: a.id as any, target: tid as any, type: rel.type, strength: Math.abs(rel.strength) });
    }
  }
  return { nodes, links };
}

// ─── SVG defs ─────────────────────────────────────────────────────────────────

function Defs() {
  return (
    <defs>
      <filter id="glow-sm">
        <feGaussianBlur stdDeviation="3" result="blur" />
        <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
      <filter id="glow-lg">
        <feGaussianBlur stdDeviation="7" result="blur" />
        <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
      <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(0,255,136,0.07)" strokeWidth="0.5" />
      </pattern>
      <marker id="arrow-influence" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
        <path d="M 0 0 L 6 3 L 0 6 Z" fill="#a855f7" opacity="0.8" />
      </marker>
      <marker id="arrow-rivalry" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
        <path d="M 0 0 L 6 3 L 0 6 Z" fill="#ef4444" opacity="0.8" />
      </marker>
    </defs>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export function RelationshipGraph({
  agents,
  selection,
  onSelect,
}: {
  agents: Agent[];
  selection: Selection;
  onSelect: (s: Selection) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const groupRef = useRef<SVGGElement>(null);
  const nodeRefs = useRef<Map<string, SVGGElement>>(new Map());
  const linkRefs = useRef<Map<string, SVGPathElement>>(new Map());
  const simRef = useRef<ReturnType<typeof forceSimulation<GraphNode, GraphLink>> | null>(null);
  const simNodes = useRef<GraphNode[]>([]);
  const simLinks = useRef<GraphLink[]>([]);

  const [tf, setTf] = useState<Transform>({ x: 0, y: 0, k: 1 });
  const [showLabels, setShowLabels] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);
  const [, tick] = useState(0); // triggers re-render after simulation settles

  const isPanning = useRef(false);
  const panOrigin = useRef({ x: 0, y: 0 });
  const draggingNode = useRef<string | null>(null);

  const { nodes: graphNodes, links: graphLinks } = useMemo(
    () => buildGraphData(agents),
    [agents]
  );

  const groupColors = useMemo(() => buildGroupColors(agents), [agents]);

  // ── simulation ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const W = svgRef.current?.clientWidth ?? 700;
    const H = svgRef.current?.clientHeight ?? 500;

    // Preserve old positions if IDs match
    const oldPos = new Map(simNodes.current.map((n) => [n.id, { x: n.x, y: n.y }]));
    const count = graphNodes.length;
    // Spread initial positions evenly across a larger radius so nodes don't start stacked
    const initR = Math.max(Math.min(W, H) * 0.38, count * 14);
    const angle = (i: number) => (i / Math.max(1, count)) * 2 * Math.PI;

    const nodes: GraphNode[] = graphNodes.map((n, i) => ({
      ...n,
      x: oldPos.get(n.id)?.x ?? W / 2 + initR * Math.cos(angle(i)),
      y: oldPos.get(n.id)?.y ?? H / 2 + initR * Math.sin(angle(i)),
    }));
    const links: GraphLink[] = graphLinks.map((l) => ({ ...l }));

    simNodes.current = nodes;
    simLinks.current = links;

    // collision radius = node visual radius + nameplate + influence bar + buffer
    const collisionR = (d: GraphNode) => nodeR(d.influence) + 55;

    const sim = forceSimulation<GraphNode, GraphLink>(nodes)
      .force("charge", forceManyBody<GraphNode>().strength(-600).distanceMin(30).distanceMax(600))
      .force("link", forceLink<GraphNode, GraphLink>(links).id((d) => d.id).distance(180).strength(0.25))
      .force("center", forceCenter<GraphNode>(W / 2, H / 2).strength(0.02))
      .force("collide", forceCollide<GraphNode>(collisionR).strength(0.85).iterations(3))
      .alphaDecay(0.012)
      .on("tick", () => {
        simNodes.current.forEach((n) => {
          const el = nodeRefs.current.get(n.id);
          if (el) el.setAttribute("transform", `translate(${n.x ?? 0},${n.y ?? 0})`);
        });
        simLinks.current.forEach((l) => {
          const el = linkRefs.current.get(l.key);
          if (!el) return;
          const src = l.source as GraphNode;
          const tgt = l.target as GraphNode;
          if (src.x != null && tgt.x != null) {
            el.setAttribute("d", edgePath(src.x, src.y!, tgt.x, tgt.y!));
          }
        });
      })
      .on("end", () => tick((t) => t + 1));

    simRef.current = sim;
    return () => { sim.stop(); };
  }, [graphNodes.length, agents]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── derived sets for dimming ─────────────────────────────────────────────────
  const { connectedNodes, connectedEdges } = useMemo(() => {
    if (!selection) return { connectedNodes: null, connectedEdges: null };
    const cn = new Set<string>();
    const ce = new Set<string>();
    if (selection.kind === "node") {
      cn.add(selection.id);
      graphLinks.forEach((l) => {
        const sid = typeof l.source === "object" ? (l.source as GraphNode).id : String(l.source);
        const tid = typeof l.target === "object" ? (l.target as GraphNode).id : String(l.target);
        if (sid === selection.id || tid === selection.id) {
          ce.add(l.key);
          cn.add(sid);
          cn.add(tid);
        }
      });
    } else if (selection.kind === "edge") {
      ce.add(selection.key);
      const link = graphLinks.find((l) => l.key === selection.key);
      if (link) {
        const sid = typeof link.source === "object" ? (link.source as GraphNode).id : link.source as string;
        const tid = typeof link.target === "object" ? (link.target as GraphNode).id : link.target as string;
        cn.add(sid); cn.add(tid);
      }
    }
    return { connectedNodes: cn, connectedEdges: ce };
  }, [selection, graphLinks]);

  function isNodeDimmed(id: string) {
    return connectedNodes !== null && !connectedNodes.has(id);
  }
  function isEdgeDimmed(key: string) {
    return connectedEdges !== null && !connectedEdges.has(key);
  }

  // ── zoom / pan ───────────────────────────────────────────────────────────────
  function onWheel(e: React.WheelEvent) {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    const newK = Math.max(0.15, Math.min(6, tf.k * factor));
    const rect = svgRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    setTf((t) => ({
      x: mx - (mx - t.x) * (newK / t.k),
      y: my - (my - t.y) * (newK / t.k),
      k: newK,
    }));
  }

  function onBgDown(e: PointerEvent<SVGRectElement>) {
    if (draggingNode.current) return;
    isPanning.current = true;
    panOrigin.current = { x: e.clientX - tf.x, y: e.clientY - tf.y };
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function onBgMove(e: PointerEvent<SVGRectElement>) {
    if (!isPanning.current) return;
    setTf((t) => ({ ...t, x: e.clientX - panOrigin.current.x, y: e.clientY - panOrigin.current.y }));
  }

  function onBgUp(e: PointerEvent<SVGRectElement>) {
    isPanning.current = false;
  }

  // ── node drag ────────────────────────────────────────────────────────────────
  function onNodeDown(e: PointerEvent<SVGGElement>, id: string) {
    e.stopPropagation();
    draggingNode.current = id;
    const simNode = simNodes.current.find((n) => n.id === id);
    if (simNode) { simNode.fx = simNode.x; simNode.fy = simNode.y; }
    simRef.current?.alphaTarget(0.3).restart();
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function onNodeMove(e: PointerEvent<SVGGElement>, id: string) {
    if (draggingNode.current !== id) return;
    const rect = svgRef.current!.getBoundingClientRect();
    const gx = (e.clientX - rect.left - tf.x) / tf.k;
    const gy = (e.clientY - rect.top - tf.y) / tf.k;
    const simNode = simNodes.current.find((n) => n.id === id);
    if (simNode) { simNode.fx = gx; simNode.fy = gy; }
  }

  function onNodeUp(e: PointerEvent<SVGGElement>, id: string) {
    if (draggingNode.current !== id) return;
    draggingNode.current = null;
    const simNode = simNodes.current.find((n) => n.id === id);
    if (simNode) { simNode.fx = null; simNode.fy = null; }
    simRef.current?.alphaTarget(0);
  }

  // ── render ───────────────────────────────────────────────────────────────────
  const selNodeId = selection?.kind === "node" ? selection.id : null;
  const selEdgeKey = selection?.kind === "edge" ? selection.key : null;

  return (
    <div className="relative flex flex-col" style={{ height: "100%", background: "#03030a", overflow: "hidden" }}>
      {/* top controls */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10, padding: "7px 14px",
        borderBottom: "1px solid rgba(0,255,136,0.1)", background: "rgba(5,5,15,0.95)",
        zIndex: 10, flexShrink: 0,
      }}>
        <span className="font-pixel" style={{ fontSize: 7, color: "rgba(0,255,136,0.5)", letterSpacing: "0.08em" }}>
          {agents.length} AGENTS · {graphLinks.length} LINKS
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={() => setShowLabels((v) => !v)}
          className="font-pixel"
          style={{
            fontSize: 6, padding: "4px 9px", cursor: "pointer", letterSpacing: "0.08em",
            background: showLabels ? "rgba(0,212,255,0.1)" : "transparent",
            color: showLabels ? "var(--cyan)" : "rgba(0,255,136,0.4)",
            border: `1px solid ${showLabels ? "var(--cyan)" : "rgba(0,255,136,0.15)"}`,
            textTransform: "uppercase",
          }}
        >
          LABELS
        </button>
        <button
          onClick={() => simRef.current?.alpha(0.5).restart()}
          className="font-pixel"
          style={{
            fontSize: 6, padding: "4px 9px", cursor: "pointer", letterSpacing: "0.08em",
            background: "transparent", color: "rgba(0,255,136,0.4)",
            border: "1px solid rgba(0,255,136,0.15)", textTransform: "uppercase",
          }}
        >
          LAYOUT
        </button>
        <button
          onClick={() => setTf({ x: 0, y: 0, k: 1 })}
          className="font-pixel"
          style={{
            fontSize: 6, padding: "4px 9px", cursor: "pointer", letterSpacing: "0.08em",
            background: "transparent", color: "rgba(0,255,136,0.4)",
            border: "1px solid rgba(0,255,136,0.15)", textTransform: "uppercase",
          }}
        >
          RESET
        </button>
      </div>

      {/* SVG canvas */}
      <svg
        ref={svgRef}
        style={{ flex: 1, cursor: "grab", userSelect: "none" }}
        onWheel={onWheel}
      >
        <Defs />
        <rect width="100%" height="100%" fill="url(#grid)" />

        <g
          ref={groupRef}
          transform={`translate(${tf.x},${tf.y}) scale(${tf.k})`}
        >
          {/* invisible bg for pan */}
          <rect
            x={-10000} y={-10000} width={20000} height={20000}
            fill="transparent"
            style={{ cursor: isPanning.current ? "grabbing" : "grab" }}
            onPointerDown={onBgDown}
            onPointerMove={onBgMove}
            onPointerUp={onBgUp}
            onClick={() => onSelect(null)}
          />

          {/* edges */}
          {graphLinks.map((l) => {
            const cfg = EDGE[l.type] || EDGE.trust;
            const dimmed = isEdgeDimmed(l.key);
            const highlighted = selEdgeKey === l.key || hoveredEdge === l.key;
            const isConnected = connectedEdges?.has(l.key);
            return (
              <g key={l.key}>
                {/* wider invisible hit area */}
                <path
                  ref={(el) => { if (el) linkRefs.current.set(l.key, el as any); }}
                  d=""
                  fill="none"
                  stroke="transparent"
                  strokeWidth={16}
                  style={{ cursor: "pointer" }}
                  onClick={(e) => { e.stopPropagation(); onSelect({ kind: "edge", key: l.key }); }}
                  onMouseEnter={() => setHoveredEdge(l.key)}
                  onMouseLeave={() => setHoveredEdge(null)}
                />
                {/* visible edge (re-uses same path d via ref below) */}
                <GraphEdge
                  l={l}
                  cfg={cfg}
                  dimmed={dimmed}
                  highlighted={highlighted}
                  isConnected={!!isConnected}
                  showLabels={showLabels}
                  simNodes={simNodes}
                />
              </g>
            );
          })}

          {/* nodes */}
          {graphNodes.map((n) => {
            const dimmed = isNodeDimmed(n.id);
            const selected = selNodeId === n.id;
            const hovered = hoveredNode === n.id;
            const moodColor = MOOD_COLOR[n.mood] || "#6b7785";
            const groupColor = n.groups.length ? (groupColors.get(n.groups[0]) ?? "#6b7785") : "#6b7785";
            const r = nodeR(n.influence);
            const relCount = graphLinks.filter(l => {
              const sid = typeof l.source === "object" ? (l.source as GraphNode).id : String(l.source);
              const tid = typeof l.target === "object" ? (l.target as GraphNode).id : String(l.target);
              return sid === n.id || tid === n.id;
            }).length;
            const infPct = Math.max(0, Math.min(1, n.influence / 25));
            const barW = Math.max(r * 1.8, 48);
            const nameplateW = Math.max(r * 2 + 10, n.name.length * 6.2 + 16);
            return (
              <g
                key={n.id}
                ref={(el) => {
                  if (el) nodeRefs.current.set(n.id, el);
                  else nodeRefs.current.delete(n.id);
                }}
                transform="translate(0,0)"
                style={{
                  opacity: dimmed ? 0.12 : 1,
                  cursor: "pointer",
                  transition: "opacity 0.2s",
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(selected ? null : { kind: "node", id: n.id });
                }}
                onPointerDown={(e) => onNodeDown(e, n.id)}
                onPointerMove={(e) => onNodeMove(e, n.id)}
                onPointerUp={(e) => onNodeUp(e, n.id)}
                onMouseEnter={() => setHoveredNode(n.id)}
                onMouseLeave={() => setHoveredNode(null)}
              >
                {/* rotating dashed selection ring */}
                {selected && (
                  <circle r={r + 13} fill="none" stroke="#60a5fa" strokeWidth={1.5}
                    strokeDasharray="7 4" opacity={0.75}>
                    <animateTransform attributeName="transform" type="rotate"
                      from="0" to="360" dur="10s" repeatCount="indefinite" />
                  </circle>
                )}

                {/* hover / selection glow */}
                {(selected || hovered) && (
                  <circle r={r + 8} fill="none"
                    stroke={selected ? "#60a5fa" : groupColor}
                    strokeWidth={selected ? 3 : 2}
                    opacity={0.65}
                    style={{ filter: `blur(${selected ? 9 : 5}px)` }}
                  />
                )}

                {/* group color ring (outer) */}
                <circle r={r + 5} fill="none" stroke={groupColor}
                  strokeWidth={2.5} opacity={selected ? 1 : 0.55} />

                {/* mood ring (inner) */}
                <circle r={r + 1} fill="none" stroke={moodColor}
                  strokeWidth={selected ? 2 : 1} opacity={selected ? 0.8 : 0.4} />

                {/* node fill */}
                <circle r={r} fill={selected ? "#060f18" : "#030309"}
                  stroke={selected ? "#00ff88" : groupColor}
                  strokeWidth={selected ? 2 : 1.5} />

                {/* group color tint */}
                <circle r={r} fill={groupColor} opacity={0.07} />

                {/* inner specular highlight */}
                <circle r={r * 0.55} cx={-r * 0.22} cy={-r * 0.22} fill="white" opacity={0.05} />

                {/* initials */}
                <text
                  y={-1}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={r * 0.58}
                  fontWeight="700"
                  fontFamily="ui-monospace, 'Courier New', monospace"
                  fill={selected ? "#93c5fd" : "rgba(230,232,235,0.9)"}
                  style={{ pointerEvents: "none", letterSpacing: "0.06em" }}
                >
                  {initials(n.name)}
                </text>

                {/* mood badge — top right */}
                <g transform={`translate(${r * 0.72}, ${-r * 0.72})`} style={{ pointerEvents: "none" }}>
                  <circle r={9} fill={moodColor} opacity={0.92} />
                  <circle r={9} fill="none" stroke="#000" strokeWidth={1} opacity={0.4} />
                  <text textAnchor="middle" dominantBaseline="central"
                    fontSize={8} fill="white" fontWeight="700"
                    style={{ pointerEvents: "none" }}>
                    {MOOD_SYMBOL[n.mood] ?? "?"}
                  </text>
                </g>

                {/* relationship count badge — bottom right */}
                {relCount > 0 && (
                  <g transform={`translate(${r * 0.72}, ${r * 0.72})`} style={{ pointerEvents: "none" }}>
                    <circle r={8} fill="#0b0f17" stroke={groupColor} strokeWidth={1.5} />
                    <text textAnchor="middle" dominantBaseline="central"
                      fontSize={8} fill={groupColor} fontWeight="700"
                      style={{ pointerEvents: "none" }}>
                      {relCount}
                    </text>
                  </g>
                )}

                {/* nameplate */}
                <g transform={`translate(0, ${r + 10})`} style={{ pointerEvents: "none" }}>
                  <rect x={-nameplateW / 2} y={-9} width={nameplateW} height={17} rx={3}
                    fill="#0b0f17"
                    stroke={selected ? "#2563eb" : groupColor}
                    strokeWidth={selected ? 1.5 : 0.8}
                    opacity={0.96} />
                  <text textAnchor="middle" dominantBaseline="central"
                    fontSize={10} fontWeight="600"
                    fontFamily="ui-sans-serif, system-ui, sans-serif"
                    fill={selected ? "#e2e8f0" : "#94a3b8"}
                    style={{ pointerEvents: "none" }}>
                    {n.name}
                  </text>
                </g>

                {/* role label */}
                <text y={r + 27} textAnchor="middle" dominantBaseline="central"
                  fontSize={8.5} fontFamily="ui-sans-serif, system-ui, sans-serif"
                  fill="#374151" style={{ pointerEvents: "none" }}>
                  {n.role.length > 20 ? n.role.slice(0, 19) + "…" : n.role}
                </text>

                {/* influence bar */}
                <g transform={`translate(0, ${r + 38})`} style={{ pointerEvents: "none" }}>
                  <rect x={-barW / 2} y={0} width={barW} height={3} rx={1.5} fill="#111827" />
                  <rect x={-barW / 2} y={0} width={barW * infPct} height={3} rx={1.5}
                    fill={moodColor} opacity={0.85} />
                </g>
              </g>
            );
          })}
        </g>
      </svg>

      {/* legend */}
      <div style={{
        borderTop: "1px solid rgba(0,255,136,0.1)",
        background: "rgba(3,3,10,0.97)", flexShrink: 0,
      }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 12px", padding: "5px 14px" }}>
          {(Object.entries(EDGE) as [RelationshipType, typeof EDGE[RelationshipType]][]).map(([t, cfg]) => (
            <span key={t} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <svg width={16} height={4}>
                <line x1={0} y1={2} x2={16} y2={2}
                  stroke={cfg.color} strokeWidth={cfg.width}
                  strokeDasharray={cfg.dash === "none" ? undefined : cfg.dash}
                />
              </svg>
              <span className="font-pixel" style={{ fontSize: 6, color: cfg.color, letterSpacing: "0.06em" }}>{cfg.label.toUpperCase()}</span>
            </span>
          ))}
        </div>
        {groupColors.size > 0 && (
          <div style={{
            display: "flex", flexWrap: "wrap", gap: "4px 10px",
            padding: "3px 14px 6px", borderTop: "1px solid rgba(0,255,136,0.05)",
          }}>
            <span className="font-pixel" style={{ fontSize: 6, color: "rgba(0,255,136,0.3)", marginRight: 4, alignSelf: "center", letterSpacing: "0.08em" }}>FACTIONS</span>
            {Array.from(groupColors.entries()).map(([group, color]) => (
              <span key={group} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 6, height: 6, background: color, flexShrink: 0, boxShadow: `0 0 4px ${color}` }} />
                <span className="font-pixel" style={{ fontSize: 6, color: "rgba(200,216,240,0.5)", letterSpacing: "0.04em" }}>{group}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── GraphEdge sub-component (reads live sim positions) ───────────────────────

function GraphEdge({
  l, cfg, dimmed, highlighted, isConnected, showLabels, simNodes,
}: {
  l: GraphLink;
  cfg: typeof EDGE[RelationshipType];
  dimmed: boolean;
  highlighted: boolean;
  isConnected: boolean;
  showLabels: boolean;
  simNodes: React.RefObject<GraphNode[]>;
}) {
  const src = l.source as GraphNode;
  const tgt = l.target as GraphNode;
  if (!src?.x || !tgt?.x) return null;

  const d = edgePath(src.x, src.y!, tgt.x, tgt.y!);
  const mid = labelMid(src.x, src.y!, tgt.x, tgt.y!);
  const opacity = dimmed ? 0 : highlighted ? 1 : isConnected ? 0.75 : 0.35;
  const width = highlighted ? cfg.width + 1.5 : cfg.width;

  return (
    <>
      <path
        d={d}
        fill="none"
        stroke={cfg.color}
        strokeWidth={width}
        strokeDasharray={cfg.dash === "none" ? undefined : cfg.dash}
        strokeOpacity={opacity}
        markerEnd={l.type === "influence" ? "url(#arrow-influence)" : l.type === "rivalry" ? "url(#arrow-rivalry)" : undefined}
        style={{ transition: "stroke-opacity 0.2s", pointerEvents: "none" }}
      />
      {showLabels && !dimmed && (
        <text
          x={mid.x} y={mid.y}
          textAnchor="middle" dominantBaseline="central"
          fontSize={9} fontFamily="ui-sans-serif, system-ui, sans-serif"
          fill={cfg.color} fillOpacity={0.9}
          style={{ pointerEvents: "none" }}
        >
          <tspan
            style={{
              background: "#0b0d10",
            }}
          >
            {cfg.label}
          </tspan>
        </text>
      )}
    </>
  );
}
