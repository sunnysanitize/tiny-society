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

# The premise rides along on EVERY per-agent call, so its cost is paid once per agent per
# day. Cap it: a player can paste an essay into the world prompt, and the character sheet
# and memories below it matter more to the action than paragraph six of the setting.
MAX_PREMISE_CHARS = 600


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
