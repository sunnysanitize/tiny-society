from __future__ import annotations

import json
import logging
import re

from models import World, WorldGraph, WorldEntity, WorldRelationship

WORLD_GRAPH_SYSTEM = """WORLD_GRAPH_EXTRACTION
You build a compact factual knowledge graph for a multi-agent social simulation.
You are given a world premise (and optionally a prediction question). Extract the shared
ground truth every character should know. Return STRICT JSON only — no prose.

JSON schema:
{
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
- Output only JSON. No markdown, no commentary, no preamble.
"""


def extract_world_graph(world: World) -> WorldGraph:
    """One LLM call turning the world prompt (+ question) into shared ground truth.

    Mock-safe: the WORLD_GRAPH_EXTRACTION mock branch returns deterministic valid JSON.
    """
    from llm import call_llm

    user_parts = [f"WORLD PREMISE\n{world.prompt}"]
    if world.question:
        user_parts.append(f"\nPREDICTION QUESTION\n{world.question}")
    user_parts.append("\nReturn the knowledge graph as JSON now.")
    user = "\n".join(user_parts)

    try:
        raw = call_llm(WORLD_GRAPH_SYSTEM, user, json_mode=True, max_tokens=1024)
    except Exception as e:
        logging.warning(f"World graph extraction failed: {e}")
        return WorldGraph()

    data = _safe_json(raw)
    if not data:
        logging.warning(f"Empty/invalid world-graph JSON: {raw[:120]!r}")
        return WorldGraph()

    try:
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
        )
    except Exception as e:
        logging.warning(f"World graph parse error: {e}")
        return WorldGraph()


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
