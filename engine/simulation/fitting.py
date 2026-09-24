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
