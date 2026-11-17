"""Score simulation transcripts for story accuracy.

Usage (from engine/):
    venv/bin/python -m tools.sim_eval.judge RUN_DIR [--model anthropic/claude-sonnet-4.5]
    venv/bin/python -m tools.sim_eval.judge RUN_DIR --judge-version 2 --out OUT_DIR

--judge-version 2 asks for verbatim quotes with every error and drops errors whose quotes
are not in the transcript (see verify_quotes). --out writes scores.json into OUT_DIR (with
links to the transcripts) so an existing RUN_DIR/scores.json is never overwritten.

Two layers:
  * deterministic checks computed from the raw JSON (fallbacks, repeats, banned words, ...)
  * an LLM judge (a different, stronger model than the simulator) that grades the
    transcript against a fixed accuracy rubric and lists concrete errors.
Writes RUN_DIR/scores.json and prints a summary table.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DIMENSIONS = [
    "premise_fidelity",
    "character_consistency",
    "causal_coherence",
    "event_grounding",
    "relationship_plausibility",
    "report_faithfulness",
    "progression",
]

JUDGE_SYSTEM_V1 = """You are a strict editor auditing a generated multi-day story for ACCURACY.
The story comes from an agent-based social simulation. You get the world premise, the cast at
day 0 (traits, goals, memories, starting relationships), the day-by-day action log, the final
relationship graph, and a final written report.

Score each dimension 1-10 (10 = flawless, 5 = noticeable recurring problems, 1 = broken):
- premise_fidelity: era, technology, species and social rules of the premise are respected
  (no anachronisms, no talking animals if they can't speak, vocabulary fits the setting).
- character_consistency: each character acts in line with their stated traits, goals,
  role and history; no personality flips without cause.
- causal_coherence: actions follow from what that character could plausibly know and from
  prior events; no one reacts to things they never witnessed or were told; time passes
  sensibly (an event from day 1 is not treated as brand-new news on day 4).
- event_grounding: the starting event is engaged concretely — the people it names or implies
  are identifiable in the cast or clearly offstage, and its consequences develop rather than
  everyone vaguely "pondering whispers".
- relationship_plausibility: the final relationship types/strengths are justified by the
  interactions actually shown (no rivalry from one glance, no deep friendship from nothing).
- report_faithfulness: every claim in the final report is supported by the log; penalize
  invented events, misattributed actions, wrong names, numbers or claims not in the data.
- progression: the story moves; characters don't repeat the same action day after day;
  scenes escalate, resolve, or change.

Then list the concrete errors you found (most severe first, max 12), each with the
dimension, a severity (high/medium/low), and a short quote or day reference as evidence.

Return STRICT JSON only:
{"scores": {"premise_fidelity": n, ...}, "errors": [{"dimension": "...", "severity": "...", "evidence": "..."}], "summary": "two sentences"}
"""


JUDGE_SYSTEM = JUDGE_SYSTEM_V1

# v2: same rubric and scores, but every error must be checkable. Rules below come from
# hand-checking v1's flagged errors (most were false positives; see verify_errors.py).
JUDGE_SYSTEM_V2 = JUDGE_SYSTEM_V1.split("Then list the concrete errors")[0] + """How to read the transcript:
- "## Event casting: X" sections (printed first) happen on the day whose header names event X,
  not on day 1. Characters may know about an event only from that day on.
- Cast traits/goals belong only to the character on whose Cast line they appear. Traits are
  not an exhaustive whitelist, and mixed traits (e.g. insecure + controlling) can coexist.
- Relationships are DIRECTED: "A (mood): B:conflict-0.5" is A's edge toward B, not B's toward A.
- "- SAYS name: ..." lines are that character's spoken words or gestures that day; they are
  part of the log and can support report claims.
- "Standing change" and "Belief means" are data the report was given; report claims based on
  them are supported. Compare numbers carefully before calling one wrong or overstated.

Then list the concrete errors (most severe first, max 12). Precision matters more than
recall: list an error only if a careful reader checking the quoted lines would agree it is a
real error. Zero errors is a fine answer. Do NOT list:
- paraphrases, adjectives or wording choices in the report that are fair summaries of the log;
- plausible character choices you would have written differently;
- threads that are simply unfinished when the transcript ends;
- claims that something "never happens" unless you checked every day and can quote the line
  that makes its absence an error (e.g. the report line asserting it).

Each error needs "quotes": 1-3 strings copied VERBATIM from the transcript (exact characters,
10-200 chars each, each from a single line, no ellipses, no paraphrase, no added labels like
"Day 2:" or section names) that prove the error. For report_faithfulness,
the first quote must be the report sentence (or part of it) you dispute, and the others the
log/cast/graph text it contradicts. Errors whose quotes are not found verbatim are discarded.

Return STRICT JSON only:
{"scores": {"premise_fidelity": n, ...}, "errors": [{"dimension": "...", "severity": "...", "quotes": ["...", "..."], "evidence": "one sentence: why the quotes show an error"}], "summary": "two sentences"}
"""
JUDGE_SYSTEMS = {1: JUDGE_SYSTEM_V1, 2: JUDGE_SYSTEM_V2}


def judge_llm(transcript: str, model: str, version: int = 1) -> dict:
    out = _post_judge(JUDGE_SYSTEMS[version], transcript, model)
    if version >= 2 and "errors" in out:
        kept, out["dropped_errors"] = verify_quotes(out["errors"], transcript)
        out["errors"] = kept
    return out


def _norm(s: str) -> str:
    """Case/whitespace/quote-style-insensitive form for verbatim matching."""
    s = s.lower().replace("**", "").replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s).strip()


def verify_quotes(errors: list[dict], transcript: str) -> tuple[list[dict], list[dict]]:
    """Keep errors whose every quote appears verbatim in the transcript; report_faithfulness
    errors must also quote the final report itself. Returns (kept, dropped)."""
    full = _norm(transcript)
    report = _norm(transcript.split("## Final report", 1)[1]) if "## Final report" in transcript else ""
    kept, dropped = [], []
    for e in errors:
        qs = [q for q in e.get("quotes") or [] if isinstance(q, str)]
        # a quote spanning several transcript lines must match line by line
        parts = [[_norm(p) for p in q.splitlines() if p.strip()] for q in qs]
        ok = bool(qs) and all(ps and len(" ".join(ps)) >= 10 and all(p in full for p in ps) for ps in parts)
        if ok and e.get("dimension") == "report_faithfulness":
            ok = all(p in report for p in parts[0])
        (kept if ok else dropped).append(e)
    return kept, dropped


def _post_judge(system: str, user: str, model: str) -> dict:
    """One judge call returning parsed JSON, or {"error": ...} after retries."""
    base = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    key = os.getenv("OPENAI_COMPAT_API_KEY")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 5000,
        "temperature": 0,
    }
    err = None
    for attempt in range(4):
        try:
            r = httpx.post(f"{base}/chat/completions", json=payload,
                           headers={"Authorization": f"Bearer {key}"}, timeout=240)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"] or ""
            content = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", content.strip())
            start, end = content.find("{"), content.rfind("}")
            return json.loads(content[start:end + 1])
        except Exception as e:  # retry on transient/parse errors
            err = e
    return {"error": repr(err)}


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z']{4,}", s.lower()))


def deterministic(data: dict) -> dict:
    res = data["result"]
    world = data["world"]
    names = [a["name"] for a in world["agents"]]
    banned = [b.lower() for b in data["lens"].get("banned_vocabulary", []) if b]
    snaps = res["snapshots"]
    hls = [(s["day"], h) for s in snaps for h in s["highlights"]]
    n = max(1, len(hls))

    fallbacks = sum(1 for _, h in hls if h["summary"].startswith("I kept to myself today"))
    vetoes = sum(1 for s in snaps for l in s["event_log"] if l.startswith("[persona]"))

    # near-duplicate actions by the same actor anywhere in the run
    by_actor: dict[str, list[set[str]]] = {}
    dups = 0
    for _, h in hls:
        t = _tokens(h["summary"])
        prev = by_actor.setdefault(h["agent"], [])
        if any(len(t & p) / max(1, len(t | p)) > 0.55 for p in prev):
            dups += 1
        prev.append(t)

    # how concentrated the interactions are on one target
    targets = Counter()
    for s in snaps:
        for line in s["event_log"]:
            for nm in names:
                if nm in line and not line.startswith(f"[{nm}]"):
                    targets[nm] += 1
    top_share = (targets.most_common(1)[0][1] / max(1, sum(targets.values()))) if targets else 0

    text = " ".join(h["summary"] + " " + h["utterance"] for _, h in hls) + " " + (res.get("final_report") or "")
    banned_hits = sum(len(re.findall(rf"\b{re.escape(b)}\b", text.lower())) for b in banned)

    events = [e for s in snaps for e in s.get("events", [])]
    outcomes = Counter(e["outcome"] for e in events if e["outcome"])
    final_efforts = [f for a in snaps[-1]["agents"] for f in a.get("efforts", [])] if snaps else []
    return {
        "attempts": sum(outcomes.values()),
        "outcomes": dict(outcomes),
        "efforts": len(final_efforts),
        "efforts_open": sum(not f["done"] for f in final_efforts),
        "known_share": round(sum(len(e["known_by"]) for e in events)
                             / max(1, len(events) * len(names)), 3),
        "actions": n,
        "fallback_rate": round(fallbacks / n, 3),
        "veto_count": vetoes,
        "dup_action_rate": round(dups / n, 3),
        "top_target_share": round(top_share, 3),
        "banned_hits": banned_hits,
    }


def build_transcript(md_path: Path, version: int = 1) -> str:
    lines = md_path.read_text().splitlines()
    if version >= 2:
        # v2 keeps what characters actually said/did: reports cite it, and v1 flagged those
        # report claims as unsupported. Transcripts stay well under the 120k cap either way.
        lines = [_says(l) if l.startswith("- HL ") else l for l in lines]
    else:
        # keep the judge's input bounded; the highlights duplicate the log
        lines = [l for l in lines if not l.startswith("- HL ")]
    return "\n".join(lines)[:120_000]


def _says(hl: str) -> str:
    """'- HL Name: summary — outcome | says: words' -> '- SAYS Name: words'."""
    name = hl[5:].split(":", 1)[0]
    words = hl.split("| says:", 1)[1].strip() if "| says:" in hl else ""
    return f"- SAYS {name}: {words}"


def score_one(json_path: Path, model: str, version: int = 1) -> dict:
    data = json.loads(json_path.read_text())
    det = deterministic(data)
    llm = judge_llm(build_transcript(json_path.with_suffix(".md"), version), model, version)
    return {"run": json_path.stem, "judge_version": version, "det": det, "llm": llm}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--model", default="deepseek/deepseek-v3.2")
    ap.add_argument("--judge-version", type=int, choices=sorted(JUDGE_SYSTEMS), default=1)
    ap.add_argument("--out", help="write scores.json here instead of RUN_DIR (must not exist)")
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    paths = sorted(run_dir.glob("*.json"))
    paths = [p for p in paths if p.name != "scores.json" and not p.name.startswith("pairwise")]
    out_dir = run_dir
    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True)  # refuses to reuse an existing dir
        for p in paths:  # link transcripts so tools reading OUT_DIR find <run>.md
            for f in (p, p.with_suffix(".md")):
                (out_dir / f.name).symlink_to(f.resolve())
    with cf.ThreadPoolExecutor(6) as ex:
        results = list(ex.map(lambda p: score_one(p, args.model, args.judge_version), paths))
    (out_dir / "scores.json").write_text(json.dumps(results, indent=2))
    kept = sum(len(r["llm"].get("errors", [])) for r in results)
    dropped = sum(len(r["llm"].get("dropped_errors", [])) for r in results)
    print(f"judge v{args.judge_version}: {len(results)} calls, {kept} errors kept, {dropped} dropped by quote check")

    hdr = ["run"] + [d[:8] for d in DIMENSIONS] + ["avg", "fallbk", "dup", "veto", "topT", "ban"]
    print(" | ".join(f"{h:>9}" for h in hdr))
    totals: dict[str, list[float]] = {d: [] for d in DIMENSIONS + ["avg"]}
    det_tot: dict[str, list[float]] = {}
    for r in results:
        sc = r["llm"].get("scores", {})
        if not sc:
            print(f"{r['run']}: judge failed ({r['llm'].get('error')}) — excluded")
            continue
        vals = [float(sc.get(d, 0) or 0) for d in DIMENSIONS]
        avg = sum(vals) / len(vals)
        for d, v in zip(DIMENSIONS, vals):
            totals[d].append(v)
        totals["avg"].append(avg)
        det = r["det"]
        for k, v in det.items():
            det_tot.setdefault(k, []).append(v)
        row = [r["run"]] + [f"{v:.0f}" for v in vals] + [f"{avg:.2f}", det["fallback_rate"], det["dup_action_rate"],
                                                         det["veto_count"], det["top_target_share"], det["banned_hits"]]
        print(" | ".join(f"{str(c):>9}" for c in row))
    mean = lambda xs: sum(xs) / max(1, len(xs))
    row = ["MEAN"] + [f"{mean(totals[d]):.2f}" for d in DIMENSIONS] + [f"{mean(totals['avg']):.2f}"] + [
        f"{mean(det_tot.get(k, [0])):.3f}" for k in ["fallback_rate", "dup_action_rate", "veto_count", "top_target_share", "banned_hits"]]
    print(" | ".join(f"{str(c):>9}" for c in row))


if __name__ == "__main__":
    main()
