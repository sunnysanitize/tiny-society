"""Score the second-pass error checker (judge.CHECK_SYSTEM) against codex's labels.

Usage (from engine/):
    venv/bin/python -m tools.sim_eval.check_flags --model anthropic/claude-sonnet-5.5
    venv/bin/python -m tools.sim_eval.check_flags --model ... --split test

Every flag codex labeled (runs/error_labels.json + runs/blind_labels.json) is sent to the
checker with its full transcript. Scenarios are split by hash into dev (rules were written
from codex's dev reasons) and test (held out); tune on dev, report test. Verdicts are cached
in runs/checks/<model>.json, so re-running only calls the model for new flags; delete the
file after changing CHECK_SYSTEM.

Reported per split: precision of the flags the checker keeps (vs precision with no checker),
how many codex-confirmed errors survive (recall of y), and agreement with codex on y/n.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
from pathlib import Path

from tools.sim_eval.judge import check_error
from tools.sim_eval.verify_errors import BLIND_LABELS, LABELS, RUNS, all_errors, load, wilson

CHECKS = RUNS / "checks"


def split_of(item_id: str) -> str:
    scen = item_id.split("/")[1].split("#")[0]
    return "dev" if int(hashlib.md5(scen.encode()).hexdigest(), 16) % 2 == 0 else "test"


def labeled_items(rater: str) -> list[dict]:
    labels = {**load(LABELS).get(rater, {}), **load(BLIND_LABELS).get(rater, {})}
    runs = {k.split("/")[0] for k in labels}
    items = [it for r in runs for it in all_errors(r) if it["id"] in labels]
    return [dict(it, label=labels[it["id"]]["label"], split=split_of(it["id"])) for it in items]


def run_checks(items: list[dict], model: str) -> dict:
    CHECKS.mkdir(exist_ok=True)
    path = CHECKS / f"{model.replace('/', '_')}.json"
    cache = load(path)
    todo = [it for it in items if it["id"] not in cache]
    text = {md: Path(md).read_text()[:120_000] for md in {it["md"] for it in todo}}
    failed = 0
    with cf.ThreadPoolExecutor(8) as ex:
        for it, out in zip(todo, ex.map(lambda it: check_error(it, text[it["md"]], model), todo)):
            if "error" in out:  # API/parse failure: don't cache, so a re-run retries it
                failed += 1
                print(f"  {it['id']}: {out['error'][:120]}")
            else:
                cache[it["id"]] = out
    path.write_text(json.dumps(cache, indent=1))
    print(f"{model}: {len(todo) - failed} new checks, {failed} failed, {len(cache)} cached -> {path.relative_to(RUNS.parent)}")
    if failed:
        raise SystemExit("some checks failed; re-run to retry them before trusting the numbers")
    return cache


def report(items: list[dict], checks: dict) -> None:
    for split in ("dev", "test", "all"):
        sel = [it for it in items if split in ("all", it["split"]) and it["label"] in "yn"]
        if not sel:
            continue
        y = sum(it["label"] == "y" for it in sel)
        kept = [it for it in sel if checks[it["id"]]["verdict"] == "error"]
        ky = sum(it["label"] == "y" for it in kept)
        agree = sum((checks[it["id"]]["verdict"] == "error") == (it["label"] == "y") for it in sel)
        lo, hi = wilson(ky, len(kept))
        print(f"{split:>5}: no checker {y}/{len(sel)} = {y / len(sel):4.0%} | "
              f"checker keeps {len(kept)}, precision {ky / max(1, len(kept)):4.0%} "
              f"(95% CI {lo:.0%}-{hi:.0%}) | real errors kept {ky}/{y} | agreement {agree / len(sel):.0%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--rater", default="codex")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev",
                    help="which flags to send to the model (default dev; test is held out)")
    ap.add_argument("--show", action="store_true", help="print each disagreement with codex")
    args = ap.parse_args()
    items = [it for it in labeled_items(args.rater) if args.split in ("all", it["split"])]
    checks = run_checks(items, args.model)
    report(items, checks)
    if args.show:
        for it in items:
            v = checks[it["id"]]["verdict"]
            if it["label"] in "yn" and (v == "error") != (it["label"] == "y"):
                print(f"\n{it['id']} codex={it['label']} checker={v} [{it['dimension']}]\n"
                      f"  flag: {it.get('evidence', '')[:200]}\n  checker: {checks[it['id']].get('reason', '')[:300]}")


if __name__ == "__main__":
    main()
