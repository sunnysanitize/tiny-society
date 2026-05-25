from __future__ import annotations

import asyncio
import copy
import logging
import random
from typing import Callable, Optional

from models import (
    Agent, AgentAction, World, SimulationConfig, SimulationResult,
    DaySnapshot, DayHighlight, Vignette,
)
from .selector import select_reasoning_agents
from .reasoner import reason_for_agent, areason_for_agent
from .reflector import reflect
from .planner import form_plan
from .deterministic import apply_background_rules
from .applicator import apply_action
from .persona import vet_action
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
    pause_on_days: Optional[list[int]] = None,
    baseline_influence: Optional[dict[str, float]] = None,
    prior_event_log: Optional[list[str]] = None,
    active_event_in: Optional[str] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> SimulationResult:
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

    # DAY-BY-DAY: reuse the persisted day-0 baseline when advancing (so gainers/losers
    # stay measured against day 0); otherwise capture it now (fresh run).
    if not baseline_influence:
        baseline_influence = snapshot_influence(agents)
    initial_metrics = compute_metrics(agents, baseline_influence=baseline_influence)

    snapshots: list[DaySnapshot] = []
    # Seed the running log with prior days' events (passed on an advance/continue) so the
    # selector keeps recent-event context and dynamic-event generation has material to
    # work from even when each call only simulates a single day.
    full_event_log: list[str] = list(prior_event_log or [])
    dynamic_events: dict[str, str] = {}

    # Carry the active event across calls so day-by-day advancing matches a batch run:
    # a dynamic event generated on (say) day 5 stays "active" on day 6+ until the next
    # one fires. On a continue/advance, callers pass the previous day's active_event;
    # otherwise the starting event is active for the first 3 absolute days.
    if active_event_in is not None:
        active_event: Optional[str] = active_event_in
    else:
        active_event = world.starting_event if (day_offset + 1) <= 3 else None

    # INJECT-AN-EVENT nudge (Slice E): a player-authored event queued on the world
    # becomes the active_event on this run's FIRST day, taking priority over the
    # starting/auto-generated events, then is cleared so it fires exactly once. Works
    # for both the batch and stream continue paths since both call run_simulation.
    pending_event: Optional[str] = world.pending_event
    if pending_event:
        world.pending_event = None

    for day in range(1, config.days + 1):
        abs_day = day + day_offset
        # USER CANCEL: stop before starting a new day if the player asked to halt the run.
        # Gated on `snapshots` so at least one day of THIS call always completes — that
        # guarantees a non-empty, resumable partial result (continue/merge expect a last
        # snapshot). The day already in progress when cancel arrives finishes; the next
        # one doesn't start. Treated like a natural early end (same as pause_on_days).
        if should_cancel and snapshots and should_cancel():
            logging.info(f"Cancelling simulation before day {abs_day} (user request)")
            break
        day_log: list[str] = []
        day_highlights: list[DayHighlight] = []
        day_vignettes: list[Vignette] = []
        type_changes = 0
        # Per-day RNG derived from the absolute day, so advancing one day at a time
        # produces the SAME randomness as running the days in a batch (day N's draws
        # depend only on seed+N, not on how many days were simulated in this call).
        day_rng = random.Random(seed + abs_day)

        # Clear starting event once we're past day 3 (works for both batch and 1-day steps)
        if abs_day > 3 and active_event == world.starting_event:
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

        # MORNING: promote ALL of yesterday's short-term memories to long-term (deduped),
        # then reset. Promoting only the last one lost everything from multi-action /
        # multi-turn-exchange days and everything an agent remembered being done TO them
        # (two-sided memory), flattening their history — so promote them all.
        for a in agents:
            if abs_day > 1:
                if a.short_term_memory:
                    existing_texts = {m.text for m in a.long_term_memory}
                    for mem in a.short_term_memory:
                        if mem.text and mem.text not in existing_texts:
                            a.long_term_memory.append(mem)
                            existing_texts.add(mem.text)
                    a.long_term_memory = a.long_term_memory[-60:]
                a.short_term_memory = []

        # AFTERNOON: select agents, run AI reasoning + deterministic rules
        selected = select_reasoning_agents(
            agents,
            world.starting_event if abs_day == 1 else _recent_event_summary(full_event_log),
            config.reasoning_agents_per_day,
            day_rng,
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

        day_perception_notes: list = []
        day_milestones: list[str] = []
        by_name = {a.name: a for a in agents}
        exchanges_today = 0

        def _commit_action(actor: Agent, action) -> str:
            """Apply an action, route its observation/perception, log + highlight it.

            Returns the action's log line. Used identically for primary actions and
            multi-turn response turns; also accumulates relationship milestones."""
            nonlocal type_changes
            # PERSONA VETO (Stage 3): before any consequence is applied, reject intents this
            # character plausibly wouldn't act on given mood/traits/standing (e.g. courting
            # while heartbroken). Downgrades happen in place; vetoes are logged so the
            # restraint is visible in the story instead of silent.
            veto_notes = vet_action(actor, action, by_name)
            day_log.extend(veto_notes)
            log_line, notes, milestones = apply_action(actor, action, agents, day=abs_day)
            day_log.append(log_line)
            day_milestones.extend(milestones)
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
            # Volatility = realized significant relationship changes this action, i.e.
            # the milestones the consequence layer actually produced (earned transitions),
            # not the agent's proposed bids.
            type_changes += len(milestones)
            return log_line

        # PARALLEL PASS: form plans + reason for every selected actor concurrently.
        # Reasoning is read-only on shared state, so it's safe to fan out; results
        # are applied sequentially below for determinism.
        async def _plan_and_reason(actor: Agent):
            # PLANNING (④): refresh this selected agent's short-term intention if it's
            # missing or stale, BEFORE reasoning, so today's action can pursue it.
            if actor.plan is None or (abs_day - actor.plan_day) >= PLAN_REFRESH_DAYS:
                new_plan = await asyncio.to_thread(form_plan, actor, active_event, abs_day)
                if new_plan:
                    actor.plan = new_plan
                    actor.plan_day = abs_day
            logging.info(f"Day {abs_day}: reasoning for {actor.name}")
            return await areason_for_agent(
                actor,
                agents,
                event=active_event,
                current_day=abs_day,
                world_graph=world.world_graph,
            )

        async def _gather_day_actions(actors):
            return await asyncio.gather(*[_plan_and_reason(a) for a in actors])

        # run_simulation stays sync; the calling thread has no running loop in both
        # the sync-endpoint and streaming-thread cases, so asyncio.run is safe here.
        actions = asyncio.run(_gather_day_actions(selected))

        # SEQUENTIAL PASS: apply in selection order for determinism, then run any
        # multi-turn exchanges (which depend on prior applied state — kept serial).
        for actor, action in zip(selected, actions):
            if action is None:
                # The LLM call failed or returned unparseable JSON. Rather than silently
                # dropping the agent's whole turn (which flatlines the story), commit a
                # neutral "kept to themselves" beat so the day still reflects them.
                action = _fallback_action(actor)
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
                    resp_event = f"In direct response to you: {prior_line}"
                    logging.info(
                        f"Day {abs_day}: exchange turn — {responder.name} responds to {speaker.name}"
                    )
                    # Charged exchanges are the dramatic, pivotal turns — use the
                    # strong model here even though the routine fan-out runs cheap.
                    resp = reason_for_agent(
                        responder,
                        agents,
                        event=resp_event,
                        current_day=abs_day,
                        world_graph=world.world_graph,
                        tier="strong",
                    )
                    if resp is None:
                        break
                    prior_line = _commit_action(responder, resp)
                    speaker, responder = responder, speaker

        # EVENING: background rules + relationship decay
        bg_log = apply_background_rules(background, agents, day_rng)
        day_log.extend(bg_log)

        # THEATRICAL VIGNETTES (Slice E): occasionally let an agent have a charming
        # first-person moment (dream / catchphrase / dramatic announcement). Bounded to
        # MAX_VIGNETTES_PER_DAY to control cost; gated so it doesn't fire every day.
        if selected and day_rng.random() < 0.7:
            n_vig = min(MAX_VIGNETTES_PER_DAY, len(selected))
            vig_actors = day_rng.sample(selected, day_rng.randint(1, n_vig))
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
            milestones=day_milestones,
        )
        snapshots.append(snap)

        if on_day:
            on_day(snap)

        # MID-RUN PAUSE (Part C, Level 2): stop exactly on a requested pause day, after
        # the snapshot is built/appended and on_day fired. Treated as a natural early end —
        # the partial result is finalized and returned normally so the player can inject a
        # character (or other nudge) and resume via the continue flow.
        if abs_day in (pause_on_days or []):
            logging.info(f"Pausing simulation on day {abs_day} (pause_on_days)")
            break

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
        baseline_influence=baseline_influence,
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
            "DYNAMIC_EVENT_GENERATION\n"
            "Generate a single-sentence world event for a social simulation. No quotes, no prefix, under 20 words.",
            prompt,
            max_tokens=60,
            tier="cheap",
        )
        ev = raw.strip().strip('"').strip("'").strip()
        if ev and len(ev) > 10:
            return ev
    except Exception as e:
        logging.warning(f"Dynamic event generation failed: {e}")
    return None


def _fallback_action(actor: Agent) -> AgentAction:
    """A neutral, target-less 'observe' action used when reasoning failed to produce a
    valid one — keeps the agent present in the day's log without inventing interactions."""
    return AgentAction(
        action="observe",
        action_kind="interact",
        target_agents=[],
        emotional_reaction=actor.mood,
        intents={},
        utterance="",
        stance_shift={},
        new_memory="",
        explanation="kept to themselves today",
    )


def _is_charged(actor: Agent, action) -> bool:
    """A charged interaction warrants a multi-turn exchange (Slice D ⑤).

    Charged when the actor targeted a specific person AND any of:
      - the existing relationship type is rivalry/romance/conflict, OR
      - the existing relationship |strength| >= 0.4, OR
      - the agent's INTENT toward them is antagonistic or romantic (rivalry/conflict/romance).
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

    from . import consequence
    proposed_type, _ = consequence.intent_to_bid(action.intents.get(primary, ""))
    return proposed_type in _CHARGED_REL_TYPES


def _recent_event_summary(log: list[str]) -> Optional[str]:
    if not log:
        return None
    return " | ".join(log[-3:])
