from __future__ import annotations

import json
import re
from typing import Optional

from models import Agent, AgentAction, RelationshipEffect, WorldGraph, normalize_action_kind
from llm import call_llm, acall_llm
from .memory import retrieve
from .observation import rank_feed

REASONER_SYSTEM = """AGENT_REASONING
You are a single fictional character in a multi-agent social simulation.
You will be given your personality, memories, relationships, and the current world event.
Reason about what your character would do today, then return STRICT JSON only — no prose.

JSON schema:
{
  "action": "short verb phrase (e.g. 'confront', 'befriend', 'comfort', 'gossip about')",
  "action_kind": "post | direct | amplify | comment | interact",
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
  "stance_shift": {
    "TopicName": -0.3 to 0.3
  },
  "new_memory": "first-person past-tense sentence describing what you did today",
  "explanation": "one sentence linking your traits and memories to this specific action"
}

action_kind — how you act, which decides who sees it:
  - post     : a public broadcast everyone in the world sees (use for big statements).
  - direct   : a private exchange only your named target(s) witness.
  - amplify  : you boost/repost another agent — raises THEIR influence and spreads
               their standing to people who see you. (Set target_agents to who you boost.)
  - comment  : a reply, seen by your usual circle (medium reach).
  - interact : default — an ordinary interaction (your circle + public if you're prominent).

CRITICAL RULES:
- ANTI-REPETITION: Read your LAST ACTION field below carefully. If your last action targeted
  the same person with the same intent, you MUST do something meaningfully different today.
  Escalate, de-escalate, redirect to a different person, withdraw, or take an internal action.
  Repeating the identical action is always wrong — real people adapt.
- Stay in character. Let traits, mood, goals, and memories drive the choice.
- PURSUE YOUR PLAN: if a "YOUR CURRENT PLAN" section is present, strongly prefer an
  action that advances that intention today (unless the world event makes it impossible).
- Only reference agent names from the roster — never invent names.
- Keep strength_delta values modest: -0.4 to +0.4 unless the event is extreme.
- stance_shift: ONLY include WORLD TOPICS you actually engaged with today, and use small
  magnitudes (-0.3 to 0.3). Leave it as {} if your action didn't touch any topic.
- Output only JSON. No markdown, no commentary, no preamble.
"""


def reason_for_agent(
    agent: Agent,
    roster: list[Agent],
    event: Optional[str],
    current_day: int = 1,
    world_graph: Optional[WorldGraph] = None,
) -> Optional[AgentAction]:
    import logging
    user = _build_prompt(agent, roster, event, current_day, world_graph)
    try:
        raw = call_llm(REASONER_SYSTEM, user, json_mode=True, max_tokens=1024, tier="cheap")
    except Exception as e:
        logging.warning(f"LLM call failed for agent {agent.name}: {e}")
        return None
    return _parse_action(agent, raw)


async def areason_for_agent(
    agent: Agent,
    roster: list[Agent],
    event: Optional[str],
    current_day: int = 1,
    world_graph: Optional[WorldGraph] = None,
) -> Optional[AgentAction]:
    import logging
    user = _build_prompt(agent, roster, event, current_day, world_graph)
    try:
        raw = await acall_llm(REASONER_SYSTEM, user, json_mode=True, max_tokens=1024, tier="cheap")
    except Exception as e:
        logging.warning(f"LLM call failed for agent {agent.name}: {e}")
        return None
    return _parse_action(agent, raw)


def _parse_action(agent: Agent, raw: str) -> Optional[AgentAction]:
    import logging
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
        stance_shift = {
            str(k): _clamp(float(v), -0.3, 0.3)
            for k, v in (data.get("stance_shift") or {}).items()
            if isinstance(v, (int, float))
        }
        return AgentAction(
            action=str(data.get("action", "observe"))[:60],
            action_kind=normalize_action_kind(data.get("action_kind", "interact")),
            target_agents=[str(t) for t in (data.get("target_agents") or [])][:5],
            emotional_reaction=data.get("emotional_reaction", agent.mood),
            relationship_effects=rel_effects,
            influence_effects=influence_effects,
            stance_shift=stance_shift,
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
    world_graph: Optional[WorldGraph] = None,
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

    # WORLD FACTS & POWER STRUCTURE: compact shared ground truth from the knowledge
    # graph, plus the contested topics + this agent's current stance on them.
    topics = world_graph.topics if world_graph else []
    fact_lines: list[str] = []
    if world_graph:
        for e in world_graph.entities[:6]:
            desc = f" — {e.description}" if e.description else ""
            fact_lines.append(f"- {e.name} ({e.kind}){desc}")
        for p in world_graph.power_structures[:3]:
            fact_lines.append(f"- POWER: {p}")
    # RANKED FEED (interest + hot-score): show this viewer the top entries from their
    # structured feed, ordered by how much the content matches their interests plus the
    # author's influence and recency — different agents see different, biased feeds.
    ranked_feed = rank_feed(agent, agent.feed, k=8)

    topic_lines = []
    for t in topics:
        pos = agent.stance.get(t)
        if pos is not None:
            topic_lines.append(f"- {t} (your current stance: {pos:+.2f})")
        else:
            topic_lines.append(f"- {t}")

    parts = [
        "WORLD FACTS & POWER STRUCTURE",
        "\n".join(fact_lines) if fact_lines else "(none extracted)",
        "",
        "WORLD TOPICS (stance axes; shift only those you engage with, -0.3..0.3)",
        "\n".join(topic_lines) if topic_lines else "(none)",
        "",
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
        *(["YOUR CURRENT PLAN", agent.plan, ""] if agent.plan else []),
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
        "YOUR FEED — what's reaching you (ranked by your interests + what's hot)",
        "\n".join(f"- {e.text}" for e in ranked_feed) or "(nothing notable yet)",
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
