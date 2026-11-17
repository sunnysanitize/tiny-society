"""Event casting — bind an event to the people in the world, once.

Events are written about the world, not the cast: "two senior monks each claim the abbot
whispered their name", "someone has been secretly rationing oxygen". Left unbound, every
per-agent call resolved the ambiguity on its own, so the story contradicted itself —
nobody knew who the claimants were, the accused accepted guilt and then denounced the
thief, everyone interrogated the same bystander about "the whispers".

One strong-tier call reads the event against the cast and fixes:
  - public      : what everyone knows, naming the cast members involved;
  - truth       : the hidden facts (who really did it), for consistency only — never
                  shown to anyone who wouldn't know it;
  - involvement : per character, a first-person line of what they did or privately know.

Involvement is planted as a high-importance memory on the day the event begins, so the
culprit remembers doing it and the claimants remember their claim. A failed call leaves
an empty cast and the run proceeds exactly as before.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import Agent, EventCast
from .memory import make_memory
from .premise import premise_lines

EVENT_CASTING_SYSTEM = """EVENT_CASTING
You are the continuity editor of a multi-agent story. An event has just happened in the
world. Decide, once and for everyone, how it concretely involves the cast, so that every
character's later choices rest on the same facts.

Return STRICT JSON only:
{
  "public": "1-3 sentences: what everyone in the world now knows, naming the cast members involved",
  "truth": "1-2 sentences: the full hidden facts behind the event (who really did what), or '' if nothing is hidden",
  "involvement": {
    "Name": "one first-person past-tense sentence: what this character did, saw, or privately knows about the event"
  }
}

RULES:
- If the event refers to unnamed people ("two senior monks", "someone", "the star player"),
  assign those roles to specific cast members who fit them by role and traits. Use people
  outside the cast only if nobody in the cast fits; then name them as offstage figures.
- A hidden wrongdoer must be someone whose traits and goals make the act believable —
  never a character defined by honesty or generosity unless their memories give a reason.
- Secrets stay secret. "public" contains only what the world could know right now. A hidden
  culprit appears in "truth" and in their own involvement line, never in "public".
- Include an involvement line for EVERY cast member — for bystanders, say how they heard
  of it or what small thing they noticed. Never let a bystander know a secret.
- Stay within the event as written: do not resolve it, add deaths, or decide the outcome.
- Use only cast names exactly as given. Write in the world's own vocabulary.
- Output only JSON. No markdown, no commentary.
"""

# High enough to surface in retrieval for the rest of the run.
_INVOLVEMENT_IMPORTANCE = 9.0


def cast_event(
    event: str, agents: list[Agent], day: int, world_premise: Optional[str] = None,
) -> EventCast:
    """Bind `event` to `agents`. Always returns a cast (empty fields on failure)."""
    from llm import call_llm

    cast_lines = []
    for a in agents:
        rels = ", ".join(f"{n} ({r.type})" for n, r in a.relationships.items()) or "none"
        cast_lines.append(
            f"- {a.name}: {a.role}; traits: {', '.join(a.traits)}; "
            f"goals: {', '.join(a.goals)}; relationships: {rels}"
        )
    user = "\n".join([
        *premise_lines(world_premise),
        "CAST",
        "\n".join(cast_lines),
        "",
        "EVENT",
        event,
        "",
        "Return the casting as JSON now.",
    ])
    cast = EventCast(day=day)
    try:
        raw = call_llm(EVENT_CASTING_SYSTEM, user, json_mode=True, max_tokens=1200, tier="strong")
    except Exception as e:
        logging.warning(f"Event casting failed: {e}")
        return cast
    data = _safe_json(raw)
    if not data:
        logging.warning(f"Event casting returned no JSON: {raw[:120]!r}")
        return cast
    names = {a.name for a in agents}
    cast.public = str(data.get("public") or "").strip()[:600]
    cast.truth = str(data.get("truth") or "").strip()[:400]
    inv = data.get("involvement") if isinstance(data.get("involvement"), dict) else {}
    cast.involvement = {
        str(k): str(v).strip()[:300]
        for k, v in inv.items()
        if str(k) in names and isinstance(v, str) and v.strip()
    }
    return cast


def plant_involvement(cast: EventCast, agents: list[Agent]) -> None:
    """Give each character their own first-person memory of the event (idempotent)."""
    for a in agents:
        line = cast.involvement.get(a.name)
        if not line or any(m.text == line for m in a.long_term_memory):
            continue
        mem = make_memory(line, day=cast.day)
        mem.importance = max(mem.importance, _INVOLVEMENT_IMPORTANCE)
        a.long_term_memory.append(mem)


def render_event(event: Optional[str], cast: Optional[EventCast], day: int) -> Optional[str]:
    """The event as a character should see it on `day`: the public facts, and how old
    the news is, so day 4 doesn't react to day 1's event as if it just broke."""
    if not event:
        return event
    text = event
    if cast and cast.public:
        text = f"{event}\nWhat everyone knows: {cast.public}"
    if cast and cast.day and day > cast.day:
        ago = day - cast.day
        text = (
            f"(This began on day {cast.day}, {ago} day{'s' if ago > 1 else ''} ago. It is not "
            f"news anymore — act on where things stand now, given what has happened since.)\n"
            + text
        )
    return text


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
