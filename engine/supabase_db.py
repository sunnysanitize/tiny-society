from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from supabase import Client, create_client

from models import SimulationResult, World

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

_client: Optional[Client] = None


def _db() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _client


def list_saves(user_id: str) -> list[dict]:
    res = (
        _db()
        .table("saves")
        .select("id, name, day_count, agent_count, world_prompt, created_at, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return res.data


def create_save(
    user_id: str,
    name: str,
    world: World,
    result: Optional[SimulationResult],
) -> dict:
    row = {
        "user_id": user_id,
        "name": name,
        "world_data": world.model_dump(),
        "result_data": result.model_dump() if result else None,
        "day_count": result.days if result else 0,
        "agent_count": len(world.agents),
        "world_prompt": world.prompt[:200],
    }
    res = _db().table("saves").insert(row).execute()
    return res.data[0]


def get_save(save_id: str, user_id: str) -> Optional[dict]:
    res = (
        _db()
        .table("saves")
        .select("*")
        .eq("id", save_id)
        .eq("user_id", user_id)
        .execute()
    )
    return res.data[0] if res.data else None


def update_save(
    save_id: str,
    user_id: str,
    name: str,
    world: World,
    result: Optional[SimulationResult],
) -> Optional[dict]:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "name": name,
        "world_data": world.model_dump(),
        "result_data": result.model_dump() if result else None,
        "day_count": result.days if result else 0,
        "agent_count": len(world.agents),
        "world_prompt": world.prompt[:200],
        "updated_at": now,
    }
    res = (
        _db()
        .table("saves")
        .update(row)
        .eq("id", save_id)
        .eq("user_id", user_id)
        .execute()
    )
    return res.data[0] if res.data else None


def delete_save(save_id: str, user_id: str) -> bool:
    res = (
        _db()
        .table("saves")
        .delete()
        .eq("id", save_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(res.data)
