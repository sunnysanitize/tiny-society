"""Needs — off-screen reasons to break routine.

Without needs, every character spends every day on the central drama, so they all
converge on the same few people. Each character tracks a handful of needs (0 = starved,
1 = satisfied). They drain daily at personality-dependent rates and are restored in code
by what the character actually did. Urgency is nonlinear, as in The Sims: a need is
ignorable until it runs low, then dominates. Only an urgent need reaches the prompt.
"""
from __future__ import annotations

import re
from typing import Optional

from models import Agent, AgentAction

BASE_NEEDS = ("rest", "company", "solitude", "purpose")
# A need this urgent (urgency = (1 - level) ** 2.5) is mentioned to the character.
URGENT = 0.3
_DESCRIBE = {
    "rest": "rest — you are worn out",
    "company": "company — you've hardly had a real conversation with anyone",
    "solitude": "time alone — you've been with people constantly",
    "purpose": "getting something real done — your efforts haven't come to anything",
}
_WORD_RE = re.compile(r"[a-z]{4,}")


def init_needs(agent: Agent) -> None:
    if agent.needs:
        return
    names = list(BASE_NEEDS) + [n.lower() for n in (agent.profile.needs if agent.profile else [])]
    agent.needs = {n: 0.75 for n in names}


def drain(agent: Agent) -> None:
    """Overnight: needs run down; sleep restores rest."""
    if not agent.needs:
        init_needs(agent)
    e = agent.profile.extraversion if agent.profile else 0.5
    rates = {"rest": -0.25, "company": 0.12 * (0.5 + e), "solitude": 0.12 * (1.5 - e), "purpose": 0.1}
    for n in agent.needs:
        rate = rates.get(n, 0.1)
        agent.needs[n] = round(min(1.0, max(0.0, agent.needs[n] - rate)), 3)


def satisfy(agent: Agent, action: AgentAction) -> None:
    """Credit what this action actually did toward the agent's needs."""
    if not agent.needs:
        init_needs(agent)
    gains = {"rest": -0.08}
    if action.target_agents:
        gains["company"], gains["solitude"] = 0.3, -0.05
    else:
        gains["solitude"] = 0.3
    gains["purpose"] = {"completed": 0.5, "success": 0.35, "partial": 0.2}.get(action.outcome, 0.0)
    words = set(_WORD_RE.findall(f"{action.new_memory} {action.utterance} {action.attempt}".lower()))
    for n in agent.needs:
        if n not in BASE_NEEDS and words & set(_WORD_RE.findall(n)):
            gains[n] = 0.35
    for n, g in gains.items():
        if n in agent.needs:
            agent.needs[n] = round(min(1.0, max(0.0, agent.needs[n] + g)), 3)


def urgent_need(agent: Agent) -> Optional[str]:
    """The most pressing need, described for the prompt, or None if nothing presses."""
    if not agent.needs:
        return None
    name, level = min(agent.needs.items(), key=lambda kv: kv[1])
    if (1 - level) ** 2.5 < URGENT:
        return None
    return _DESCRIBE.get(name, f"{name} — it has been neglected")
