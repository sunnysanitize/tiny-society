from __future__ import annotations

import hashlib
import re

from models import Agent

# Belief stance used to be pure hash noise, uncorrelated with the character — so the
# population's "lean" and the forecast confidence were noise, and (with only the day's
# selected agents ever shifting) the aggregate barely moved. We instead GROUND the
# starting position in the character's disposition along an openness↔caution axis, then
# add a small deterministic jitter for variety. Stances now correlate with who the
# character is, while staying LLM-free and deterministic.
_OPENNESS_POS = {
    "idealistic", "ambitious", "creative", "curious", "rebellious", "progressive",
    "adaptable", "optimistic", "visionary", "open", "experimental", "restless",
    "reformist", "bold", "inventive", "radical",
}
_OPENNESS_NEG = {
    "loyal", "traditional", "stubborn", "cautious", "conservative", "principled",
    "disciplined", "reserved", "skeptical", "pragmatic", "dutiful", "guarded",
    "wary", "orthodox", "rigid",
}

_WORD_RE = re.compile(r"[a-z']+")


def _disposition(agent: Agent) -> float:
    """A signed openness↔caution lean in [-1, 1] from the agent's trait/goal vocabulary.
    0.0 when the character gives no signal either way."""
    tokens: set[str] = set()
    for phrase in agent.traits + agent.revealed_traits + agent.goals + [agent.role]:
        tokens |= set(_WORD_RE.findall((phrase or "").lower()))
    pos = len(tokens & _OPENNESS_POS)
    neg = len(tokens & _OPENNESS_NEG)
    if pos == neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def _jitter(agent_id: str, topic: str) -> float:
    """Deterministic small per-(agent, topic) noise in [-0.2, 0.2]."""
    h = hashlib.sha256(f"{agent_id}|{topic}".encode()).hexdigest()
    frac = int(h[:8], 16) / 0xFFFFFFFF
    return (frac * 0.4) - 0.2


def _seed_position(agent: Agent, topic: str, disposition: float) -> float:
    """Starting stance: a personality-driven lean (up to ±0.4) plus jitter, clamped.
    Agents whose trait vocabulary overlaps the topic care more, so their lean is stronger."""
    topic_tokens = set(_WORD_RE.findall(topic.lower()))
    agent_tokens: set[str] = set()
    for phrase in agent.traits + agent.goals:
        agent_tokens |= set(_WORD_RE.findall((phrase or "").lower()))
    engaged = bool(topic_tokens & agent_tokens)
    base = disposition * (0.6 if engaged else 0.4)
    pos = base + _jitter(agent.id, topic)
    return round(max(-0.6, min(0.6, pos)), 3)


def initialize_stances(agents: list[Agent], topics: list[str]) -> None:
    """Give each agent a deterministic, character-grounded starting stance on each topic.

    Idempotent and additive: only fills in topics the agent doesn't already have a
    position on, so re-running (or continuing a sim) won't reset moved stances.
    """
    if not topics:
        return
    for a in agents:
        disposition = _disposition(a)
        for topic in topics:
            if topic not in a.stance:
                a.stance[topic] = _seed_position(a, topic, disposition)
