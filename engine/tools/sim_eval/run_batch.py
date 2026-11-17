"""Run many full simulations against the configured real LLM and dump transcripts.

Usage (from engine/):
    venv/bin/python -m tools.sim_eval.run_batch --out RUN_DIR [--only key1,key2] [--days 5] [--seeds 1]

Each scenario: create world (lens + graph) -> generate fillers -> set event -> run.
Writes RUN_DIR/<key>-s<seed>.json (raw result + world) and .md (readable story).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from models import World, SimulationConfig  # noqa: E402
from simulation.engine import run_simulation  # noqa: E402
from simulation.generator import generate_fillers  # noqa: E402
from simulation.worldgraph import extract_world_context  # noqa: E402

from .scenarios import SCENARIOS  # noqa: E402


def transcript(world: World, result) -> str:
    out = [f"# {world.prompt}", "", f"**Starting event:** {world.starting_event}", ""]
    lens = world.lens
    out += ["## Lens", f"- actors: {lens.actor_noun_plural} / collective: {lens.collective_noun}",
            f"- stake: {lens.central_stake}", f"- banned: {lens.banned_vocabulary}", ""]
    for ev, c in world.event_casts.items():
        out += [f"## Event casting: {ev}", f"- public: {c.public}", f"- hidden truth: {c.truth}"]
        out += [f"- {n}: {line}" for n, line in c.involvement.items()]
        out.append("")
    out.append("## Cast (day 0)")
    for a in world.agents:
        rels = ", ".join(f"{n}:{r.type}{r.strength:+.2f}" for n, r in a.relationships.items())
        out.append(f"- **{a.name}** — {a.role}; traits={a.traits}; goals={a.goals}; mood={a.mood}; groups={a.groups}; rels=[{rels}]")
        for m in a.long_term_memory[:4]:
            out.append(f"    - mem: {m.text}")
    out.append("")
    for s in result.snapshots:
        c = world.event_casts.get(s.active_event or "")
        since = f" (ongoing since day {c.day})" if c and c.day and c.day < s.day else ""
        out.append(f"## Day {s.day} — event{since}: {s.active_event}")
        for line in s.event_log:
            out.append(f"- {line}")
        if s.milestones:
            out.append(f"- MILESTONES: {s.milestones}")
        for v in s.vignettes:
            out.append(f"- VIGNETTE ({v.kind}) {v.agent}: {v.text}")
        for h in s.highlights:
            out.append(f"- HL {h.agent}: {h.summary} | says: {h.utterance}")
        out.append("")
    out += ["## Final relationships"]
    for a in result.snapshots[-1].agents:
        rels = ", ".join(f"{n}:{r.type}{r.strength:+.2f}" for n, r in a.relationships.items())
        out.append(f"- {a.name} ({a.mood}): {rels}")
    # The report is given standing and belief data the log doesn't show; without it
    # the judge flags every true number in the report as invented.
    before = {a.name: a.influence_score for a in world.agents}
    final_agents = result.snapshots[-1].agents
    out += ["", "## Standing change (influence, given to the report)"]
    out += [f"- {a.name}: {a.influence_score - before.get(a.name, 0.0):+.1f}" for a in final_agents]
    fm = result.snapshots[-1].metrics
    out += ["", "## Belief means per topic (given to the report)"]
    out += [f"- day {s.day}: " + ", ".join(f"{t}={v:+.2f}" for t, v in s.metrics.topic_means.items())
            for s in result.snapshots]
    out.append(f"- final confidence: {fm.belief_confidence:.2f}")
    out += ["", "## Final report", result.final_report or "(none)"]
    return "\n".join(out)


def run_one(sc: dict, seed: int, days: int, out_dir: Path) -> str:
    key = f"{sc['key']}-s{seed}"
    t0 = time.time()
    world = World(prompt=sc["prompt"], target_population=sc.get("population", 6))
    world.world_graph, world.lens = extract_world_context(world)
    world.agents.extend(generate_fillers(world, world.target_population))
    world.starting_event = sc["event"]
    world.question = sc.get("question")
    world_day0 = world.model_copy(deep=True)
    result = run_simulation(world, SimulationConfig(days=days, reasoning_agents_per_day=sc.get("per_day", 5)), seed=seed)
    (out_dir / f"{key}.json").write_text(json.dumps({
        "scenario": sc, "seed": seed, "world": world_day0.model_dump(), "event_casts": {k: v.model_dump() for k, v in world.event_casts.items()}, "lens": world.lens.model_dump(),
        "graph": world.world_graph.model_dump(), "result": result.model_dump(),
    }, default=str))
    # A run whose LLM calls failed (no credit, outage) is all "kept to myself" fallback
    # beats; it finishes in seconds and would otherwise be judged as a real story.
    hls = [h for snap in result.snapshots for h in snap.highlights]
    fallback = sum(h.summary.startswith("I kept to myself today") for h in hls) / max(1, len(hls))
    if fallback > 0.3:
        raise RuntimeError(f"{fallback:.0%} of actions are fallbacks — LLM calls are failing")
    world_day0.event_casts = world.event_casts
    (out_dir / f"{key}.md").write_text(transcript(world_day0, result))
    return f"{key} done in {time.time() - t0:.0f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--seed-start", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "WARNING"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, args.only.split(",")))
    jobs = [(sc, seed) for sc in SCENARIOS if not only or sc["key"] in only for seed in range(args.seed_start, args.seed_start + args.seeds)]
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(run_one, sc, seed, args.days, out_dir): sc["key"] for sc, seed in jobs}
        for f in cf.as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # keep the batch going
                print(f"{futs[f]} FAILED: {e!r}", flush=True)


if __name__ == "__main__":
    main()
