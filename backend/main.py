from __future__ import annotations

import asyncio
import json as _json
import os
import queue as _queue
import threading
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()

from models import (
    Agent, CharacterInput, World, WorldInput,
    SimulationConfig, SimulationResult, DaySnapshot,
)
from state import store
from simulation.engine import run_simulation
from simulation.generator import generate_fillers
from simulation.memory import make_memory

app = FastAPI(title="Tiny Society AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True, "llm_provider": os.getenv("LLM_PROVIDER", "mock")}


class CreateWorldResponse(BaseModel):
    world_id: str
    world: World


@app.post("/world", response_model=CreateWorldResponse)
def create_world(body: WorldInput):
    world = World(prompt=body.prompt, target_population=body.target_population)
    wid = store.create(world)
    return CreateWorldResponse(world_id=wid, world=world)


@app.get("/world/{wid}", response_model=World)
def get_world(wid: str):
    w = store.get(wid)
    if not w:
        raise HTTPException(404, "world not found")
    return w


@app.post("/world/{wid}/character", response_model=Agent)
def add_character(wid: str, body: CharacterInput):
    w = _require(wid)
    agent = Agent(
        id=f"a_{uuid.uuid4().hex[:8]}",
        name=body.name,
        role=body.role,
        traits=body.traits,
        goals=body.goals,
        mood=body.mood,
        groups=body.groups,
        short_term_memory=[make_memory(m, day=0) for m in body.starting_memories],
        long_term_memory=[make_memory(m, day=0) for m in body.starting_memories],
        relationships=dict(body.starting_relationships),
        is_custom=True,
    )
    w.agents.append(agent)
    store.update(wid, w)
    return agent


@app.delete("/world/{wid}/character/{agent_id}")
def remove_character(wid: str, agent_id: str):
    w = _require(wid)
    before = len(w.agents)
    w.agents = [a for a in w.agents if a.id != agent_id]
    if len(w.agents) == before:
        raise HTTPException(404, "agent not found")
    store.update(wid, w)
    return {"ok": True}


class FillerRequest(BaseModel):
    count: Optional[int] = None


@app.post("/world/{wid}/generate-fillers", response_model=World)
def generate_filler_agents(wid: str, body: FillerRequest):
    w = _require(wid)
    needed = body.count if body.count is not None else max(0, w.target_population - len(w.agents))
    if needed <= 0:
        return w
    fillers = generate_fillers(w, needed)
    w.agents.extend(fillers)
    store.update(wid, w)
    return w


class EventInput(BaseModel):
    starting_event: str


@app.post("/world/{wid}/event", response_model=World)
def set_event(wid: str, body: EventInput):
    w = _require(wid)
    w.starting_event = body.starting_event
    store.update(wid, w)
    return w


class SimulateRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    reasoning_agents_per_day: int = Field(default=8, ge=1, le=30)
    seed: int = 42


@app.post("/world/{wid}/simulate", response_model=SimulationResult)
def simulate(wid: str, body: SimulateRequest):
    w = _require(wid)
    if not w.agents:
        raise HTTPException(400, "world has no agents")
    config = SimulationConfig(
        days=body.days,
        reasoning_agents_per_day=body.reasoning_agents_per_day,
    )
    result = run_simulation(w, config, seed=body.seed)
    store.save_result(wid, result)
    return result


@app.post("/world/{wid}/simulate/stream")
async def simulate_stream(wid: str, body: SimulateRequest):
    w = _require(wid)
    if not w.agents:
        raise HTTPException(400, "world has no agents")
    config = SimulationConfig(
        days=body.days,
        reasoning_agents_per_day=body.reasoning_agents_per_day,
    )
    return _make_stream_response(wid, w, config, body.seed, day_offset=0, initial_agents=None)


class ContinueRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=365)
    reasoning_agents_per_day: int = Field(default=8, ge=1, le=30)
    seed: int = 42


@app.post("/world/{wid}/simulate/continue", response_model=SimulationResult)
def simulate_continue(wid: str, body: ContinueRequest):
    w = _require(wid)
    prev = store.get_result(wid)
    if not prev:
        raise HTTPException(400, "no previous simulation to continue from")
    last_snap = prev.snapshots[-1]
    config = SimulationConfig(
        days=body.days,
        reasoning_agents_per_day=body.reasoning_agents_per_day,
    )
    new_result = run_simulation(
        w, config,
        seed=body.seed,
        initial_agents=last_snap.agents,
        day_offset=last_snap.day,
    )
    merged = _merge_results(prev, new_result)
    store.save_result(wid, merged)
    return merged


@app.post("/world/{wid}/simulate/continue/stream")
async def simulate_continue_stream(wid: str, body: ContinueRequest):
    w = _require(wid)
    prev = store.get_result(wid)
    if not prev:
        raise HTTPException(400, "no previous simulation to continue from")
    last_snap = prev.snapshots[-1]
    config = SimulationConfig(
        days=body.days,
        reasoning_agents_per_day=body.reasoning_agents_per_day,
    )
    return _make_stream_response(
        wid, w, config, body.seed,
        day_offset=last_snap.day,
        initial_agents=last_snap.agents,
        prev_result=prev,
    )


@app.get("/world/{wid}/result", response_model=SimulationResult)
def get_result(wid: str):
    r = store.get_result(wid)
    if not r:
        raise HTTPException(404, "no result yet")
    return r


class ChatRequest(BaseModel):
    message: str
    day: int = 1


class ChatResponse(BaseModel):
    reply: str
    agent_name: str


CHAT_SYSTEM = """You are roleplaying as a fictional character inside an AI social simulation.
You will be given your character's full profile: name, role, traits, goals, mood, memories, and relationships.
Respond to the user's message as this character would — authentically, in first person, in their voice.
Keep your reply to 2–4 sentences. Stay true to your traits and current emotional state.
Never break character. Never mention that you are an AI or a simulation."""


@app.post("/world/{wid}/agent/{agent_id}/chat", response_model=ChatResponse)
def agent_chat(wid: str, agent_id: str, body: ChatRequest):
    from llm import call_llm

    result = store.get_result(wid)
    world = _require(wid)

    agent = None
    if result:
        snap = next((s for s in result.snapshots if s.day == body.day), result.snapshots[-1])
        agent = next((a for a in snap.agents if a.id == agent_id), None)
    if agent is None:
        agent = next((a for a in world.agents if a.id == agent_id), None)
    if agent is None:
        raise HTTPException(404, "agent not found")

    rel_lines = "\n".join(
        f"  - {name}: {r.type} (strength {r.strength:+.2f})"
        for name, r in agent.relationships.items()
    ) or "  (none yet)"

    memories = "\n".join(
        f"  - {m.text}" for m in (agent.long_term_memory[-6:] + agent.short_term_memory[-4:])
    ) or "  (none)"

    user_prompt = (
        f"CHARACTER PROFILE\n"
        f"Name: {agent.name}\n"
        f"Role: {agent.role}\n"
        f"Traits: {', '.join(agent.traits) or 'none'}\n"
        f"Goals: {', '.join(agent.goals) or 'none'}\n"
        f"Current mood: {agent.mood}\n"
        f"Influence score: {agent.influence_score:.1f}\n"
        f"Groups: {', '.join(agent.groups) or 'none'}\n\n"
        f"RELATIONSHIPS\n{rel_lines}\n\n"
        f"MEMORIES\n{memories}\n\n"
        f"WORLD EVENT\n{world.starting_event or '(none)'}\n\n"
        f"USER MESSAGE\n{body.message}"
    )

    try:
        reply = call_llm(CHAT_SYSTEM, user_prompt, max_tokens=300)
    except Exception as e:
        reply = f"(Chat unavailable — check LLM_PROVIDER setting. Error: {e})"

    return ChatResponse(reply=reply, agent_name=agent.name)


# ─── save files ───────────────────────────────────────────────────────────────

import supabase_db
from auth import UserIdDep


class SaveMeta(BaseModel):
    id: str
    name: str
    day_count: int
    agent_count: int
    world_prompt: str = ""
    created_at: str
    updated_at: str


class SaveRequest(BaseModel):
    name: str
    world_data: dict
    result_data: Optional[dict] = None


class LoadSaveResponse(BaseModel):
    world_id: str
    world: World
    result: Optional[SimulationResult] = None


@app.get("/saves", response_model=list[SaveMeta])
def list_saves(user_id: UserIdDep):
    return supabase_db.list_saves(user_id)


@app.post("/saves", response_model=SaveMeta)
def create_save(body: SaveRequest, user_id: UserIdDep):
    world = World(**body.world_data)
    result = SimulationResult(**body.result_data) if body.result_data else None
    return supabase_db.create_save(user_id, body.name, world, result)


@app.put("/saves/{save_id}", response_model=SaveMeta)
def overwrite_save(save_id: str, body: SaveRequest, user_id: UserIdDep):
    world = World(**body.world_data)
    result = SimulationResult(**body.result_data) if body.result_data else None
    save = supabase_db.update_save(save_id, user_id, body.name, world, result)
    if not save:
        raise HTTPException(404, "save not found")
    return save


@app.delete("/saves/{save_id}")
def delete_save(save_id: str, user_id: UserIdDep):
    ok = supabase_db.delete_save(save_id, user_id)
    if not ok:
        raise HTTPException(404, "save not found")
    return {"ok": True}


@app.post("/saves/{save_id}/load", response_model=LoadSaveResponse)
def load_save(save_id: str, user_id: UserIdDep):
    save = supabase_db.get_save(save_id, user_id)
    if not save:
        raise HTTPException(404, "save not found")
    world = World(**save["world_data"])
    result = SimulationResult(**save["result_data"]) if save.get("result_data") else None
    wid = store.create(world)
    if result:
        store.save_result(wid, result)
    return LoadSaveResponse(world_id=wid, world=world, result=result)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _require(wid: str) -> World:
    w = store.get(wid)
    if not w:
        raise HTTPException(404, "world not found")
    return w


def _merge_results(prev: SimulationResult, new: SimulationResult) -> SimulationResult:
    last_day = new.snapshots[-1].day if new.snapshots else prev.snapshots[-1].day
    return SimulationResult(
        days=last_day,
        snapshots=prev.snapshots + new.snapshots,
        initial_metrics=prev.initial_metrics,
        final_metrics=new.final_metrics,
        final_report=new.final_report,
        dynamic_events={**prev.dynamic_events, **new.dynamic_events},
    )


def _make_stream_response(
    wid: str,
    world: World,
    config: SimulationConfig,
    seed: int,
    *,
    day_offset: int,
    initial_agents,
    prev_result: Optional[SimulationResult] = None,
) -> StreamingResponse:
    q: _queue.Queue = _queue.Queue()
    DONE = object()

    def _run():
        try:
            def on_day(snap: DaySnapshot):
                q.put(("day", snap))

            result = run_simulation(
                world, config,
                seed=seed,
                on_day=on_day,
                initial_agents=initial_agents,
                day_offset=day_offset,
            )
            if prev_result is not None:
                result = _merge_results(prev_result, result)
            store.save_result(wid, result)
            q.put(("done", result))
        except Exception as exc:
            q.put(("error", str(exc)))

    threading.Thread(target=_run, daemon=True).start()

    async def event_gen():
        loop = asyncio.get_running_loop()
        while True:
            kind, payload = await loop.run_in_executor(None, q.get)
            if kind == "day":
                data = _json.dumps({"type": "day", "snapshot": payload.model_dump()})
                yield f"data: {data}\n\n"
            elif kind == "done":
                data = _json.dumps({"type": "done", "result": payload.model_dump()})
                yield f"data: {data}\n\n"
                break
            elif kind == "error":
                data = _json.dumps({"type": "error", "message": payload})
                yield f"data: {data}\n\n"
                break

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
