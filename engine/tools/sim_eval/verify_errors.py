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
By default only judge-v1 scores are sampled (so the seed-0 sample stays fixed); --source GLOB
picks other run dirs, e.g. --source '*-j2' for judge-v2 errors.

Blind old-vs-new comparison (same transcripts, judge version hidden while labeling):
    venv/bin/python -m tools.sim_eval.verify_errors --blind --old v3 --old v7-lite --new v3-j2 --new v7-lite-j2
    venv/bin/python -m tools.sim_eval.verify_errors --blind --old v3 --old v7-lite --new v3-j2 --new v7-lite-j2 --report
--n errors are drawn from each judge (only from transcripts both judges scored, skipping
anything already in runs/error_labels.json), then shuffled together. Labels go to
runs/blind_labels.json; the judge is revealed only by --report.
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
BLIND_LABELS = RUNS / "blind_labels.json"
_MAX_LINES = 70


def all_errors(source: str | None = None) -> list[dict]:
    """Errors from runs/<source>/scores.json; source=None means every judge-v1 run dir."""
    items = []
    for scores in sorted(RUNS.glob(f"{source or '*'}/scores.json")):
        for r in json.loads(scores.read_text()):
            v = r.get("judge_version", 1)
            if source is None and v != 1:
                continue
            for i, e in enumerate(r["llm"].get("errors", [])):
                items.append({"id": f"{scores.parent.name}/{r['run']}#{i}", "judge": f"v{v}",
                              # resolved, so old and new items point at the same transcript file
                              "md": str((scores.parent / f"{r['run']}.md").resolve()), **e})
    return items


def sample(n: int, seed: int, source: str | None = None) -> list[dict]:
    items = all_errors(source)
    return random.Random(seed).sample(items, min(n, len(items)))


def blind_sample(n: int, seed: int, old: list[str], new: list[str]) -> list[dict]:
    """n errors from each judge, restricted to transcripts both scored, shuffled together."""
    olds = [it for g in old for it in all_errors(g)]
    news = [it for g in new for it in all_errors(g)]
    shared = {it["md"] for it in olds} & {it["md"] for it in news}
    seen = {k for rater in load(LABELS).values() for k in rater}  # don't re-show labeled items
    olds = [it for it in olds if it["md"] in shared and it["id"] not in seen]
    news = [it for it in news if it["md"] in shared and it["id"] not in seen]
    k = min(n, len(olds), len(news))
    rng = random.Random(seed)
    items = [dict(it, arm="old") for it in rng.sample(olds, k)] + [dict(it, arm="new") for it in rng.sample(news, k)]
    rng.shuffle(items)
    return items


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
    # judge-v2 errors carry verbatim quotes; they join v1-style inline quotes in the same
    # "[lines quoting the evidence]" block, so both judges' items look alike in blind mode
    extra = [q for q in item.get("quotes") or [] if isinstance(q, str)]
    ev = " ".join([item["evidence"]] + extra)
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
    quotes = [q for q in re.findall(r"'([^']{6,})'|\"([^\"]{6,})\"", item["evidence"]) for q in q if q]
    quotes += [p.strip() for q in extra for p in q.splitlines() if p.strip()]
    hits = list(dict.fromkeys(l for s in secs.values() for l in s
                              if any(q.lower() in l.lower().replace("**", "") for q in quotes)))[:12]
    if hits:
        lines = ["[lines quoting the evidence]"] + hits + [""] + lines
    return lines


def load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def items_for(args, labels: dict) -> list[dict]:
    if not args.blind:
        return sample(args.n, args.seed, args.source)
    # the blind sample is frozen in the labels file on first use, so later changes to
    # error_labels.json or the run dirs can't reshuffle it mid-study
    spec = {"old": args.old, "new": args.new, "n": args.n, "seed": args.seed}
    frozen = labels.get("_sample")
    if frozen is None:
        frozen = labels["_sample"] = dict(spec, items=[[it["id"], it["arm"]] for it in
                                                       blind_sample(args.n, args.seed, args.old, args.new)])
        args.labels.write_text(json.dumps(labels, indent=2))
    elif {k: frozen[k] for k in spec} != spec:
        raise SystemExit(f"{args.labels} holds a different blind sample {[frozen[k] for k in spec]}; "
                         "pass the same --old/--new/--n/--seed or another --labels file")
    by_id = {it["id"]: it for g in args.old + args.new for it in all_errors(g)}
    return [dict(by_id[i], arm=a) for i, a in frozen["items"]]


def label(args):
    labels = load(args.labels)
    items = items_for(args, labels)
    mine = labels.setdefault(args.rater, {})
    todo = [it for it in items if it["id"] not in mine]
    print(f"{len(mine)} labeled, {len(todo)} to go\n")
    for k, it in enumerate(todo, 1):
        ctx = context(it)
        os.system("clear")
        # blind mode hides the id (its run dir names the judge); the scenario name is shared
        shown = Path(it["md"]).stem if args.blind else it["id"]
        print(f"[{len(mine) + 1}/{len(items)}] {shown}  ({it['dimension']}, {it['severity']})\n")
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
        args.labels.write_text(json.dumps(labels, indent=2))
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


def fisher_p(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for the 2x2 table [[a, b], [c, d]]."""
    r1, c1, n = a + b, a + c, a + b + c + d
    pr = lambda x: math.comb(r1, x) * math.comb(n - r1, c1 - x) / math.comb(n, c1)
    p0 = pr(a)
    return min(1.0, sum(pr(x) for x in range(max(0, c1 - (n - r1)), min(r1, c1) + 1) if pr(x) <= p0 * (1 + 1e-9)))


def precision_lines(entries: list[dict], prefix: str = "") -> None:
    groups = defaultdict(list)
    for v in entries:
        for g in ("all", f"severity={v['severity']}", f"dim={v['dimension']}"):
            groups[g].append(v["label"])
    for g, ls in sorted(groups.items(), key=lambda kv: (kv[0] != "all", kv[0])):
        y, n = ls.count("y"), ls.count("n")
        lo, hi = wilson(y, y + n)
        prec = f"{y / (y + n):.0%}" if y + n else "-"
        print(f"  {prefix + g:>40}: precision {prec:>4} ({y}/{y + n}, 95% CI {lo:.0%}-{hi:.0%}), unsure {ls.count('?')}")


def blind_report(args):
    labels = load(args.labels)
    if "_sample" not in labels:
        raise SystemExit(f"no blind sample in {args.labels} yet")
    spec = labels.pop("_sample")
    arm = dict(spec["items"])
    for rater, mine in labels.items():
        entries = [dict(v, arm=arm[k]) for k, v in mine.items() if k in arm]
        print(f"rater {rater}: {len(entries)}/{len(arm)} labeled (blind; old = {spec['old']}, new = {spec['new']})")
        for a in ("old", "new"):
            precision_lines([e for e in entries if e["arm"] == a], f"{a} judge, ")
        (oy, on), (ny, nn) = [[sum(e["arm"] == a and e["label"] == l for e in entries) for l in "yn"]
                              for a in ("old", "new")]
        if oy + on and ny + nn:
            print(f"  new - old precision: {ny / (ny + nn) - oy / (oy + on):+.0%} "
                  f"(Fisher exact p = {fisher_p(ny, nn, oy, on):.3f}; errors from one transcript "
                  f"are correlated, so treat the CI/p as optimistic)")


def report(args):
    if args.blind:
        return blind_report(args)
    labels = load(args.labels)
    for rater, mine in labels.items():
        print(f"rater {rater}: {len(mine)} labeled")
        precision_lines(list(mine.values()))
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
    ap.add_argument("--n", type=int, help="sample size (blind: per judge); default 60, blind 30")
    ap.add_argument("--seed", type=int, help="default 0, blind 1")
    ap.add_argument("--rater", default="me")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--source", help="run dir glob under runs/ (default: all judge-v1 dirs)")
    ap.add_argument("--blind", action="store_true", help="label --old and --new errors mixed, judge hidden")
    ap.add_argument("--old", action="append", default=[], help="old-judge run dir glob (repeatable)")
    ap.add_argument("--new", action="append", default=[], help="new-judge run dir glob (repeatable)")
    ap.add_argument("--labels", type=Path, help="labels file (default runs/error_labels.json, blind runs/blind_labels.json)")
    args = ap.parse_args()
    if args.blind and not (args.old and args.new):
        ap.error("--blind needs --old and --new")
    args.n = args.n or (30 if args.blind else 60)
    args.seed = (1 if args.blind else 0) if args.seed is None else args.seed
    args.labels = args.labels or (BLIND_LABELS if args.blind else LABELS)
    report(args) if args.report else label(args)


if __name__ == "__main__":
    main()
