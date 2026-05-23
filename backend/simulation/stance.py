from __future__ import annotations

import hashlib

from models import Agent


def _seed_position(agent_id: str, topic: str) -> float:
    """Deterministic mild starting position in roughly [-0.4, 0.4] from agent+topic."""
    h = hashlib.sha256(f"{agent_id}|{topic}".encode()).hexdigest()
    # Map first 8 hex digits to [0, 1), then to [-0.4, 0.4].
    frac = int(h[:8], 16) / 0xFFFFFFFF
    return round((frac * 0.8) - 0.4, 3)


def initialize_stances(agents: list[Agent], topics: list[str]) -> None:
    """Give each agent a mild, deterministic starting stance on each world topic.

    Idempotent and additive: only fills in topics the agent doesn't already have a
    position on, so re-running (or continuing a sim) won't reset moved stances.
    """
    if not topics:
        return
    for a in agents:
        for topic in topics:
            if topic not in a.stance:
                a.stance[topic] = _seed_position(a.id, topic)
