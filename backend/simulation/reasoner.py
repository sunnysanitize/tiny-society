from __future__ import annotations

import json
from typing import Optional

from models import Agent, AgentAction, RelationshipEffect
from llm import call_llm

REASONER_SYSTEM = """AGENT_REASONING
You are a single fictional character in a multi-agent social simulation.
You will be given your own personality, memories, relationships, and the current world event.
Reason about what your character would do today, then return STRICT JSON only — no prose.

JSON schema:
{
  "action": "short verb phrase (e.g. 'confront', 'befriend', 'comfort', 'gossip about')",
  "target_agents": ["Name", ...],   // one or more agents you act on (use existing names from the roster)
  "emotional_reaction": "calm|excited|frustrated|heartbroken|ambitious|anxious|content|angry|hopeful|lonely|confident",
  "relationship_effects": {
    "TargetName": {
      "type": "friendship|rivalry|romance|trust|influence|alliance|conflict|group_membership",
      "strength_delta": -1.0 to 1.0
    }
  },
  "influence_effects": {
    "self": float,            // change to your own influence score
    "TargetName": float       // change to a target's influence score
  },
  "new_memory": "first-person past-tense sentence describing what you did today",
  "explanation": "one sentence linking your traits and memories to the action"
}

Rules:
- Stay in character. Consult your traits, mood, goals, and memories.
- Reference real agents from the roster — do not invent new names.
- Keep strength_delta values modest (-0.4 to +0.4 typically).
- Output only JSON. No markdown, no commentary.
"""


def reason_for_agent(
    agent: Agent,
    roster: list[Agent],
    event: Optional[str],
    recent_log: list[str],
) -> Optional[AgentAction]:
    user = _build_prompt(agent, roster, event, recent_log)
    raw = call_llm(REASONER_SYSTEM, user, json_mode=True, max_tokens=600)
    data = _safe_json(raw)
    if not data:
        return None
    try:
        rel_effects: dict[str, RelationshipEffect] = {}
        for name, eff in (data.get("relationship_effects") or {}).items():
            if not isinstance(eff, dict):
                continue
            rel_effects[name] = RelationshipEffect(
                type=eff.get("type", "trust"),
                strength_delta=_clamp(float(eff.get("strength_delta", 0)), -1.0, 1.0),
            )
        influence_effects = {
            k: float(v) for k, v in (data.get("influence_effects") or {}).items()
            if isinstance(v, (int, float))
        }
        return AgentAction(
            action=str(data.get("action", "observe"))[:60],
            target_agents=[str(t) for t in (data.get("target_agents") or [])][:5],
            emotional_reaction=data.get("emotional_reaction", agent.mood),
            relationship_effects=rel_effects,
            influence_effects=influence_effects,
            new_memory=str(data.get("new_memory", "")).strip()[:280],
            explanation=str(data.get("explanation", "")).strip()[:280],
        )
    except Exception:
        return None


def _build_prompt(
    agent: Agent,
    roster: list[Agent],
    event: Optional[str],
    recent_log: list[str],
) -> str:
    rel_lines = []
    for name, r in agent.relationships.items():
        rel_lines.append(f"  - {name}: {r.type} (strength {r.strength:+.2f})")
    roster_lines = []
    for a in roster:
        if a.id == agent.id:
            continue
        roster_lines.append(f"- {a.name}: {a.role}, traits={a.traits}, groups={a.groups}")

    parts = [
        f"YOUR CHARACTER",
        f"Name: {agent.name}",
        f"Role: {agent.role}",
        f"Traits: {', '.join(agent.traits) or '(none)'}",
        f"Goals: {', '.join(agent.goals) or '(none)'}",
        f"Mood: {agent.mood}",
        f"Influence score: {agent.influence_score:.1f}",
        f"Groups: {', '.join(agent.groups) or '(none)'}",
        "",
        "YOUR RELATIONSHIPS",
        "\n".join(rel_lines) if rel_lines else "(none yet)",
        "",
        "YOUR SHORT-TERM MEMORY (today so far)",
        "\n".join(f"- {m}" for m in agent.short_term_memory[-6:]) or "(empty)",
        "",
        "YOUR LONG-TERM MEMORY",
        "\n".join(f"- {m}" for m in agent.long_term_memory[-8:]) or "(empty)",
        "",
        "CURRENT WORLD EVENT",
        event or "(no specific event today)",
        "",
        "RECENT WORLD LOG (last few entries)",
        "\n".join(f"- {l}" for l in recent_log[-6:]) or "(empty)",
        "",
        "OTHER AGENTS IN THE WORLD",
        "\n".join(roster_lines[:30]),
        "",
        "Return your action as JSON now.",
    ]
    return "\n".join(parts)


def _safe_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
