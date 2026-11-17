"""Personality profiles — free-text traits turned into engine parameters.

Characters are written with free-text traits ("meticulous", "quietly vengeful"), which
the LLM reads well but the engine can't compute with. Mood baselines, how readily someone
gossips or keeps a secret, how far they'll move toward another's opinion, and what
they keep wanting all need numbers. One LLM call per cast estimates a Big Five +
honesty-humility profile, 2-3 stable desires, world-specific needs and a speaking voice
for every character who doesn't have one yet.

Where the call fails (or on the mock provider), a keyword heuristic fills the profile,
so every downstream consumer can rely on `agent.profile` being set.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import Agent, Profile
from .premise import premise_lines

PROFILE_SYSTEM = """PERSONALITY_PROFILING
You are a character psychologist. For each character, estimate a personality profile
from their role, traits, goals and memories, and describe how they talk.

Return STRICT JSON only:
{
  "profiles": {
    "Name": {
      "openness": 0.0-1.0, "conscientiousness": 0.0-1.0, "extraversion": 0.0-1.0,
      "agreeableness": 0.0-1.0, "neuroticism": 0.0-1.0,
      "honesty": 0.0-1.0,
      "desires": ["2-3 of: status, acceptance, power, independence, order, curiosity, vengeance, family, idealism, tranquility, honor, romance, saving"],
      "needs": ["0-2 needs specific to this world, e.g. 'faith', 'the hunt', 'clean air'"],
      "voice": "one line: how they speak (length, register, habits)",
      "speech_samples": ["2-3 short lines they might actually say, under 15 words each"]
    }
  }
}

RULES:
- Spread the numbers: these people differ. Avoid putting everyone near 0.5.
- honesty is HEXACO honesty-humility: high = keeps confidences, won't manipulate.
- Voices must be distinct from one another and fit the world. Speech samples are
  everyday lines, not speeches.
- Output only JSON.
"""

_KEYWORDS = {
    "openness": ({"curious", "creative", "idealistic", "visionary", "restless", "rebellious", "bold"},
                 {"traditional", "rigid", "cautious", "orthodox", "conservative", "dutiful"}),
    "conscientiousness": ({"meticulous", "disciplined", "dutiful", "organized", "perfectionistic", "methodical"},
                          {"impulsive", "careless", "reckless", "lazy", "chaotic"}),
    "extraversion": ({"charismatic", "social", "outgoing", "loud", "attention-seeking", "confident"},
                     {"introverted", "shy", "reserved", "withdrawn", "solitary", "quiet"}),
    "agreeableness": ({"kind", "compassionate", "loyal", "gentle", "people-pleasing", "nurturing"},
                      {"volatile", "bitter", "ruthless", "competitive", "vengeful", "abrasive"}),
    "neuroticism": ({"anxious", "volatile", "insecure", "paranoid", "defensive", "self-sabotaging"},
                    {"calm", "stoic", "steady", "serene", "confident"}),
    "honesty": ({"honest", "principled", "loyal", "compulsively honest", "humble"},
                {"manipulative", "calculating", "deceitful", "scheming", "vengeful"}),
}
_WORD_RE = re.compile(r"[a-z\-]+")


def profile_agents(agents: list[Agent], world_premise: Optional[str] = None) -> None:
    """Fill `profile` (and starting needs) for every agent that lacks one. In place."""
    missing = [a for a in agents if a.profile is None]
    if not missing:
        return
    from llm import call_llm

    lines = []
    for a in missing:
        mems = "; ".join(m.text for m in a.long_term_memory[:3])
        lines.append(f"- {a.name}: {a.role}; traits: {', '.join(a.traits)}; "
                     f"goals: {', '.join(a.goals)}; memories: {mems}")
    user = "\n".join([*premise_lines(world_premise), "CHARACTERS", *lines, "",
                      "Return the profiles as JSON now."])
    data: dict = {}
    try:
        data = _safe_json(call_llm(PROFILE_SYSTEM, user, json_mode=True,
                                   max_tokens=400 * len(missing), tier="cheap"))
    except Exception as e:
        logging.warning(f"Personality profiling failed, using trait keywords: {e}")
    found = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    for a in missing:
        a.profile = _from_json(found.get(a.name)) or heuristic_profile(a)
        from .needs import init_needs
        init_needs(a)


def heuristic_profile(agent: Agent) -> Profile:
    words: set[str] = set()
    for phrase in agent.traits + agent.revealed_traits:
        words |= set(_WORD_RE.findall(phrase.lower()))
        words.add(phrase.lower().strip())
    values = {}
    for dim, (pos, neg) in _KEYWORDS.items():
        values[dim] = round(min(0.9, max(0.1, 0.5 + 0.2 * len(words & pos) - 0.2 * len(words & neg))), 2)
    return Profile(**values)


def _from_json(d) -> Optional[Profile]:
    if not isinstance(d, dict):
        return None
    try:
        nums = {k: round(min(1.0, max(0.0, float(d.get(k, 0.5)))), 2)
                for k in ("openness", "conscientiousness", "extraversion",
                          "agreeableness", "neuroticism", "honesty")}
        return Profile(
            **nums,
            desires=[str(x)[:30] for x in (d.get("desires") or [])][:3],
            needs=[str(x)[:30] for x in (d.get("needs") or [])][:2],
            voice=str(d.get("voice") or "")[:160],
            speech_samples=[str(x)[:100] for x in (d.get("speech_samples") or [])][:3],
        )
    except (TypeError, ValueError):
        return None


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
