"""Game master — attempts get outcomes, efforts get endings.

Characters used to propose actions that nothing ever resolved: a search, a hunt or an
investigation was re-attempted every day and never succeeded or failed, so stories
stalled and the report had nothing concrete to say. Following DeepMind Concordia's
game-master pattern, an agent now only PROPOSES; this module decides what came of it.

Two phases, so outcomes stay both plausible and unbiased:
  1. judge (LLM, runs in parallel with other agents' reasoning): rate difficulty and
     the actor's competence, and write every possible result up front — success,
     partial, failure, plus how a multi-day effort finishes or falls apart — and say
     who would learn of it. Writing all branches before the roll keeps the LLM from
     simply granting success.
  2. settle (code, sequential, seeded): roll against difficulty vs competence, pick the
     branch, and advance the agent's progress clock (models.Effort). Clocks force a
     conclusion after MAX_EFFORT_ATTEMPTS tries, so nothing drags on forever.

The game master is the narrator, not a character: it may read the event's hidden truth
(to decide what a successful search actually finds) but its output only reaches the
characters it names as aware.
"""
from __future__ import annotations

import json
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Optional

from models import Agent, AgentAction, Effort, EventCast
from .premise import premise_lines

GAME_MASTER_SYSTEM = """GAME_MASTER_ADJUDICATION
You are the game master of a multi-character story. A character has just ATTEMPTED
something whose result is not theirs to decide. Judge it, and write what each possible
result would concretely be. A die roll you don't control picks the result afterwards,
so write every branch as if it were the one that happens.

Return STRICT JSON only:
{
  "difficulty": 1-5,          // how hard this is here, in this world, today
  "competence": 1-5,          // how suited THIS character is (role, traits, situation)
  "size": "single|short|long",// single = settled today; short/long = takes several days of effort
  "effort": "short name of the undertaking (reuse an ONGOING EFFORT's exact name if this continues it)",
  "success": "what concretely happens if it goes well",
  "partial": "what concretely happens if it half-works (progress, at a cost, or an incomplete find)",
  "failure": "what concretely happens if it fails — a setback or complication, not just 'nothing'",
  "completion": "if this effort is finished now: the concrete end result",
  "collapse": "if this effort has to be given up now: how it concretely falls apart",
  "aware": ["names of OTHER cast members who would learn the result today"]
}

RULES:
- Concrete, never vague: say exactly what is found, caught, mended, lost or learned.
  Never "something", "a clue", "signs of".
- Decide only the world: objects, places, animals, weather, records, bodies, offstage
  people. NEVER decide what another cast member feels, says, chooses, does or agrees to —
  another character may NOTICE something, but how they respond is theirs to decide later.
- Uncovering the HIDDEN TRUTH is hard and gradual (difficulty 4-5, size "long"). On
  success or partial, an investigation finds ONE concrete clue that points toward the
  truth without proving it — a detail, an inconsistency, an object — never the full
  answer or the culprit's name outright. Only "completion" may establish the truth
  plainly. Failure finds nothing true, or a misleading lead. Never reveal it to an
  attempt that isn't looking for it.
- EVERY branch must be consistent with the hidden truth. If the character suspects the
  wrong person or thing, success and completion show the suspicion doesn't hold (or point
  toward what really happened) — they never "prove" something the truth says is false.
- Size it honestly: investigations, hunts, repairs, cures, building, winning someone
  over to a cause and other undertakings that take real time are "short" or "long";
  "single" is for things settled in one go (grab, hide, check one fact, one errand).
- Don't settle the central conflict, kill anyone or end the story outside a completion.
- "aware": only people present, told, or who'd plainly notice. Usually 0-2 people.
- One sentence per branch, third person, past tense, in the world's own vocabulary.
- Output only JSON.
"""

# Segments per effort size, Blades-in-the-Dark style progress clocks.
# A success fills 2, so "short" takes two good days and "long" at least three.
_SEGMENTS = {"single": 0, "short": 3, "long": 5}
# Ticks a result puts on the clock.
_TICKS = {"success": 2, "partial": 1, "failure": 0}
# An effort is forced to finish or collapse on this many attempts.
MAX_EFFORT_ATTEMPTS = 3
# Base success probability at equal difficulty and competence, and the shift per step.
_BASE_P = 0.55
_STEP_P = 0.12


@dataclass
class Adjudication:
    difficulty: int
    competence: int
    size: str
    effort: str
    branches: dict[str, str]
    aware: list[str] = field(default_factory=list)


@dataclass
class Settlement:
    outcome: str             # success | partial | failure | completed | collapsed
    text: str
    effort: str = ""
    aware: list[str] = field(default_factory=list)


def judge_attempt(
    actor: Agent,
    action: AgentAction,
    roster: list[Agent],
    *,
    cast: Optional[EventCast] = None,
    recent: Optional[list[str]] = None,
    world_premise: Optional[str] = None,
) -> Optional[Adjudication]:
    """Phase 1: one LLM call. None when there's nothing to resolve or the call fails."""
    if not action.attempt:
        return None
    from llm import call_llm

    user = _build_prompt(actor, action, roster, cast, recent or [], world_premise)
    try:
        raw = call_llm(GAME_MASTER_SYSTEM, user, json_mode=True, max_tokens=700, tier="cheap")
    except Exception as e:
        logging.warning(f"Game master call failed for {actor.name}: {e}")
        return None
    return _parse(raw, actor, roster)


def settle(adj: Adjudication, actor: Agent, day: int, rng: random.Random) -> Settlement:
    """Phase 2: deterministic roll + progress clock. Mutates actor.efforts."""
    p = min(0.9, max(0.1, _BASE_P + _STEP_P * (adj.competence - adj.difficulty)))
    r = rng.random()
    if r < p:
        result = "success"
    elif r < p + (1 - p) / 2:
        result = "partial"
    else:
        result = "failure"

    segments = _SEGMENTS.get(adj.size, 0)
    if not segments or not adj.effort:
        return Settlement(result, adj.branches[result], aware=adj.aware)

    eff = _find_effort(actor, adj.effort)
    if eff is None:
        eff = Effort(name=adj.effort, segments=segments, opened_day=day)
        actor.efforts.append(eff)
    eff.attempts += 1
    eff.filled = min(eff.segments, eff.filled + _TICKS[result])

    if eff.filled >= eff.segments:
        eff.done = True
        return Settlement("completed", adj.branches.get("completion") or adj.branches[result],
                          eff.name, adj.aware)
    if eff.attempts >= MAX_EFFORT_ATTEMPTS:
        # Out of road: past halfway it lands (imperfectly), otherwise it falls apart.
        eff.done = True
        if eff.filled * 2 >= eff.segments:
            return Settlement("completed", adj.branches.get("completion") or adj.branches["partial"],
                              eff.name, adj.aware)
        return Settlement("collapsed", adj.branches.get("collapse") or adj.branches["failure"],
                          eff.name, adj.aware)
    return Settlement(result, adj.branches[result], eff.name, adj.aware)


def open_efforts(actor: Agent) -> list[Effort]:
    return [e for e in actor.efforts if not e.done]


def _find_effort(actor: Agent, name: str) -> Optional[Effort]:
    key = _norm(name)
    for e in open_efforts(actor):
        if _norm(e.name) == key:
            return e
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", (s or "").lower()).strip()


def _build_prompt(
    actor: Agent, action: AgentAction, roster: list[Agent], cast: Optional[EventCast],
    recent: list[str], world_premise: Optional[str],
) -> str:
    efforts = open_efforts(actor)
    parts = [
        *premise_lines(world_premise),
        "CAST: " + ", ".join(f"{a.name} ({a.role})" for a in roster),
        "",
    ]
    if cast and (cast.public or cast.truth):
        parts += [f"WHAT EVERYONE KNOWS: {cast.public}",
                  f"HIDDEN TRUTH (narrator only): {cast.truth or '(nothing hidden)'}", ""]
    parts += [
        "RECENT EVENTS",
        "\n".join(f"- {line}" for line in recent[-10:]) or "(none)",
        "",
        "THE CHARACTER",
        f"{actor.name}, {actor.role}; traits: {', '.join(actor.traits) or '(none)'}",
        "ONGOING EFFORTS: " + ("; ".join(
            f"'{e.name}' ({e.filled}/{e.segments} done, attempt {e.attempts + 1} of {MAX_EFFORT_ATTEMPTS})"
            for e in efforts) or "(none)"),
        "",
        "THE ATTEMPT",
        f"Trying to: {action.attempt}",
        f"What they did: {action.new_memory or action.action}",
        f"Where / who was around: {action.audience.who or '(unspecified)'}",
        f"With: {', '.join(action.target_agents) or '(alone)'}",
        "",
        "Return the adjudication as JSON now.",
    ]
    return "\n".join(parts)


def _parse(raw: str, actor: Agent, roster: list[Agent]) -> Optional[Adjudication]:
    data = _safe_json(raw)
    branches = {k: str(data.get(k) or "").strip()[:300]
                for k in ("success", "partial", "failure", "completion", "collapse")}
    if not all(branches[k] for k in ("success", "partial", "failure")):
        logging.warning(f"Game master gave no usable branches for {actor.name}: {raw[:120]!r}")
        return None
    names = {a.name for a in roster} - {actor.name}
    aware = [str(n) for n in (data.get("aware") or []) if str(n) in names]
    size = str(data.get("size") or "single").strip().lower()
    return Adjudication(
        difficulty=_level(data.get("difficulty")),
        competence=_level(data.get("competence")),
        size=size if size in _SEGMENTS else "single",
        effort=str(data.get("effort") or "").strip()[:80],
        branches=branches,
        aware=aware,
    )


def _level(v) -> int:
    try:
        return max(1, min(5, int(v)))
    except (TypeError, ValueError):
        return 3


def _safe_json(raw: str) -> dict:
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
