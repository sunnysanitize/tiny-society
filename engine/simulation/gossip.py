"""Gossip — what one person knows can reach others.

Information used to move only when the LLM happened to repeat it, so a confession to one
person never reached anyone else and secrets never came out mid-week. Social talk is
most of real conversation (Dunbar 1997), so here every logged event becomes a
KnowledgeItem for each character who knows it, and whenever two characters actually
interact, each may pass on one thing the other doesn't know yet.

Retelling is an independent-cascade draw (seeded, deterministic):
    p = BASE × juiciness × trust(teller→listener) × (1 − secrecy penalty) × leakiness
Secrets leak rarely; low honesty-humility characters leak more; people talk more freely
about those they dislike. When a secret is spread by someone other than the person it
belongs to, word can get back to them, and that costs the teller.
The rates are design values, not measured ones (no per-dyad rate exists for small groups).
"""
from __future__ import annotations

import random

from models import Agent, AgentAction, FeedEntry, KnowledgeItem, WorldEvent
from . import consequence
from .affect import feel
from .audience import REACH_EVERYONE, REACH_ONE
from .memory import make_memory

BASE = 0.35
SECRECY_PENALTY = {"public": 0.0, "private": 0.5, "secret": 0.85}
MAX_RETELLS_PER_DAY = 4
# Old news is rarely retold.
STALE_DAYS = 3
# Chance word gets back to the owner of a spread secret, and what it costs the teller.
BACKFIRE_P = 0.35
BETRAYAL_BID = -0.3
KNOWLEDGE_CAP = 40

_CONFIDING = {"confide", "trust"}


def secrecy_of(action: AgentAction, covert: bool) -> str:
    if covert or _CONFIDING & set(action.intents.values()):
        return "secret"
    if action.audience.reach == REACH_EVERYONE:
        return "public"
    if action.audience.reach == REACH_ONE:
        return "private"
    return "private"


def record(event: WorldEvent, secrecy: str, by_name: dict[str, Agent]) -> None:
    """Everyone in the event's known_by now knows it first-hand."""
    item = KnowledgeItem(id=event.id, text=event.text, about=[event.actor] + event.targets,
                         secrecy=secrecy, day=event.day)
    for name in event.known_by:
        agent = by_name.get(name)
        if agent is not None:
            _learn(agent, item)


def spread(agents: list[Agent], day_events: list[WorldEvent], day: int,
           rng: random.Random) -> list[WorldEvent]:
    """End of day: retell along today's real contacts. Returns new log events."""
    by_name = {a.name: a for a in agents}
    pairs: list[tuple[str, str]] = []
    for e in day_events:
        for t in e.targets:
            if t in e.known_by and e.actor in by_name and t in by_name:
                pairs += [(e.actor, t), (t, e.actor)]
    pairs = list(dict.fromkeys(pairs))  # keep order, drop repeats

    new_events: list[WorldEvent] = []
    for teller_name, listener_name in pairs:
        if len(new_events) >= MAX_RETELLS_PER_DAY:
            break
        teller, listener = by_name[teller_name], by_name[listener_name]
        known = {k.id for k in listener.knowledge}
        best, best_p = None, 0.0
        for item in teller.knowledge:
            if (item.id in known or listener_name in item.about
                    or item.secrecy == "public" or day - item.day > STALE_DAYS):
                continue
            p = _probability(teller, listener, item)
            if p > best_p:
                best, best_p = item, p
        if best is None or rng.random() >= best_p:
            continue
        new_events.append(_retell(teller, listener, best, day, len(new_events) + 1))
        _maybe_backfire(teller, best, by_name, day, rng)
    return new_events


def _probability(teller: Agent, listener: Agent, item: KnowledgeItem) -> float:
    rel = teller.relationships.get(listener.name)
    trust = 0.6 + 0.6 * max(-0.5, min(1.0, rel.strength if rel else 0.0))
    juicy = 1.5 if item.secrecy == "secret" else (1.2 if "⇒" in item.text else 1.0)
    # People talk more freely about those they're at odds with.
    if any((r := teller.relationships.get(n)) and r.strength <= consequence.RIVALRY_AFFINITY
           for n in item.about):
        juicy *= 1.3
    honesty = teller.profile.honesty if teller.profile else 0.5
    leak = 1.5 - honesty
    return BASE * juicy * trust * (1 - SECRECY_PENALTY.get(item.secrecy, 0.5)) * leak


def _retell(teller: Agent, listener: Agent, item: KnowledgeItem, day: int, n: int) -> WorldEvent:
    heard = item.model_copy(update={"source": teller.name, "hops": item.hops + 1, "day": day})
    _learn(listener, heard)
    listener.short_term_memory.append(
        make_memory(f"{teller.name} told me about something: {item.text}", day))
    listener.feed.append(FeedEntry(text=f"[{teller.name}, passing it on] {item.text}",
                                   author=teller.name, author_influence=teller.influence_score,
                                   day=day, reach=REACH_ONE))
    return WorldEvent(id=f"E{day}.g{n}", day=day, actor=teller.name, targets=[listener.name],
                      text=f"{teller.name} passed on to {listener.name} what they knew of {item.id}: {item.text}",
                      known_by=sorted({teller.name, listener.name}))


def _maybe_backfire(teller: Agent, item: KnowledgeItem, by_name: dict[str, Agent],
                    day: int, rng: random.Random) -> None:
    owner = by_name.get(item.about[0]) if item.about else None
    if item.secrecy != "secret" or owner is None or owner.name == teller.name:
        return
    if rng.random() >= BACKFIRE_P:
        return
    owner.short_term_memory.append(make_memory(
        f"I found out {teller.name} has been repeating what was meant to stay between us.", day))
    consequence.accumulate(owner, teller.name, "conflict", BETRAYAL_BID)
    consequence.realize(owner, teller.name, teller)
    feel(owner, "angry")


def _learn(agent: Agent, item: KnowledgeItem) -> None:
    if any(k.id == item.id for k in agent.knowledge):
        return
    agent.knowledge.append(item)
    agent.knowledge = agent.knowledge[-KNOWLEDGE_CAP:]
