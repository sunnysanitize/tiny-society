from __future__ import annotations

import json
import logging
import re
import uuid

from models import Agent, World
from llm import call_llm
from .memory import make_memory
from . import consequence

FILLER_SYSTEM = """FILLER_AGENT_GENERATION
You generate fictional citizens for a multi-agent social simulation. Return STRICT JSON only.

Schema:
{
  "agents": [
    {
      "name": "string",
      "role": "string (specific, not generic)",
      "traits": ["string", ...],
      "goals": ["string", ...],
      "mood": "calm|excited|frustrated|heartbroken|ambitious|anxious|content|angry|hopeful|lonely|confident",
      "groups": ["string", ...],
      "memories": ["string", ...]
    }
  ]
}

Rules:
- All characters are fictional. Do not use real public figures.
- 3-4 traits per agent. 1-2 goals. 1-2 group memberships.
- 3-4 memories per agent in first-person past tense. Memories must reveal backstory,
  unresolved tensions, personal failures or wins, and hints of relationships with others.
  Make them specific and emotionally loaded — not generic.
- TRAIT DIVERSITY IS MANDATORY: Every agent in this batch must have a psychologically
  distinct profile. Do NOT reuse trait combinations across agents.
  Avoid overused combos: [ambitious+calculating], [loyal+honorable].
  Draw from a wide range including: defensive, self-sabotaging, avoidant, volatile,
  people-pleasing, paranoid, quietly vengeful, attention-seeking, compulsively honest,
  trauma-bonded, overconfident, secretly generous, bitter, martyrdom-prone,
  emotionally unavailable, idealistic-but-disappointed, ruthless-but-guilty.
- Roles must be specific and contextual to the world — not generic labels.
- Group names must fit the world prompt.
- Output only JSON. No markdown, no commentary.
"""

RELATIONSHIP_SEED_SYSTEM = """RELATIONSHIP_SEEDING
You are initializing the social graph for a multi-agent simulation.
Given a list of characters, generate 3-6 pre-existing relationships between specific pairs
whose traits and memories suggest prior history together.

Return STRICT JSON only:
{
  "relationships": [
    {
      "agent_a": "Name",
      "agent_b": "Name",
      "type": "friendship|rivalry|romance|trust|conflict|alliance|influence",
      "strength": 0.15 to 0.7,
      "mutual": true|false
    }
  ]
}

Rules:
- Only use names that appear in the character list.
- Mix positive and negative relationships — include at least one rivalry or conflict.
- strength 0.15–0.35 = early/fragile, 0.4–0.6 = established, 0.6–0.7 = deep/intense.
- mutual=false means only agent_a has this relationship view of agent_b (one-sided awareness).
- Each agent should appear in at most 2 relationships to avoid over-connecting one character.
- Output only JSON. No markdown, no commentary.
"""


BATCH_SIZE = 3  # agents per LLM call — smaller batches keep each response well within
                # the model's output budget (rich memories make 5 agents overflow / truncate)


def generate_fillers(world: World, count: int) -> list[Agent]:
    if count <= 0:
        return []
    existing_names = {a.name for a in world.agents}
    out: list[Agent] = []
    remaining = count

    while remaining > 0:
        batch = min(BATCH_SIZE, remaining)
        entries = _fetch_batch(world, batch, existing_names)
        for entry in entries:
            name = (entry.get("name") or "").strip() or f"Agent-{uuid.uuid4().hex[:4]}"
            if name in existing_names:
                name = f"{name}-{uuid.uuid4().hex[:3]}"
            existing_names.add(name)
            raw_memories = entry.get("memories") or []
            # Backstory memories exist from before the sim (day 0). Heuristic importance.
            memories = [make_memory(str(m), day=0) for m in raw_memories if str(m).strip()]
            out.append(Agent(
                id=f"a_{uuid.uuid4().hex[:8]}",
                name=name,
                role=entry.get("role") or "citizen",
                traits=entry.get("traits") or [],
                goals=entry.get("goals") or [],
                mood=entry.get("mood") or "calm",
                groups=entry.get("groups") or [],
                short_term_memory=[m.model_copy() for m in memories],
                long_term_memory=[m.model_copy() for m in memories],
                is_custom=False,
            ))
            remaining -= 1
            if remaining <= 0:
                break

    _seed_relationships(out, world.prompt)
    return out


def _fetch_batch(world: World, count: int, existing_names: set[str]) -> list[dict]:
    user = (
        f"World prompt:\n{world.prompt}\n\n"
        f"Generate {count} fictional agents that fit this world. "
        f"Avoid these existing names: {sorted(existing_names) or 'none'}."
    )
    try:
        raw = call_llm(FILLER_SYSTEM, user, json_mode=True, max_tokens=4096, tier="cheap")
        logging.info(f"Filler batch LLM raw ({len(raw)} chars): {raw[:120]!r}")
        data = _safe_json(raw)
        if not data.get("agents"):
            raise ValueError("empty agents list")
        return (data.get("agents") or [])[:count]
    except Exception as e:
        logging.warning(f"LLM filler batch failed ({e}), using mock fallback")
        from llm import _mock
        raw = _mock(FILLER_SYSTEM, user, json_mode=True)
        data = _safe_json(raw)
        return (data.get("agents") or [])[:count]


def _seed_relationships(agents: list[Agent], world_prompt: str) -> None:
    """Ask the LLM to generate initial relationship pairs and apply them to the agents."""
    if len(agents) < 2:
        return

    summaries = "\n".join(
        f"- {a.name}: {a.role} | traits: {', '.join(a.traits[:3])} "
        f"| last memory: {a.long_term_memory[-1].text[:100] if a.long_term_memory else 'none'}"
        for a in agents
    )
    user = (
        f"World: {world_prompt}\n\n"
        f"Characters:\n{summaries}\n\n"
        f"Generate 3-6 pre-existing relationships between these characters."
    )

    name_map = {a.name: a for a in agents}

    try:
        raw = call_llm(RELATIONSHIP_SEED_SYSTEM, user, json_mode=True, max_tokens=1024, tier="cheap")
        data = _safe_json(raw)
        for rel in (data.get("relationships") or []):
            a_name = rel.get("agent_a", "")
            b_name = rel.get("agent_b", "")
            a = name_map.get(a_name)
            b = name_map.get(b_name)
            if not a or not b or a_name == b_name:
                continue
            rel_type = rel.get("type", "trust")
            strength = float(rel.get("strength", 0.25))
            strength = max(0.1, min(0.7, strength))
            mutual = bool(rel.get("mutual", True))
            # Seed via the consequence layer so the affinity carries the correct SIGN for
            # its type (a seeded rivalry/conflict is negative) and survives `realize`.
            consequence.seed_relationship(a, b, rel_type, strength, mutual)
        logging.info(f"Seeded relationships for {len(agents)} agents")
    except Exception as e:
        logging.warning(f"Relationship seeding failed: {e}")


def _safe_json(raw: str) -> dict:
    if not raw:
        return {}
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw)
    raw = raw.strip()

    # Try parsing the whole thing first
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
        if isinstance(result, list):
            return {"agents": result}
    except json.JSONDecodeError:
        pass

    # Find outermost { ... } (handles preamble text before the JSON)
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        try:
            result = json.loads(raw[start:end + 1])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Fallback: bare array
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1:
        try:
            return {"agents": json.loads(raw[start:end + 1])}
        except json.JSONDecodeError:
            pass

    # Salvage: the response was truncated mid-JSON (common with small/free models or
    # reasoning models). Recover every COMPLETE agent object that arrived before the
    # cutoff so we still get usable characters instead of falling back to mock.
    salvaged = _salvage_objects(raw)
    if salvaged:
        logging.warning(f"_safe_json salvaged {len(salvaged)} complete object(s) from truncated JSON")
        return {"agents": salvaged}

    logging.warning(f"_safe_json could not parse ({len(raw)} chars): {raw[:200]!r}")
    return {}


def _salvage_objects(raw: str) -> list[dict]:
    """Extract every balanced {...} that parses as a dict with a 'name' field.

    A truncated array like `{"agents":[{...},{...},{partial...` leaves the complete
    agent objects intact (they closed) while the outer object never closes — so we
    recover the finished agents and drop the partial tail.
    """
    objs: list[dict] = []
    stack: list[int] = []
    in_str = esc = False
    for i, ch in enumerate(raw):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            frag = raw[stack.pop():i + 1]
            try:
                d = json.loads(frag)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and "name" in d:
                objs.append(d)
    return objs
