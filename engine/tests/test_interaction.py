"""Tests for the interaction foundations (Plan 1).

Kept separate from test_realism.py, which is the realism CALIBRATION anchor —
this file holds ordinary unit tests for the action contract, text trimming,
generation de-duplication, and prompt hygiene.

Run:
    LLM_PROVIDER=mock python3 tests/test_interaction.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("LLM_PROVIDER", "mock")
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from models import SimulationConfig, WorldInput  # noqa: E402


def test_caps_reject_oversized_runs():
    import pydantic
    SimulationConfig(days=7, reasoning_agents_per_day=7)  # allowed
    WorldInput(prompt="a school club", target_population=7)  # allowed
    for bad in (SimulationConfig, ):
        try:
            bad(days=8)
        except pydantic.ValidationError:
            pass
        else:
            raise AssertionError("days=8 should be rejected")
    try:
        SimulationConfig(reasoning_agents_per_day=8)
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("reasoning_agents_per_day=8 should be rejected")
    try:
        WorldInput(prompt="a school club", target_population=8)
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("target_population=8 should be rejected")


def test_caps_defaults_are_seven():
    c = SimulationConfig()
    assert c.days == 7, c.days
    assert c.reasoning_agents_per_day == 7, c.reasoning_agents_per_day
    assert WorldInput(prompt="x").target_population == 7


_TESTS = [
    test_caps_reject_oversized_runs,
    test_caps_defaults_are_seven,
]


def _main() -> int:
    failures = 0
    for t in _TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as exc:  # noqa: BLE001 — harness reports, does not crash
            failures += 1
            import traceback
            print(f"FAIL  {t.__name__}: {exc}")
            traceback.print_exc()
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
