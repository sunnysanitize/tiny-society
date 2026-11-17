"""Director — pacing and payoffs for the week.

The old engine dropped a random one-line "dynamic event" every 5 days; it rarely tied
into anything and was mostly ignored. Stories also opened questions they never closed.
Borrowing from RimWorld's storyteller (state-aware pacing on a tension curve), Façade's
drama manager (beats chosen against a target arc) and tabletop "fronts" (pressures that
advance on their own), the director runs once at the end of each day:

  - it keeps a ledger of open story threads and marks them resolved when the log shows it;
  - it rates today's tension against a rising target for the week;
  - when the story stalls or sits far below the target, it queues ONE complication for
    tomorrow — from the world (weather, an offstage person, a broken thing, a deadline),
    tied to an open thread, never dictating a cast member's choice;
  - in the last days it stops opening threads and names what is coming to a head, so
    the week converges instead of trailing off.
The queued complication becomes tomorrow's event and is cast like any other.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import EventCast, StoryThread, World, WorldEvent
from .premise import premise_lines

# Story length the tension curve is drawn over; day-by-day runs don't know their end,
# so the arc is fixed to the maximum week.
STORY_DAYS = 7
# Minimum days between complications, so the cast can react to each one.
COMPLICATION_GAP = 2
# From this many days before the end, no new threads: converge.
CLOSING_DAYS = 2
MAX_THREADS = 8

DIRECTOR_SYSTEM = """STORY_DIRECTOR
You are the story director of a week-long, multi-character simulation. You do not
control the characters. Once a day you read what happened and keep the story honest
and moving.

Return STRICT JSON only:
{
  "threads": [{"id": "T1", "summary": "one line: the open question", "status": "open|resolved"}],
  "tension": 1-5,
  "stalled": true|false,
  "complication": "one sentence, or \\"\\"",
  "coming_to_a_head": "one sentence, or \\"\\""
}

RULES:
- threads: keep existing ids; mark a thread resolved only when today's log settled it;
  add a thread only for a real new open question raised today (none in the closing days).
- tension: how charged today was (1 calm routine .. 5 crisis).
- stalled: true if characters are circling — repeating moves without anything changing.
- complication: ONLY if asked for below. It comes from the world — weather, an offstage
  person, an animal, a broken or found object, a deadline, news from outside — and it
  must press on an OPEN thread. It must not decide what any cast member does, feels or
  says, must not reveal hidden truths outright, and must fit the world's rules.
- coming_to_a_head: in the closing days, one sentence naming which open matters can no
  longer wait; otherwise "".
- Output only JSON.
"""


def tension_target(day: int) -> float:
    """Rising arc: ~2 at the start, ~4 by the last third, held there."""
    frac = min(1.0, day / (STORY_DAYS * 0.8))
    return 2.0 + 2.0 * frac


def direct(
    world: World,
    day: int,
    day_events: list[WorldEvent],
    cast: Optional[EventCast],
    world_premise: Optional[str] = None,
) -> None:
    """End-of-day pass. Updates world.threads / director_event / director_note in place."""
    from llm import call_llm

    closing = day >= STORY_DAYS - CLOSING_DAYS
    target = tension_target(day + 1)
    may_complicate = (not closing) and day - world.last_complication_day >= COMPLICATION_GAP
    open_threads = [t for t in world.threads if t.status == "open"]
    user = "\n".join([
        *premise_lines(world_premise),
        *( [f"WHAT EVERYONE KNOWS: {cast.public}", f"HIDDEN TRUTH (yours only): {cast.truth or '(none)'}"]
           if cast and (cast.public or cast.truth) else []),
        "",
        f"DAY {day} of {STORY_DAYS}" + (" — CLOSING DAYS: converge, open no new threads." if closing else ""),
        "THREADS SO FAR:",
        "\n".join(f"- {t.id} [{t.status}] {t.summary}" for t in world.threads) or "(none yet)",
        "",
        "TODAY'S LOG:",
        "\n".join(f"- {e.text}" for e in day_events[:40]) or "(quiet day)",
        "",
        (f"Tomorrow's target tension is {target:.1f}/5. If today ran well below it or the story "
         "stalled, write ONE complication; otherwise leave it empty.")
        if may_complicate else "Do NOT write a complication today (leave it empty).",
        "",
        "Return the director's notes as JSON now.",
    ])
    try:
        raw = call_llm(DIRECTOR_SYSTEM, user, json_mode=True, max_tokens=700, tier="strong")
    except Exception as e:
        logging.warning(f"Director call failed on day {day}: {e}")
        return
    data = _safe_json(raw)
    if not data:
        return

    _merge_threads(world, data.get("threads"), day, closing)
    tension = _num(data.get("tension"), 3.0)
    stalled = bool(data.get("stalled"))
    complication = str(data.get("complication") or "").strip().strip('"')[:240]
    # Code, not the model, decides whether a complication is warranted: the pacing rule.
    if may_complicate and complication and (stalled or tension < target - 0.5) and open_threads:
        world.director_event = complication
        world.last_complication_day = day + 1
        logging.info(f"Director queued a complication for day {day + 1}: {complication!r}")
    world.director_note = str(data.get("coming_to_a_head") or "").strip()[:240] if closing else ""


def _merge_threads(world: World, raw_threads, day: int, closing: bool) -> None:
    if not isinstance(raw_threads, list):
        return
    by_id = {t.id: t for t in world.threads}
    for item in raw_threads:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or "").strip()[:8]
        summary = str(item.get("summary") or "").strip()[:200]
        status = "resolved" if str(item.get("status")).lower() == "resolved" else "open"
        if not tid or not summary:
            continue
        if tid in by_id:
            t = by_id[tid]
            if t.status == "open" and status == "resolved":
                t.status, t.last_day = "resolved", day
        elif not closing and len(world.threads) < MAX_THREADS:
            t = StoryThread(id=tid, summary=summary, status=status, opened_day=day, last_day=day)
            world.threads.append(t)
            by_id[tid] = t


def _num(v, default: float) -> float:
    try:
        return max(1.0, min(5.0, float(v)))
    except (TypeError, ValueError):
        return default


def _safe_json(raw: str) -> dict:
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", raw.strip())
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
