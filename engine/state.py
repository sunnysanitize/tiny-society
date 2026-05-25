from __future__ import annotations

import os
import uuid
from collections import OrderedDict
from threading import Lock
from typing import Optional

from models import World, SimulationResult

# Cap the number of live worlds kept in RAM. A long-running server otherwise
# accumulates worlds forever (each holds agents + full snapshot history). When the
# cap is exceeded we evict the least-recently-used world and its result together.
# Saved worlds live in Supabase, so eviction only drops the in-memory working copy;
# clients can reload from /saves. Override with MAX_LIVE_WORLDS.
MAX_LIVE_WORLDS = int(os.getenv("MAX_LIVE_WORLDS", "200"))


class WorldStore:
    def __init__(self, max_worlds: int = MAX_LIVE_WORLDS) -> None:
        self._lock = Lock()
        self._max = max_worlds
        # OrderedDict as an LRU: most-recently-touched key is moved to the end.
        self._worlds: "OrderedDict[str, World]" = OrderedDict()
        self._results: dict[str, SimulationResult] = {}

    def _touch(self, wid: str) -> None:
        """Mark a world as most-recently-used. Caller must hold the lock."""
        if wid in self._worlds:
            self._worlds.move_to_end(wid)

    def _evict_if_needed(self) -> None:
        """Drop LRU worlds (and their results) until within the cap. Caller holds lock."""
        while len(self._worlds) > self._max:
            old_wid, _ = self._worlds.popitem(last=False)
            self._results.pop(old_wid, None)

    def create(self, world: World) -> str:
        wid = uuid.uuid4().hex[:12]
        with self._lock:
            self._worlds[wid] = world
            self._touch(wid)
            self._evict_if_needed()
        return wid

    def get(self, wid: str) -> Optional[World]:
        with self._lock:
            w = self._worlds.get(wid)
            if w is not None:
                self._touch(wid)
            return w

    def update(self, wid: str, world: World) -> None:
        with self._lock:
            self._worlds[wid] = world
            self._touch(wid)
            self._evict_if_needed()

    def save_result(self, wid: str, result: SimulationResult) -> None:
        with self._lock:
            self._results[wid] = result
            self._touch(wid)

    def get_result(self, wid: str) -> Optional[SimulationResult]:
        with self._lock:
            if wid in self._worlds:
                self._touch(wid)
            return self._results.get(wid)


store = WorldStore()
