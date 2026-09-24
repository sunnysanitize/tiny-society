"""The world premise, formatted for a per-agent prompt.

The premise the player typed ("a League of Legends team at U of T — five undergrad
friends") used to reach only three places: world-graph extraction, filler generation,
and the final report. Every per-day LLM call that actually writes the story — reason,
plan, reflect, vignette — ran without it, so the model saw five names, some traits and
a relationship table and nothing else. With no setting to write toward it falls back to
the median of "group of people with a shared goal", which is why a varsity esports roster
produced offsite prose: team-building activities, strategic discussions, holistic
development. Threading the premise through is what keeps the world's own vocabulary
(scrims, solo queue, VOD review, midterms) in the generated text.

The block is deliberately small and identical everywhere, so a premise cannot drift
between the call that plans an action and the call that carries it out.
"""
from __future__ import annotations

from typing import Optional

from models import WorldLens

# The premise rides along on EVERY per-agent call, so its cost is paid once per agent per
# day. Cap it: a player can paste an essay into the world prompt, and the character sheet
# and memories below it matter more to the action than paragraph six of the setting.
MAX_PREMISE_CHARS = 600

# Bounds on the rendered body. The block rides on every per-agent call each day, so its
# size must track the lens's own caps, never the length of what the user pasted.
_MAX_RENDER_CHARS = 1400


def render_premise(lens: Optional[WorldLens], world_prompt: str) -> str:
    """The premise body handed to every per-day prompt.

    Prefers the lens: its summary, what is and isn't possible here, where people meet,
    how this world sounds, and the words that would break it. Falls back to the raw
    prompt when the lens is empty — a world created before the lens existed, or one
    whose extraction failed — so no code path depends on interpretation succeeding.
    """
    if lens is None or lens.is_empty():
        return (world_prompt or "").strip()

    parts: list[str] = []
    if lens.premise_summary:
        parts.append(lens.premise_summary)
    elif world_prompt:
        parts.append(world_prompt.strip())
    if lens.central_stake:
        parts.append(f"At stake: {lens.central_stake}")
    if lens.affordances:
        parts.append("What is true here: " + "; ".join(lens.affordances))
    if lens.gathering_places:
        parts.append("Where you encounter each other: " + ", ".join(lens.gathering_places))
    if lens.register_notes:
        parts.append(f"How this world sounds: {lens.register_notes}")
    if lens.banned_vocabulary:
        parts.append(
            "Never use these words — they belong to another world: "
            + ", ".join(lens.banned_vocabulary)
        )
    return "\n".join(parts)[:_MAX_RENDER_CHARS]


def premise_lines(world_premise: Optional[str]) -> list[str]:
    """Prompt lines introducing the world, or [] when there is no premise.

    Returning a list lets callers splat this into their `parts` list with `*`, so a
    missing premise leaves no empty header behind.
    """
    text = (world_premise or "").strip()
    if not text:
        return []
    if len(text) > MAX_PREMISE_CHARS:
        text = text[:MAX_PREMISE_CHARS].rstrip() + "…"
    return [
        "WORLD PREMISE (the setting you live in — think, speak and act inside it)",
        text,
        "Use the specific vocabulary, places, pressures and routines of THIS world. Never "
        "fall back on generic organizational language.",
        "",
    ]
