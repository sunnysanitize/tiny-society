from __future__ import annotations

import copy
import logging
import os
import random
import time
from typing import Callable, Optional

from models import (
    Agent, World, SimulationConfig, SimulationResult,
    DaySnapshot, DayHighlight, Vignette,
)
from .selector import select_reasoning_agents
from .reasoner import reason_for_agent
from .reflector import reflect
from .planner import form_plan
from .deterministic import apply_background_rules
from .applicator import apply_action
from .observation import distribute_observation
from .metrics import compute_metrics, snapshot_influence
from .reporter import generate_final_report
from .worldgraph import extract_world_graph
from .stance import initialize_stances
from .vignette import generate_vignette_struct
from .prophecy import grade_prophecy

# Run a reflection pass (Stanford "Generative Agents" style) every N sim days for
# the agents reasoning that day, so the day's reasoning can use fresh reflections.
REFLECT_EVERY_DAYS = 4

# GOAL-DRIVEN PLANNING (Slice D ④): refresh a selected agent's short-term intention
# when they have none or it's at least this many sim days old. Keeps cost bounded —
# only the day's selected reasoning agents ever form plans.
PLAN_REFRESH_DAYS = 3

# MULTI-TURN EXCHANGES (Slice D ⑤): when an action is "charged", the primary target
# reasons in response, and optionally the actor replies once more. Per-chain extra
# turns and per-day total exchanges are capped to bound LLM cost.
MAX_EXCHANGE_TURNS = 2          # extra turns beyond the original action, per chain
MAX_EXCHANGES_PER_DAY = 3       # how many charged chains can fire in a single day

# A relationship type that makes any interaction emotionally charged.
_CHARGED_REL_TYPES = {"rivalry", "romance", "conflict"}

# THEATRICAL VIGNETTES (Slice E): at most this many charming first-person moments are
# generated per day (cost bound). Roughly one per day fires given the gating below.
MAX_VIGNETTES_PER_DAY = 2


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

    # WORLD KNOWLEDGE GRAPH: extract shared ground truth once (entities, power
    # structures, and the stance topics the society will divide on). Stored on the
    # world object so snapshots/saves carry it.
    if world.world_graph is None or world.world_graph.is_empty():
        world.world_graph = extract_world_graph(world)
    topics = world.world_graph.topics

    # PER-AGENT STANCE: seed each agent with a mild, varied starting position on each
    # world topic now that topics are known.
    initialize_stances(agents, topics)

    baseline_influence = snapshot_influence(agents)
    initial_metrics = compute_metrics(agents, baseline_influence=baseline_influence)

    snapshots: list[DaySnapshot] = []
    full_event_log: list[str] = []
    dynamic_events: dict[str, str] = {}

    # Starting event shown for first 3 days of a fresh run
    active_event: Optional[str] = world.starting_event if day_offset == 0 else None

    # INJECT-AN-EVENT nudge (Slice E): a player-authored event queued on the world
    # becomes the active_event on this run's FIRST day, taking priority over the
    # starting/auto-generated events, then is cleared so it fires exactly once. Works
    # for both the batch and stream continue paths since both call run_simulation.
    pending_event: Optional[str] = world.pending_event
    if pending_event:
        world.pending_event = None

    for day in range(1, config.days + 1):
        abs_day = day + day_offset
        day_log: list[str] = []
        day_highlights: list[DayHighlight] = []
        day_vignettes: list[Vignette] = []
        type_changes = 0

        # Clear starting event after day 3
        if day == 4 and active_event == world.starting_event:
            active_event = None

        # Player-injected event takes priority on the run's first day.
        if day == 1 and pending_event:
            active_event = pending_event

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
                    existing_texts = {m.text for m in a.long_term_memory}
                    if promoted.text and promoted.text not in existing_texts:
                        a.long_term_memory.append(promoted)
                        a.long_term_memory = a.long_term_memory[-40:]
                a.short_term_memory = []

        # AFTERNOON: select agents, run AI reasoning + deterministic rules
        selected = select_reasoning_agents(
            agents,
            world.starting_event if abs_day == 1 else _recent_event_summary(full_event_log),
            config.reasoning_agents_per_day,
            rng,
        )
        selected_ids = {a.id for a in selected}
        background = [a for a in agents if a.id not in selected_ids]

        # REFLECTION: every N days, the day's selected agents synthesize high-level
        # insights from their recent memories into high-importance long-term memories
        # (which then surface in this same day's relevance-based retrieval).
        if abs_day > 1 and abs_day % REFLECT_EVERY_DAYS == 0:
            for actor in selected:
                new_reflections = reflect(actor, current_day=abs_day)
                if new_reflections:
                    logging.info(
                        f"Day {abs_day}: {actor.name} reflected, "
                        f"{len(new_reflections)} new insight(s)"
                    )

        _llm_delay = float(os.getenv("LLM_CALL_DELAY_SECS", "2.0"))

        day_perception_notes: list = []
        by_name = {a.name: a for a in agents}
        exchanges_today = 0

        def _commit_action(actor: Agent, action) -> int:
            """Apply an action, route its observation/perception, log + highlight it.

            Returns the count of significant relationship-type changes it produced.
            Used identically for primary actions and multi-turn response turns."""
            nonlocal type_changes
            log_line, notes = apply_action(actor, action, agents, day=abs_day)
            day_log.append(log_line)
            # PER-AGENT OBSERVATION LOCALITY: route this action only to the agents
            # who could plausibly witness it (actor, targets, group-mates, or
            # everyone if the actor is a high-influence public figure).
            distribute_observation(
                log_line, actor, action.target_agents, agents,
                action_kind=action.action_kind, day=abs_day,
            )
            day_perception_notes.extend(notes)
            day_highlights.append(DayHighlight(
                agent=actor.name,
                summary=action.new_memory or f"{action.action} {', '.join(action.target_agents) or '(no one)'} — {action.explanation}",
            ))
            changed = sum(
                1 for eff in action.relationship_effects.values()
                if abs(eff.strength_delta) >= 0.15
            )
            type_changes += changed
            return log_line

        for i, actor in enumerate(selected):
            if i > 0 and _llm_delay > 0:
                time.sleep(_llm_delay)

            # PLANNING (④): refresh this selected agent's short-term intention if it's
            # missing or stale, BEFORE reasoning, so today's action can pursue it.
            if actor.plan is None or (abs_day - actor.plan_day) >= PLAN_REFRESH_DAYS:
                new_plan = form_plan(actor, active_event, abs_day)
                if new_plan:
                    actor.plan = new_plan
                    actor.plan_day = abs_day

            logging.info(f"Day {abs_day}: reasoning for {actor.name} ({i+1}/{len(selected)})")
            action = reason_for_agent(
                actor,
                agents,
                event=active_event,
                current_day=abs_day,
                world_graph=world.world_graph,
            )
            if action is None:
                continue
            log_line = _commit_action(actor, action)

            # MULTI-TURN EXCHANGES (⑤): if this was a CHARGED interaction with a
            # specific target, let that target respond, then optionally the actor
            # replies once more. Capped per chain and per day.
            if exchanges_today < MAX_EXCHANGES_PER_DAY and _is_charged(actor, action):
                exchanges_today += 1
                speaker, responder = actor, by_name.get(action.target_agents[0])
                prior_line = log_line
                for _turn in range(MAX_EXCHANGE_TURNS):
                    if responder is None or responder.id == speaker.id:
                        break
                    if _llm_delay > 0:
                        time.sleep(_llm_delay)
                    resp_event = f"In direct response to you: {prior_line}"
                    logging.info(
                        f"Day {abs_day}: exchange turn — {responder.name} responds to {speaker.name}"
                    )
                    resp = reason_for_agent(
                        responder,
                        agents,
                        event=resp_event,
                        current_day=abs_day,
                        world_graph=world.world_graph,
                    )
                    if resp is None:
                        break
                    prior_line = _commit_action(responder, resp)
                    speaker, responder = responder, speaker

        # EVENING: background rules + relationship decay
        bg_log = apply_background_rules(background, agents, rng)
        day_log.extend(bg_log)

        # THEATRICAL VIGNETTES (Slice E): occasionally let an agent have a charming
        # first-person moment (dream / catchphrase / dramatic announcement). Bounded to
        # MAX_VIGNETTES_PER_DAY to control cost; gated so it doesn't fire every day.
        if selected and rng.random() < 0.7:
            n_vig = min(MAX_VIGNETTES_PER_DAY, len(selected))
            vig_actors = rng.sample(selected, rng.randint(1, n_vig))
            for actor in vig_actors:
                struct = generate_vignette_struct(actor, active_event, abs_day)
                if struct:
                    kind, text = struct
                    day_vignettes.append(Vignette(agent=actor.name, kind=kind, text=text))
                if len(day_vignettes) >= MAX_VIGNETTES_PER_DAY:
                    break

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
            vignettes=day_vignettes,
        )
        snapshots.append(snap)

        if on_day:
            on_day(snap)

    final_metrics = snapshots[-1].metrics if snapshots else initial_metrics
    report, forecast = generate_final_report(
        initial_metrics,
        final_metrics,
        snapshots,
        world.prompt,
        world.starting_event,
        question=world.question,
        topics=topics,
        dynamic_events=dynamic_events,
    )

    # PROPHECY (Slice E): if the player set a free-text prediction, grade it once at the
    # end of the run against the final narrative/forecast + notable highlights.
    prophecy_verdict = None
    if world.prophecy:
        notable = [
            f"Day {s.day} — {h.agent}: {h.summary}"
            for s in snapshots for h in s.highlights[:2]
        ]
        prophecy_verdict = grade_prophecy(
            world.prophecy,
            final_metrics,
            forecast,
            report,
            notable_highlights=notable,
        )

    return SimulationResult(
        days=abs_day if snapshots else config.days,
        snapshots=snapshots,
        initial_metrics=initial_metrics,
        final_metrics=final_metrics,
        final_report=report,
        dynamic_events=dynamic_events,
        forecast=forecast,
        prophecy_verdict=prophecy_verdict,
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


def _is_charged(actor: Agent, action) -> bool:
    """A charged interaction warrants a multi-turn exchange (Slice D ⑤).

    Charged when the actor targeted a specific person AND any of:
      - the existing relationship type is rivalry/romance/conflict, OR
      - the existing relationship |strength| >= 0.4, OR
      - a relationship_effect of those types with |delta| >= 0.2.
    """
    if not action.target_agents:
        return False
    primary = action.target_agents[0]
    if primary == actor.name:
        return False

    rel = actor.relationships.get(primary)
    if rel is not None:
        if rel.type in _CHARGED_REL_TYPES:
            return True
        if abs(rel.strength) >= 0.4:
            return True

    eff = action.relationship_effects.get(primary)
    if eff is not None and eff.type in _CHARGED_REL_TYPES and abs(eff.strength_delta) >= 0.2:
        return True
    return False


def _recent_event_summary(log: list[str]) -> Optional[str]:
    if not log:
        return None
    return " | ".join(log[-3:])
