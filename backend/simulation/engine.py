from __future__ import annotations

import copy
import logging
import os
import random
import time
from typing import Callable, Optional

from models import (
    Agent, World, SimulationConfig, SimulationResult,
    DaySnapshot, DayHighlight,
)
from .selector import select_reasoning_agents
from .reasoner import reason_for_agent
from .deterministic import apply_background_rules
from .applicator import apply_action
from .metrics import compute_metrics, snapshot_influence
from .reporter import generate_final_report


def run_simulation(
    world: World,
    config: SimulationConfig,
    *,
    seed: int = 42,
    on_day: Optional[Callable[[DaySnapshot], None]] = None,
    initial_agents: Optional[list[Agent]] = None,
    day_offset: int = 0,
) -> SimulationResult:
    rng = random.Random(seed)
    agents = [copy.deepcopy(a) for a in (initial_agents or world.agents)]
    if not agents:
        raise ValueError("World has no agents")

    baseline_influence = snapshot_influence(agents)
    initial_metrics = compute_metrics(agents, baseline_influence=baseline_influence)

    snapshots: list[DaySnapshot] = []
    full_event_log: list[str] = []
    dynamic_events: dict[str, str] = {}

    # Starting event shown for first 3 days of a fresh run
    active_event: Optional[str] = world.starting_event if day_offset == 0 else None

    for day in range(1, config.days + 1):
        abs_day = day + day_offset
        day_log: list[str] = []
        day_highlights: list[DayHighlight] = []
        type_changes = 0

        # Clear starting event after day 3
        if day == 4 and active_event == world.starting_event:
            active_event = None

        # AI-generated dynamic event every 5 absolute days (after day 3)
        if abs_day > 3 and abs_day % 5 == 0:
            new_ev = _generate_dynamic_event(full_event_log, agents)
            if new_ev:
                active_event = new_ev
                dynamic_events[str(abs_day)] = new_ev
                logging.info(f"Dynamic event generated for day {abs_day}: {new_ev!r}")

        # MORNING: promote last short-term memory to long-term; reset
        for a in agents:
            if abs_day > 1:
                if a.short_term_memory:
                    promoted = a.short_term_memory[-1]
                    if promoted and promoted not in a.long_term_memory:
                        a.long_term_memory.append(promoted)
                        a.long_term_memory = a.long_term_memory[-20:]
                a.short_term_memory = []

        # AFTERNOON: select agents, run AI reasoning + deterministic rules
        selected = select_reasoning_agents(
            agents,
            world.starting_event if abs_day == 1 else _recent_event_summary(full_event_log),
            config.reasoning_agents_per_day,
        )
        selected_ids = {a.id for a in selected}
        background = [a for a in agents if a.id not in selected_ids]

        _llm_delay = float(os.getenv("LLM_CALL_DELAY_SECS", "2.0"))

        day_perception_notes: list = []

        for i, actor in enumerate(selected):
            if i > 0 and _llm_delay > 0:
                time.sleep(_llm_delay)
            logging.info(f"Day {abs_day}: reasoning for {actor.name} ({i+1}/{len(selected)})")
            action = reason_for_agent(
                actor,
                agents,
                event=active_event,
                recent_log=full_event_log[-10:],
            )
            if action is None:
                continue
            log_line, notes = apply_action(actor, action, agents)
            day_log.append(log_line)
            day_perception_notes.extend(notes)
            day_highlights.append(DayHighlight(
                agent=actor.name,
                summary=action.new_memory or f"{action.action} {', '.join(action.target_agents) or '(no one)'} — {action.explanation}",
            ))
            type_changes += sum(
                1 for eff in action.relationship_effects.values()
                if abs(eff.strength_delta) >= 0.15
            )

        # EVENING: background rules + relationship decay
        bg_log = apply_background_rules(background, agents, rng)
        day_log.extend(bg_log)

        # NIGHT: compute metrics + snapshot
        metrics = compute_metrics(
            agents,
            type_changes_today=type_changes,
            baseline_influence=baseline_influence,
        )
        full_event_log.extend(day_log)

        snap = DaySnapshot(
            day=abs_day,
            agents=[copy.deepcopy(a) for a in agents],
            event_log=day_log,
            highlights=day_highlights,
            metrics=metrics,
            active_event=active_event,
            perception_notes=day_perception_notes,
        )
        snapshots.append(snap)

        if on_day:
            on_day(snap)

    final_metrics = snapshots[-1].metrics if snapshots else initial_metrics
    report = generate_final_report(
        initial_metrics,
        final_metrics,
        snapshots,
        world.prompt,
        world.starting_event,
    )

    return SimulationResult(
        days=abs_day if snapshots else config.days,
        snapshots=snapshots,
        initial_metrics=initial_metrics,
        final_metrics=final_metrics,
        final_report=report,
        dynamic_events=dynamic_events,
    )


def _generate_dynamic_event(recent_log: list[str], agents: list[Agent]) -> Optional[str]:
    from llm import call_llm
    if not recent_log:
        return None
    tense = [a for a in agents if a.mood in ("angry", "frustrated", "anxious", "heartbroken", "lonely")]
    mood_hint = f"Several agents feel {tense[0].mood}." if tense else ""
    activity = "\n".join(recent_log[-8:])
    prompt = (
        f"Recent activity:\n{activity}\n\n{mood_hint}\n\n"
        "Generate one world event sentence (no quotes, no prefix, under 20 words) "
        "that naturally follows from this activity."
    )
    try:
        raw = call_llm(
            "Generate a single-sentence world event for a social simulation. No quotes, no prefix, under 20 words.",
            prompt,
            max_tokens=60,
        )
        ev = raw.strip().strip('"').strip("'").strip()
        if ev and len(ev) > 10:
            return ev
    except Exception as e:
        logging.warning(f"Dynamic event generation failed: {e}")
    return None


def _recent_event_summary(log: list[str]) -> Optional[str]:
    if not log:
        return None
    return " | ".join(log[-3:])
