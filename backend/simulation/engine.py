from __future__ import annotations

import copy
import random
from typing import Optional

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
) -> SimulationResult:
    rng = random.Random(seed)
    agents = [copy.deepcopy(a) for a in world.agents]
    if not agents:
        raise ValueError("World has no agents")

    baseline_influence = snapshot_influence(agents)
    initial_metrics = compute_metrics(agents, baseline_influence=baseline_influence)

    snapshots: list[DaySnapshot] = []
    full_event_log: list[str] = []

    for day in range(1, config.days + 1):
        day_log: list[str] = []
        day_highlights: list[DayHighlight] = []
        type_changes = 0

        # MORNING: reset short-term memory; agents update goals (light)
        for a in agents:
            if day > 1:
                # Carry the most important short-term memory into long-term
                if a.short_term_memory:
                    promoted = a.short_term_memory[-1]
                    if promoted and promoted not in a.long_term_memory:
                        a.long_term_memory.append(promoted)
                        a.long_term_memory = a.long_term_memory[-20:]
                a.short_term_memory = []

        # AFTERNOON: select agents, run AI reasoning + deterministic rules
        selected = select_reasoning_agents(
            agents,
            world.starting_event if day == 1 else _recent_event_summary(full_event_log),
            config.reasoning_agents_per_day,
        )
        selected_ids = {a.id for a in selected}
        background = [a for a in agents if a.id not in selected_ids]

        active_event = world.starting_event if day <= 3 else None

        for actor in selected:
            action = reason_for_agent(
                actor,
                agents,
                event=active_event,
                recent_log=full_event_log[-10:],
            )
            if action is None:
                continue
            log_line = apply_action(actor, action, agents)
            day_log.append(log_line)
            day_highlights.append(DayHighlight(
                agent=actor.name,
                summary=f"{action.action} {', '.join(action.target_agents) or '(no one)'} — {action.explanation}",
            ))
            # Count type changes for volatility
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

        snapshots.append(DaySnapshot(
            day=day,
            agents=[copy.deepcopy(a) for a in agents],
            event_log=day_log,
            highlights=day_highlights,
            metrics=metrics,
        ))

    final_metrics = snapshots[-1].metrics if snapshots else initial_metrics
    report = generate_final_report(
        initial_metrics,
        final_metrics,
        snapshots,
        world.prompt,
        world.starting_event,
    )

    return SimulationResult(
        days=config.days,
        snapshots=snapshots,
        initial_metrics=initial_metrics,
        final_metrics=final_metrics,
        final_report=report,
    )


def _recent_event_summary(log: list[str]) -> Optional[str]:
    if not log:
        return None
    return " | ".join(log[-3:])
