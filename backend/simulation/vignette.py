from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import Agent
from llm import call_llm

VIGNETTE_SYSTEM = """VIGNETTE_GENERATION
You are a single fictional character in a multi-agent social simulation, having a
small theatrical moment. Given your character profile, recent mood, and the current
world event, produce ONE short, flavorful, first-person moment — a dream you had, a
catchphrase you blurt out, or a dramatic announcement you make. Make it charming,
surprising, and true to the character (Tomodachi-Life energy).

Return STRICT JSON only — no prose, no markdown:
{
  "kind": "dream" | "catchphrase" | "announcement",
  "text": "one short first-person line, under 30 words"
}

RULES:
- One line, first person, under 30 words. Punchy and theatrical.
- Pick the kind that best fits the character's mood and the moment.
- Output only JSON. No commentary, no preamble.
"""


def maybe_generate_vignette(
    agent: Agent,
    world_event: Optional[str],
    current_day: int,
) -> Optional[str]:
    """Produce a short theatrical first-person moment for `agent`, or None on failure.

    Gating (whether/how often to call this) is the CALLER's responsibility — the engine
    caps vignettes per day. This function performs exactly one LLM call and returns the
    vignette text (the structured kind+text is parsed; this returns just the text for
    convenience). Use `generate_vignette_struct` if you need the kind too.
    """
    result = generate_vignette_struct(agent, world_event, current_day)
    return result[1] if result else None


def generate_vignette_struct(
    agent: Agent,
    world_event: Optional[str],
    current_day: int,
) -> Optional[tuple[str, str]]:
    """One LLM call → (kind, text) or None on failure. kind ∈ dream|catchphrase|announcement."""
    user = _build_prompt(agent, world_event, current_day)
    try:
        raw = call_llm(VIGNETTE_SYSTEM, user, json_mode=True, max_tokens=160)
    except Exception as e:
        logging.warning(f"Vignette LLM call failed for agent {agent.name}: {e}")
        return None

    data = _safe_json(raw)
    if not isinstance(data, dict):
        return None
    text = str(data.get("text", "")).strip()[:240]
    if not text:
        return None
    kind = str(data.get("kind", "announcement")).strip().lower()
    if kind not in ("dream", "catchphrase", "announcement"):
        kind = "announcement"
    return kind, text


def _build_prompt(agent: Agent, world_event: Optional[str], current_day: int) -> str:
    parts = [
        "YOUR CHARACTER",
        f"Name: {agent.name}",
        f"Role: {agent.role}",
        f"Traits: {', '.join(agent.traits + agent.revealed_traits) or '(none)'}",
        f"Goals: {', '.join(agent.goals) or '(none)'}",
        f"Mood: {agent.mood}",
        "",
        "CURRENT WORLD EVENT",
        world_event or "(none)",
        "",
        f"DAY {current_day}. Have your theatrical moment and return it as JSON now.",
    ]
    return "\n".join(parts)


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
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}
