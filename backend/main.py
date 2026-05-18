from __future__ import annotations

import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from models import (
    Agent, CharacterInput, World, WorldInput,
    SimulationConfig, SimulationResult,
)
from state import store
from simulation.engine import run_simulation
from simulation.generator import generate_fillers

app = FastAPI(title="Tiny Society AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"), "*"],
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
        short_term_memory=list(body.starting_memories),
        long_term_memory=list(body.starting_memories),
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
    days: int = 30
    reasoning_agents_per_day: int = 8
    seed: int = 42


@app.post("/world/{wid}/simulate", response_model=SimulationResult)
def simulate(wid: str, body: SimulateRequest):
    w = _require(wid)
    if not w.agents:
        raise HTTPException(400, "world has no agents")
    if body.days not in (7, 30):
        raise HTTPException(400, "days must be 7 or 30 for MVP")
    config = SimulationConfig(
        days=body.days,
        reasoning_agents_per_day=body.reasoning_agents_per_day,
    )
    result = run_simulation(w, config, seed=body.seed)
    store.save_result(wid, result)
    return result


@app.get("/world/{wid}/result", response_model=SimulationResult)
def get_result(wid: str):
    r = store.get_result(wid)
    if not r:
        raise HTTPException(404, "no result yet")
    return r


def _require(wid: str) -> World:
    w = store.get(wid)
    if not w:
        raise HTTPException(404, "world not found")
    return w
