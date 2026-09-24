"""Propose who an authored character IS inside this world — never decide it.

The point of the app is that you populate a world with people you actually care about:
your friends, people you know, characters you invented. Those descriptions are yours,
so nothing here writes to a world. `fit_character` returns a PROPOSAL the client shows
beside what the user typed; only an explicit accept turns it into an agent.

The split is load-bearing. Fitting touches role, groups, goals and memories — where a
person STANDS in a world. It never touches name, traits, mood or avatar — who the
person IS, and the thing the user came to watch get dropped into a world. Dave stays
stubborn and broke; 1340 decides what stubborn and broke look like.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import CharacterFit, CharacterInput, World
from .premise import render_premise

CHARACTER_FIT_SYSTEM = """CHARACTER_WORLD_FIT
You place an existing character into a world without changing who they are.

You are given a world and a character as their author wrote them. Propose what this
person's SITUATION would be in this world. Return STRICT JSON only — no prose.

{
  "role": "what they do here, specific and of this world",
  "groups": ["which groups of this world they belong to", ...],
  "goals": ["1-2 goals that are THEIR goals, expressed in this world's terms", ...],
  "starting_memories": ["1-3 first-person past-tense memories set in this world", ...],
  "note": "one sentence explaining the placement in terms of their given traits"
}

Rules:
- NEVER propose a different name, traits, mood or personality. Those are fixed. Your job
  is to find where a person with THOSE traits would stand in THIS world.
- The role must be specific to the world, never a generic label like "member".
- Goals must be recognisably the same person's goals, restated in this world's terms.
- Memories: first person, past tense, concrete, set in this world, hinting at friction
  with someone. Do not invent other characters' names unless given to you.
- Output only JSON. No markdown, no commentary, no preamble.
"""

_MAX_LIST = 4
_MAX_ITEM = 200


def fit_character(world: World, body: CharacterInput) -> CharacterFit:
    """One LLM call proposing this character's situation in this world. Writes nothing.

    Returns an empty CharacterFit with an explanatory `note` when the world has no lens
    or the call fails, so the caller can always render something and the user's own text
    is never at risk.
    """
    from llm import call_llm

    premise = render_premise(world.lens, world.prompt)
    if not premise.strip():
        return CharacterFit(note="This world has no description to fit the character to.")

    user = "\n".join([
        "WORLD",
        premise,
        "",
        "CHARACTER AS THEIR AUTHOR WROTE THEM",
        f"Name: {body.name}",
        f"Traits: {', '.join(body.traits) or '(none given)'}",
        f"Mood: {body.mood}",
        f"Role as typed: {body.role or '(blank)'}",
        f"Goals as typed: {', '.join(body.goals) or '(none)'}",
        f"Groups as typed: {', '.join(body.groups) or '(none)'}",
        "",
        "Propose their situation in this world as JSON now.",
    ])

    try:
        raw = call_llm(CHARACTER_FIT_SYSTEM, user, json_mode=True, max_tokens=600, tier="strong")
    except Exception as e:
        logging.warning(f"Character fit failed for {body.name}: {e}")
        return CharacterFit(note="A suggestion isn't available right now.")

    data = _safe_json(raw)
    if not data:
        return CharacterFit(note="A suggestion isn't available right now.")

    return CharacterFit(
        role=str(data.get("role") or "").strip()[:80],
        groups=_str_list(data.get("groups")),
        goals=_str_list(data.get("goals")),
        starting_memories=_str_list(data.get("starting_memories")),
        note=str(data.get("note") or "").strip()[:240],
    )


CHARACTER_SURPRISE_SYSTEM = """CHARACTER_SURPRISE
You invent ONE character who plainly belongs in the world you are given — someone a
reader would accept instantly as part of it. Return STRICT JSON only — no prose.

{
  "name": "a name that fits this world",
  "role": "specific and of this world, never a generic label",
  "traits": ["2-4 psychologically specific traits", ...],
  "goals": ["1-2 concrete goals", ...],
  "groups": ["1-2 groups of this world", ...],
  "mood": "calm|excited|frustrated|heartbroken|ambitious|anxious|content|angry|hopeful|lonely|confident",
  "starting_memories": ["1-2 first-person past-tense memories, specific and loaded", ...]
}

Rules:
- The name, role and groups must come from THIS world, not a generic modern one.
- Never reuse a name from EXISTING NAMES.
- Traits must be specific ("quietly vengeful", "people-pleasing"), not "nice" or "smart".
- Output only JSON. No markdown, no commentary, no preamble.
"""


def surprise_character(world: World) -> Optional[CharacterInput]:
    """Roll ONE world-appropriate character. Writes nothing; returns None on failure so
    the client can fall back to its own static pools rather than show an error."""
    from llm import call_llm
    from models import normalize_mood

    premise = render_premise(world.lens, world.prompt)
    if not premise.strip():
        return None

    existing = ", ".join(a.name for a in world.agents) or "(none)"
    user = "\n".join([
        "WORLD", premise, "",
        "EXISTING NAMES", existing, "",
        "Invent one character as JSON now.",
    ])

    try:
        raw = call_llm(CHARACTER_SURPRISE_SYSTEM, user, json_mode=True, max_tokens=500, tier="cheap")
    except Exception as e:
        logging.warning(f"Character surprise failed: {e}")
        return None

    data = _safe_json(raw)
    name = str(data.get("name") or "").strip()[:60]
    if not name:
        return None
    taken = {a.name.lower() for a in world.agents}
    if name.lower() in taken:
        name = f"{name} the younger"

    return CharacterInput(
        name=name,
        role=str(data.get("role") or "").strip()[:80] or "member",
        traits=_str_list(data.get("traits")),
        goals=_str_list(data.get("goals")),
        groups=_str_list(data.get("groups")),
        mood=normalize_mood(data.get("mood")),
        starting_memories=_str_list(data.get("starting_memories")),
        fitted_to_world=True,
    )


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip()[:_MAX_ITEM] for v in value if str(v or "").strip()][:_MAX_LIST]


def _safe_json(raw: str) -> dict:
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw).strip()
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}
