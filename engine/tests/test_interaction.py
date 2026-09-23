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


def test_roles_are_unique_across_batches():
    from models import World
    from simulation import generator
    # BATCH_SIZE is 3, so 7 agents means three separate LLM calls that cannot
    # see each other's output — the source of two "Lead Programmer" characters.
    world = World(prompt="a high school robotics and debate club", target_population=7)
    agents = generator.generate_fillers(world, 7)
    assert len(agents) == 7, len(agents)
    norm = [generator._normalize_role(a.role) for a in agents]
    assert len(set(norm)) == len(norm), sorted(norm)


def test_normalize_role_ignores_articles_and_case():
    from simulation import generator
    a = generator._normalize_role("Lead Programmer for Robotics Club")
    b = generator._normalize_role("Lead Programmer for the Robotics Club")
    assert a == b, (a, b)


def test_blank_roles_do_not_collide():
    from models import World
    from simulation import generator
    # A provider that omits `role` entirely — reachable via the _safe_json salvage
    # path, which accepts an object on `name` alone. Before the fix these all
    # defaulted to "member" without ever being checked for uniqueness.
    original = generator._fetch_batch
    generator._fetch_batch = lambda world, count, names, roles, attempt=0: [
        {"name": f"Blank{i}", "traits": ["quiet"], "goals": ["get by"],
         "mood": "calm", "groups": ["club"], "memories": ["I said little."]}
        for i in range(count)
    ]
    try:
        world = World(prompt="a school club", target_population=7)
        agents = generator.generate_fillers(world, 6)
    finally:
        generator._fetch_batch = original
    norm = [generator._normalize_role(a.role) for a in agents]
    assert len(set(norm)) == len(norm), sorted(norm)


def test_action_naming_nobody_is_rejected():
    import json
    from models import Agent
    from simulation import reasoner
    actor = Agent(id="id_a", name="Jasper", role="Lead Programmer")
    raw = json.dumps({
        "action": "work on the drone",
        "action_kind": "interact",
        "target_agents": [],
        "about_agents": [],
        "emotional_reaction": "anxious",
        "intents": {},
        "utterance": "I kept my head down and worked.",
        "stance_shift": {},
        "new_memory": "I worked on the drone's code today.",
        "explanation": "Avoidant, so I stayed with the machine.",
    })
    assert reasoner._parse_action(actor, raw) is None


def test_action_with_only_about_agents_is_accepted():
    import json
    from models import Agent
    from simulation import reasoner
    actor = Agent(id="id_a", name="Jasper", role="Lead Programmer")
    raw = json.dumps({
        "action": "work on the drone",
        "action_kind": "interact",
        "target_agents": [],
        "about_agents": ["Milo"],
        "emotional_reaction": "anxious",
        "intents": {},
        "utterance": "Milo will find it eventually. Let him look.",
        "stance_shift": {},
        "new_memory": "I worked alone on the drone, thinking about Milo.",
        "explanation": "I avoid him but cannot stop competing with him.",
    })
    act = reasoner._parse_action(actor, raw)
    assert act is not None
    assert act.about_agents == ["Milo"]
    assert act.target_agents == []
    assert act.intents == {}, "referents must not be given intents"


def test_referent_moves_no_relationship():
    from models import Agent, AgentAction
    from simulation.applicator import apply_action
    jasper = Agent(id="id_j", name="Jasper", role="Lead Programmer")
    milo = Agent(id="id_m", name="Milo", role="Reviewer")
    action = AgentAction(
        action="work on the drone",
        action_kind="interact",
        target_agents=[],
        about_agents=["Milo"],
        emotional_reaction="anxious",
        intents={},
        utterance="Milo will find it eventually.",
        stance_shift={},
        new_memory="I worked alone on the drone, thinking about Milo.",
        explanation="I avoid him but cannot stop competing with him.",
    )
    log_line, notes, milestones = apply_action(jasper, action, [jasper, milo], day=1)
    assert jasper.relationships == {}, jasper.relationships
    assert milo.relationships == {}, milo.relationships
    assert notes == [] and milestones == []
    assert jasper.short_term_memory, "the actor must still remember their own day"
    assert "Milo" in log_line


def test_referent_named_in_log_line_when_no_memory():
    """With new_memory empty the log line must still name the referent, which is
    only true if the applicator's about_agents branch runs."""
    from models import Agent, AgentAction
    from simulation.applicator import apply_action
    jasper = Agent(id="id_j", name="Jasper", role="Lead Programmer")
    milo = Agent(id="id_m", name="Milo", role="Reviewer")
    action = AgentAction(
        action="work on the drone",
        action_kind="interact",
        target_agents=[],
        about_agents=["Milo"],
        emotional_reaction="anxious",
        intents={},
        utterance="",
        stance_shift={},
        new_memory="",
        explanation="I avoid him but cannot stop competing with him.",
    )
    log_line, notes, milestones = apply_action(jasper, action, [jasper, milo], day=1)
    assert "Milo" in log_line, log_line
    assert "alone, about" in log_line, log_line
    assert jasper.relationships == {} and milo.relationships == {}


def test_fallback_action_names_someone():
    from models import Agent
    from simulation import engine as eng
    a = Agent(id="id_a", name="Ana", role="Captain")
    b = Agent(id="id_b", name="Ben", role="Editor")
    act = eng._fallback_action(a, [a, b])
    assert act.target_agents or act.about_agents, "fallback must never be inert"


def test_fallback_action_is_deterministic():
    from models import Agent
    from simulation import engine as eng
    roster = [Agent(id=f"id_{n}", name=n, role="member") for n in ("Ana", "Ben", "Cy")]
    first = eng._fallback_action(roster[0], roster)
    second = eng._fallback_action(roster[0], roster)
    assert first.about_agents == second.about_agents


def test_planner_prompt_demands_a_person():
    from simulation import planner
    sys_prompt = planner.PLANNER_SYSTEM
    low = sys_prompt.lower()
    assert "name" in low and "person" in low, "plan must be about somebody"
    assert "relationships" in low or "who" in low


def test_planner_prompt_includes_relationships():
    from models import Agent, Relationship
    from simulation import planner
    a = Agent(id="id_a", name="Ana", role="Captain", goals=["win regionals"])
    a.relationships["Ben"] = Relationship(type="rivalry", strength=-0.4)
    prompt = planner._build_prompt(a, "the club vote is tomorrow", 1)
    assert "Ben" in prompt, "the planner cannot name a person it never sees"


_TESTS = [
    test_caps_reject_oversized_runs,
    test_caps_defaults_are_seven,
    test_trim_never_cuts_mid_word,
    test_trim_leaves_short_text_untouched,
    test_report_prompt_does_not_leak_section_names,
    test_roles_are_unique_across_batches,
    test_normalize_role_ignores_articles_and_case,
    test_blank_roles_do_not_collide,
    test_action_naming_nobody_is_rejected,
    test_action_with_only_about_agents_is_accepted,
    test_referent_moves_no_relationship,
    test_referent_named_in_log_line_when_no_memory,
    test_fallback_action_names_someone,
    test_fallback_action_is_deterministic,
    test_planner_prompt_demands_a_person,
    test_planner_prompt_includes_relationships,
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
