"""Pairwise comparison of two run directories (same scenarios and seeds).

Usage (from engine/):
    venv/bin/python -m tools.sim_eval.pairwise RUN_DIR_A RUN_DIR_B

Absolute 1-10 scores cluster at 6-8 and can't see small effects; judges are far more
reliable at "which of these two is better" (Zheng et al. 2023; Chhun et al. 2024).
Presentation order alternates across pairs so position bias cancels out.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
from pathlib import Path

from .judge import build_transcript, _post_judge

DIMENSIONS = ["overall", "causal_coherence", "event_grounding", "progression", "report_faithfulness"]

PAIR_SYSTEM = """You compare two generated multi-day stories from the same agent-based
simulation setup (same world premise and starting event, different runs) for ACCURACY
and REALISM: characters act on what they could know, the event is engaged concretely,
attempts lead somewhere, the story moves, and the final report matches the log.

For each dimension pick "1", "2" or "tie" (use tie only when truly indistinguishable):
- overall
- causal_coherence: actions follow from what each character could know and from prior events
- event_grounding: the starting event is engaged concretely and develops
- progression: efforts resolve, the story moves rather than looping
- report_faithfulness: the final report's claims are supported by the log

Return STRICT JSON only: {"overall": "1|2|tie", "causal_coherence": ..., "event_grounding": ...,
"progression": ..., "report_faithfulness": ..., "reason": "one sentence"}
"""

# Each story is trimmed so two fit comfortably in one judge call.
_MAX_STORY_CHARS = 45_000


def compare(a: Path, b: Path, flip: bool, model: str) -> dict:
    sa, sb = build_transcript(a)[:_MAX_STORY_CHARS], build_transcript(b)[:_MAX_STORY_CHARS]
    first, second = (sb, sa) if flip else (sa, sb)
    out = _post_judge(PAIR_SYSTEM, f"STORY 1\n{first}\n\n=====\n\nSTORY 2\n{second}", model)
    if "error" in out:
        return out
    # Map the judge's "1"/"2" back to arm A/B.
    mapped = {}
    for d in DIMENSIONS:
        v = str(out.get(d, "tie")).strip()
        if v in ("1", "2"):
            a_won = (v == "1") != flip
            mapped[d] = "A" if a_won else "B"
        else:
            mapped[d] = "tie"
    mapped["reason"] = out.get("reason", "")
    return mapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir_a")
    ap.add_argument("dir_b")
    ap.add_argument("--model", default="deepseek/deepseek-v3.2")
    args = ap.parse_args()
    da, db = Path(args.dir_a), Path(args.dir_b)
    names = sorted(p.stem for p in da.glob("*.md") if (db / p.name).exists())
    with cf.ThreadPoolExecutor(6) as ex:
        results = list(ex.map(
            lambda i_n: (i_n[1], compare(da / f"{i_n[1]}.md", db / f"{i_n[1]}.md", i_n[0] % 2 == 1, args.model)),
            enumerate(names)))
    (db / f"pairwise_vs_{da.name}.json").write_text(json.dumps(results, indent=2))
    ok = [r for _, r in results if "error" not in r]
    print(f"A = {da.name}   B = {db.name}   pairs judged: {len(ok)}/{len(results)}")
    for d in DIMENSIONS:
        wa = sum(r[d] == "A" for r in ok)
        wb = sum(r[d] == "B" for r in ok)
        n = wa + wb
        # Two-sided sign test on decisive pairs.
        p = sum(math.comb(n, k) for k in range(0, min(wa, wb) + 1)) * 2 / 2 ** n if n else 1.0
        print(f"{d:>20}: A {wa:2d}  B {wb:2d}  tie {len(ok) - n:2d}   sign-test p={min(1.0, p):.3f}")
    for name, r in results:
        print(f"  {name}: {r.get('overall', r.get('error'))} — {r.get('reason', '')[:140]}")


if __name__ == "__main__":
    main()
