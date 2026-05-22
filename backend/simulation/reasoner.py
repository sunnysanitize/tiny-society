from __future__ import annotations

import json
import re
from typing import Optional

from models import Agent, AgentAction, RelationshipEffect
from llm import call_llm
from .memory import retrieve

REASONER_SYSTEM = """AGENT_REASONING
You are a single fictional character in a multi-agent social simulation.
You will be given your personality, memories, relationships, and the current world event.
Reason about what your character would do today, then return STRICT JSON only — no prose.

JSON schema:
{
  "action": "short verb phrase (e.g. 'confront', 'befriend', 'comfort', 'gossip about')",
  "target_agents": ["Name", ...],
  "emotional_reaction": "calm|excited|frustrated|heartbroken|ambitious|anxious|content|angry|hopeful|lonely|confident",
  "relationship_effects": {
    "TargetName": {
      "type": "friendship|rivalry|romance|trust|influence|alliance|conflict|group_membership",
      "strength_delta": -1.0 to 1.0
    }
  },
  "influence_effects": {
    "self": float,
    "TargetName": float
  },
  "new_memory": "first-person past-tense sentence describing what you did today",
  "explanation": "one sentence linking your traits and memories to this specific action"
}

CRITICAL RULES:
- ANTI-REPETITION: Read your LAST ACTION field below carefully. If your last action targeted
  the same person with the same intent, you MUST do something meaningfully different today.
  Escalate, de-escalate, redirect to a different person, withdraw, or take an internal action.
  Repeating the identical action is always wrong — real people adapt.
- Stay in character. Let traits, mood, goals, and memories drive the choice.
- Only reference agent names from the roster — never invent names.
- Keep strength_delta values modest: -0.4 to +0.4 unless the event is extreme.
- Output only JSON. No markdown, no commentary, no preamble.
"""


def reason_for_agent(
    agent: Agent,
    roster: list[Agent],
    event: Optional[str],
    current_day: int = 1,
) -> Optional[AgentAction]:
    import logging
    user = _build_prompt(agent, roster, event, current_day)
    try:
        raw = call_llm(REASONER_SYSTEM, user, json_mode=True, max_tokens=1024)
    except Exception as e:
        logging.warning(f"LLM call failed for agent {agent.name}: {e}")
        return None
    data = _safe_json(raw)
    if not data:
        logging.warning(f"Empty/invalid JSON from LLM for agent {agent.name}: {raw[:100]!r}")
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
    current_day: int = 1,
) -> str:
    rel_lines = []
    for name, r in agent.relationships.items():
        rel_lines.append(f"  - {name}: {r.type} (strength {r.strength:+.2f})")
    roster_lines = []
    for a in roster:
        if a.id == agent.id:
            continue
        roster_lines.append(f"- {a.name}: {a.role}, traits={a.traits}, groups={a.groups}")

    # RELEVANCE-BASED RETRIEVAL: query = today's event + the agent's relationship
    # names (its likely targets). Long-term memory is selected by relevance + recency
    # + importance rather than pure recency truncation.
    query = " ".join(filter(None, [event or ""] + list(agent.relationships.keys())))
    retrieved = retrieve(
        agent.long_term_memory,
        query,
        current_day=current_day,
        k=10,
    )

    # Extract last action from short-term memory (today) to surface it explicitly
    last_pool = agent.short_term_memory or agent.long_term_memory
    last_action = last_pool[-1].text if last_pool else None

    parts = [
        "YOUR CHARACTER",
        f"Name: {agent.name}",
        f"Role: {agent.role}",
        f"Traits: {', '.join(agent.traits + agent.revealed_traits) or '(none)'}",
        f"Goals: {', '.join(agent.goals) or '(none)'}",
        f"Mood: {agent.mood}",
        f"Influence score: {agent.influence_score:.1f}",
        f"Groups: {', '.join(agent.groups) or '(none)'}",
        "",
        "YOUR RELATIONSHIPS",
        "\n".join(rel_lines) if rel_lines else "(none yet)",
        "",
        "YOUR SHORT-TERM MEMORY (today so far)",
        "\n".join(f"- {m.text}" for m in agent.short_term_memory[-4:]) or "(empty)",
        "",
        "YOUR LONG-TERM MEMORY (most relevant to today)",
        "\n".join(f"- {m.text}" for m in retrieved) or "(empty)",
        "",
        f"LAST ACTION: {last_action or '(none — this is your first day)'}",
        "→ Do NOT repeat this. Choose a different action, target, or approach today.",
        "",
        "CURRENT WORLD EVENT",
        event or "(no specific event today)",
        "",
        "WHAT YOU'VE OBSERVED (only things you could witness — your own view)",
        "\n".join(f"- {l}" for l in agent.observations[-8:]) or "(nothing notable yet)",
        "",
        "OTHER AGENTS IN THE WORLD",
        "\n".join(roster_lines[:30]),
        "",
        "Return your action as JSON now.",
    ]
    return "\n".join(parts)


def _safe_json(raw: str) -> dict:
    if not raw:
        return {}
    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw).strip()
    # Try full parse first
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        pass
    # Find outermost { ... } (handles preamble/postamble)
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
