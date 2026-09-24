from __future__ import annotations

import json
import logging
import re

from models import World, WorldGraph, WorldEntity, WorldRelationship, WorldLens

WORLD_GRAPH_SYSTEM = """WORLD_GRAPH_EXTRACTION
You build a compact factual knowledge graph for a multi-agent social simulation.
You are given a world premise (and optionally a prediction question). Extract the shared
ground truth every character should know. Return STRICT JSON only — no prose.

JSON schema:
{
  "lens": {
    "premise_summary": "2-3 sentences restating the premise concretely",
    "actor_noun": "what ONE participant is called here (brother, deckhand, nation)",
    "actor_noun_plural": "the plural",
    "collective_noun": "what the whole group is called (the house, the crew)",
    "affordances": ["what is and is not possible here — travel, contact, scarcity", ...],
    "gathering_places": ["named places where these people actually meet", ...],
    "register_notes": "one or two sentences on how narration should sound here",
    "banned_vocabulary": ["words that would break this world if they appeared", ...],
    "central_stake": "the one thing everyone is contending over"
  },
  "entities": [
    {"name": "string", "kind": "person|place|institution|resource|stake|event", "description": "short"}
  ],
  "relationships": [
    {"source": "EntityName", "target": "EntityName", "relation": "short verb phrase"}
  ],
  "power_structures": ["string describing who controls/decides what", ...],
  "topics": ["short stance axis the society divides on", ...]
}

Rules:
- 3-8 entities (key places, institutions, resources, and the central stake).
- 2-6 relationships between those entities.
- 1-3 power_structures (who holds authority / controls the stake).
- 3-6 topics: SHORT contested axes (a few words each) the population will take sides on,
  derived from the premise and the question if given. These are stance axes, not questions.
- lens.affordances: 2-5 entries — how word travels, what cannot be known, what is scarce.
  This is what keeps the fiction inside the world.
- lens.gathering_places: 2-5 concrete places, named as people in this world would name them.
- lens.banned_vocabulary: 3-8 words belonging to a DIFFERENT setting. Always include
  generic organizational filler ("team-building", "stakeholder", "strategic discussions",
  "holistic") unless the world is literally a modern workplace.
- Lens fields must be terse. Use empty strings/lists where the premise is too thin.
- Output only JSON. No markdown, no commentary, no preamble.
"""


def extract_world_context(world: World) -> tuple[WorldGraph, WorldLens]:
    """One LLM call turning the world prompt (+ question) into shared ground truth
    (`WorldGraph`) and the register it must be written in (`WorldLens`).

    Mock-safe: the WORLD_GRAPH_EXTRACTION mock branch returns deterministic valid JSON.
    """
    from llm import call_llm

    user_parts = [f"WORLD PREMISE\n{world.prompt}"]
    if world.question:
        user_parts.append(f"\nPREDICTION QUESTION\n{world.question}")
    user_parts.append("\nReturn the knowledge graph as JSON now.")
    user = "\n".join(user_parts)

    try:
        raw = call_llm(WORLD_GRAPH_SYSTEM, user, json_mode=True, max_tokens=1024, tier="strong")
    except Exception as e:
        logging.warning(f"World graph extraction failed: {e}")
        return WorldGraph(), WorldLens()

    data = _safe_json(raw)
    if not data:
        logging.warning(f"Empty/invalid world-graph JSON: {raw[:120]!r}")
        return WorldGraph(), WorldLens()

    try:
        lens_data = data.get("lens") if isinstance(data.get("lens"), dict) else {}
        lens = WorldLens(
            premise_summary=_str(lens_data.get("premise_summary"), 600),
            actor_noun=_str(lens_data.get("actor_noun"), 40),
            actor_noun_plural=_str(lens_data.get("actor_noun_plural"), 60),
            collective_noun=_str(lens_data.get("collective_noun"), 60),
            affordances=_str_list(lens_data.get("affordances"), 120, 6),
            gathering_places=_str_list(lens_data.get("gathering_places"), 120, 6),
            register_notes=_str(lens_data.get("register_notes"), 300),
            banned_vocabulary=_str_list(lens_data.get("banned_vocabulary"), 60, 8),
            central_stake=_str(lens_data.get("central_stake"), 160),
        )
        entities = [
            WorldEntity(
                name=str(e.get("name", "")).strip()[:80],
                kind=str(e.get("kind", "entity")).strip()[:30] or "entity",
                description=str(e.get("description", "")).strip()[:200],
            )
            for e in (data.get("entities") or [])
            if isinstance(e, dict) and str(e.get("name", "")).strip()
        ][:12]
        relationships = [
            WorldRelationship(
                source=str(r.get("source", "")).strip()[:80],
                target=str(r.get("target", "")).strip()[:80],
                relation=str(r.get("relation", "related to")).strip()[:60] or "related to",
            )
            for r in (data.get("relationships") or [])
            if isinstance(r, dict) and str(r.get("source", "")).strip() and str(r.get("target", "")).strip()
        ][:12]
        power_structures = [
            str(p).strip()[:160] for p in (data.get("power_structures") or []) if str(p).strip()
        ][:6]
        topics = [
            str(t).strip()[:60] for t in (data.get("topics") or []) if str(t).strip()
        ][:6]
        return WorldGraph(
            entities=entities,
            relationships=relationships,
            power_structures=power_structures,
            topics=topics,
        ), lens
    except Exception as e:
        logging.warning(f"World graph parse error: {e}")
        return WorldGraph(), WorldLens()


def extract_world_graph(world: World) -> WorldGraph:
    """Back-compat wrapper: the graph alone, for callers that predate the lens."""
    graph, _lens = extract_world_context(world)
    return graph


def _str(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _str_list(value: object, item_limit: int, count: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip()[:item_limit] for v in value if str(v or "").strip()][:count]


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
