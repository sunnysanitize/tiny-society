from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import Agent, PerceptionNote
from llm import call_llm

PERCEPTION_SYSTEM = """PERCEPTION_NARRATION
You are the internal perception filter of a fictional character in a social simulation.
A social event just occurred that involves your character as the receiver. Your job is to
determine how your character actually perceived and internalized this event — which may
differ significantly from its face value depending on their personality, history, and
current emotional state.

You will be given:
- Your character's full profile: declared traits, revealed behavioral patterns, mood, memories
- The incoming event: what another character did, and the raw social signal strength
- Your existing relationship with the acting character

Return STRICT JSON only — no prose, no markdown:
{
  "perceived_delta": float,       // -1.0 to 1.0: how much this actually lands for your character
  "narrative": "string",          // one sentence, third-person observer voice, specific to this
                                  // character's personality and history with the actor
  "revealed_trait": "string|null" // if this reaction surfaces a behavioral pattern not already
                                  // in declared traits (e.g. "slow to forgive", "craves validation"),
                                  // name it concisely; otherwise null
}

Rules:
- perceived_delta can be less than, equal to, or greater than the raw_delta
- Perception can amplify OR dampen — a supportive gesture from a distrusted person lands weakly;
  a blunt challenge from a respected rival can land positively
- A negative raw_delta can be perceived positively if the character's personality warrants it
- The narrative MUST reference this specific character's traits or memories — not generic psychology
- revealed_trait should only be set when the reaction reveals something genuinely new and specific
- Output only JSON. Nothing else.
"""


def perceive_event(
    perceiver: Agent,
    actor: Agent,
    raw_delta: float,
    rel_type: str,
    action_summary: str,
) -> tuple[float, Optional[PerceptionNote]]:
    """
    Filter an incoming social event through the perceiver's character.

    Returns (perceived_delta, PerceptionNote | None).
    When the event is below significance threshold, returns raw_delta and None.
    On LLM failure, returns raw_delta and None — the simulation continues unaffected.
    """
    if not _is_significant(perceiver, actor, raw_delta):
        return raw_delta, None

    user_prompt = _build_prompt(perceiver, actor, raw_delta, rel_type, action_summary)
    try:
        raw = call_llm(PERCEPTION_SYSTEM, user_prompt, json_mode=True, max_tokens=400)
    except Exception as e:
        logging.warning(f"Perception LLM failed ({perceiver.name} ← {actor.name}): {e}")
        return raw_delta, None

    data = _safe_json(raw)
    if not data:
        logging.warning(f"Perception LLM bad JSON ({perceiver.name} ← {actor.name}): {raw[:120]!r}")
        return raw_delta, None

    try:
        perceived_delta = float(data.get("perceived_delta", raw_delta))
        perceived_delta = round(max(-1.0, min(1.0, perceived_delta)), 3)

        narrative = str(data.get("narrative") or "").strip()[:300]
        if not narrative:
            return raw_delta, None

        revealed_trait_raw = data.get("revealed_trait")
        revealed_trait: Optional[str] = None
        if isinstance(revealed_trait_raw, str):
            revealed_trait = revealed_trait_raw.strip()[:60] or None

        # Feed the revealed trait back into the agent's live profile
        if revealed_trait and revealed_trait not in perceiver.revealed_traits:
            perceiver.revealed_traits.append(revealed_trait)
            perceiver.revealed_traits = perceiver.revealed_traits[-10:]

        note = PerceptionNote(
            perceiver=perceiver.name,
            actor=actor.name,
            raw_delta=round(raw_delta, 3),
            perceived_delta=perceived_delta,
            relationship_type=rel_type,
            narrative=narrative,
            revealed_trait=revealed_trait,
        )
        return perceived_delta, note

    except Exception as e:
        logging.warning(f"PerceptionNote build failed ({perceiver.name}): {e}")
        return raw_delta, None


def _is_significant(perceiver: Agent, actor: Agent, raw_delta: float) -> bool:
    """
    Only fire the LLM when there is enough personal context to generate
    meaningful perception — i.e. the result could plausibly differ from raw_delta.
    """
    if abs(raw_delta) < 0.05:
        return False
    # Prior relationship exists: perceiver has a formed view of this person
    if actor.name in perceiver.relationships:
        return True
    # Actor appears in perceiver's memory: personal history exists
    actor_lower = actor.name.lower()
    for mem in perceiver.short_term_memory + perceiver.long_term_memory:
        if actor_lower in mem.text.lower():
            return True
    return False


def _build_prompt(
    perceiver: Agent,
    actor: Agent,
    raw_delta: float,
    rel_type: str,
    action_summary: str,
) -> str:
    existing = perceiver.relationships.get(actor.name)
    existing_desc = (
        f"{existing.type} (strength {existing.strength:+.2f})"
        if existing else "no prior relationship on record"
    )

    # Memories that mention the actor are most relevant; fall back to recent general memory
    actor_lower = actor.name.lower()
    actor_memories = [
        m.text for m in (perceiver.short_term_memory + perceiver.long_term_memory)
        if actor_lower in m.text.lower()
    ][-4:]
    context_memories = actor_memories or [
        m.text for m in (perceiver.long_term_memory[-3:] + perceiver.short_term_memory[-2:])
    ]

    direction = "positive" if raw_delta >= 0 else "negative"
    signal_desc = f"{direction}, magnitude {abs(raw_delta):.2f} — relationship type: {rel_type}"

    parts = [
        "YOUR CHARACTER",
        f"Name: {perceiver.name}",
        f"Role: {perceiver.role}",
        f"Declared traits: {', '.join(perceiver.traits) or '(none)'}",
        f"Revealed behavioral patterns: {', '.join(perceiver.revealed_traits) or '(none yet)'}",
        f"Current mood: {perceiver.mood}",
        f"Goals: {', '.join(perceiver.goals) or '(none)'}",
        "",
        "INCOMING EVENT",
        f"Acting character: {actor.name} ({actor.role})",
        f"What they did: {action_summary}",
        f"Raw social signal toward you: {signal_desc}",
        "",
        f"YOUR EXISTING RELATIONSHIP WITH {actor.name.upper()}",
        existing_desc,
        "",
        "YOUR MEMORIES MOST RELEVANT TO THIS PERSON",
        "\n".join(f"- {m}" for m in context_memories) if context_memories else "(none on record)",
        "",
        "Return your perception as JSON now.",
    ]
    return "\n".join(parts)


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
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}
