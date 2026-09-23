from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid

from models import Agent, World, normalize_mood
from llm import call_llm
from .memory import make_memory
from . import consequence

FILLER_SYSTEM = """FILLER_AGENT_GENERATION
You generate fictional citizens for a multi-agent social simulation. Return STRICT JSON only.

Schema:
{
  "agents": [
    {
      "name": "string",
      "role": "string (specific, not generic)",
      "traits": ["string", ...],
      "goals": ["string", ...],
      "mood": "calm|excited|frustrated|heartbroken|ambitious|anxious|content|angry|hopeful|lonely|confident",
      "groups": ["string", ...],
      "memories": ["string", ...]
    }
  ]
}

Rules:
- All characters are fictional. Do not use real public figures.
- 3-4 traits per agent. 1-2 goals. 1-2 group memberships.
- 3-4 memories per agent in first-person past tense. Memories must reveal backstory,
  unresolved tensions, personal failures or wins, and hints of relationships with others.
  Make them specific and emotionally loaded — not generic.
- TRAIT DIVERSITY IS MANDATORY: Every agent in this batch must have a psychologically
  distinct profile. Do NOT reuse trait combinations across agents.
  Avoid overused combos: [ambitious+calculating], [loyal+honorable].
  Draw from a wide range including: defensive, self-sabotaging, avoidant, volatile,
  people-pleasing, paranoid, quietly vengeful, attention-seeking, compulsively honest,
  trauma-bonded, overconfident, secretly generous, bitter, martyrdom-prone,
  emotionally unavailable, idealistic-but-disappointed, ruthless-but-guilty.
- Roles must be specific and contextual to the world — not generic labels.
- Group names must fit the world prompt.
- Output only JSON. No markdown, no commentary.
"""

RELATIONSHIP_SEED_SYSTEM = """RELATIONSHIP_SEEDING
You are initializing the social graph for a multi-agent simulation.
Given a list of characters, generate 3-6 pre-existing relationships between specific pairs
whose traits and memories suggest prior history together.

Return STRICT JSON only:
{
  "relationships": [
    {
      "agent_a": "Name",
      "agent_b": "Name",
      "type": "friendship|rivalry|romance|trust|conflict|alliance|influence",
      "strength": 0.15 to 0.7,
      "mutual": true|false
    }
  ]
}

Rules:
- Only use names that appear in the character list.
- Mix positive and negative relationships — include at least one rivalry or conflict.
- strength 0.15–0.35 = early/fragile, 0.4–0.6 = established, 0.6–0.7 = deep/intense.
- mutual=false means only agent_a has this relationship view of agent_b (one-sided awareness).
- Each agent should appear in at most 2 relationships to avoid over-connecting one character.
- Output only JSON. No markdown, no commentary.
"""


BATCH_SIZE = 3  # agents per LLM call — smaller batches keep each response well within
                # the model's output budget (rich memories make 5 agents overflow / truncate)


_ROLE_NOISE_RE = re.compile(r"\b(the|a|an|of|for|at)\b")


def _normalize_role(role: str) -> str:
    """Compare roles case-, article- and punctuation-insensitively, so
    'Lead Programmer for Robotics Club' and 'Lead Programmer for the Robotics Club'
    are recognised as the same role."""
    r = (role or "").strip().lower()
    r = _ROLE_NOISE_RE.sub(" ", r)
    r = re.sub(r"[^a-z0-9 ]+", " ", r)
    return re.sub(r"\s+", " ", r).strip()


# How many times to re-ask the provider for a non-duplicate role before falling back
# to deterministic disambiguation.
_MAX_ROLE_ATTEMPTS = 3


def _disambiguate_role(role: str, existing_roles: set[str]) -> str:
    """Last-resort deterministic uniqueness.

    Only reached when the provider returned an already-taken role on every attempt.
    Qualifying the title is worse prose than a fresh role but better than shipping two
    characters with identical jobs, which is the bug this task exists to fix.
    """
    base = (role or "member").strip()
    candidate = base
    n = 2
    while _normalize_role(candidate) in existing_roles:
        candidate = f"{base} ({n})"
        n += 1
    return candidate


def generate_fillers(world: World, count: int) -> list[Agent]:
    if count <= 0:
        return []
    existing_names = {a.name for a in world.agents}
    existing_roles = {_normalize_role(a.role) for a in world.agents if a.role}
    out: list[Agent] = []
    remaining = count

    while remaining > 0:
        batch = min(BATCH_SIZE, remaining)
        fresh: list[dict] = []

        # Ask up to _MAX_ROLE_ATTEMPTS times, keeping only non-duplicate roles. Each
        # attempt sends a different prompt, so a deterministic provider still varies.
        for attempt in range(_MAX_ROLE_ATTEMPTS):
            entries = _fetch_batch(world, batch, existing_names, existing_roles, attempt)
            if not entries:
                break
            for entry in entries:
                if len(fresh) >= batch:
                    break
                # Default here must match what Agent(...) will actually store below,
                # or a blank role slips past de-duplication and materialises as a
                # duplicate "member".
                role_key = _normalize_role(entry.get("role") or "member")
                if role_key in existing_roles:
                    continue
                existing_roles.add(role_key)
                fresh.append(entry)
            if len(fresh) >= batch:
                break

        # Still short: the provider kept returning taken roles. Disambiguate
        # deterministically rather than shipping duplicate titles.
        if len(fresh) < batch:
            entries = _fetch_batch(world, batch, existing_names, existing_roles,
                                   _MAX_ROLE_ATTEMPTS)
            for entry in entries:
                if len(fresh) >= batch:
                    break
                role = _disambiguate_role(entry.get("role") or "member", existing_roles)
                entry["role"] = role
                existing_roles.add(_normalize_role(role))
                fresh.append(entry)

        # Guarantees termination: without this, a provider returning nothing usable
        # would spin `while remaining > 0` forever, since `remaining` only decrements
        # for entries that survive.
        if not fresh:
            logging.warning(
                "Filler generation produced no usable entries; stopping at %d of %d",
                count - remaining, count,
            )
            break

        for entry in fresh:
            raw_name = (entry.get("name") or "").strip()
            if not raw_name:
                # Deterministic placeholder. uuid4 here made two otherwise-identical
                # runs produce different rosters.
                stem = hashlib.sha256(f"{world.prompt}|{len(out)}".encode()).hexdigest()[:4]
                raw_name = f"Agent-{stem}"
            name = raw_name
            if name in existing_names:
                # Deterministic collision suffix, for the same reason: this fed
                # _seed_relationships' prompt and made romance-mutuality flaky.
                stem = hashlib.sha256(f"{name}|{len(existing_names)}".encode()).hexdigest()[:3]
                name = f"{name}-{stem}"
            existing_names.add(name)
            raw_memories = entry.get("memories") or []
            # Backstory memories exist from before the sim (day 0). Heuristic importance.
            memories = [make_memory(str(m), day=0) for m in raw_memories if str(m).strip()]
            out.append(Agent(
                id=f"a_{uuid.uuid4().hex[:8]}",
                name=name,
                role=entry.get("role") or "member",
                traits=entry.get("traits") or [],
                goals=entry.get("goals") or [],
                # The model is given the Mood enum in FILLER_SYSTEM but still returns
                # off-enum words (it bleeds trait vocabulary like "bitter" into this
                # field), which made Agent() raise ValidationError and 500 the whole
                # generate-fillers request. Normalize like the reasoner already does.
                mood=normalize_mood(entry.get("mood")),
                groups=entry.get("groups") or [],
                short_term_memory=[m.model_copy() for m in memories],
                long_term_memory=[m.model_copy() for m in memories],
                is_custom=False,
            ))
            remaining -= 1
            if remaining <= 0:
                break

    # Seed across the ENTIRE cast, not just the fillers. Custom characters arrive with
    # starting_relationships={} (CharacterEditor sends no relationships and exposes no UI
    # for them), so passing `out` alone left every hand-made character isolated on day 1 —
    # the precise failure this seeding exists to prevent.
    _seed_relationships(list(world.agents) + out, world.prompt)
    return out


def _fetch_batch(world: World, count: int, existing_names: set[str],
                 existing_roles: set[str], attempt: int = 0) -> list[dict]:
    retry_note = ""
    if attempt:
        retry_note = (
            f"\n\nATTEMPT {attempt + 1}: your previous response reused a role that is "
            f"already taken. Invent clearly different roles this time — a different "
            f"function in this world, not a reworded version of the same job."
        )
    user = (
        f"World prompt:\n{world.prompt}\n\n"
        f"Generate {count} fictional agents that fit this world. "
        f"Avoid these existing names: {sorted(existing_names) or 'none'}. "
        f"These roles are already taken — every new agent must have a clearly "
        f"different role, not a rewording of one of these: "
        f"{sorted(existing_roles) or 'none'}."
        f"{retry_note}"
    )
    try:
        raw = call_llm(FILLER_SYSTEM, user, json_mode=True, max_tokens=4096, tier="cheap")
        logging.info(f"Filler batch LLM raw ({len(raw)} chars): {raw[:120]!r}")
        data = _safe_json(raw)
        if not data.get("agents"):
            raise ValueError("empty agents list")
        return (data.get("agents") or [])[:count]
    except Exception as e:
        logging.warning(f"LLM filler batch failed ({e}), using mock fallback")
        from llm import _mock
        raw = _mock(FILLER_SYSTEM, user, json_mode=True)
        data = _safe_json(raw)
        return (data.get("agents") or [])[:count]


# Day-1 coverage: a cast where some agents know nobody produces a day of solo
# monologues, because an agent with no relationships has nobody to act on. After the
# LLM seeding pass, connect anyone still isolated and guarantee some friction.
# Day-1 friction: how many CHARGED PAIRS to guarantee. Counted as pairs, not directed
# edges — a mutual seed creates two directed edges, and conflating the two is what made
# this loop seed double its apparent target.
_MIN_CHARGED_PAIRS = 2
_CHARGED_SEED_TYPES = ("rivalry", "conflict")


def _ensure_coverage(agents: list[Agent]) -> None:
    """Connect isolated agents and guarantee at least `_MIN_CHARGED_PAIRS` charged
    pairs. Deterministic: pairing is by sorted name and a stable hash, never by
    `random`, so a replayed run seeds identically."""
    if len(agents) < 2:
        return
    ordered = sorted(agents, key=lambda a: a.name)

    def _partner_for(a: Agent) -> Agent:
        pool = [o for o in ordered if o.id != a.id]
        idx = int(hashlib.sha256(a.name.encode()).hexdigest()[:8], 16) % len(pool)
        return pool[idx]

    for a in ordered:
        if not a.relationships:
            consequence.seed_relationship(a, _partner_for(a), "trust", 0.25, True)

    def _charged_pairs() -> int:
        """Distinct unordered pairs joined by a charged bond, counted off the live
        relationship table rather than tracked in a local counter."""
        pairs = set()
        for x in ordered:
            for name, r in x.relationships.items():
                if r.type in ("rivalry", "conflict", "romance"):
                    pairs.add(tuple(sorted((x.name, name))))
        return len(pairs)

    seeded_pairs = 0
    i = 0
    while _charged_pairs() < _MIN_CHARGED_PAIRS and i + 1 < len(ordered):
        a, b = ordered[i], ordered[i + 1]
        # Cycle on pairs seeded, not on `i` — `i` advances by 2, so indexing with it
        # pinned this to index 0 and "conflict" was never reachable.
        rel_type = _CHARGED_SEED_TYPES[seeded_pairs % len(_CHARGED_SEED_TYPES)]
        consequence.seed_relationship(a, b, rel_type, 0.35, True)
        seeded_pairs += 1
        i += 2


def _seed_relationships(agents: list[Agent], world_prompt: str) -> None:
    """Ask the LLM to generate initial relationship pairs and apply them to the agents."""
    if len(agents) < 2:
        return

    summaries = "\n".join(
        f"- {a.name}: {a.role} | traits: {', '.join(a.traits[:3])} "
        f"| last memory: {a.long_term_memory[-1].text[:100] if a.long_term_memory else 'none'}"
        for a in agents
    )
    user = (
        f"World: {world_prompt}\n\n"
        f"Characters:\n{summaries}\n\n"
        f"Generate 3-6 pre-existing relationships between these characters."
    )

    name_map = {a.name: a for a in agents}

    try:
        raw = call_llm(RELATIONSHIP_SEED_SYSTEM, user, json_mode=True, max_tokens=1024, tier="cheap")
        data = _safe_json(raw)
        seeded = 0
        for rel in (data.get("relationships") or []):
            # Per-entry guard. A single malformed entry (non-numeric strength, or an
            # entry that isn't even a dict) used to raise out to the batch-level handler
            # below, silently discarding every relationship after it. Skip the bad one
            # and keep the rest.
            try:
                a_name = rel.get("agent_a", "")
                b_name = rel.get("agent_b", "")
                a = name_map.get(a_name)
                b = name_map.get(b_name)
                if not a or not b or a_name == b_name:
                    continue
                rel_type = rel.get("type", "trust")
                try:
                    strength = float(rel.get("strength", 0.25))
                except (TypeError, ValueError):
                    strength = 0.25
                strength = max(0.1, min(0.7, strength))
                mutual = bool(rel.get("mutual", True))
                # Seed via the consequence layer so the affinity carries the correct SIGN for
                # its type (a seeded rivalry/conflict is negative) and survives `realize`.
                consequence.seed_relationship(a, b, rel_type, strength, mutual)
                seeded += 1
            except Exception as e:  # noqa: BLE001 — drop this entry, not the batch
                logging.warning(f"Skipped malformed relationship entry {rel!r}: {e}")
        logging.info(f"Seeded {seeded} relationships for {len(agents)} agents")
    except Exception as e:
        logging.warning(f"Relationship seeding failed: {e}")

    _ensure_coverage(agents)


def _safe_json(raw: str) -> dict:
    if not raw:
        return {}
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw)
    raw = raw.strip()

    # Try parsing the whole thing first
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
        if isinstance(result, list):
            return {"agents": result}
    except json.JSONDecodeError:
        pass

    # Find outermost { ... } (handles preamble text before the JSON)
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        try:
            result = json.loads(raw[start:end + 1])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Fallback: bare array
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1:
        try:
            return {"agents": json.loads(raw[start:end + 1])}
        except json.JSONDecodeError:
            pass

    # Salvage: the response was truncated mid-JSON (common with small/free models or
    # reasoning models). Recover every COMPLETE agent object that arrived before the
    # cutoff so we still get usable characters instead of falling back to mock.
    salvaged = _salvage_objects(raw)
    if salvaged:
        logging.warning(f"_safe_json salvaged {len(salvaged)} complete object(s) from truncated JSON")
        return {"agents": salvaged}

    logging.warning(f"_safe_json could not parse ({len(raw)} chars): {raw[:200]!r}")
    return {}


def _salvage_objects(raw: str) -> list[dict]:
    """Extract every balanced {...} that parses as a dict with a 'name' field.

    A truncated array like `{"agents":[{...},{...},{partial...` leaves the complete
    agent objects intact (they closed) while the outer object never closes — so we
    recover the finished agents and drop the partial tail.
    """
    objs: list[dict] = []
    stack: list[int] = []
    in_str = esc = False
    for i, ch in enumerate(raw):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            frag = raw[stack.pop():i + 1]
            try:
                d = json.loads(frag)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and "name" in d:
                objs.append(d)
    return objs
