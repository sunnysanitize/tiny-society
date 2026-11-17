from __future__ import annotations

import logging
import re
from typing import Optional

from models import Agent, DaySnapshot, EventCast, MacroMetrics, Forecast, StoryThread, WorldLens
from llm import call_llm

def _report_system(lens: Optional["WorldLens"] = None) -> str:
    """The FINAL_REPORT system prompt, with its vocabulary parameterised from the lens.

    The report is the artifact where the branch's original failure was observed — a
    hardcoded "social-dynamics analyst" writing about "the society" and "the population"
    is a fair description of the voice that produced "holistic team development", and it
    used to sit in the highest-authority position (the system prompt) while the lens's
    own "use that, not 'society'" instruction was merely appended to the user message
    underneath it. Callers get a world-specific voice when a lens is available and a
    neutral fallback ("the society" / "the population") when it isn't — those two nouns
    remain acceptable DEFAULTS, just no longer hardcoded overrides.
    """
    collective = (lens.collective_noun.strip() if lens and lens.collective_noun else "") or "the society"
    population = (lens.actor_noun_plural.strip() if lens and lens.actor_noun_plural else "") or "the population"
    return f"""FINAL_REPORT
You are writing a concise narrative report on a multi-agent simulation of {collective}.
You will be given before/after macro metrics, the day-by-day highlights, and (if present) a
PREDICTION QUESTION plus {population}'s BELIEF TRAJECTORY and PIVOTAL DAYS.

Write a 4-6 paragraph summary in plain prose covering:
- how the injected event reshaped {collective}
- which agents gained or lost influence and why
- which factions, romances, rivalries, or alliances formed
- the relationship turning points, when the input includes them — trace these as the spine
  of the story: who changed toward whom, and what it set in motion. Do not just list
  activity; show the arc.
- any surprising emergent dynamics
- the final social shape compared to Day 0

If a PREDICTION QUESTION is given, END with a clearly-labeled forecast paragraph that answers it,
grounded in {population}'s final belief means, the quantified confidence, and the causal chain of
pivotal days (what happened on each that moved sentiment).

Do not invent agent names that weren't in the data.
ACCURACY IS THE FIRST RULE. Every sentence must be traceable to a line of the input:
- Attribute each action only to the person the log credits it to, on the day it happened.
- Describe relationships only as the RELATIONSHIP CHANGES list shows them; a pair not on
  the list did not meaningfully change. Never state counts, percentages or "tripled".
- Describe standing only as the STANDING list shows it.
- Never quote raw numbers, scores or decimals ("+2.8", "0.7691", "mean of 0.27"); the
  reader sees the numbers elsewhere. Say what they mean in words ("rose sharply",
  "barely moved", "the {population} stayed split").
- Never resolve what the log leaves open (who is guilty, who wins) unless the log shows it.
- Never embellish. Quote words only if they appear verbatim in the log; never add places,
  gestures, tones or details the log doesn't state. Use each person's role exactly as the
  CAST list gives it. Plain and exact beats vivid and invented.
- When the input has an EVENT LOG, end every sentence that states something that happened
  with the id(s) of the event(s) it rests on, like [E2.3] or [E1.4][E3.2]. A sentence you
  can't cite to an event is a sentence you shouldn't write. Outcomes marked ⇒ are what
  actually came of an attempt — use them; an attempt without ⇒ did not resolve.
WRITE IN THE WORLD'S OWN VOCABULARY. The WORLD line tells you the setting; use its
specific language, places, pressures and routines, and name the concrete things these
people actually did. Generic organizational prose — "team-building activity",
"strategic discussions", "holistic development", "stakeholder alignment" — is always
wrong: it describes no world in particular. Stay clear-eyed and specific rather than
breathless, but sound like someone who was there.
Write about what IS in the input. Never mention a section, heading, or category that
was not provided, and never state that information was missing or not detailed.
"""


# Neutral default (no lens) — kept as a module-level constant since some tests and
# callers reference the prompt without a lens in hand. generate_final_report below
# builds its own per-call via _report_system(lens) so a lens, when present, actually
# reaches the highest-authority position instead of only the user message.
REPORT_SYSTEM = _report_system(None)

# How many pivotal days to surface in the forecast/report.
MAX_PIVOTAL_DAYS = 3


def _topic_drift(prev: MacroMetrics, cur: MacroMetrics) -> float:
    """Total day-over-day movement of the aggregate distribution: sum of absolute
    changes in per-topic mean across all shared topics."""
    drift = 0.0
    for topic, cur_mean in cur.topic_means.items():
        prev_mean = prev.topic_means.get(topic)
        if prev_mean is not None:
            drift += abs(cur_mean - prev_mean)
    return drift


def _attribute_day(snap: DaySnapshot, dynamic_events: dict[str, str]) -> str:
    """What happened on a given day, for causal attribution: prefer a dynamic
    world event, else the day's highlights, else the raw event log."""
    parts: list[str] = []
    ev = dynamic_events.get(str(snap.day)) or snap.active_event
    if ev:
        parts.append(f"event: {ev}")
    if snap.highlights:
        parts.append("; ".join(f"{h.agent}: {h.summary}" for h in snap.highlights[:3]))
    elif snap.event_log:
        parts.append("; ".join(snap.event_log[:3]))
    return " | ".join(parts) if parts else "(no notable activity)"


def build_forecast(
    snapshots: list[DaySnapshot],
    question: Optional[str],
    topics: list[str],
    dynamic_events: dict[str, str],
    narrative: str,
) -> Optional[Forecast]:
    """Compute the structured Forecast from real per-day metrics.

    Pivotal days = the days with the largest day-over-day movement of the
    aggregate stance distribution (sum of |Δ mean| across topics), most-pivotal
    first. Numeric fields come straight from the final day's MacroMetrics; the
    narrative is supplied by the (single) FINAL_REPORT LLM call.

    Returns None only when there's nothing to forecast (no question and no topics).
    """
    if not snapshots:
        return None
    final = snapshots[-1].metrics
    has_topics = bool(final.topic_means)
    if not question and not has_topics:
        return None

    # Day-over-day drift of the aggregate distribution → pivotal days.
    drifts: list[tuple[int, float]] = []
    for i in range(1, len(snapshots)):
        d = _topic_drift(snapshots[i - 1].metrics, snapshots[i].metrics)
        drifts.append((snapshots[i].day, d))
    drifts.sort(key=lambda x: x[1], reverse=True)
    pivotal_days = [day for day, drift in drifts[:MAX_PIVOTAL_DAYS] if drift > 1e-9]

    return Forecast(
        question=question,
        topic_means=dict(final.topic_means),
        topic_uncertainty=dict(final.topic_uncertainty),
        confidence=final.belief_confidence,
        pivotal_days=pivotal_days,
        narrative=narrative,
    )


def _belief_trajectory_blob(snapshots: list[DaySnapshot], topics: list[str]) -> str:
    """Compact per-day population-mean trajectory for the report prompt."""
    lines: list[str] = []
    for s in snapshots:
        tm = s.metrics.topic_means
        if not tm:
            continue
        means = ", ".join(f"{t}={tm[t]:+.2f}" for t in tm)
        lines.append(f"Day {s.day}: {means} (confidence={s.metrics.belief_confidence:.2f})")
    return "\n".join(lines)


def _pivotal_blob(
    snapshots: list[DaySnapshot], pivotal_days: list[int], dynamic_events: dict[str, str]
) -> str:
    by_day = {s.day: s for s in snapshots}
    lines: list[str] = []
    for day in pivotal_days:
        snap = by_day.get(day)
        if snap:
            lines.append(f"Day {day} (belief shifted most): {_attribute_day(snap, dynamic_events)}")
    return "\n".join(lines)


# A pair is worth reporting when its type changed or its affinity moved at least this much.
_REL_CHANGE_MIN = 0.15


def _relationship_changes(initial_agents: list[Agent], final_agents: list[Agent]) -> list[str]:
    """Per-pair, per-direction relationship changes from day 0 to the end — the ground
    truth the report used to guess at from aggregate counts."""
    before = {a.name: a.relationships for a in initial_agents}
    lines: list[str] = []
    for a in final_agents:
        for other, rel in a.relationships.items():
            old = before.get(a.name, {}).get(other)
            old_type, old_str = (old.type, old.strength) if old else ("none", 0.0)
            if old_type == rel.type and abs(rel.strength - old_str) < _REL_CHANGE_MIN:
                continue
            lines.append(
                f"{a.name} → {other}: {old_type} {old_str:+.2f} ⇒ {rel.type} {rel.strength:+.2f}"
            )
    return lines


def _standing_changes(initial_agents: list[Agent], final_agents: list[Agent]) -> list[str]:
    before = {a.name: a.influence_score for a in initial_agents}
    rows = sorted(
        ((a.influence_score - before.get(a.name, 0.0), a.name) for a in final_agents),
        reverse=True,
    )
    return [f"{name}: {delta:+.1f}" for delta, name in rows]


_CITE_RE = re.compile(r"\s*\[(E\d+\.\d+)\]")


def _check_citations(narrative: str, valid_ids: set[str]) -> str:
    """Count how many cited event ids exist, then strip the markers for display.

    Citing forces each claim to rest on a logged event; the ids themselves are noise
    to a reader. Invalid ids mean the report referenced an event that doesn't exist."""
    cited = _CITE_RE.findall(narrative)
    if cited:
        bad = [c for c in cited if c not in valid_ids]
        logging.info(f"Report cited {len(cited)} events, {len(bad)} unknown: {bad[:5]}")
    return _CITE_RE.sub("", narrative)


def generate_final_report(
    initial: MacroMetrics,
    final: MacroMetrics,
    snapshots: list[DaySnapshot],
    world_prompt: str,
    starting_event: str | None,
    *,
    question: Optional[str] = None,
    topics: Optional[list[str]] = None,
    dynamic_events: Optional[dict[str, str]] = None,
    lens: Optional["WorldLens"] = None,
    initial_agents: Optional[list[Agent]] = None,
    event_casts: Optional[dict[str, EventCast]] = None,
    threads: Optional[list[StoryThread]] = None,
) -> tuple[str, Optional[Forecast]]:
    """Returns (narrative report string, structured Forecast or None).

    A single FINAL_REPORT LLM call produces the narrative; its prompt is enriched
    with the population belief trajectory and pivotal-day causal summaries when a
    question/topics are present. The Forecast's numeric fields are computed in
    Python from the real per-day metrics.

    `lens`, when given and non-empty, does double duty: its vocabulary (collective
    noun, actor noun, register, banned words) parameterises the SYSTEM prompt itself
    (see `_report_system`), not just the user message, and is also summarised into a
    "HOW TO WRITE THIS WORLD" block prepended to the user message below.
    """
    topics = topics or []
    dynamic_events = dynamic_events or {}

    highlights_blob = []
    for s in snapshots:
        if not s.highlights:
            continue
        # Every action of the day, not a sample: a report that sees only the first few
        # fills the gaps itself and misattributes who did what.
        highlights_blob.append(f"Day {s.day}:\n" + "\n".join(
            f"  - {h.agent}: {h.summary}" for h in s.highlights[:12]
        ))

    # Pre-compute pivotal days so we can feed their causal attribution into the prompt.
    prelim = build_forecast(snapshots, question, topics, dynamic_events, narrative="")
    pivotal_days = prelim.pivotal_days if prelim else []

    # Relationship turning points across the run — the narrative spine.
    milestone_lines: list[str] = []
    for s in snapshots:
        ms = getattr(s, "milestones", None) or []
        if ms:
            milestone_lines.append(f"Day {s.day}: " + "; ".join(ms[:6]))

    user = f"WORLD: {world_prompt}\n\nSTARTING EVENT: {starting_event or '(none)'}\n\n"
    if snapshots:
        user += "CAST:\n" + "\n".join(f"- {a.name}: {a.role}" for a in snapshots[-1].agents) + "\n\n"
    cast = (event_casts or {}).get(starting_event or "")
    if cast and (cast.public or cast.truth):
        user += f"WHAT EVERYONE KNEW: {cast.public}\n"
        if cast.truth:
            user += f"THE HIDDEN TRUTH (only revealed if the log shows it coming out): {cast.truth}\n"
        user += "\n"
    events = [e for s in snapshots for e in s.events]
    if events:
        # The canonical log: what actually happened, with the outcome of every attempt.
        user += "EVENT LOG (cite these ids):\n" + "\n".join(
            f"[{e.id}] {e.text}" for e in events[:150]
        )
    else:  # snapshots from before the event log existed
        user += "DAILY ACTIONS:\n" + "\n".join(highlights_blob[:30])
    if snapshots and initial_agents is not None:
        final_agents = snapshots[-1].agents
        start = snapshots[0].day - 1
        rel_lines = _relationship_changes(initial_agents, final_agents)
        user += (
            f"\n\nRELATIONSHIP CHANGES (Day {start} ⇒ Day {snapshots[-1].day}, each direction):\n"
            + ("\n".join(rel_lines) if rel_lines else "(no relationship changed meaningfully)")
            + f"\n\nSTANDING CHANGE (influence, Day {start} ⇒ end):\n"
            + "\n".join(_standing_changes(initial_agents, final_agents))
        )
    else:
        user += (
            f"\n\nINITIAL METRICS (Day 0):\n{initial.model_dump_json(indent=2)}\n\n"
            f"FINAL METRICS:\n{final.model_dump_json(indent=2)}"
        )
    if lens is not None and not lens.is_empty():
        vocab: list[str] = []
        if lens.actor_noun_plural:
            vocab.append(f"These people are called {lens.actor_noun_plural}.")
        if lens.collective_noun:
            vocab.append(f"Collectively they are {lens.collective_noun} — use that, not 'society'.")
        if lens.register_notes:
            vocab.append(f"Register: {lens.register_notes}")
        if lens.banned_vocabulary:
            vocab.append(
                "Never use these words: " + ", ".join(lens.banned_vocabulary)
            )
        if vocab:
            user = "HOW TO WRITE THIS WORLD\n" + "\n".join(vocab) + "\n\n" + user

    if threads:
        user += "\n\nSTORY THREADS (say which were settled and which are still open):\n" + "\n".join(
            f"- [{t.status}] {t.summary}" for t in threads)

    if milestone_lines:
        user += (
            "\n\nRELATIONSHIP TURNING POINTS (chronological — anchor the narrative on these):\n"
            + "\n".join(milestone_lines[:40])
        )

    if question:
        traj = _belief_trajectory_blob(snapshots, topics)
        pivotal = _pivotal_blob(snapshots, pivotal_days, dynamic_events)
        user += "\n\n"
        if question:
            user += f"PREDICTION QUESTION: {question}\n\n"
        if traj:
            user += f"POPULATION BELIEF TRAJECTORY (per-topic mean stance per day):\n{traj}\n\n"
        if pivotal:
            user += f"PIVOTAL DAYS (largest belief shifts) and what drove them:\n{pivotal}\n\n"
        user += (
            f"FINAL BELIEF MEANS: {final.topic_means}\n"
            f"FINAL DISAGREEMENT (stddev per topic): {final.topic_uncertainty}\n"
            f"OVERALL CONFIDENCE (1=consensus, 0=split): {final.belief_confidence}\n"
        )

    try:
        narrative = call_llm(_report_system(lens), user, max_tokens=1800, tier="strong")
    except Exception as e:
        narrative = f"(Report generation failed: {e})"
    else:
        narrative = _check_citations(narrative, {e.id for e in events})

    forecast = build_forecast(snapshots, question, topics, dynamic_events, narrative)
    return narrative, forecast
