from __future__ import annotations

import uuid
from threading import Lock
from typing import Optional

from models import World, SimulationResult


class WorldStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._worlds: dict[str, World] = {}
        self._results: dict[str, SimulationResult] = {}

    def create(self, world: World) -> str:
        wid = uuid.uuid4().hex[:12]
        with self._lock:
            self._worlds[wid] = world
        return wid

    def get(self, wid: str) -> Optional[World]:
        return self._worlds.get(wid)

    def update(self, wid: str, world: World) -> None:
        with self._lock:
            self._worlds[wid] = world

    def save_result(self, wid: str, result: SimulationResult) -> None:
        with self._lock:
            self._results[wid] = result

    def get_result(self, wid: str) -> Optional[SimulationResult]:
        return self._results.get(wid)


store = WorldStore()
