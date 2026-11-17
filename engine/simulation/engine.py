from __future__ import annotations

import asyncio
import copy
import logging
import random
from typing import Callable, Optional

from models import (
    Agent, AgentAction, World, SimulationConfig, SimulationResult,
    DaySnapshot, DayHighlight, Vignette, WorldEvent,
)
from .selector import select_reasoning_agents
from .reasoner import reason_for_agent, areason_for_agent
from .reflector import reflect, update_self_summary
from .planner import form_plan
from .deterministic import apply_background_rules
from .applicator import apply_action
from .persona import vet_action, vet_knowledge
from .observation import distribute_observation, is_covert, witness_line
from .metrics import compute_metrics, snapshot_influence
from .reporter import generate_final_report
from .worldgraph import extract_world_context
from .stance import initialize_stances
from .vignette import generate_vignette_struct
from .prophecy import grade_prophecy
from .premise import render_premise, premise_lines
from .event_casting import cast_event, plant_involvement, render_event
from .game_master import judge_attempt, settle
from .memory import make_memory
from .audience import REACH_ONE
from .personality import profile_agents
from .affect import overnight
from .needs import drain, satisfy
from .gossip import record as record_knowledge, secrecy_of, spread
from .director import STORY_DAYS, direct
from . import dynamics

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

# Someone sought out by this many different people in a day is "crowded" tomorrow.
CROWDED_AT = 3
# Word-overlap (Jaccard) above which an action or memory counts as a repeat.
REPEAT_SIMILARITY = 0.55


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
        world.world_graph, world.lens = extract_world_context(world)
    topics = world.world_graph.topics

    # PER-AGENT STANCE: seed each agent with a mild, varied starting position on each
    # world topic now that topics are known.
    initialize_stances(agents, topics)
    # Day-0 state for the report's relationship/standing diff. On a continue run this is
    # the state at the start of this call; the merged report is regenerated per call.
    day0_agents = [copy.deepcopy(a) for a in agents]

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

    # Render the world's premise ONCE per run: every per-day call gets the same text,
    # so day 6 cannot drift to a different reading of the world than day 1.
    premise_text = render_premise(world.lens, world.prompt)

    # PERSONALITY: turn free-text traits into engine parameters once per character
    # (mood baseline, secrecy, openness to persuasion, needs, voice).
    profile_agents(agents, premise_text)
    for a in agents:
        if not a.stance_anchor:
            a.stance_anchor = dict(a.stance)

    # People that several characters came at yesterday — today's prompts say so, so
    # the cast doesn't keep converging on the same person.
    crowded: list[str] = []

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
        day_events: list[WorldEvent] = []
        type_changes = 0
        # Per-day RNG derived from the absolute day, so advancing one day at a time
        # produces the SAME randomness as running the days in a batch (day N's draws
        # depend only on seed+N, not on how many days were simulated in this call).
        day_rng = random.Random(seed + abs_day)
        # The game master's dice get their own stream so adding adjudication doesn't
        # shift the draws every other per-day decision already depends on.
        gm_rng = random.Random(f"gm|{seed}|{abs_day}")

        # Clear starting event once we're past day 3 (works for both batch and 1-day steps)
        if abs_day > 3 and active_event == world.starting_event:
            active_event = None

        # Player-injected event takes priority on the run's first day.
        if day == 1 and pending_event:
            active_event = pending_event

        # DIRECTOR COMPLICATION: queued last night when the story stalled or ran cold.
        # Lives on the world so it survives a day-by-day boundary. A player-injected
        # event on this run's first day takes priority and the complication waits.
        if world.director_event and not (day == 1 and pending_event):
            active_event = world.director_event
            dynamic_events[str(abs_day)] = world.director_event
            world.director_event = None

        # EVENT CASTING: the first day an event is active, bind it to the cast once —
        # who it involves, the hidden truth, and what each character privately knows —
        # so every later call reads the same facts. Keyed by event text and stored on
        # the world, so a day-by-day advance reuses the cast a batch run made.
        if active_event and active_event not in world.event_casts:
            world.event_casts[active_event] = cast_event(
                active_event, agents, abs_day, premise_text
            )
        if active_event:
            plant_involvement(world.event_casts[active_event], agents)
        event_text = render_event(active_event, world.event_casts.get(active_event), abs_day)
        if world.director_note:
            event_text = f"{event_text or ''}\nComing to a head: {world.director_note}".strip()

        # MORNING: promote ALL of yesterday's short-term memories to long-term (deduped),
        # then reset. Promoting only the last one lost everything from multi-action /
        # multi-turn-exchange days and everything an agent remembered being done TO them
        # (two-sided memory), flattening their history — so promote them all.
        for a in agents:
            if abs_day > 1:
                # Overnight: moods settle toward each person's baseline, needs run down.
                overnight(a)
                drain(a)
                if a.short_term_memory:
                    existing_texts = {m.text for m in a.long_term_memory}
                    for mem in a.short_term_memory:
                        if not mem.text or mem.text in existing_texts:
                            continue
                        # A near-repeat strengthens the memory it repeats instead of
                        # crowding recall with copies of the same day.
                        twin = _near_duplicate(mem.text, a.long_term_memory[-30:])
                        if twin is not None:
                            twin.importance = min(10.0, twin.importance + 0.5)
                            twin.day = max(twin.day, mem.day)
                            continue
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
                new_reflections = reflect(
                    actor, current_day=abs_day, world_premise=premise_text
                )
                if new_reflections:
                    logging.info(
                        f"Day {abs_day}: {actor.name} reflected, "
                        f"{len(new_reflections)} new insight(s)"
                    )

        day_perception_notes: list = []
        day_milestones: list[str] = []
        by_name = {a.name: a for a in agents}
        exchanges_today = 0

        def _adjudicate(actor: Agent, action) -> object:
            """Phase 1 of the game master (LLM): judge an attempt, if the action has one."""
            if action is None or not action.attempt:
                return None
            return judge_attempt(
                actor, action, agents,
                cast=world.event_casts.get(active_event or ""),
                recent=full_event_log[-10:] + day_log[-5:],
                world_premise=premise_text,
            )

        def _commit_action(actor: Agent, action, adj=None) -> str:
            """Settle any attempt, apply the action, route what was seen and what came
            of it, and record it in the day's canonical event log.

            Returns what witnesses saw (the line an exchange responds to). Used
            identically for primary actions and multi-turn response turns; also
            accumulates relationship milestones."""
            nonlocal type_changes
            # GAME MASTER phase 2: roll and advance the effort clock (deterministic).
            settlement = settle(adj, actor, abs_day, gm_rng) if adj is not None else None
            if settlement:
                action.outcome, action.outcome_text = settlement.outcome, settlement.text
            # PERSONA VETO (Stage 3): before any consequence is applied, reject intents this
            # character plausibly wouldn't act on given mood/traits/standing (e.g. courting
            # while heartbroken). Downgrades happen in place; vetoes are logged so the
            # restraint is visible in the story instead of silent.
            veto_notes = vet_action(actor, action, by_name)
            veto_notes += vet_knowledge(actor, action, event_text)
            day_log.extend(veto_notes)
            log_line, notes, milestones = apply_action(
                actor, action, agents, day=abs_day, world_premise=premise_text
            )
            day_log.append(log_line)
            day_milestones.extend(milestones)
            # PER-AGENT OBSERVATION LOCALITY: route this action only to the agents
            # who could plausibly witness it (actor, targets, group-mates, or
            # everyone if the actor is a high-influence public figure).
            #
            # STANDING SPREAD, derived rather than declared: publicly lifting someone
            # raises their standing in any world. The (praise|support) + everyone rule
            # lives in ONE place — audience.derive_action_kind, which has already
            # resolved it into action.action_kind. Gate on that instead of
            # re-checking the intent/reach condition here, so the rule never drifts
            # into two copies (see the RULING comment in simulation/audience.py).
            lifted = (
                [name for name, intent in (action.intents or {}).items()
                 if intent in ("praise", "support") and name in action.target_agents]
                if action.action_kind == "amplify" else []
            )
            # Witnesses see the outward move, never the private memory/explanation in
            # log_line; a covert move (only watching) reaches no one but the actor.
            public_line = witness_line(actor, action)
            witnessed = distribute_observation(
                public_line, actor, [] if is_covert(action) else action.target_agents,
                [actor] if is_covert(action) else agents,
                reach=action.audience.reach, day=abs_day, amplify_targets=lifted,
            )
            known = {a.name for a in witnessed} | {actor.name}
            if settlement:
                # The actor learns the result; so do the few the game master says would.
                # Everyone else has to hear it from someone.
                result = f"{settlement.outcome}: {settlement.text}"
                actor.short_term_memory.append(
                    make_memory(f"What came of my attempt to {action.attempt}: {settlement.text}", abs_day))
                if actor.recent_actions:
                    actor.recent_actions[-1] += f" ⇒ {settlement.outcome}: {settlement.text[:120]}"
                day_log[-1] = f"{log_line} ⇒ [{result}]"
                for name in settlement.aware:
                    other = by_name.get(name)
                    if other is not None:
                        other.short_term_memory.append(
                            make_memory(f"I learned that {settlement.text}", abs_day))
                if settlement.aware:
                    distribute_observation(
                        f"[{actor.name}] {settlement.text}", actor, settlement.aware,
                        agents, reach=REACH_ONE, day=abs_day,
                    )
                known |= set(settlement.aware)
            satisfy(actor, action)
            day_log.extend(dynamics.on_action(actor, action, by_name))
            day_events.append(WorldEvent(
                id=f"E{abs_day}.{len(day_events) + 1}",
                day=abs_day,
                actor=actor.name,
                targets=list(action.target_agents),
                text=public_line + (f" ⇒ {settlement.text}" if settlement else ""),
                outcome=settlement.outcome if settlement else "",
                effort=settlement.effort if settlement else "",
                known_by=sorted(known),
            ))
            record_knowledge(day_events[-1], secrecy_of(action, is_covert(action)), by_name)
            day_perception_notes.extend(notes)
            day_highlights.append(DayHighlight(
                agent=actor.name,
                summary=(action.new_memory + (f" — {settlement.text}" if settlement else ""))
                if action.new_memory else (
                    f"{action.action} {', '.join(action.target_agents)} — {action.explanation}"
                    if action.target_agents else
                    f"{action.action} about {', '.join(action.about_agents)} — {action.explanation}"
                    if action.about_agents else
                    f"{action.action} (no one) — {action.explanation}"
                ),
                utterance=action.utterance,
                explanation=action.explanation,
            ))
            # Volatility = realized significant relationship changes this action, i.e.
            # the milestones the consequence layer actually produced (earned transitions),
            # not the agent's proposed bids.
            type_changes += len(milestones)
            return public_line

        # PARALLEL PASS: form plans + reason for every selected actor concurrently.
        # Reasoning is read-only on shared state, so it's safe to fan out; results
        # are applied sequentially below for determinism.
        async def _plan_and_reason(actor: Agent):
            # PLANNING (④): refresh this selected agent's short-term intention if it's
            # missing or stale, BEFORE reasoning, so today's action can pursue it.
            if actor.plan is None or (abs_day - actor.plan_day) >= PLAN_REFRESH_DAYS:
                new_plan = await asyncio.to_thread(
                    form_plan, actor, event_text, abs_day, premise_text
                )
                if new_plan:
                    actor.plan = new_plan
                    actor.plan_day = abs_day
            logging.info(f"Day {abs_day}: reasoning for {actor.name}")
            action = await areason_for_agent(
                actor,
                agents,
                event=event_text,
                current_day=abs_day,
                world_graph=world.world_graph,
                world_premise=premise_text,
                crowded=crowded,
            )
            # LOOP CRITIC: a near-copy of something this agent already did gets one
            # retry with the repetition pointed out.
            echo = _repeats(actor, action)
            if echo:
                retry = await areason_for_agent(
                    actor, agents,
                    event=f"{event_text or ''}\n\nYou already did nearly this: \"{echo}\". "
                          "Today, do something different — follow up on it, drop it, or turn elsewhere.",
                    current_day=abs_day, world_graph=world.world_graph,
                    world_premise=premise_text, crowded=crowded,
                )
                action = retry or action
            # Judge the attempt right away, still in parallel; the roll waits for the
            # sequential pass so outcomes stay deterministic.
            adj = await asyncio.to_thread(_adjudicate, actor, action)
            return action, adj

        async def _gather_day_actions(actors):
            return await asyncio.gather(*[_plan_and_reason(a) for a in actors])

        # run_simulation stays sync; the calling thread has no running loop in both
        # the sync-endpoint and streaming-thread cases, so asyncio.run is safe here.
        results = asyncio.run(_gather_day_actions(selected))

        # SEQUENTIAL PASS: apply in selection order for determinism, then run any
        # multi-turn exchanges (which depend on prior applied state — kept serial).
        for actor, (action, adj) in zip(selected, results):
            if action is None:
                # The LLM call failed or returned unparseable JSON. Rather than silently
                # dropping the agent's whole turn (which flatlines the story), commit a
                # neutral "kept to themselves" beat so the day still reflects them.
                action = _fallback_action(actor, agents)
            public_line = _commit_action(actor, action, adj)

            # MULTI-TURN EXCHANGES (⑤): if this was a CHARGED interaction with a
            # specific target, let that target respond, then optionally the actor
            # replies once more. Capped per chain and per day.
            if exchanges_today < MAX_EXCHANGES_PER_DAY and _is_charged(actor, action):
                exchanges_today += 1
                speaker, responder = actor, by_name.get(action.target_agents[0])
                prior_line = public_line
                for _turn in range(MAX_EXCHANGE_TURNS):
                    if responder is None or responder.id == speaker.id:
                        break
                    resp_event = (
                        f"In direct response to you: {prior_line}\n"
                        "Answer as yourself, in your own manner and toward your own aims — you "
                        "may agree, refuse, deflect, push back or walk away. Don't mirror them."
                    )
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
                        world_premise=premise_text,
                    )
                    if resp is None:
                        break
                    prior_line = _commit_action(responder, resp, _adjudicate(responder, resp))
                    speaker, responder = responder, speaker

        # GOSSIP: along today's real contacts, people pass on what the other doesn't know.
        told = spread(agents, day_events, abs_day, random.Random(f"gossip|{seed}|{abs_day}"))
        day_events.extend(told)
        day_log.extend(f"[word spreads] {e.text}" for e in told)
        # Familiarity, triad balance and opinion exchange between those who met.
        dynamics.daily(agents, day_events)

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
                struct = generate_vignette_struct(
                    actor, event_text, abs_day, premise_text
                )
                if struct:
                    kind, text = struct
                    day_vignettes.append(Vignette(agent=actor.name, kind=kind, text=text))
                if len(day_vignettes) >= MAX_VIGNETTES_PER_DAY:
                    break

        # SELF-SUMMARY: everyone who acted today updates their own account of where
        # they stand (in parallel; one cheap call each).
        async def _summarize_all(actors):
            await asyncio.gather(*[
                asyncio.to_thread(update_self_summary, a, abs_day, premise_text) for a in actors
            ])
        acted = [a for a in agents if a.short_term_memory and a.id in selected_ids]
        if acted:
            asyncio.run(_summarize_all(acted))

        # DIRECTOR: update the threads ledger, and queue a complication if the story
        # stalled or ran cold. Skipped on the arc's last day.
        if abs_day < STORY_DAYS:
            direct(world, abs_day, day_events,
                   world.event_casts.get(world.starting_event or ""), premise_text)

        # Who got crowded today shapes tomorrow's prompts.
        approached: dict[str, set[str]] = {}
        for e in day_events:
            if ".g" in e.id:
                continue
            for t in e.targets:
                approached.setdefault(t, set()).add(e.actor)
        crowded = sorted(n for n, who in approached.items() if len(who) >= CROWDED_AT)

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
            events=day_events,
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
        lens=world.lens,
        threads=world.threads,
        initial_agents=day0_agents,
        event_casts=world.event_casts,
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


def _fallback_action(actor: Agent, roster: list[Agent]) -> AgentAction:
    """A neutral action used when reasoning failed to produce a valid one.

    It names someone as a REFERENT rather than a target: the agent kept to themselves,
    but the day is still about somebody, so it is not socially inert. Choice is
    deterministic — strongest existing bond, else a group-mate, else the first other
    agent by name — because the determinism test compares a batch run byte-for-byte
    against a day-by-day run.
    """
    others = [a for a in roster if a.id != actor.id]
    if not others:
        # No one else on the roster — the single-agent case. Still cannot return
        # both fields empty (spec §2's invariant), so the day is about the actor
        # themselves rather than nobody.
        referents: list[str] = [actor.name]
    else:
        bonded = sorted(
            (a for a in others if a.name in actor.relationships),
            key=lambda a: (-abs(actor.relationships[a.name].strength), a.name),
        )
        if bonded:
            referents = [bonded[0].name]
        else:
            groups = set(actor.groups)
            mates = sorted((a for a in others if groups & set(a.groups)), key=lambda a: a.name)
            referents = [(mates or sorted(others, key=lambda a: a.name))[0].name]
    referent = referents[0] if referents and referents[0] != actor.name else None
    memory = (
        f"I kept to myself today, thinking about {referent}."
        if referent else "I kept to myself today."
    )
    return AgentAction(
        action="observe",
        action_kind="interact",
        target_agents=[],
        about_agents=referents,
        emotional_reaction=actor.mood,
        intents={},
        utterance="",
        stance_shift={},
        new_memory=memory,
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
    from .observation import is_covert
    if is_covert(action):
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


def _words(text: str) -> set[str]:
    import re
    return set(re.findall(r"[a-z']{4,}", (text or "").lower()))


def _similar(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _repeats(actor: Agent, action) -> Optional[str]:
    """The earlier action this one nearly copies (its recorded memory), if any."""
    if action is None or not action.new_memory:
        return None
    mine = _words(action.new_memory)
    for entry in actor.recent_actions[-4:]:
        quoted = entry.split(' — "', 1)[1].split('"', 1)[0] if ' — "' in entry else ""
        if quoted and _similar(mine, _words(quoted)) >= REPEAT_SIMILARITY:
            return quoted
    return None


def _near_duplicate(text: str, memories: list) -> Optional[object]:
    mine = _words(text)
    for m in reversed(memories):
        if _similar(mine, _words(m.text)) >= 0.7:
            return m
    return None


def _recent_event_summary(log: list[str]) -> Optional[str]:
    if not log:
        return None
    return " | ".join(log[-3:])
