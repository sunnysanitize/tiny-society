from __future__ import annotations

import json
import re
from typing import Optional

from models import Agent, AgentAction, WorldGraph, normalize_action_kind
from llm import call_llm, acall_llm
from .memory import retrieve
from .observation import rank_feed

REASONER_SYSTEM = """AGENT_REASONING
You are a single fictional character in a multi-agent social simulation.
You will be given your personality, memories, relationships, and the current world event.
Reason about what your character would actually do today, then return STRICT JSON only — no prose.

You do NOT control relationship numbers. You only decide WHAT YOU DO and YOUR INTENT toward
each person; the world decides the consequences, and relationships change slowly, only through
sustained, mutual behavior (a romance can't happen in a day, or one-sidedly).

JSON schema:
{
  "action": "short verb phrase summarizing the move (e.g. 'confront', 'open up to', 'rally')",
  "action_kind": "post | direct | amplify | comment | interact",
  "target_agents": ["Name", ...],
  "utterance": "what you actually say or do, in your own voice (1-2 sentences)",
  "intents": {
    "TargetName": "one intent verb from the list below"
  },
  "emotional_reaction": "calm|excited|frustrated|heartbroken|ambitious|anxious|content|angry|hopeful|lonely|confident",
  "stance_shift": { "TopicName": -0.3 to 0.3 },
  "new_memory": "first-person past-tense sentence describing what you did today",
  "explanation": "one sentence linking your traits and memories to this specific action"
}

INTENT VERBS (pick the one that matches your true intent toward each target):
  warmth:     befriend, support, comfort, praise, reconcile, confide, trust
  romance:    flirt, court          (only use these if you genuinely feel romantic — they're rare)
  strategic:  ally, collaborate
  antagonism: confront, rebuke, reject, undermine, challenge, compete, distance
  neutral:    talk, observe

action_kind — how you act, which decides who sees it:
  - post     : a public broadcast everyone in the world sees (use for big statements).
  - direct   : a private exchange only your named target(s) witness.
  - amplify  : you boost/repost another agent — raises THEIR standing. (target_agents = who you boost.)
  - comment  : a reply, seen by your usual circle (medium reach).
  - interact : default — an ordinary interaction (your circle + public if you're prominent).

CRITICAL RULES:
- ANTI-REPETITION: read YOUR RECENT ACTIONS. If you keep engaging the same person the same way,
  you MUST change course — escalate, resolve, withdraw, or turn to someone new.
- Stay in character. Let traits, mood, goals, and memories drive the choice and the utterance.
- BE REALISTIC: most days are ordinary. Reserve romance ('flirt'/'court') for when there is a
  real, established, mutual closeness — never as a sudden leap. Don't manufacture drama.
- PURSUE YOUR PLAN if one is present (unless the event makes it impossible).
- Only reference agent names from the roster — never invent names. Put each target in BOTH
  target_agents and intents.
- stance_shift: ONLY topics you actually engaged with today, small magnitudes (-0.3..0.3), else {}.
- Output only JSON. No markdown, no commentary, no preamble.
"""


def reason_for_agent(
    agent: Agent,
    roster: list[Agent],
    event: Optional[str],
    current_day: int = 1,
    world_graph: Optional[WorldGraph] = None,
    tier: str = "cheap",
) -> Optional[AgentAction]:
    import logging
    user = _build_prompt(agent, roster, event, current_day, world_graph)
    try:
        raw = call_llm(REASONER_SYSTEM, user, json_mode=True, max_tokens=1024, tier=tier)
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
    tier: str = "cheap",
) -> Optional[AgentAction]:
    import logging
    user = _build_prompt(agent, roster, event, current_day, world_graph)
    try:
        raw = await acall_llm(REASONER_SYSTEM, user, json_mode=True, max_tokens=1024, tier=tier)
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
        intents = {
            str(name): str(verb).strip().lower()
            for name, verb in (data.get("intents") or {}).items()
            if isinstance(verb, str) and verb.strip()
        }
        targets = [str(t) for t in (data.get("target_agents") or [])][:5]
        # Be forgiving: if intents are missing but targets exist, default to neutral contact
        # so the action still has consequence-layer effects.
        for t in targets:
            intents.setdefault(t, "talk")
        stance_shift = {
            str(k): _clamp(float(v), -0.3, 0.3)
            for k, v in (data.get("stance_shift") or {}).items()
            if isinstance(v, (int, float))
        }
        return AgentAction(
            action=str(data.get("action", "observe"))[:60],
            action_kind=normalize_action_kind(data.get("action_kind", "interact")),
            target_agents=targets,
            emotional_reaction=data.get("emotional_reaction", agent.mood),
            intents=intents,
            utterance=str(data.get("utterance", "")).strip()[:400],
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
    # Rolling action history (structured: kind/verb → targets) drives anti-repetition —
    # the model sees its OWN recent pattern, not just one stale line.
    recent_actions = agent.recent_actions[-5:]

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
        "YOUR RECENT ACTIONS (vary from these — do NOT repeat the same target or the same move)",
        "\n".join(f"- {r}" for r in recent_actions)
            or f"- {last_action or '(none — this is your first day)'}",
        "→ If you keep engaging the same person, you MUST change course: escalate it, resolve it, "
        "withdraw, or turn to someone new. Repeating yesterday verbatim is always wrong.",
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
