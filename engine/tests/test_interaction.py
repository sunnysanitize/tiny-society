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


def test_long_utterance_is_not_cut_mid_word():
    """utterance became the primary quoted beat text (Tasks 9/10) but was never moved
    off the old hard [:400] slice, so a long line renders with a word sheared in half."""
    import json
    from models import Agent
    from simulation import reasoner
    actor = Agent(id="id_a", name="Jasper", role="Lead Programmer")
    long_utterance = (
        "We should just talk about the problem honestly instead of pretending the drone "
        "code review went fine, because Milo already knows I rewrote his section without "
        "telling him first and if I keep dodging this conversation it is only going to get "
        "worse between us before regionals even start, so let's just talk about the pro"
        "totype failures directly, figure out who actually owns which module, stop "
        "pretending the schedule is fine when it clearly is not, and settle this before "
        "Friday's judging panel arrives and asks us questions neither of us can answer."
    )
    assert len(long_utterance) > 400, len(long_utterance)
    raw = json.dumps({
        "action": "confront Milo",
        "action_kind": "interact",
        "target_agents": ["Milo"],
        "about_agents": [],
        "emotional_reaction": "anxious",
        "intents": {"Milo": "talk"},
        "utterance": long_utterance,
        "stance_shift": {},
        "new_memory": "I finally talked to Milo about the code review.",
        "explanation": "Avoidant but ran out of road.",
    })
    act = reasoner._parse_action(actor, raw)
    assert act is not None
    tail = act.utterance.rstrip("…").strip()
    assert tail.split()[-1] in long_utterance.split(), tail.split()[-1]


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


def test_fallback_action_yields_one_beat():
    """Replicates StoryChapter's beat dedup (same agent AND startsWith) against the
    REAL log_line from apply_action and the REAL highlight summary the engine builds,
    to catch the fallback action rendering twice (once as a highlight, once as an
    undeduped event-log line) because the two strings shared no common prefix."""
    import re
    from models import Agent
    from simulation import engine as eng
    from simulation.applicator import apply_action
    a = Agent(id="id_a", name="Ana", role="Captain")
    b = Agent(id="id_b", name="Ben", role="Editor")
    action = eng._fallback_action(a, [a, b])
    log_line, _notes, _milestones = apply_action(a, action, [a, b], day=1)
    # Mirrors engine.py's DayHighlight.summary construction exactly.
    summary = action.new_memory or (
        f"{action.action} {', '.join(action.target_agents)} — {action.explanation}"
        if action.target_agents else
        f"{action.action} about {', '.join(action.about_agents)} — {action.explanation}"
        if action.about_agents else
        f"{action.action} (no one) — {action.explanation}"
    )
    # Mirrors StoryChapter.tsx's parseLogLine (strip "[Name] " prefix, capitalise) +
    # its dedup rule (same agent AND the log text starts with the summary).
    m = re.match(r"^\s*\[([^\]]+)\]\s*(.*)$", log_line)
    assert m, log_line
    log_name, log_text = m.group(1).strip(), m.group(2).strip()
    log_text = log_text[:1].upper() + log_text[1:]
    dup = bool(summary) and log_name == a.name and log_text.lower().startswith(summary.strip().lower())
    assert dup, f"fallback action would render twice: summary={summary!r} log_line={log_line!r}"


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


def test_every_agent_starts_connected():
    from models import Agent
    from simulation import generator
    agents = [Agent(id=f"id_{n}", name=n, role="member")
              for n in ("Ana", "Ben", "Cy", "Dee", "Eve", "Fay", "Gus")]
    generator._seed_relationships(agents, "a high school club")
    for a in agents:
        assert a.relationships, f"{a.name} starts with nobody"
    charged = sum(
        1 for a in agents for r in a.relationships.values()
        if r.type in ("rivalry", "conflict", "romance")
    )
    assert charged >= 2, f"only {charged} charged edges; day 1 has no friction"


def test_seeding_is_deterministic():
    """Casts with identical names but different (uuid-style) ids must seed identically.

    Draws many independent casts rather than two: keying pairing on a random id fails
    this only probabilistically per draw, so a two-draw version missed the regression
    roughly one run in six.
    """
    import uuid
    from models import Agent
    from simulation import generator

    def build():
        agents = [Agent(id=f"a_{uuid.uuid4().hex[:8]}", name=n, role="member")
                  for n in ("Ana", "Ben", "Cy", "Dee", "Eve", "Fay", "Gus")]
        generator._seed_relationships(agents, "a high school club")
        return [(a.name, sorted(a.relationships.keys())) for a in agents]

    first = build()
    for _ in range(19):
        assert build() == first


def test_custom_characters_are_not_left_isolated():
    """Customs + fillers is the real UI flow: the user names some characters, then
    generates the rest. Seeding only the fillers left every named character with nobody
    to act on — a uniform hand-built cast cannot catch that, so build the mixed shape."""
    from models import Agent, World
    from simulation import generator
    world = World(prompt="a high school robotics and debate club", target_population=7)
    world.agents = [
        Agent(id=f"c_{n}", name=n, role=r, is_custom=True)
        for n, r in (("Jasper", "Lead Programmer"), ("Milo", "Reviewer"), ("Nina", "Captain"))
    ]
    fillers = generator.generate_fillers(world, 4)
    everyone = list(world.agents) + fillers
    isolated = [a.name for a in everyone if not a.relationships]
    assert not isolated, f"isolated after setup: {isolated}"


def test_highlights_carry_dialogue():
    from models import World, SimulationConfig
    from simulation import generator, engine as eng
    world = World(prompt="a high school robotics club", target_population=7)
    world.agents = generator.generate_fillers(world, 7)
    world.starting_event = "The regional competition is announced."
    result = eng.run_simulation(world, SimulationConfig(days=1, reasoning_agents_per_day=7), seed=7)
    highlights = [h for s in result.snapshots for h in s.highlights]
    assert highlights, "a day must produce highlights"
    assert any(h.utterance for h in highlights), "no highlight carried an utterance"


def test_mock_utterance_differs_from_memory():
    import json
    from llm import _mock
    from simulation.reasoner import REASONER_SYSTEM
    raw = _mock(REASONER_SYSTEM, "YOUR CHARACTER\nName: Ana\n", json_mode=True)
    data = json.loads(raw)
    assert data["utterance"], "mock must emit an utterance"
    assert data["utterance"] != data["new_memory"], "utterance must be distinct dialogue"



# ---------------------------------------------------------------------------
# WORLD PREMISE THREADING
#
# The premise ("a League of Legends team at U of T") used to reach only world-graph
# extraction, filler generation and the final report. Every per-day call that actually
# writes the story — reason, plan, reflect, vignette — ran blind, so the model fell back
# to generic organizational prose ("team-building activity", "strategic discussions")
# no matter what world the player typed. These tests pin the premise into those prompts.
# ---------------------------------------------------------------------------

PREMISE = "a League of Legends team at the University of Toronto: five undergrad friends"


def _premise_agent():
    from models import Agent, Relationship
    a = Agent(id="id_a", name="Ana", role="Mid laner", goals=["make playoffs"])
    a.relationships["Ben"] = Relationship(type="rivalry", strength=-0.4)
    return a


def test_reasoner_prompt_carries_world_premise():
    from simulation import reasoner
    prompt = reasoner._build_prompt(
        _premise_agent(), [_premise_agent()], "scrim tonight", 2, None, world_premise=PREMISE
    )
    assert "League of Legends" in prompt, "the reasoner cannot write a world it never sees"
    assert "University of Toronto" in prompt


def test_planner_prompt_carries_world_premise():
    from simulation import planner
    prompt = planner._build_prompt(_premise_agent(), "scrim tonight", 2, world_premise=PREMISE)
    assert "League of Legends" in prompt


def test_reflector_prompt_carries_world_premise():
    from models import Memory
    from simulation import reflector
    mems = [Memory(text="I int'd the 2v2 and Ben flamed me", day=1, importance=8.0)]
    prompt = reflector._build_prompt(_premise_agent(), mems, world_premise=PREMISE)
    assert "League of Legends" in prompt


def test_vignette_prompt_carries_world_premise():
    from simulation import vignette
    prompt = vignette._build_prompt(_premise_agent(), "scrim tonight", 2, world_premise=PREMISE)
    assert "League of Legends" in prompt


def test_premise_block_is_omitted_when_absent():
    from simulation import planner
    prompt = planner._build_prompt(_premise_agent(), "scrim tonight", 2)
    assert "WORLD PREMISE" not in prompt, "no premise means no empty header"


def test_premise_is_capped():
    """The premise rides on every per-agent call, so a pasted essay must not
    crowd out the character sheet and memories below it."""
    from simulation.premise import premise_lines, MAX_PREMISE_CHARS
    long_premise = "x" * (MAX_PREMISE_CHARS + 5000)
    block = "\n".join(premise_lines(long_premise))
    assert "WORLD PREMISE" in block
    assert "x" * (MAX_PREMISE_CHARS + 1) not in block, "premise text was not truncated"
    # Whatever fixed scaffolding the block carries, its size must not track the input.
    longer = "\n".join(premise_lines("x" * (MAX_PREMISE_CHARS + 50000)))
    assert len(longer) == len(block), "block length must be bounded, not input-driven"


def test_report_prompt_does_not_forbid_the_world_voice():
    from simulation import reporter
    low = reporter.REPORT_SYSTEM.lower()
    assert "not gamey" not in low, "this clamp is what produced the consulting-memo voice"
    assert "vocabulary" in low, "the report must be told to speak the world's own language"


def test_world_context_returns_graph_and_lens():
    from models import World
    from simulation.worldgraph import extract_world_context, extract_world_graph
    w = World(
        prompt="A besieged Cistercian monastery in 1340; the grain is running out.",
        target_population=5,
    )
    graph, lens = extract_world_context(w)
    assert graph.topics, "the graph must still be extracted"
    assert not lens.is_empty(), "a real premise must yield a populated lens"
    assert lens.actor_noun, "actors need a name in this world"
    # The old entry point must keep working for every existing caller.
    assert extract_world_graph(w).topics


def test_created_world_carries_a_lens():
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app)
    r = client.post("/world", json={
        "prompt": "A besieged Cistercian monastery in 1340; the grain is running out.",
        "target_population": 5,
    })
    assert r.status_code == 200, r.text
    world = r.json()["world"]
    assert world["lens"]["actor_noun"], "the created world must carry its interpretation"
    assert world["world_graph"]["topics"], "the graph must still be its own field"


def test_world_lens_survives_a_setting_less_prompt():
    """Review Focus #1: a one-word, non-English or mashed prompt must degrade to a
    usable-or-empty lens, never an exception."""
    from models import World
    from simulation.worldgraph import extract_world_context
    for prompt in ("cats", "asdkjhasd kjhasd", "五人の友達", "", "   "):
        graph, lens = extract_world_context(World(prompt=prompt, target_population=5))
        assert lens is not None and graph is not None   # must not raise
        for item in lens.affordances + lens.gathering_places + lens.banned_vocabulary:
            assert len(item) <= 120


def test_render_premise_uses_lens_fields():
    from models import WorldLens
    from simulation.premise import render_premise
    lens = WorldLens(
        premise_summary="A besieged Cistercian monastery in 1340; the grain is running out.",
        actor_noun="brother",
        affordances=["word travels on foot"],
        gathering_places=["the chapter house"],
        register_notes="Plain, concrete, of its century.",
        banned_vocabulary=["team-building", "stakeholder"],
        central_stake="who controls the failing grain stores",
    )
    text = render_premise(lens, "ignored raw prompt")
    assert "1340" in text
    assert "word travels on foot" in text
    assert "the chapter house" in text
    assert "team-building" in text, "banned words must be named so the model can avoid them"
    assert "ignored raw prompt" not in text, "the lens supersedes the raw prompt"


def test_render_premise_falls_back_to_raw_prompt():
    from models import WorldLens
    from simulation.premise import render_premise
    assert "a raw world" in render_premise(WorldLens(), "a raw world")
    assert "a raw world" in render_premise(None, "a raw world")


def test_render_premise_caps_a_large_lens_block():
    """Review Focus #2: the premise rides on every per-agent call every day. A rich
    lens (long summary plus many affordances/gathering places) must not multiply the
    cost of the entire run. Drives render_premise's own cap directly — routing through
    premise_lines would hide a regression there, since premise_lines truncates again on
    top of whatever render_premise returns."""
    from models import WorldLens
    from simulation.premise import render_premise, MAX_PREMISE_CHARS

    lens = WorldLens(
        premise_summary=(
            "The kingdom of Valmere endures a long winter, and its people are worn "
            "thin by a siege that has not yet broken. " * 5
        ),
        affordances=[
            "messengers ride for days between the valley's scattered holds"
            for _ in range(10)
        ],
        gathering_places=["the great hall at dusk, when the fires are lit" for _ in range(10)],
        register_notes="Formal, wintry, spoken in long clauses. " * 10,
        banned_vocabulary=["stakeholder", "team-building"],
        central_stake="who controls the last granary",
    )
    # Sanity check: the raw joined content is well over the cap, so a passing
    # assertion below proves truncation actually happened.
    naive_length = (
        len(lens.premise_summary) + len(lens.register_notes)
        + sum(len(a) for a in lens.affordances) + sum(len(g) for g in lens.gathering_places)
    )
    assert naive_length > MAX_PREMISE_CHARS, "test fixture must exceed the cap to prove anything"

    text = render_premise(lens, "ignored")
    # Truncation appends one "…" past the slice point (matching premise_lines' own
    # style below), so the bound is MAX_PREMISE_CHARS + 1, not MAX_PREMISE_CHARS exactly.
    assert len(text) <= MAX_PREMISE_CHARS + 1, f"render_premise grew to {len(text)} chars"
    assert text.endswith("…"), "a block this large must actually get truncated"


def test_realistic_lens_banned_vocabulary_survives_into_prompt():
    """Regression guard: banned_vocabulary is the LAST section render_premise appends,
    and premise_lines truncates again on top of that. A realistic lens must still carry
    a banned word all the way into the final per-day prompt block, or every per-day call
    silently loses the single most direct anti-staleness instruction in this feature."""
    from models import WorldLens
    from simulation.premise import render_premise, premise_lines

    lens = WorldLens(
        premise_summary="A besieged Cistercian monastery in 1340; the grain is running out.",
        affordances=["word travels on foot", "no clocks strike the hour"],
        gathering_places=["the chapter house", "the refectory"],
        register_notes="Plain, concrete, of its century.",
        banned_vocabulary=["team-building", "stakeholder"],
        central_stake="who controls the failing grain stores",
    )
    block = "\n".join(premise_lines(render_premise(lens, "ignored")))
    assert "team-building" in block, "banned vocabulary must survive both truncation passes"


def test_report_prompt_carries_lens_vocabulary():
    from models import MacroMetrics, WorldLens
    from simulation import reporter
    # MacroMetrics has no field defaults (see models.py), so MacroMetrics() alone would
    # fail Pydantic validation before the lens plumbing is even exercised — fill in the
    # required fields with neutral values instead.
    empty_metrics = MacroMetrics(
        friendship_count=0, rivalry_count=0, conflict_count=0, romance_count=0,
        alliance_count=0, average_relationship_strength=0.0, average_trust_score=0.0,
        most_connected=[], influence_gainers=[], influence_losers=[],
        relationship_volatility=0, social_fragmentation=0.0, group_centrality={},
    )
    lens = WorldLens(
        premise_summary="A besieged monastery in 1340.",
        actor_noun_plural="brothers",
        collective_noun="the house",
        banned_vocabulary=["team-building", "stakeholder"],
        register_notes="Plain and of its century.",
    )
    captured = {}
    real = reporter.call_llm

    def spy(system, user, **kw):
        captured["user"] = user
        captured["system"] = system
        return "report text"

    reporter.call_llm = spy
    try:
        reporter.generate_final_report(
            empty_metrics, empty_metrics, [], "a monastery", None, lens=lens
        )
    finally:
        reporter.call_llm = real

    assert "brothers" in captured["user"], "the report must know what these people are called"
    assert "team-building" in captured["user"], "banned words must reach the report prompt"


def test_banned_vocabulary_instructs_but_never_filters():
    """Review Focus #3: the AI may ban a word that also appears in a character's name,
    a role, or the premise. Banning is an instruction to the model — it must never
    rewrite, strip or filter text that already exists."""
    from models import WorldLens
    from simulation.premise import render_premise
    lens = WorldLens(
        premise_summary="The Stakeholder Guild of Verrin controls the granary.",
        banned_vocabulary=["stakeholder", "guild"],
        affordances=["the Guild keeps the only ledger"],
    )
    text = render_premise(lens, "raw")
    assert "Stakeholder Guild of Verrin" in text, "premise content must survive verbatim"
    assert "the Guild keeps the only ledger" in text, "affordances must survive verbatim"
    assert "stakeholder" in text and "guild" in text, "banned list is named, not applied"


def test_fit_preserves_identity_and_proposes_situation():
    from models import World, CharacterInput
    from simulation.fitting import fit_character
    w = World(prompt="A besieged Cistercian monastery in 1340.", target_population=5)
    from simulation.worldgraph import extract_world_context
    w.world_graph, w.lens = extract_world_context(w)
    body = CharacterInput(name="Dave", role="", traits=["stubborn", "broke"], mood="calm")
    fit = fit_character(w, body)
    assert fit.role, "fitting must propose a role"
    assert not hasattr(fit, "name"), "fitting must never propose a name"
    assert not hasattr(fit, "traits"), "fitting must never propose traits"
    assert not hasattr(fit, "mood"), "fitting must never propose a mood"


def test_fit_endpoint_mutates_nothing():
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app)
    wid = client.post("/world", json={
        "prompt": "A besieged Cistercian monastery in 1340.", "target_population": 5,
    }).json()["world_id"]
    before = client.get(f"/world/{wid}").json()
    r = client.post(f"/world/{wid}/character/fit", json={
        "name": "Dave", "role": "", "traits": ["stubborn"], "mood": "calm",
    })
    assert r.status_code == 200, r.text
    after = client.get(f"/world/{wid}").json()
    assert before == after, "fit must not touch the world"


def test_added_character_is_unfitted_by_default():
    from models import CharacterInput
    from main import _build_agent_from_input
    a = _build_agent_from_input(CharacterInput(name="Dave"), day=0)
    assert a.fitted_to_world is False
    b = _build_agent_from_input(CharacterInput(name="Ana", fitted_to_world=True), day=0)
    assert b.fitted_to_world is True


def test_fit_on_a_lensless_world_returns_200_not_500():
    """Review Focus #5: worlds created before the lens existed have an empty lens and
    are loaded from saves every day. Asking to fit a character in one must degrade to
    an explanatory empty proposal, never an error."""
    from models import World, WorldLens, CharacterInput
    from simulation.fitting import fit_character
    w = World(prompt="", target_population=5)
    w.lens = WorldLens()
    fit = fit_character(w, CharacterInput(name="Dave"))
    assert fit.role == "" and fit.note, "empty proposal must explain itself"

    w2 = World(prompt="A monastery in 1340.", target_population=5)
    w2.lens = WorldLens()   # pre-lens save: prompt present, lens empty
    fit2 = fit_character(w2, CharacterInput(name="Dave"))
    assert fit2.role, "a raw prompt is enough to fit against"


def test_surprise_character_fits_the_world_and_avoids_existing_names():
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app)
    wid = client.post("/world", json={
        "prompt": "A besieged Cistercian monastery in 1340.", "target_population": 5,
    }).json()["world_id"]
    client.post(f"/world/{wid}/character", json={"name": "Anselm", "role": "cellarer"})
    before = client.get(f"/world/{wid}").json()
    r = client.post(f"/world/{wid}/character/surprise")
    assert r.status_code == 200, r.text
    ch = r.json()
    assert ch["name"] and ch["name"] != "Anselm", "must not collide with the roster"
    assert ch["role"] and ch["role"] != "member", "a surprise must belong to this world"
    roster = client.get(f"/world/{wid}").json()["agents"]
    assert len(roster) == 1, "surprise must not add anyone"
    after = client.get(f"/world/{wid}").json()
    assert before == after, "surprise must not touch the world"


def test_reach_normalization():
    from simulation.audience import normalize_reach, REACH_EVERYONE, REACH_PRESENT, REACH_ONE
    assert normalize_reach("everyone") == REACH_EVERYONE
    assert normalize_reach("those present") == REACH_PRESENT
    assert normalize_reach("one person") == REACH_ONE
    assert normalize_reach("ONE PERSON") == REACH_ONE
    assert normalize_reach(None) == REACH_PRESENT, "missing must default like 'interact' did"
    assert normalize_reach("gibberish") == REACH_PRESENT
    assert normalize_reach(7) == REACH_PRESENT


def test_legacy_action_kind_maps_to_reach():
    from simulation.audience import reach_from_action_kind, REACH_EVERYONE, REACH_PRESENT, REACH_ONE
    assert reach_from_action_kind("post") == REACH_EVERYONE
    assert reach_from_action_kind("direct") == REACH_ONE
    for k in ("amplify", "comment", "interact", "", "nonsense"):
        assert reach_from_action_kind(k) == REACH_PRESENT


def test_reasoner_parses_audience_and_trims_who():
    from models import Agent
    from simulation import reasoner
    a = Agent(id="a1", name="Kai", role="jungler")
    raw = __import__("json").dumps({
        "action": "confront", "target_agents": ["Lena"],
        "intents": {"Lena": "confront"},
        "audience": {"who": "x" * 400, "reach": "everyone"},
        "utterance": "We need to talk about last night.",
        "new_memory": "I confronted Lena in front of everyone.",
        "explanation": "My pride would not let it go.",
    })
    action = reasoner._parse_action(a, raw)
    assert action is not None
    assert action.audience.reach == "everyone"
    assert len(action.audience.who) <= 160, "free text must be trimmed like every other field"


def test_legacy_saved_action_and_feed_entry_still_load():
    """Review Focus #4: saves written before the audience model carry action_kind on
    both stored actions and feed entries. Loading one and continuing must work."""
    from models import AgentAction, FeedEntry, Agent
    from simulation import reasoner
    from simulation.audience import REACH_EVERYONE, REACH_PRESENT

    legacy_entry = FeedEntry(text="x", author="Ana", day=1, action_kind="post")
    assert legacy_entry.reach == REACH_PRESENT, "legacy entries take the safe default"

    a = Agent(id="a1", name="Kai", role="jungler")
    raw = __import__("json").dumps({
        "action": "announce", "target_agents": ["Lena"],
        "intents": {"Lena": "talk"}, "action_kind": "post",
        "utterance": "Everyone should hear this.",
        "new_memory": "I announced it.", "explanation": "Pride.",
    })
    action = reasoner._parse_action(a, raw)
    assert action is not None
    assert action.audience.reach == REACH_EVERYONE, "legacy action_kind must map to reach"

    legacy_action = AgentAction(
        action="x", target_agents=["Lena"], new_memory="I did x.", explanation="testing",
    )
    assert legacy_action.audience.reach == REACH_PRESENT


def test_action_kind_derived_from_audience_not_agent_authored():
    """Correction to Task 6's brief: action_kind is kept (consequence.py, applicator.py
    and the realism suite key off it) but is no longer agent-authored — it is derived
    from the parsed audience + intents, matching the rule Task 7 uses for standing-spread."""
    import json
    from models import Agent
    from simulation import reasoner

    def _act(reach, intents):
        a = Agent(id="a1", name="Kai", role="jungler")
        raw = json.dumps({
            "action": "act", "target_agents": list(intents),
            "intents": intents,
            "audience": {"who": "nearby", "reach": reach},
            "new_memory": "I acted.", "explanation": "because.",
        })
        return reasoner._parse_action(a, raw)

    assert _act("everyone", {"Lena": "praise"}).action_kind == "amplify"
    assert _act("everyone", {"Lena": "support"}).action_kind == "amplify"
    assert _act("everyone", {"Lena": "confront"}).action_kind == "post"
    assert _act("one person", {"Lena": "confide"}).action_kind == "direct"
    assert _act("those present", {"Lena": "talk"}).action_kind == "interact"


def test_derivation_retires_comment_and_narrows_amplify():
    """Fix round 1, Finding 2: `comment` can never come back out of derive_action_kind
    (it shared interact's 0.2 self-influence weight, so retiring it costs nothing), and
    `amplify` only comes out for reach == "everyone" WITH a praise/support intent — never
    for a private exchange, since amplifying means boosting someone PUBLICLY. This is a
    deliberate narrowing, ruled on and accepted; this test pins it so a future edit can't
    silently reopen or further narrow the mapping."""
    from simulation.audience import derive_action_kind, REACH_EVERYONE, REACH_PRESENT, REACH_ONE

    reaches = (REACH_EVERYONE, REACH_PRESENT, REACH_ONE)
    intent_sets = (
        {},
        {"A": "praise"},
        {"A": "support"},
        {"A": "confront"},
        {"A": "talk", "B": "praise"},
        {"A": "confide", "B": "support"},
        {"A": "talk"},
    )
    for reach in reaches:
        for intents in intent_sets:
            kind = derive_action_kind(reach, intents)
            assert kind != "comment", (reach, intents, kind)
            assert kind in ("amplify", "post", "direct", "interact"), (reach, intents, kind)
            has_boost_intent = any(v in ("praise", "support") for v in intents.values())
            if kind == "amplify":
                assert reach == REACH_EVERYONE and has_boost_intent, (reach, intents, kind)
    # And the positive half: every everyone+praise/support combination DOES amplify.
    assert derive_action_kind(REACH_EVERYONE, {"A": "praise"}) == "amplify"
    assert derive_action_kind(REACH_EVERYONE, {"A": "support"}) == "amplify"
    assert derive_action_kind(REACH_EVERYONE, {"A": "talk", "B": "support"}) == "amplify"
    # A boost intent at a narrower reach must NOT amplify.
    assert derive_action_kind(REACH_PRESENT, {"A": "praise"}) != "amplify"
    assert derive_action_kind(REACH_ONE, {"A": "support"}) != "amplify"


_TESTS = [
    test_caps_reject_oversized_runs,
    test_caps_defaults_are_seven,
    test_trim_never_cuts_mid_word,
    test_long_utterance_is_not_cut_mid_word,
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
    test_fallback_action_yields_one_beat,
    test_fallback_action_is_deterministic,
    test_planner_prompt_demands_a_person,
    test_planner_prompt_includes_relationships,
    test_every_agent_starts_connected,
    test_seeding_is_deterministic,
    test_custom_characters_are_not_left_isolated,
    test_highlights_carry_dialogue,
    test_mock_utterance_differs_from_memory,
    test_reasoner_prompt_carries_world_premise,
    test_planner_prompt_carries_world_premise,
    test_reflector_prompt_carries_world_premise,
    test_vignette_prompt_carries_world_premise,
    test_premise_block_is_omitted_when_absent,
    test_premise_is_capped,
    test_report_prompt_does_not_forbid_the_world_voice,
    test_world_context_returns_graph_and_lens,
    test_created_world_carries_a_lens,
    test_world_lens_survives_a_setting_less_prompt,
    test_render_premise_uses_lens_fields,
    test_render_premise_falls_back_to_raw_prompt,
    test_render_premise_caps_a_large_lens_block,
    test_realistic_lens_banned_vocabulary_survives_into_prompt,
    test_report_prompt_carries_lens_vocabulary,
    test_banned_vocabulary_instructs_but_never_filters,
    test_fit_preserves_identity_and_proposes_situation,
    test_fit_endpoint_mutates_nothing,
    test_added_character_is_unfitted_by_default,
    test_fit_on_a_lensless_world_returns_200_not_500,
    test_surprise_character_fits_the_world_and_avoids_existing_names,
    test_reach_normalization,
    test_legacy_action_kind_maps_to_reach,
    test_reasoner_parses_audience_and_trims_who,
    test_legacy_saved_action_and_feed_entry_still_load,
    test_action_kind_derived_from_audience_not_agent_authored,
    test_derivation_retires_comment_and_narrows_amplify,
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
