"""Regenerate only the final reports of finished runs with the current reporter.

Usage (from engine/):
    venv/bin/python -m tools.sim_eval.rereport SRC_RUN_DIR DST_RUN_DIR

Isolates report changes: same simulated days, new report, at a fraction of a full
run's cost. Writes DST/<run>.json and .md exactly as run_batch does.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from models import EventCast, SimulationResult, World  # noqa: E402
from simulation.reporter import generate_final_report  # noqa: E402

from .run_batch import transcript  # noqa: E402


def redo(src: Path, dst_dir: Path) -> str:
    data = json.loads(src.read_text())
    world = World(**data["world"])
    world.event_casts = {k: EventCast(**v) for k, v in data.get("event_casts", {}).items()}
    result = SimulationResult(**data["result"])
    snaps = result.snapshots
    report, forecast = generate_final_report(
        result.initial_metrics, result.final_metrics, snaps, world.prompt, world.starting_event,
        question=world.question, topics=world.world_graph.topics,
        dynamic_events=result.dynamic_events, lens=world.lens,
        initial_agents=world.agents, event_casts=world.event_casts,
    )
    result.final_report, result.forecast = report, forecast
    data["result"] = result.model_dump()
    (dst_dir / src.name).write_text(json.dumps(data, default=str))
    (dst_dir / src.with_suffix(".md").name).write_text(transcript(world, result))
    return src.stem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    args = ap.parse_args()
    src, dst = Path(args.src), Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)
    paths = [p for p in sorted(src.glob("*.json")) if p.name != "scores.json" and not p.name.startswith("pairwise")]
    with cf.ThreadPoolExecutor(8) as ex:
        for name in ex.map(lambda p: redo(p, dst), paths):
            print(f"{name} re-reported", flush=True)


if __name__ == "__main__":
    main()
