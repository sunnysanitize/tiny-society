from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import Agent
from llm import call_llm
from .memory import retrieve

# How many relevant long-term memories to ground the plan in.
_RETRIEVE_K = 3
# Max length of a stored plan sentence.
_MAX_PLAN_LEN = 200

PLANNER_SYSTEM = """PLAN_FORMATION
You are a single fictional character in a multi-agent social simulation.
Given your goals, current mood, a couple of recent memories, and the current world
event, state ONE concrete short-term intention — what you actually want to accomplish
soon to advance a goal. Not a vague wish: a specific, actionable next move.

Return STRICT JSON only — no prose, no markdown:
{
  "plan": "one first-person sentence stating a concrete short-term intention"
}

RULES:
- Exactly one sentence, first person, concrete and actionable.
- It must serve one of your goals given your current situation.
- Reference real people from your memories/relationships by name only if relevant; never invent names.
- Output only JSON. No commentary, no preamble.
"""


def form_plan(agent: Agent, world_event: Optional[str], current_day: int) -> Optional[str]:
    """Form a concrete short-term intention for the agent via ONE LLM call.

    Returns the plan string (also stored on the agent by the caller), or None on
    failure so the simulation continues unaffected.
    """
    user = _build_prompt(agent, world_event, current_day)
    try:
        raw = call_llm(PLANNER_SYSTEM, user, json_mode=True, max_tokens=256, tier="cheap")
    except Exception as e:
        logging.warning(f"Plan LLM call failed for agent {agent.name}: {e}")
        return None

    data = _safe_json(raw)
    plan = data.get("plan") if isinstance(data, dict) else None
    if not isinstance(plan, str):
        logging.warning(f"Empty/invalid plan JSON for agent {agent.name}: {raw[:100]!r}")
        return None
    plan = plan.strip()[:_MAX_PLAN_LEN]
    return plan or None


def _build_prompt(agent: Agent, world_event: Optional[str], current_day: int) -> str:
    query = " ".join(filter(None, [world_event or ""] + list(agent.goals)))
    retrieved = retrieve(agent.long_term_memory, query, current_day=current_day, k=_RETRIEVE_K)
    recent = list(agent.short_term_memory[-2:]) + list(retrieved)
    seen: set[str] = set()
    mem_lines: list[str] = []
    for m in recent:
        if m.text and m.text not in seen:
            seen.add(m.text)
            mem_lines.append(f"- {m.text}")

    parts = [
        "YOUR CHARACTER",
        f"Name: {agent.name}",
        f"Role: {agent.role}",
        f"Traits: {', '.join(agent.traits + agent.revealed_traits) or '(none)'}",
        f"Goals: {', '.join(agent.goals) or '(none)'}",
        f"Mood: {agent.mood}",
        "",
        "YOUR RECENT MEMORIES",
        "\n".join(mem_lines[:5]) or "(empty)",
        "",
        "CURRENT WORLD EVENT",
        world_event or "(no specific event today)",
        "",
        "State your single concrete short-term intention as JSON now.",
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
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}
