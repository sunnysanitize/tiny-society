"""Hand-check a random sample of the errors the LLM judge flagged, to measure its precision.

Usage (from engine/):
    venv/bin/python -m tools.sim_eval.verify_errors            # label (resumes where you left off)
    venv/bin/python -m tools.sim_eval.verify_errors --report   # precision by severity / dimension

Each item shows the judge's evidence plus the transcript sections it points at (quoted
phrases, referenced days, report / relationship / belief sections). Keys: y = the judge is
right (a real error), n = the judge is wrong (not an error), ? = can't tell, f = page the
full transcript, s = skip, q = quit.
Labels are saved after every answer to runs/error_labels.json. A second rater can label the
same sample with --rater NAME; --report then adds Cohen's kappa between raters.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import subprocess
from collections import defaultdict
from pathlib import Path

RUNS = Path(__file__).resolve().parent / "runs"
LABELS = RUNS / "error_labels.json"
_MAX_LINES = 70


def all_errors() -> list[dict]:
    items = []
    for scores in sorted(RUNS.glob("*/scores.json")):
        for r in json.loads(scores.read_text()):
            for i, e in enumerate(r["llm"].get("errors", [])):
                items.append({"id": f"{scores.parent.name}/{r['run']}#{i}",
                              "md": str(scores.parent / f"{r['run']}.md"), **e})
    return items


def sample(n: int, seed: int) -> list[dict]:
    items = all_errors()
    return random.Random(seed).sample(items, min(n, len(items)))


def sections(md: str) -> dict[str, list[str]]:
    out, cur = {"_head": []}, "_head"
    for line in md.splitlines():
        if line.startswith("## "):
            cur = line[3:]
            out[cur] = []
        out[cur].append(line)
    return out


def context(item: dict) -> list[str]:
    """Transcript lines relevant to one flagged error."""
    ev = item["evidence"]
    secs = sections(Path(item["md"]).read_text())
    picked = []
    for day in sorted(set(re.findall(r"[Dd]ay (\d+)", ev)), key=int):
        picked += [k for k in secs if k.startswith(f"Day {day} ")]
    low = ev.lower()
    for key, prefix in [("report", "Final report"), ("forecast", "Final report"),
                        ("graph", "Final relationships"), ("relationship", "Final relationships"),
                        ("belief", "Belief means"), ("influence", "Standing change"),
                        ("premise", "Lens"), ("trait", "Cast")]:
        if key in low:
            picked += [k for k in secs if k.startswith(prefix)]
    lines = []
    for k in dict.fromkeys(picked):
        lines += secs[k] + [""]
    quotes = [q for q in re.findall(r"'([^']{6,})'|\"([^\"]{6,})\"", ev) for q in q if q]
    hits = [l for s in secs.values() for l in s
            if any(q.lower() in l.lower() for q in quotes) and l not in lines]
    if hits:
        lines = ["[lines quoting the evidence]"] + hits + [""] + lines
    return lines


def load() -> dict:
    return json.loads(LABELS.read_text()) if LABELS.exists() else {}


def label(args):
    labels = load()
    mine = labels.setdefault(args.rater, {})
    todo = [it for it in sample(args.n, args.seed) if it["id"] not in mine]
    print(f"{len(mine)} labeled, {len(todo)} to go\n")
    for k, it in enumerate(todo, 1):
        ctx = context(it)
        os.system("clear")
        print(f"[{len(mine) + 1}/{args.n}] {it['id']}  ({it['dimension']}, {it['severity']})\n")
        print("JUDGE SAYS:", it["evidence"], "\n")
        print("\n".join(ctx[:_MAX_LINES]) or "(no section matched; press f to read the transcript)")
        if len(ctx) > _MAX_LINES:
            print(f"... {len(ctx) - _MAX_LINES} more lines (f to page)")
        while True:
            a = input("\nIs the judge RIGHT? y = yes, real error / n = no, judge is wrong"
                      "  [y/n/?/f/s/q] ").strip().lower()
            if a == "f":
                subprocess.run([os.getenv("PAGER", "less"), it["md"]])
            elif a in ("y", "n", "?", "s", "q"):
                break
        if a == "q":
            break
        if a == "s":
            continue
        mine[it["id"]] = {"label": a, "dimension": it["dimension"], "severity": it["severity"]}
        LABELS.write_text(json.dumps(labels, indent=2))
    print(f"\n{len(mine)} labeled. Run with --report for results.")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def report(args):
    labels = load()
    for rater, mine in labels.items():
        groups = defaultdict(list)
        for v in mine.values():
            for g in ("all", f"severity={v['severity']}", f"dim={v['dimension']}"):
                groups[g].append(v["label"])
        print(f"rater {rater}: {len(mine)} labeled")
        for g, ls in sorted(groups.items(), key=lambda kv: (kv[0] != "all", kv[0])):
            y, n = ls.count("y"), ls.count("n")
            lo, hi = wilson(y, y + n)
            prec = f"{y / (y + n):.0%}" if y + n else "-"
            print(f"  {g:>36}: precision {prec:>4} ({y}/{y + n}, 95% CI {lo:.0%}-{hi:.0%}), unsure {ls.count('?')}")
    raters = list(labels)
    for i in range(len(raters)):
        for j in range(i + 1, len(raters)):
            a, b = labels[raters[i]], labels[raters[j]]
            shared = [k for k in a if k in b and "?" not in (a[k]["label"], b[k]["label"])]
            if shared:
                xs, ys = [a[k]["label"] for k in shared], [b[k]["label"] for k in shared]
                print(f"{raters[i]} vs {raters[j]}: {len(shared)} shared, "
                      f"agreement {sum(x == y for x, y in zip(xs, ys)) / len(shared):.0%}, "
                      f"Cohen's kappa {kappa(xs, ys):.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--rater", default="me")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    report(args) if args.report else label(args)


if __name__ == "__main__":
    main()
