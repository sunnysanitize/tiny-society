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


def test_trim_never_cuts_mid_word():
    from simulation import reasoner
    source = (
        "Given my avoidant and self-sabotaging traits, and my goal to maintain control "
        "while avoiding public failure, I am introducing a minor flaw into the code that "
        "I can fix later, subtly asserting my continued importance and control over the "
        "project without having to present it publicly to the club."
    )
    out = reasoner._trim(source, 280)
    assert len(out) <= 281, len(out)          # 280 + optional ellipsis
    tail = out.rstrip("…").strip()
    assert not tail.endswith("publi"), out    # the observed real-world failure
    # every word kept must be a whole word from the source
    assert tail.split()[-1] in source.split(), tail.split()[-1]


def test_trim_leaves_short_text_untouched():
    from simulation import reasoner
    assert reasoner._trim("I kept to myself today.", 280) == "I kept to myself today."


def test_report_prompt_does_not_leak_section_names():
    from simulation import reporter
    sys_prompt = reporter.REPORT_SYSTEM
    assert "(if given)" not in sys_prompt, "invites the model to narrate absent sections"
    assert "never mention" in sys_prompt.lower(), "must forbid naming absent sections"


_TESTS = [
    test_caps_reject_oversized_runs,
    test_caps_defaults_are_seven,
    test_trim_never_cuts_mid_word,
    test_trim_leaves_short_text_untouched,
    test_report_prompt_does_not_leak_section_names,
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
