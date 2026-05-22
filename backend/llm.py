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
    import time as _time

    base = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    key = os.getenv("OPENAI_COMPAT_API_KEY")
    model = os.getenv("OPENAI_COMPAT_MODEL", "minimax/minimax-m2.5:free")
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
    # Only send response_format if explicitly enabled — not all models support it
    if json_mode and os.getenv("OPENAI_COMPAT_JSON_MODE", "").lower() == "true":
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Tiny Society AI",
    }

    import logging as _logging

    for attempt in range(4):
        try:
            with httpx.Client(timeout=90) as c:
                r = c.post(f"{base}/chat/completions", json=payload, headers=headers)

                if r.status_code == 429:
                    wait = float(r.headers.get("Retry-After", 10 * (attempt + 1)))
                    wait = min(wait, 60)
                    _logging.warning(f"Rate limited (attempt {attempt+1}/4), retrying in {wait:.0f}s")
                    _time.sleep(wait)
                    continue

                r.raise_for_status()
                data = r.json()

                # Some providers embed errors in 200 responses
                if not data.get("choices") and "error" in data:
                    err_msg = data["error"].get("message", str(data["error"]))
                    _logging.warning(f"Provider error in 200 response (attempt {attempt+1}/4): {err_msg[:120]}")
                    if attempt < 3:
                        _time.sleep(5 * (attempt + 1))
                        continue
                    raise LLMError(f"Provider error: {err_msg}")

                content = data["choices"][0]["message"]["content"]
                if not content:
                    _logging.warning("LLM returned empty content")
                    return ""
                return content.strip()

        except LLMError:
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            _logging.warning(f"Network error (attempt {attempt+1}/4): {e}")
            if attempt < 3:
                _time.sleep(5 * (attempt + 1))
            else:
                raise LLMError(f"Network failed after 4 attempts: {e}")
        except httpx.HTTPStatusError as e:
            if attempt < 3 and e.response.status_code >= 500:
                _logging.warning(f"HTTP {e.response.status_code} (attempt {attempt+1}/4), retrying")
                _time.sleep(5 * (attempt + 1))
                continue
            raise LLMError(f"HTTP {e.response.status_code}: {e.response.text[:300]}")

    raise LLMError("All 4 retry attempts exhausted (persistent rate limit or provider outage)")


# ── trait / mood action templates ──────────────────────────────────────────────

_TRAIT_ACTIONS: dict[str, list[tuple]] = {
    "ambitious": [
        ("forge a strategic alliance with", "alliance", 0.3, "ambitious",
         "Their ambition made this alliance feel like a necessary move toward their goals."),
        ("angle for influence over", "influence", 0.25, "confident",
         "They saw an opening and took it — the ambitious always do."),
    ],
    "competitive": [
        ("escalate a rivalry with", "rivalry", -0.25, "excited",
         "Their competitive streak turned a simple disagreement into a contest."),
        ("openly challenge", "conflict", -0.2, "ambitious",
         "The competitive fire in them refused to let the moment pass quietly."),
    ],
    "loyal": [
        ("stand up for", "friendship", 0.25, "content",
         "Their loyalty made walking away from someone in need impossible."),
        ("confide a secret in", "trust", 0.3, "calm",
         "They trust deeply once they've committed — and they had."),
    ],
    "anxious": [
        ("quietly avoid", "conflict", -0.1, "anxious",
         "The anxiety made closeness feel risky, so they kept their distance."),
        ("seek reassurance from", "trust", 0.15, "hopeful",
         "The anxiety pushed them toward someone steady."),
    ],
    "charismatic": [
        ("draw into their circle", "friendship", 0.25, "excited",
         "Their natural charm opened the door before they even knocked."),
        ("rally support from", "alliance", 0.3, "confident",
         "Their magnetism made it easy to get others on board."),
    ],
    "introverted": [
        ("share a quiet moment with", "friendship", 0.15, "calm",
         "They chose depth over breadth, as always — one real connection over many shallow ones."),
        ("observe from a distance before reaching out to", "trust", 0.1, "calm",
         "They watched first, acted second. That's just who they are."),
    ],
    "social": [
        ("spend meaningful time with", "friendship", 0.2, "content",
         "Being around people recharged them. It always had."),
        ("bring together", "alliance", 0.15, "excited",
         "They couldn't help it — they see connection potential everywhere."),
    ],
    "stubborn": [
        ("refuse to back down from", "conflict", -0.2, "frustrated",
         "Their stubbornness turned a small disagreement into something bigger than it needed to be."),
        ("double down on their position with", "rivalry", -0.15, "confident",
         "Once they made up their mind, no one was moving them."),
    ],
    "thoughtful": [
        ("offer unexpected support to", "trust", 0.2, "hopeful",
         "They'd been thinking about this person's situation for days. Today they acted on it."),
        ("have a difficult but honest conversation with", "trust", 0.25, "calm",
         "They chose truth over comfort because they believed the other person deserved it."),
    ],
    "creative": [
        ("collaborate creatively with", "alliance", 0.2, "excited",
         "They saw a creative opportunity and invited someone in to share it."),
        ("pitch an unusual idea to", "influence", 0.15, "hopeful",
         "The idea had been rattling around for a while. Today felt like the right time."),
    ],
    "patient": [
        ("quietly mend fences with", "friendship", 0.2, "calm",
         "They gave the situation time to breathe, then stepped in at exactly the right moment."),
        ("de-escalate tensions between themselves and", "conflict", 0.1, "content",
         "Their patience let them wait until the other person was ready to talk."),
    ],
    "easily annoyed": [
        ("snap at", "conflict", -0.25, "angry",
         "Something small was the final straw. It always is."),
        ("complain openly about", "rivalry", -0.15, "frustrated",
         "They'd been holding this in and finally stopped bothering."),
    ],
}

_MOOD_ACTIONS: dict[str, tuple] = {
    "frustrated": ("vent their frustration at", "conflict", -0.2, "frustrated",
                   "The built-up frustration finally found a direction."),
    "excited":    ("enthusiastically pull into their plans", "friendship", 0.2, "excited",
                   "Their excitement was contagious and they needed someone to share it with."),
    "heartbroken": ("pull away from", "conflict", -0.15, "lonely",
                    "The heartbreak made closeness feel too dangerous right now."),
    "ambitious":  ("make a calculated move toward", "alliance", 0.3, "ambitious",
                   "Every decision they make traces back to what they're trying to build."),
    "lonely":     ("reach out hesitantly to", "friendship", 0.1, "hopeful",
                   "The loneliness finally got loud enough that they had to do something."),
    "angry":      ("confront directly", "conflict", -0.3, "angry",
                   "The anger had been building and today it broke through the surface."),
    "hopeful":    ("extend an olive branch to", "trust", 0.2, "hopeful",
                   "Hope has a way of making people brave enough to try."),
    "confident":  ("openly mentor and guide", "influence", 0.25, "confident",
                   "The confidence made stepping into a guiding role feel natural."),
    "anxious":    ("check in nervously with", "trust", 0.1, "anxious",
                   "The anxiety drove them to seek some kind of certainty."),
    "calm":       ("have a grounding conversation with", "friendship", 0.15, "calm",
                   "The calm gave them space to connect without an agenda."),
    "content":    ("strengthen their bond with", "friendship", 0.2, "content",
                   "When things are good, you want to share it with the people who matter."),
}


def _mock(system: str, user: str, json_mode: bool) -> str:
    """Deterministic contextual mock so the engine runs end-to-end without API keys."""
    seed = int(hashlib.sha256((system + "|" + user).encode()).hexdigest(), 16) % (2 ** 32)
    rng = random.Random(seed)

    # ── filler agent generation ────────────────────────────────────────────────
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

    # ── perception narration ───────────────────────────────────────────────────
    if "PERCEPTION_NARRATION" in system:
        perceiver_name, actor_name, rel_type, raw_delta_str = "", "", "trust", "0.1"
        existing_rel = ""
        memories: list[str] = []
        _section = ""
        for line in user.splitlines():
            stripped = line.strip()
            if stripped == "YOUR CHARACTER":
                _section = "char"
            elif stripped == "INCOMING EVENT":
                _section = "event"
            elif stripped.startswith("YOUR EXISTING RELATIONSHIP WITH"):
                _section = "rel"
            elif stripped == "YOUR MEMORIES MOST RELEVANT TO THIS PERSON":
                _section = "mems"
            elif _section == "char" and line.startswith("Name: "):
                perceiver_name = line[6:].strip()
            elif _section == "event" and line.startswith("Acting character: "):
                actor_name = line[18:].split("(")[0].strip()
            elif _section == "event" and line.startswith("Raw social signal"):
                parts_sig = line.split("magnitude")
                if len(parts_sig) > 1:
                    raw_delta_str = parts_sig[1].split("—")[0].strip().rstrip(",")
                if "negative" in line:
                    raw_delta_str = f"-{raw_delta_str}"
                if "relationship type:" in line:
                    rel_type = line.split("relationship type:")[-1].strip()
            elif _section == "rel" and stripped and not stripped.startswith("("):
                existing_rel = stripped
            elif _section == "mems" and stripped.startswith("- "):
                memories.append(stripped[2:])

        try:
            base = float(raw_delta_str)
        except ValueError:
            base = 0.1

        # Generate a contextually varied perceived_delta from the mock rng
        perceived = round(base * rng.uniform(0.3, 1.2), 3)
        perceived = max(-1.0, min(1.0, perceived))

        has_conflict = any(w in existing_rel for w in ("conflict", "rivalry"))
        has_trust = any(w in existing_rel for w in ("trust", "friendship", "alliance"))
        if has_conflict and base > 0:
            perceived = round(base * rng.uniform(0.1, 0.4), 3)
        elif has_trust and base > 0:
            perceived = round(base * rng.uniform(0.8, 1.15), 3)
        perceived = round(max(-1.0, min(1.0, perceived)), 3)

        actor_first = actor_name.split("-")[0] if actor_name else "them"
        perceiver_first = perceiver_name.split("-")[0] if perceiver_name else "they"

        if has_conflict and base > 0:
            narratives = [
                f"{perceiver_first} acknowledged {actor_first}'s gesture with guarded eyes — the history between them made warmth feel like a gamble.",
                f"The overture landed with less weight than intended; {perceiver_first} had learned not to read too much into {actor_first}'s moments of goodwill.",
                f"{perceiver_first} noticed the shift in {actor_first}'s tone but held back — old wounds don't close overnight.",
            ]
            trait = "slow to forgive"
        elif has_trust and base > 0:
            narratives = [
                f"{perceiver_first} felt {actor_first}'s gesture land more deeply than the moment might have warranted — trust amplifies everything.",
                f"Because the foundation was solid, {perceiver_first} let {actor_first}'s move in without questioning the motive.",
                f"{perceiver_first} received it warmly; with {actor_first}, there was nothing to second-guess.",
            ]
            trait = None
        elif base < 0:
            narratives = [
                f"{perceiver_first} absorbed the friction quietly, filing it away without drama — confrontation wasn't worth it yet.",
                f"The negative signal registered, but {perceiver_first} held their reaction close rather than showing it.",
                f"{perceiver_first} felt the sting of {actor_first}'s move but chose not to react — at least not visibly.",
            ]
            trait = "internalizes conflict"
        else:
            narratives = [
                f"{perceiver_first} processed {actor_first}'s action through the lens of their own uncertainty, unsure what to make of it.",
                f"The signal was clear enough, but {perceiver_first} hadn't yet decided what it meant for them.",
            ]
            trait = None

        return json.dumps({
            "perceived_delta": perceived,
            "narrative": rng.choice(narratives),
            "revealed_trait": trait,
        })

    # ── agent daily reasoning ──────────────────────────────────────────────────
    if "AGENT_REASONING" in system:
        lines = user.splitlines()
        agent_name = ""
        agent_role = ""
        agent_traits: list[str] = []
        agent_mood = ""
        agent_goals: list[str] = []
        relationships: dict[str, str] = {}
        world_event = ""
        section = ""

        for line in lines:
            stripped = line.strip()
            if line.startswith("Name: "):
                agent_name = line[6:].strip()
            elif line.startswith("Role: "):
                agent_role = line[6:].strip()
            elif line.startswith("Traits: "):
                agent_traits = [t.strip() for t in line[8:].split(",") if t.strip() and t.strip() != "(none)"]
            elif line.startswith("Mood: "):
                agent_mood = line[6:].strip()
            elif line.startswith("Goals: "):
                agent_goals = [g.strip() for g in line[7:].split(",") if g.strip() and g.strip() != "(none)"]
            elif stripped in ("YOUR RELATIONSHIPS", "CURRENT WORLD EVENT", "OTHER AGENTS IN THE WORLD",
                              "YOUR SHORT-TERM MEMORY (today so far)", "YOUR LONG-TERM MEMORY",
                              "RECENT WORLD LOG (last few entries)"):
                section = stripped
            elif section == "YOUR RELATIONSHIPS" and stripped.startswith("- "):
                parts = stripped[2:].split(":")
                if parts:
                    rel_name = parts[0].strip()
                    rel_desc = parts[1].strip() if len(parts) > 1 else ""
                    relationships[rel_name] = rel_desc
            elif section == "CURRENT WORLD EVENT" and stripped and not stripped.startswith("("):
                world_event = stripped

        # Candidate targets from roster lines
        candidates: list[str] = []
        in_roster = False
        for line in lines:
            if line.strip() == "OTHER AGENTS IN THE WORLD":
                in_roster = True
                continue
            if in_roster and line.startswith("- ") and ":" in line:
                name = line[2:].split(":", 1)[0].strip()
                if name and name[0].isupper() and name != agent_name:
                    candidates.append(name)
        # Also add anyone already in relationships
        for name in relationships:
            if name not in candidates and name != agent_name:
                candidates.append(name)

        target = rng.choice(candidates) if candidates else "a fellow student"

        # Pick action: trait-driven first, mood-driven fallback
        action_pool: list[tuple] = []
        for trait in agent_traits:
            if trait in _TRAIT_ACTIONS:
                action_pool.extend(_TRAIT_ACTIONS[trait])
        if not action_pool and agent_mood in _MOOD_ACTIONS:
            action_pool = [_MOOD_ACTIONS[agent_mood]]
        if not action_pool:
            action_pool = [
                ("check in on", "friendship", 0.1, "calm",
                 "Nothing dramatic — just a quiet check-in that meant more than expected."),
                ("spend some time with", "friendship", 0.15, "content",
                 "The day passed simply but the connection deepened."),
                ("have an honest conversation with", "trust", 0.2, "hopeful",
                 "They decided honesty was better than comfortable silence."),
            ]

        action_verb, rtype, base_delta, new_mood, explanation = rng.choice(action_pool)
        delta = round(base_delta + rng.uniform(-0.05, 0.05), 2)

        # Build a contextual narrative memory sentence
        goal = agent_goals[0] if agent_goals else "find my place here"
        _evt = world_event.strip().rstrip(".")
        # Strip leading article so "The event" doesn't become "The the event"
        for _art in ("A ", "An ", "The "):
            if _evt.startswith(_art):
                _evt = _evt[len(_art):]
                break
        event_clause = f" The {_evt.lower()} made everything feel more charged." if _evt else ""

        rel_desc = relationships.get(target, "")
        if "romance" in rel_desc:
            memory_opts = [
                f"I told {target} something I hadn't said out loud before. It felt fragile and true.{event_clause}",
                f"The tension between me and {target} broke today — in the best way.{event_clause}",
                f"I chose to {action_verb} {target}, and for a moment everything else fell away.{event_clause}",
            ]
        elif any(w in rel_desc for w in ("rival", "conflict")):
            memory_opts = [
                f"Things came to a head with {target}. I said what I'd been holding back.{event_clause}",
                f"I tried to {action_verb} {target}. It didn't go smoothly, but it was honest.{event_clause}",
                f"The friction between me and {target} reached a breaking point today.{event_clause}",
            ]
        elif "trust" in rel_desc or "friend" in rel_desc or "alliance" in rel_desc:
            memory_opts = [
                f"I made a point of {action_verb.rstrip('with').strip()} {target} today — they've been steady with me and I wanted to return that.{event_clause}",
                f"Me and {target} had a real conversation. The kind that actually changes something.{event_clause}",
                f"I spent time with {target} and it reminded me why I trust them.{event_clause}",
            ]
        else:
            memory_opts = [
                f"I decided to {action_verb} {target} today. My goal to {goal} doesn't happen on its own.{event_clause}",
                f"Something shifted between me and {target} — I {action_verb.split()[0]}ed them and it changed the dynamic.{event_clause}",
                f"Today I chose to {action_verb} {target}. {explanation.split('.')[0]}.{event_clause}",
            ]

        new_memory = rng.choice(memory_opts)

        return json.dumps({
            "action": action_verb,
            "target_agents": [target],
            "emotional_reaction": new_mood,
            "relationship_effects": {
                target: {"type": rtype, "strength_delta": delta}
            },
            "influence_effects": {
                "self": round(rng.uniform(-1, 3), 1),
                target: round(rng.uniform(-1, 1), 1),
            },
            "new_memory": new_memory,
            "explanation": explanation,
        })

    # ── final report ───────────────────────────────────────────────────────────
    if "FINAL_REPORT" in system:
        return (
            "Over the simulated period, the society fractured and reformed along unexpected lines. "
            "Several rivalries crystallized from minor friction, a handful of romances formed between "
            "people who started as strangers, and the most isolated agents either drifted further from "
            "the group or — against the odds — seized the social vacuum to claim real influence. "
            "(Mock report — set LLM_PROVIDER=anthropic or openai_compat for real narration.)"
        )

    # ── agent chat (in-character roleplay) ────────────────────────────────────
    # Parse every field from the structured prompt
    import re as _re

    name, role, mood, goals_str, traits_str, groups_str = "", "", "", "", "", ""
    chat_rels: dict[str, dict] = {}   # name -> {type, strength}
    chat_mems: list[str] = []
    world_event_chat = ""
    user_message = ""
    _section = ""

    for line in user.splitlines():
        stripped = line.strip()
        if stripped == "CHARACTER PROFILE":
            _section = "profile"
        elif stripped == "RELATIONSHIPS":
            _section = "rels"
        elif stripped == "MEMORIES":
            _section = "mems"
        elif stripped == "WORLD EVENT":
            _section = "event"
        elif stripped == "USER MESSAGE":
            _section = "msg"
        elif _section == "profile":
            if line.startswith("Name: "):
                name = line[6:].strip()
            elif line.startswith("Role: "):
                role = line[6:].strip()
            elif line.startswith("Current mood: "):
                mood = line[14:].strip()
            elif line.startswith("Goals: "):
                goals_str = line[7:].strip()
            elif line.startswith("Traits: "):
                traits_str = line[8:].strip()
            elif line.startswith("Groups: "):
                groups_str = line[8:].strip()
        elif _section == "rels" and stripped.startswith("- "):
            # Format: "  - Sage: friendship (strength +0.45)"
            m = _re.match(r"-\s+(.+?):\s+(\w+)\s+\(strength ([+-]?\d+\.?\d*)\)", stripped)
            if m:
                chat_rels[m.group(1).strip()] = {
                    "type": m.group(2),
                    "strength": float(m.group(3)),
                }
        elif _section == "mems" and stripped.startswith("- "):
            chat_mems.append(stripped[2:].strip())
        elif _section == "event" and stripped and not stripped.startswith("("):
            world_event_chat = stripped
        elif _section == "msg":
            user_message += line + "\n"

    user_message = user_message.strip()
    q = user_message.lower()

    traits = [t.strip() for t in traits_str.split(",") if t.strip() and t.strip() != "none"]
    goals = [g.strip() for g in goals_str.split(",") if g.strip() and g.strip() != "none"]

    # ── Intent: asking about a specific person ─────────────────────────────────
    mentioned = None
    for rel_name in chat_rels:
        if rel_name.lower() in q:
            mentioned = rel_name
            break

    if mentioned:
        rel = chat_rels[mentioned]
        rtype = rel["type"]
        strength = rel["strength"]
        abs_s = abs(strength)
        intensity = "deeply" if abs_s > 0.7 else ("genuinely" if abs_s > 0.4 else "somewhat")

        _REL_RESPONSES: dict[str, list[str]] = {
            "friendship": [
                f"{mentioned} and I just clicked. I can't always explain it — there's a trust there that built up over time. I value that.",
                f"We've been through enough together that the friendship feels real. Not just surface level.",
                f"I like {mentioned}. They're consistent. That matters more to me than most people realize.",
            ],
            "romance": [
                f"That's... a complicated thing to talk about. {mentioned} means something to me. More than I usually let on.",
                f"There's something between me and {mentioned} that I haven't figured out how to name yet. But I feel it.",
                f"I care about {mentioned} in a way that's different from everyone else. I'm still working out what to do with that.",
            ],
            "rivalry": [
                f"{mentioned} and I see the world differently. Fundamentally differently. And neither of us is backing down.",
                f"I don't hate {mentioned}. I just think we want the same things and only one of us can have them.",
                f"It's competitive. It's been competitive for a while. {mentioned} pushes me, and I can't decide if I resent that or need it.",
            ],
            "conflict": [
                f"Things between me and {mentioned} have been rough. Something happened that I haven't fully let go of.",
                f"I'm trying not to make it worse, but {mentioned} and I are not in a good place right now.",
                f"There's real tension there. I know it, they know it. Neither of us has fixed it yet.",
            ],
            "trust": [
                f"I trust {mentioned}. That's not something I say lightly.",
                f"There's a reason I confide in {mentioned} when I wouldn't with others. They've earned that.",
                f"{mentioned} has never given me a reason to doubt them. That means a lot in a place like this.",
            ],
            "alliance": [
                f"{mentioned} and I are aligned on what we're trying to accomplish. It makes sense to work together.",
                f"We're on the same side. For now, at least. And that's been useful for both of us.",
                f"It's strategic, but it's also real. I respect what {mentioned} brings to the table.",
            ],
            "influence": [
                f"{mentioned} has shifted how I think about things. I'm not always sure that's comfortable to admit.",
                f"There's an influence there — whether it's me on them or them on me, I'm honestly not sure anymore.",
                f"I've started noticing how often {mentioned}'s perspective finds its way into my thinking.",
            ],
            "group_membership": [
                f"We're in the same world, {mentioned} and me. That creates a kind of connection whether you plan for it or not.",
                f"The shared context with {mentioned} means we understand things about each other's situation that outsiders don't.",
                f"Being in the same group gives us common ground. What we do with that is another question.",
            ],
        }

        responses = _REL_RESPONSES.get(rtype, [
            f"My relationship with {mentioned} is... complicated. I don't think I can sum it up easily.",
        ])

        # Check if the question is specifically "why"
        if "why" in q:
            _WHY: dict[str, list[str]] = {
                "friendship": [
                    f"{mentioned} showed up when it counted. That's really the whole reason.",
                    f"Some friendships just happen. Ours did. I stopped questioning it.",
                    f"We have shared history and I trust them. That's the short version.",
                ],
                "romance": [
                    f"Because they see something in me that most people miss. And I see it in them too.",
                    f"I tried not to feel this way. It didn't work.",
                    f"There's no clean answer to that. But I keep coming back to them.",
                ],
                "rivalry": [
                    f"Because we want the same things and we're both unwilling to step aside.",
                    f"It started small — a disagreement, then another. Now it's just what we are.",
                    f"Honestly? {mentioned} is good. And I hate that I have to compete with someone that good.",
                ],
                "conflict": [
                    f"Something happened between us that didn't get resolved. And it's been sitting there since.",
                    f"I said something, or they said something — I'm not even sure anymore who started it. But here we are.",
                    f"We just don't see eye to eye on things that matter. That has a way of creating friction.",
                ],
                "trust": [
                    f"They've never given me a reason not to. That's actually pretty rare.",
                    f"Because I tested it — not deliberately, but I did — and they didn't let me down.",
                    f"Trust builds slowly with me. But with {mentioned}, it built.",
                ],
            }
            responses = _WHY.get(rtype, responses)

        return f"{rng.choice(responses)} [{intensity} {rtype}, strength {strength:+.2f}]"

    # ── Intent: asking about all relationships / social life ──────────────────
    if any(w in q for w in ("relationship", "friend", "people", "social", "who do you know", "connections", "know here")):
        if chat_rels:
            closest = max(chat_rels.items(), key=lambda x: abs(x[1]["strength"]))
            cname, crel = closest
            return (
                f"I've got a few connections here. The one that stands out most right now is {cname} — "
                f"we have a {crel['type']} that's been pretty significant. "
                f"Whether that's good or complicated depends on the day."
            )
        return "I haven't built many connections yet. I'm still figuring out who in this place I actually trust."

    # ── Intent: asking about traits / identity ────────────────────────────────
    # Use word boundary check so "who are your friends" doesn't hit "who are you"
    _intro_triggers = ("trait", "personality", "like you", "describe yourself", "tell me about yourself")
    _who_are_you = q.rstrip("?").strip() in ("who are you", "who r you", "what are you like", "what are you")
    if _who_are_you or any(w in q for w in _intro_triggers):
        trait_str = ", ".join(traits[:3]) if traits else "hard to pin down"
        goal = goals[0] if goals else "find my place"
        return (
            f"I'm a {role or 'person'} — {trait_str}. "
            f"Right now I'm feeling {mood}. "
            f"What drives me most is trying to {goal}. "
            f"That probably explains most of what you see from me."
        )

    # ── Intent: asking about memories / what happened ─────────────────────────
    if any(w in q for w in ("remember", "memory", "happened", "what did you do", "tell me what", "lately", "recently")):
        if chat_mems:
            mem = chat_mems[-1]
            return f"The thing that's most on my mind right now: {mem}"
        return "Honestly, the days have been blurring together lately. Nothing I can point to clearly."

    # ── Intent: asking about the world event ──────────────────────────────────
    if any(w in q for w in ("event", "happening", "going on", "situation", "what's")):
        if world_event_chat:
            return f"You mean {world_event_chat.lower().rstrip('.')}? Yeah. That's been affecting everyone here, including me."
        return "Things are relatively quiet right now. Which, honestly, I don't fully trust."

    # ── Intent: asking about goals ────────────────────────────────────────────
    if any(w in q for w in ("goal", "want", "trying to", "ambition", "plan")):
        goal = goals[0] if goals else "figure things out"
        return f"What I'm working toward? Trying to {goal}. That's what gets me up in the morning."

    # ── Fallback: contextual response built from character's actual data ──────
    # For very short/unclear messages, ask for clarification in-character
    if len(q.split()) <= 2:
        clarify_opts = [
            f"I'm not sure what you're asking. Can you be more specific?",
            f"What do you mean exactly? I don't want to assume.",
            f"Say more — I don't know what you're getting at.",
            f"You'll have to give me more than that.",
        ]
        return rng.choice(clarify_opts)

    # Build a situational response from real character data
    parts: list[str] = []
    if mood:
        _MOOD_OPENER = {
            "frustrated": "Things haven't been easy lately.",
            "excited": "There's a lot going on and I'm trying to keep up.",
            "lonely": "It's been a quieter stretch than I'd like.",
            "ambitious": "I've been focused — head down, working toward something.",
            "heartbroken": "I'm dealing with some things. It's been heavy.",
            "confident": "Things are actually going well right now.",
            "anxious": "There's a lot on my mind that I haven't sorted out yet.",
            "hopeful": "I'm in a decent place, honestly. Cautiously.",
            "angry": "I'm not going to pretend I'm fine with how some things have gone.",
            "calm": "I'm steady. Not much to complain about.",
            "content": "Things feel settled, which is rare for me.",
        }
        parts.append(_MOOD_OPENER.get(mood, f"I'm feeling {mood} right now."))

    if chat_rels:
        strongest = max(chat_rels.items(), key=lambda x: abs(x[1]["strength"]))
        sname, srel = strongest
        _REL_SNIPPET = {
            "friendship": f"My friendship with {sname} has been one of the more grounding things lately.",
            "romance": f"There's something between me and {sname} that's been taking up more of my thinking than I expected.",
            "rivalry": f"The tension with {sname} hasn't gone away. If anything it's sharpened.",
            "conflict": f"Things with {sname} are unresolved. That's weighing on me.",
            "trust": f"I've been leaning on {sname} more than usual — they've been solid.",
            "alliance": f"{sname} and I have been moving in the same direction lately. That helps.",
            "influence": f"{sname} has been on my mind. They've shifted how I'm thinking about a few things.",
            "group_membership": f"Being connected to {sname} through our shared world has made things interesting.",
        }
        parts.append(_REL_SNIPPET.get(srel["type"], f"My situation with {sname} has been significant lately."))

    if chat_mems:
        parts.append(f"The last thing that really stuck with me: {chat_mems[-1]}")

    if parts:
        return " ".join(parts)

    return f"Honestly, I'm not sure how to answer that. Ask me something more specific."
