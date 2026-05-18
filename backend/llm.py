from __future__ import annotations

import hashlib
import json
import os
import random
from typing import Optional

import httpx


class LLMError(Exception):
    pass


def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock").lower()


def call_llm(system: str, user: str, *, json_mode: bool = False, max_tokens: int = 1024) -> str:
    """Single text completion. Returns raw string output."""
    provider = _provider()
    if provider == "anthropic":
        return _call_anthropic(system, user, max_tokens=max_tokens)
    if provider == "openai_compat":
        return _call_openai_compat(system, user, json_mode=json_mode, max_tokens=max_tokens)
    return _mock(system, user, json_mode=json_mode)


def _call_anthropic(system: str, user: str, max_tokens: int) -> str:
    from anthropic import Anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMError("ANTHROPIC_API_KEY not set")
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def _call_openai_compat(system: str, user: str, json_mode: bool, max_tokens: int) -> str:
    base = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    key = os.getenv("OPENAI_COMPAT_API_KEY")
    model = os.getenv("OPENAI_COMPAT_MODEL", "llama-3.3-70b-versatile")
    if not base or not key:
        raise LLMError("OPENAI_COMPAT_BASE_URL or OPENAI_COMPAT_API_KEY not set")
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    with httpx.Client(timeout=60) as c:
        r = c.post(
            f"{base}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Tiny Society AI",
            },
        )
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"].strip()


def _mock(system: str, user: str, json_mode: bool) -> str:
    """Deterministic fake JSON / text so the engine runs end-to-end without keys."""
    seed = int(hashlib.sha256((system + "|" + user).encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    if "FILLER_AGENT_GENERATION" in system:
        first = ["Mika", "Leo", "Aria", "Sage", "Jun", "Theo", "Noa", "Ines",
                 "Kai", "Rumi", "Eli", "Ada", "Reza", "Yuki", "Cleo", "Otto",
                 "Maya", "Asa", "Nico", "Wren", "Pax", "Vera", "Iris", "Tomo"]
        roles = ["student", "professor", "club president", "researcher",
                 "dorm RA", "barista", "intern", "athlete"]
        traits_pool = ["ambitious", "social", "introverted", "competitive",
                       "loyal", "anxious", "charismatic", "thoughtful",
                       "stubborn", "creative", "easily annoyed", "patient"]
        groups_pool = ["Dorm A", "Dorm B", "Cooking Club", "Robotics Club",
                       "Debate Team", "Music Society", "Sailing Club"]
        moods = ["calm", "excited", "ambitious", "anxious", "content", "hopeful"]
        agents = []
        n = 25
        for i in range(n):
            agents.append({
                "name": f"{rng.choice(first)}-{i}",
                "role": rng.choice(roles),
                "traits": rng.sample(traits_pool, 3),
                "goals": [rng.choice([
                    "make close friends", "join a club", "lead a project",
                    "find romance", "win a competition", "stay neutral"])],
                "mood": rng.choice(moods),
                "groups": rng.sample(groups_pool, rng.randint(1, 2)),
            })
        return json.dumps({"agents": agents})

    if "AGENT_REASONING" in system:
        # Extract names from user prompt for plausible targets
        actions = ["confront", "befriend", "ignore", "support", "compete with",
                   "share a meal with", "gossip about", "team up with",
                   "challenge", "comfort"]
        moods = ["calm", "excited", "frustrated", "ambitious", "anxious",
                 "content", "hopeful", "confident"]
        rel_types = ["friendship", "rivalry", "romance", "trust",
                     "alliance", "conflict"]
        # Find candidate target names from the prompt (very crude)
        candidates = []
        for line in user.splitlines():
            if line.startswith("- ") and ":" in line:
                name = line[2:].split(":", 1)[0].strip()
                if name and name[0].isupper():
                    candidates.append(name)
        target = rng.choice(candidates) if candidates else "Someone"
        action = rng.choice(actions)
        rtype = rng.choice(rel_types)
        delta = round(rng.uniform(-0.3, 0.4), 2)
        return json.dumps({
            "action": action,
            "target_agents": [target],
            "emotional_reaction": rng.choice(moods),
            "relationship_effects": {
                target: {"type": rtype, "strength_delta": delta}
            },
            "influence_effects": {
                "self": round(rng.uniform(-2, 4), 1),
                target: round(rng.uniform(-2, 2), 1),
            },
            "new_memory": f"Chose to {action} {target} during the day's events.",
            "explanation": f"Based on traits and current mood, {action}ing {target} fit the situation.",
        })

    if "FINAL_REPORT" in system:
        return ("Over the simulated period, the society fractured along the lines "
                "of the injected event. Several rivalries crystallized, a handful of "
                "romances formed in unexpected pairs, and the most isolated agents "
                "either drifted further or seized the social vacuum to gain influence. "
                "(Mock report — set LLM_PROVIDER=anthropic or openai_compat for real "
                "narration.)")

    return ""
