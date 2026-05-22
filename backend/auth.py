from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

_client = None


def _admin():
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _client


def get_user_id(authorization: Annotated[str, Header()] = "") -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token = authorization[7:]
    try:
        response = _admin().auth.get_user(token)
        return response.user.id
    except Exception as exc:
        raise HTTPException(401, f"Invalid token: {exc}")


UserIdDep = Annotated[str, Depends(get_user_id)]
