from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import Agent, Memory
from llm import call_llm
from .memory import retrieve

# Importance assigned to reflection-derived insights. High (out of 10) so they
# dominate later relevance+recency+importance retrieval, per the Stanford
# "Generative Agents" reflection design.
REFLECTION_IMPORTANCE = 9.0

# How many recent/relevant memories to feed the synthesis call.
_RECENT_SHORT_TERM = 4
_RETRIEVE_K = 10

REFLECTOR_SYSTEM = """REFLECTION_SYNTHESIS
You are a single fictional character in a multi-agent social simulation.
You are pausing to reflect on your recent experiences. Given a list of your recent
memories, name 1-3 higher-level realizations about yourself or your relationships —
the kind of belief a person forms after several related experiences (e.g. from
several conflicts: "I avoid confrontation when it matters to me").

Return STRICT JSON only — no prose, no markdown:
{
  "insights": ["first-person realization sentence", "..."]
}

RULES:
- Each insight is one first-person sentence, a synthesized belief — NOT a restatement
  of a single memory.
- 1 to 3 insights. Fewer is fine if little has happened.
- Reference real people from the memories by name when relevant; never invent names.
- Output only JSON. No commentary, no preamble.
"""


def reflect(agent: Agent, current_day: int) -> list[Memory]:
    """Synthesize 1-3 high-level insights from the agent's recent memories.

    Makes one LLM call, parses strict JSON, and appends the resulting insights to
    `agent.long_term_memory` as high-importance Memory objects dated `current_day`.
    Returns the list of new reflection memories (possibly empty).
    """
    memories = _gather_recent(agent, current_day)
    if not memories:
        return []

    user = _build_prompt(agent, memories)
    try:
        raw = call_llm(REFLECTOR_SYSTEM, user, json_mode=True, max_tokens=512, tier="strong")
    except Exception as e:
        logging.warning(f"Reflection LLM call failed for agent {agent.name}: {e}")
        return []

    data = _safe_json(raw)
    insights = data.get("insights") if isinstance(data, dict) else None
    if not isinstance(insights, list):
        logging.warning(f"Empty/invalid reflection JSON for agent {agent.name}: {raw[:100]!r}")
        return []

    existing_texts = {m.text for m in agent.long_term_memory}
    new_memories: list[Memory] = []
    for ins in insights[:3]:
        text = str(ins).strip()[:280]
        if not text or text in existing_texts:
            continue
        mem = Memory(
            text=text,
            importance=REFLECTION_IMPORTANCE,
            day=current_day,
            last_accessed_day=current_day,
        )
        agent.long_term_memory.append(mem)
        existing_texts.add(text)
        new_memories.append(mem)

    # Keep long-term memory bounded the same way the morning promotion does, but
    # protect the freshly-minted reflections by capping after appending.
    if len(agent.long_term_memory) > 40:
        agent.long_term_memory = agent.long_term_memory[-40:]

    return new_memories


def _gather_recent(agent: Agent, current_day: int) -> list[Memory]:
    """Recent short-term + a relevance/recency pull from long-term, de-duplicated."""
    pool: list[Memory] = list(agent.short_term_memory[-_RECENT_SHORT_TERM:])

    # Query the agent's long-term memory using its relationship names + recent
    # short-term text, so the retrieval surfaces what's been on their mind.
    query = " ".join(
        list(agent.relationships.keys())
        + [m.text for m in agent.short_term_memory[-_RECENT_SHORT_TERM:]]
    )
    retrieved = retrieve(agent.long_term_memory, query, current_day=current_day, k=_RETRIEVE_K)

    seen = {m.text for m in pool}
    for m in retrieved:
        if m.text not in seen:
            pool.append(m)
            seen.add(m.text)
    return pool


def _build_prompt(agent: Agent, memories: list[Memory]) -> str:
    rel_lines = [
        f"  - {name}: {r.type} (strength {r.strength:+.2f})"
        for name, r in agent.relationships.items()
    ]
    parts = [
        "YOUR CHARACTER",
        f"Name: {agent.name}",
        f"Role: {agent.role}",
        f"Traits: {', '.join(agent.traits + agent.revealed_traits) or '(none)'}",
        f"Goals: {', '.join(agent.goals) or '(none)'}",
        f"Mood: {agent.mood}",
        "",
        "YOUR RELATIONSHIPS",
        "\n".join(rel_lines) if rel_lines else "(none yet)",
        "",
        "YOUR RECENT MEMORIES",
        "\n".join(f"- {m.text}" for m in memories) or "(empty)",
        "",
        "Reflect and return your insights as JSON now.",
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
