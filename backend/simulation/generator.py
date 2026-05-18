from __future__ import annotations

import json
import uuid

from models import Agent, World
from llm import call_llm

FILLER_SYSTEM = """FILLER_AGENT_GENERATION
You generate fictional citizens for a multi-agent social simulation. Return STRICT JSON only.

Schema:
{
  "agents": [
    {
      "name": "string",
      "role": "string",
      "traits": ["string", ...],
      "goals": ["string", ...],
      "mood": "calm|excited|frustrated|heartbroken|ambitious|anxious|content|angry|hopeful|lonely|confident",
      "groups": ["string", ...]
    }
  ]
}

Rules:
- All characters are fictional. Do not use names of real public figures.
- 2-4 traits per agent. 1-2 goals. 1-2 group memberships.
- Vary personalities so the social dynamics will be interesting.
- Group names should align with the world prompt.
"""


def generate_fillers(world: World, count: int) -> list[Agent]:
    if count <= 0:
        return []
    existing_names = {a.name for a in world.agents}
    user = (
        f"World prompt:\n{world.prompt}\n\n"
        f"Generate {count} fictional agents that fit this world. "
        f"Avoid these existing names: {sorted(existing_names) or 'none'}."
    )
    raw = call_llm(FILLER_SYSTEM, user, json_mode=True, max_tokens=4096)
    data = _safe_json(raw)
    out: list[Agent] = []
    for entry in (data.get("agents") or [])[:count]:
        name = (entry.get("name") or "").strip() or f"Agent-{uuid.uuid4().hex[:4]}"
        if name in existing_names:
            name = f"{name}-{uuid.uuid4().hex[:3]}"
        existing_names.add(name)
        out.append(Agent(
            id=f"a_{uuid.uuid4().hex[:8]}",
            name=name,
            role=entry.get("role") or "citizen",
            traits=entry.get("traits") or [],
            goals=entry.get("goals") or [],
            mood=entry.get("mood") or "calm",
            groups=entry.get("groups") or [],
            is_custom=False,
        ))
    return out


def _safe_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    # Find the first { ... last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
