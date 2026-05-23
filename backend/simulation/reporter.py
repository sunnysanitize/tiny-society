from __future__ import annotations

from typing import Optional

from models import DaySnapshot, MacroMetrics, Forecast
from llm import call_llm

REPORT_SYSTEM = """FINAL_REPORT
You are a social-dynamics analyst writing a concise narrative report on a multi-agent simulation.
You will be given before/after macro metrics, the day-by-day highlights, and (if present) a
PREDICTION QUESTION plus the population's BELIEF TRAJECTORY and PIVOTAL DAYS.

Write a 4-6 paragraph summary in plain prose covering:
- how the injected event reshaped the society
- which agents gained or lost influence and why
- which factions, romances, rivalries, or alliances formed
- any surprising emergent dynamics
- the final social shape compared to Day 0

If a PREDICTION QUESTION is given, END with a clearly-labeled forecast paragraph that answers it,
grounded in the final population belief means, the quantified confidence, and the causal chain of
pivotal days (what happened on each that moved sentiment).

Do not invent agent names that weren't in the data. Keep tone analytical, not gamey.
"""

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
) -> tuple[str, Optional[Forecast]]:
    """Returns (narrative report string, structured Forecast or None).

    A single FINAL_REPORT LLM call produces the narrative; its prompt is enriched
    with the population belief trajectory and pivotal-day causal summaries when a
    question/topics are present. The Forecast's numeric fields are computed in
    Python from the real per-day metrics.
    """
    topics = topics or []
    dynamic_events = dynamic_events or {}

    highlights_blob = []
    for s in snapshots:
        if not s.highlights:
            continue
        line = f"Day {s.day}: " + "; ".join(
            f"{h.agent}: {h.summary}" for h in s.highlights[:4]
        )
        highlights_blob.append(line)

    # Pre-compute pivotal days so we can feed their causal attribution into the prompt.
    prelim = build_forecast(snapshots, question, topics, dynamic_events, narrative="")
    pivotal_days = prelim.pivotal_days if prelim else []

    user = (
        f"WORLD: {world_prompt}\n\n"
        f"STARTING EVENT: {starting_event or '(none)'}\n\n"
        f"INITIAL METRICS (Day 0):\n{initial.model_dump_json(indent=2)}\n\n"
        f"FINAL METRICS (Day {snapshots[-1].day if snapshots else 0}):\n"
        f"{final.model_dump_json(indent=2)}\n\n"
        f"DAILY HIGHLIGHTS:\n" + "\n".join(highlights_blob[:30])
    )

    if question or final.topic_means:
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
        narrative = call_llm(REPORT_SYSTEM, user, max_tokens=1500, tier="strong")
    except Exception as e:
        narrative = f"(Report generation failed: {e})"

    forecast = build_forecast(snapshots, question, topics, dynamic_events, narrative)
    return narrative, forecast
