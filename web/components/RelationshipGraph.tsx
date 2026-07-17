"use client";

import {
  useCallback, useEffect, useMemo, useRef, useState, type PointerEvent,
} from "react";
import {
  forceSimulation, forceManyBody, forceLink, forceCenter, forceCollide,
  type SimulationNodeDatum, type SimulationLinkDatum,
} from "d3-force";
import type { Agent, RelationshipType, Mood } from "@/lib/types";
import { PixelAvatar, isEmojiAvatar } from "./PixelAvatar";

// ─── constants ────────────────────────────────────────────────────────────────

const EDGE: Record<RelationshipType, { color: string; dash: string; label: string; width: number; flowDur?: number; pulse?: boolean }> = {
  friendship:       { color: "#22c55e", dash: "none",  label: "Friend",    width: 2.5, flowDur: 2.8 },
  romance:          { color: "#f472b6", dash: "none",  label: "Romance",   width: 2.5, flowDur: 3.5 },
  rivalry:          { color: "#ef4444", dash: "none",  label: "Rival",     width: 2.5, pulse: true  },
  trust:            { color: "#3b82f6", dash: "none",  label: "Trust",     width: 2.5, flowDur: 4   },
  influence:        { color: "#a855f7", dash: "8 3",   label: "Influence", width: 1.5, flowDur: 2   },
  alliance:         { color: "#06b6d4", dash: "none",  label: "Alliance",  width: 3,   flowDur: 2   },
  conflict:         { color: "#f97316", dash: "none",  label: "Conflict",  width: 2.5, pulse: true  },
  group_membership: { color: "#eab308", dash: "2 5",   label: "Group",     width: 1.5               },
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

// Persist node positions across mounts (e.g. switching between the Story and Network
// tabs) so the layout RESTORES instead of re-spreading and fully re-simulating each time.
const POS_CACHE = new Map<string, { x: number; y: number }>();

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
  avatar?: string | null;
}

interface GraphLink extends SimulationLinkDatum<GraphNode> {
  key: string;
  type: RelationshipType;
  strength: number;
}

interface Transform { x: number; y: number; k: number }
type Selection = { kind: "node"; id: string } | { kind: "edge"; key: string } | null;

// ─── helpers ──────────────────────────────────────────────────────────────────

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
    avatar: a.avatar ?? null,
    x: undefined, y: undefined,
  }));
  const byName = new Map(agents.map((a) => [a.name, a.id]));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  // Relationships are directed and may be ASYMMETRIC (A sees B as rivalry while B sees A
  // as trust). Collapse to one edge per unordered pair, keeping the direction with the
  // strongest |affinity| as the representative — instead of drawing two contradictory
  // edges. `strength` is the SIGNED affinity (drives width/opacity downstream).
  const byPair = new Map<string, GraphLink>();
  for (const a of agents) {
    for (const [name, rel] of Object.entries(a.relationships)) {
      const tid = byName.get(name);
      if (!tid) continue;
      const key = [a.id, tid].sort().join("|");
      const existing = byPair.get(key);
      if (!existing || Math.abs(rel.strength) > Math.abs(existing.strength)) {
        byPair.set(key, { key, source: a.id as any, target: tid as any, type: rel.type, strength: rel.strength });
      }
    }
  }
  const links: GraphLink[] = Array.from(byPair.values());
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
        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(100,80,200,0.08)" strokeWidth="0.5" />
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
  // Visible (colored) edge paths. Separate from linkRefs (the wide invisible hit area) so
  // BOTH get their `d` rewritten every tick — otherwise the visible line lags behind the
  // nodes while they move (drag / page-switch resettle) and only snaps back on re-render.
  const edgeRefs = useRef<Map<string, SVGPathElement>>(new Map());
  const connLineRefs = useRef<Map<string, SVGLineElement>>(new Map());
  const connGlowRefs = useRef<Map<string, SVGLineElement>>(new Map());
  const connBadgeRefs = useRef<Map<string, SVGGElement>>(new Map());
  const selNodeIdRef = useRef<string | null>(null);
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

    // Preserve old positions if IDs match — first from this instance, then from the
    // cross-mount cache (so a tab switch restores the layout rather than reshuffling).
    const oldPos = new Map(simNodes.current.map((n) => [n.id, { x: n.x, y: n.y }]));
    const count = graphNodes.length;
    const posFor = (id: string) => oldPos.get(id) ?? POS_CACHE.get(id);
    // If every node already has a known position, we're restoring a layout — start the
    // sim at low alpha so it barely moves instead of springing apart and re-settling.
    const restored = count > 0 && graphNodes.every((n) => posFor(n.id) != null);
    // Spread initial positions evenly across a larger radius so nodes don't start stacked
    const initR = Math.max(Math.min(W, H) * 0.38, count * 14);
    const angle = (i: number) => (i / Math.max(1, count)) * 2 * Math.PI;

    const nodes: GraphNode[] = graphNodes.map((n, i) => ({
      ...n,
      x: posFor(n.id)?.x ?? W / 2 + initR * Math.cos(angle(i)),
      y: posFor(n.id)?.y ?? H / 2 + initR * Math.sin(angle(i)),
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
          const src = l.source as GraphNode;
          const tgt = l.target as GraphNode;
          if (src.x == null || tgt.x == null) return;
          const d = edgePath(src.x, src.y!, tgt.x, tgt.y!);
          // Keep the visible line AND its invisible hit area glued to the moving nodes.
          linkRefs.current.get(l.key)?.setAttribute("d", d);
          edgeRefs.current.get(l.key)?.setAttribute("d", d);
        });
        // update selected-node connection lines
        const sid = selNodeIdRef.current;
        if (sid) {
          const sn = simNodes.current.find(n => n.id === sid);
          if (sn?.x != null) {
            connLineRefs.current.forEach((el, key) => {
              const tid = key.split("~~")[1];
              const tn = simNodes.current.find(n => n.id === tid);
              if (!tn?.x) return;
              const x1 = String(sn.x!), y1 = String(sn.y!), x2 = String(tn.x!), y2 = String(tn.y!);
              el.setAttribute("x1", x1); el.setAttribute("y1", y1);
              el.setAttribute("x2", x2); el.setAttribute("y2", y2);
              connGlowRefs.current.get(key)?.setAttribute("x1", x1);
              connGlowRefs.current.get(key)?.setAttribute("y1", y1);
              connGlowRefs.current.get(key)?.setAttribute("x2", x2);
              connGlowRefs.current.get(key)?.setAttribute("y2", y2);
              const mx = (sn.x! + tn.x!) / 2, my = (sn.y! + tn.y!) / 2;
              connBadgeRefs.current.get(key)?.setAttribute("transform", `translate(${mx},${my})`);
            });
          }
        }
      })
      .on("end", () => { tick((t) => t + 1); fitToView(); });

    simRef.current = sim;
    // Restoring a cached layout: FREEZE the physics entirely. Running it (even at low alpha)
    // lets forceCenter/collide shove the cached nodes around when the two displays (compact
    // Story tab vs larger Network tab) differ in size — that's the "jerk on page switch".
    // fitToView reframes via transform instead. A stopped sim never fires "end", so trigger
    // one re-render here so the edges mount and draw from the restored positions. Dragging
    // (onNodeDown → alphaTarget.restart) or the LAYOUT button re-activate the sim on demand.
    if (restored) {
      sim.stop();
      tick((t) => t + 1);
    }
    // Frame once after first paint, in case the container wasn't sized yet at mount.
    const raf = requestAnimationFrame(() => fitToView());

    return () => {
      cancelAnimationFrame(raf);
      // Stash final positions so the next mount (tab switch / day step) restores them.
      simNodes.current.forEach((n) => {
        if (n.x != null && n.y != null) POS_CACHE.set(n.id, { x: n.x, y: n.y });
      });
      sim.stop();
    };
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

  // ── fit to view ──────────────────────────────────────────────────────────────
  function fitToView() {
    const nodes = simNodes.current.filter(n => n.x != null && n.y != null);
    if (!nodes.length || !svgRef.current) return;
    const W = svgRef.current.clientWidth;
    const H = svgRef.current.clientHeight;
    // Small margin so the graph fills the section (was 90, which left a wide blank band).
    // Just enough that node rings/labels aren't flush against the frame.
    const pad = 34;
    const xs = nodes.map(n => n.x!);
    const ys = nodes.map(n => n.y!);
    const gx1 = Math.min(...xs) - pad, gx2 = Math.max(...xs) + pad;
    const gy1 = Math.min(...ys) - pad, gy2 = Math.max(...ys) + pad;
    // Floor must be low enough to CONTAIN the whole layout — with many characters in the
    // small (Story-tab) square the fit needs k well below 0.3, and a higher floor renders
    // the graph larger than the frame so it clips (nodes sliced off the edges, worse after
    // a drag reheats and spreads the layout). Only the floor bites when content is large,
    // which is exactly when we must zoom OUT. Keep a tiny floor to avoid degenerate zoom.
    const k = Math.max(0.05, Math.min(2, Math.min(W / (gx2 - gx1), H / (gy2 - gy1))));
    setTf({
      x: (W - (gx2 - gx1) * k) / 2 - gx1 * k,
      y: (H - (gy2 - gy1) * k) / 2 - gy1 * k,
      k,
    });
  }

  // ── re-fit when the container resizes (stack/unstack, window resize, rotate) ──
  useEffect(() => {
    const el = svgRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    let raf = 0;
    let lastW = el.clientWidth;
    let lastH = el.clientHeight;
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (w === lastW && h === lastH) return;
      lastW = w; lastH = h;
      // Debounce to a frame; nudge the sim's center force toward the new size
      // and re-fit so the graph fills the resized container.
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const sim = simRef.current;
        if (sim) {
          sim.force("center", forceCenter<GraphNode>(w / 2, h / 2).strength(0.02));
        }
        fitToView();
      });
    });
    ro.observe(el);
    return () => { ro.disconnect(); cancelAnimationFrame(raf); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── zoom / pan ───────────────────────────────────────────────────────────────
  // Must use a native listener with { passive: false } — React registers wheel
  // listeners as passive, which silently ignores preventDefault().
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    function handleWheel(e: WheelEvent) {
      e.preventDefault();
      const raw = e.deltaMode === 1 ? e.deltaY * 20 : e.deltaY;
      const capped = Math.sign(raw) * Math.min(Math.abs(raw), 40);
      setTf((t) => {
        const newK = Math.max(0.3, Math.min(2.5, t.k * (1 - capped * 0.004)));
        const rect = el!.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        return {
          x: mx - (mx - t.x) * (newK / t.k),
          y: my - (my - t.y) * (newK / t.k),
          k: newK,
        };
      });
    }
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function onBgDown(e: PointerEvent<SVGRectElement>) {
    if (draggingNode.current) return;
    isPanning.current = true;
    panOrigin.current = { x: e.clientX - tf.x, y: e.clientY - tf.y };
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  // Clamp a candidate pan so the content's bounding box can never be dragged out of the
  // viewport (the previous ±1.5·W clamp let you push the whole graph off-frame, so it
  // "cut off" and never re-centered). If the box is smaller than the viewport it stays
  // fully inside; if larger, the viewport stays inside the box — either way no empty gap.
  function clampPan(x: number, y: number, k: number, W: number, H: number) {
    const ns = simNodes.current.filter((n) => n.x != null && n.y != null);
    if (!ns.length) return { x, y };
    const pad = 20; // let a pan bring content right up to the border (was 70 → big blank gap)
    const gx1 = Math.min(...ns.map((n) => n.x!)) - pad;
    const gx2 = Math.max(...ns.map((n) => n.x!)) + pad;
    const gy1 = Math.min(...ns.map((n) => n.y!)) - pad;
    const gy2 = Math.max(...ns.map((n) => n.y!)) + pad;
    const ax = -gx1 * k, bx = W - gx2 * k;
    const ay = -gy1 * k, by = H - gy2 * k;
    return {
      x: Math.min(Math.max(x, Math.min(ax, bx)), Math.max(ax, bx)),
      y: Math.min(Math.max(y, Math.min(ay, by)), Math.max(ay, by)),
    };
  }

  function onBgMove(e: PointerEvent<SVGRectElement>) {
    if (!isPanning.current) return;
    const W = svgRef.current?.clientWidth ?? 700;
    const H = svgRef.current?.clientHeight ?? 500;
    const newX = e.clientX - panOrigin.current.x;
    const newY = e.clientY - panOrigin.current.y;
    setTf((t) => ({ ...t, ...clampPan(newX, newY, t.k, W, H) }));
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

  // Keep selNodeIdRef current so the tick closure can read it without a stale value
  useEffect(() => { selNodeIdRef.current = selNodeId; }, [selNodeId]);

  return (
    <div className="relative flex flex-col" style={{ height: "100%", background: "var(--surface-2)", overflow: "hidden" }}>
      {/* top controls */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10, padding: "7px 14px",
        borderBottom: "1px solid var(--border)", background: "var(--surface)",
        zIndex: 10, flexShrink: 0,
      }}>
        <span className="font-pixel" style={{ fontSize: 7, color: "var(--text-dim)", letterSpacing: "0.08em" }}>
          {agents.length} CHARACTERS · {graphLinks.length} LINKS
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={() => setShowLabels((v) => !v)}
          className="font-pixel"
          style={{
            fontSize: 6, padding: "4px 9px", cursor: "pointer", letterSpacing: "0.08em",
            background: showLabels ? "rgba(78,197,240,0.1)" : "transparent",
            color: showLabels ? "var(--cyan)" : "var(--text-dim)",
            border: `1px solid ${showLabels ? "var(--cyan)" : "var(--border)"}`,
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
            background: "transparent", color: "var(--text-dim)",
            border: "1px solid var(--border)", textTransform: "uppercase",
          }}
        >
          LAYOUT
        </button>
        <button
          onClick={fitToView}
          className="font-pixel"
          style={{
            fontSize: 6, padding: "4px 9px", cursor: "pointer", letterSpacing: "0.08em",
            background: "transparent", color: "var(--text-dim)",
            border: "1px solid var(--border)", textTransform: "uppercase",
          }}
        >
          RESET
        </button>
      </div>

      {/* SVG canvas */}
      <svg
        ref={svgRef}
        // width:100% is required: an <svg> has an intrinsic default width of 300px and does
        // NOT stretch across the flex cross-axis from `flex:1` alone, so clientWidth read a
        // stale 300 and the graph was framed/pan-clamped into the left 300px of the section.
        style={{ flex: 1, width: "100%", minWidth: 0, cursor: "grab", userSelect: "none" }}
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
            const showConnLabel = !!isConnected && selection?.kind === "node";
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
                  showConnLabel={showConnLabel}
                  simNodes={simNodes}
                  edgeRefs={edgeRefs}
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
            // Render the transform from the LIVE simulation position (fallback to the
            // cross-mount cache, then origin). d3 also updates this imperatively per tick,
            // but a static "translate(0,0)" would snap every node to the corner on each
            // re-render (hover/select/drag) until the next tick — nodes flicker to the
            // top-left and get clipped by the container's overflow ("cut off when dragging").
            const live = simNodes.current.find((sn) => sn.id === n.id);
            const px = live?.x ?? POS_CACHE.get(n.id)?.x ?? 0;
            const py = live?.y ?? POS_CACHE.get(n.id)?.y ?? 0;
            return (
              <g
                key={n.id}
                ref={(el) => {
                  if (el) nodeRefs.current.set(n.id, el);
                  else nodeRefs.current.delete(n.id);
                }}
                transform={`translate(${px},${py})`}
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
                <circle r={r} fill={selected ? "#f0eeff" : "#ffffff"}
                  stroke={selected ? "#7950f2" : groupColor}
                  strokeWidth={selected ? 2 : 1.5} />

                {/* group color tint */}
                <circle r={r} fill={groupColor} opacity={0.07} />

                {/* inner specular highlight */}
                <circle r={r * 0.55} cx={-r * 0.22} cy={-r * 0.22} fill="white" opacity={0.25} />

                {/* avatar — pixel sprite by default; explicit emoji pick overrides */}
                {isEmojiAvatar(n.avatar) ? (
                  <text
                    y={1}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={r * 0.95}
                    style={{ pointerEvents: "none" }}
                  >
                    {n.avatar}
                  </text>
                ) : (
                  <g transform={`translate(${-r * 0.82}, ${-r * 0.82})`} style={{ pointerEvents: "none" }}>
                    <PixelAvatar seed={n.id} avatar={n.avatar} mood={n.mood} size={r * 1.64} />
                  </g>
                )}

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
                    <circle r={8} fill="#ffffff" stroke={groupColor} strokeWidth={1.5} />
                    <text textAnchor="middle" dominantBaseline="central"
                      fontSize={8} fill={groupColor} fontWeight="700"
                      style={{ pointerEvents: "none" }}>
                      {relCount}
                    </text>
                  </g>
                )}

                {/* nameplate */}
                <g transform={`translate(0, ${r + 10})`} style={{ pointerEvents: "none" }}>
                  <rect x={-nameplateW / 2} y={-9} width={nameplateW} height={17} rx={0}
                    fill="#ffffff"
                    stroke={selected ? "#7950f2" : groupColor}
                    strokeWidth={selected ? 1.5 : 0.8}
                    opacity={0.96} />
                  <text textAnchor="middle" dominantBaseline="central"
                    fontSize={10} fontWeight="600"
                    fontFamily="ui-sans-serif, system-ui, sans-serif"
                    fill={selected ? "#2d3a50" : "#7a8a9e"}
                    style={{ pointerEvents: "none" }}>
                    {n.name}
                  </text>
                </g>

                {/* role label */}
                <text y={r + 27} textAnchor="middle" dominantBaseline="central"
                  fontSize={8.5} fontFamily="ui-sans-serif, system-ui, sans-serif"
                  fill="#7a8a9e" style={{ pointerEvents: "none" }}>
                  {n.role.length > 20 ? n.role.slice(0, 19) + "…" : n.role}
                </text>

                {/* influence bar */}
                <g transform={`translate(0, ${r + 38})`} style={{ pointerEvents: "none" }}>
                  <rect x={-barW / 2} y={0} width={barW} height={3} rx={0} fill="#ddd6f8" />
                  <rect x={-barW / 2} y={0} width={barW * infPct} height={3} rx={0}
                    fill={moodColor} opacity={0.85} />
                </g>
              </g>
            );
          })}

          {/* ── selected-node relationship lines overlay ───────────────── */}
          {selNodeId && (() => {
            const selNode = simNodes.current.find(n => n.id === selNodeId);
            const selAgent = agents.find(a => a.id === selNodeId);
            if (!selNode?.x || !selAgent) return null;
            return Object.entries(selAgent.relationships).map(([name, rel], i) => {
              const targetAgent = agents.find(a => a.name === name);
              if (!targetAgent) return null;
              const targetNode = simNodes.current.find(n => n.id === targetAgent.id);
              if (!targetNode?.x) return null;
              const key = `${selNodeId}~~${targetAgent.id}`;
              const color = EDGE[rel.type]?.color ?? "#7a8a9e";
              const mx = (selNode.x! + targetNode.x!) / 2;
              const my = (selNode.y! + targetNode.y!) / 2;
              const label = rel.type.replace("_", " ").toUpperCase();
              const badgeW = label.length * 5.2 + 16;
              const delay = `${i * 0.04}s`;
              return (
                <g key={key} style={{ pointerEvents: "none" }}>
                  {/* soft glow */}
                  <line
                    ref={el => { if (el) connGlowRefs.current.set(key, el); else connGlowRefs.current.delete(key); }}
                    x1={selNode.x} y1={selNode.y} x2={targetNode.x} y2={targetNode.y}
                    stroke={color} strokeWidth={3} opacity={0.1}
                    strokeDasharray="800" filter="url(#glow-sm)"
                    style={{ animation: `draw-line 0.35s cubic-bezier(0.22,1,0.36,1) ${delay} both` }}
                  />
                  {/* main line */}
                  <line
                    ref={el => { if (el) connLineRefs.current.set(key, el); else connLineRefs.current.delete(key); }}
                    x1={selNode.x} y1={selNode.y} x2={targetNode.x} y2={targetNode.y}
                    stroke={color} strokeWidth={1} strokeDasharray="800"
                    style={{ animation: `draw-line 0.35s cubic-bezier(0.22,1,0.36,1) ${delay} both` }}
                  />
                  {/* badge — outer g is the live-positioned anchor, inner g fades in */}
                  <g
                    ref={el => { if (el) connBadgeRefs.current.set(key, el); else connBadgeRefs.current.delete(key); }}
                    transform={`translate(${mx},${my})`}
                  >
                    <g style={{ animation: `badge-in 0.25s ease-out ${delay} both` }}>
                      <rect x={-badgeW / 2} y={-9} width={badgeW} height={18} fill={color} />
                      <rect x={-badgeW / 2 + 2} y={-7} width={badgeW - 4} height={14} fill="white" opacity={0.12} />
                      <text
                        textAnchor="middle" dominantBaseline="central"
                        fontSize={7} fontFamily="var(--font-pixel, 'Courier New', monospace)"
                        fontWeight="700" fill="white" letterSpacing="0.06em"
                      >
                        {label}
                      </text>
                    </g>
                  </g>
                </g>
              );
            });
          })()}
        </g>
      </svg>

      {/* legend */}
      <div style={{
        borderTop: "1px solid var(--border)",
        background: "var(--surface)", flexShrink: 0,
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
            padding: "3px 14px 6px", borderTop: "1px solid var(--border)",
          }}>
            <span className="font-pixel" style={{ fontSize: 6, color: "var(--text-dim)", marginRight: 4, alignSelf: "center", letterSpacing: "0.08em" }}>FACTIONS</span>
            {Array.from(groupColors.entries()).map(([group, color]) => (
              <span key={group} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 6, height: 6, background: color, flexShrink: 0, borderRadius: "50%" }} />
                <span className="font-pixel" style={{ fontSize: 6, color: "var(--text-dim)", letterSpacing: "0.04em" }}>{group}</span>
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
  l, cfg, dimmed, highlighted, isConnected, showLabels, showConnLabel, simNodes, edgeRefs,
}: {
  l: GraphLink;
  cfg: typeof EDGE[RelationshipType];
  dimmed: boolean;
  highlighted: boolean;
  isConnected: boolean;
  showLabels: boolean;
  showConnLabel: boolean;
  simNodes: React.RefObject<GraphNode[]>;
  edgeRefs: React.RefObject<Map<string, SVGPathElement>>;
}) {
  // l.source / l.target are string ids here — d3 only resolves them to node objects on
  // its own private copies (simLinks.current), never on the memoized graphLinks we render
  // from. Read the live positions out of simNodes.current by id so the edge actually draws.
  const nodes = simNodes.current ?? [];
  const srcId = typeof l.source === "object" ? (l.source as GraphNode).id : String(l.source);
  const tgtId = typeof l.target === "object" ? (l.target as GraphNode).id : String(l.target);
  const src = nodes.find((n) => n.id === srcId);
  const tgt = nodes.find((n) => n.id === tgtId);
  if (!src?.x || !tgt?.x) return null;

  const d = edgePath(src.x, src.y!, tgt.x, tgt.y!);
  const mid = labelMid(src.x, src.y!, tgt.x, tgt.y!);
  // Affinity magnitude drives visual weight: a bond that has cooled toward neutral fades
  // and thins, instead of rendering as healthy as a strong one. (l.strength is signed.)
  const mag = Math.min(1, Math.abs(l.strength));
  const baseOpacity = dimmed ? 0 : highlighted ? 1 : isConnected ? 0.85 : 0.55;
  const opacity = baseOpacity * (0.3 + 0.7 * mag);
  const width = (highlighted ? cfg.width + 1.5 : cfg.width) * (0.4 + 0.6 * mag);
  const showAnim = !dimmed && opacity > 0;
  const labelText = cfg.label.toUpperCase();
  const badgeW = labelText.length * 5.2 + 14;

  return (
    <>
      {/* base edge */}
      <path
        ref={(el) => {
          if (el) edgeRefs.current?.set(l.key, el);
          else edgeRefs.current?.delete(l.key);
        }}
        d={d}
        fill="none"
        stroke={cfg.color}
        strokeWidth={width}
        strokeDasharray={cfg.dash === "none" ? undefined : cfg.dash}
        strokeOpacity={opacity}
        markerEnd={l.type === "influence" ? "url(#arrow-influence)" : l.type === "rivalry" ? "url(#arrow-rivalry)" : undefined}
        filter={highlighted ? "url(#glow-sm)" : undefined}
        style={{ transition: "stroke-opacity 0.2s", pointerEvents: "none" }}
      />

      {/* pulsing glow halo for negative relationships */}
      {cfg.pulse && showAnim && (
        <path
          d={d}
          fill="none"
          stroke={cfg.color}
          strokeWidth={width + 4}
          style={{ pointerEvents: "none", animation: "edge-pulse 1.8s ease-in-out infinite" }}
        />
      )}

      {/* flowing particles for positive relationships */}
      {cfg.flowDur && showAnim && (
        <>
          <circle r={3} fill={cfg.color} style={{ pointerEvents: "none" }}>
            <animateMotion dur={`${cfg.flowDur}s`} repeatCount="indefinite" path={d} />
          </circle>
          <circle r={2} fill={cfg.color} opacity={0.6} style={{ pointerEvents: "none" }}>
            <animateMotion dur={`${cfg.flowDur}s`} begin={`-${cfg.flowDur * 0.5}s`} repeatCount="indefinite" path={d} />
          </circle>
        </>
      )}

      {/* relationship badge on connected edges when a node is selected */}
      {(showConnLabel || showLabels) && !dimmed && (
        <g transform={`translate(${mid.x}, ${mid.y})`} style={{ pointerEvents: "none" }}>
          <rect
            x={-badgeW / 2} y={-9}
            width={badgeW} height={18}
            fill={cfg.color}
          />
          <rect
            x={-badgeW / 2 + 2} y={-7}
            width={badgeW - 4} height={14}
            fill="white" opacity={0.12}
          />
          <text
            textAnchor="middle" dominantBaseline="central"
            fontSize={7}
            fontFamily="var(--font-pixel, 'Courier New', monospace)"
            fontWeight="700"
            fill="white"
            letterSpacing="0.06em"
          >
            {labelText}
          </text>
        </g>
      )}
    </>
  );
}
