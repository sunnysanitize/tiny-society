from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
from typing import Optional

import httpx


# Matches a capitalized first name inside memory text, used by the PLAN_FORMATION
# mock to ground a plan in a recently-mentioned person.
import re as _re_module
# Only match a capitalized word that sits MID-sentence (preceded by a lowercase
# letter or comma + space) — sentence-initial words like "Walked"/"Things" are not names.
_re_plan = _re_module.compile(r"(?<=[a-z,]\s)([A-Z][a-z]{2,})")

# Capitalized words that are NOT names — keeps the PLAN_FORMATION mock from
# grounding a plan in junk like "Nobody on my side".
_PLAN_NAME_STOP = {
    "Nobody", "Someone", "Anyone", "Everyone", "Today", "Yesterday", "Tomorrow",
    "Last", "Then", "Watch", "Attention", "Mark", "The", "This", "That", "They",
    "Their", "Them", "When", "While", "After", "Before", "Because", "Honestly",
}


def _clean_mock_event(text: str) -> str:
    """The mock prompt parsers read the line after a section header; when a day has
    no world event that line is actually the prompt's instructions. Reject those so
    plan/vignette text doesn't leak instruction fragments."""
    t = (text or "").strip()
    if not t:
        return ""
    low = t.lower()
    if any(kw in low for kw in (
        "intention", "state your", "one-sentence", "one sentence", "return ",
        "json", "describe", "declare a", "in first person", "no prose", "no quotes",
    )):
        return ""
    return t


class LLMError(Exception):
    pass


def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock").lower()


def call_llm(system: str, user: str, *, json_mode: bool = False, max_tokens: int = 1024, tier: str = "strong") -> str:
    """Single text completion. Returns raw string output."""
    provider = _provider()
    if provider == "anthropic":
        return _call_anthropic(system, user, max_tokens=max_tokens, tier=tier)
    if provider == "openai_compat":
        return _call_openai_compat(system, user, json_mode=json_mode, max_tokens=max_tokens, tier=tier)
    return _mock(system, user, json_mode=json_mode)


def _call_anthropic(system: str, user: str, max_tokens: int, tier: str = "strong") -> str:
    from anthropic import Anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMError("ANTHROPIC_API_KEY not set")
    model = os.getenv(f"ANTHROPIC_MODEL_{tier.upper()}") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def _call_openai_compat(system: str, user: str, json_mode: bool, max_tokens: int, tier: str = "strong") -> str:
    import re as _re
    import time as _time
    import logging as _logging

    base = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    key = os.getenv("OPENAI_COMPAT_API_KEY")
    model = os.getenv(f"OPENAI_COMPAT_MODEL_{tier.upper()}") or os.getenv("OPENAI_COMPAT_MODEL", "google/gemini-2.0-flash-001")
    if not base or not key:
        raise LLMError("OPENAI_COMPAT_BASE_URL or OPENAI_COMPAT_API_KEY not set")

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Tiny Society AI",
    }

    for attempt in range(5):
        try:
            with httpx.Client(timeout=120) as c:
                r = c.post(f"{base}/chat/completions", json=payload, headers=headers)

                if r.status_code == 429:
                    wait = float(r.headers.get("Retry-After", 10 * (attempt + 1)))
                    wait = min(wait, 90)
                    _logging.warning(f"Rate limited (attempt {attempt+1}/5), retrying in {wait:.0f}s")
                    _time.sleep(wait)
                    continue

                r.raise_for_status()
                data = r.json()

                # Some providers embed errors inside 200 responses
                if not data.get("choices") and "error" in data:
                    err_msg = data["error"].get("message", str(data["error"]))
                    _logging.warning(f"Provider error in 200 response (attempt {attempt+1}/5): {err_msg[:200]}")
                    if attempt < 4:
                        _time.sleep(5 * (attempt + 1))
                        continue
                    raise LLMError(f"Provider error: {err_msg}")

                msg = data["choices"][0]["message"]
                content = msg.get("content") or ""

                # Strip <think>...</think> blocks (DeepSeek-R1, QwQ, trinity-thinking, etc.)
                content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()

                # Some providers put the answer in reasoning_content when content is empty
                if not content:
                    content = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
                    content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()

                if not content:
                    _logging.warning(f"LLM returned empty content (attempt {attempt+1}/5), retrying")
                    if attempt < 4:
                        _time.sleep(3 * (attempt + 1))
                        continue
                    raise LLMError("LLM returned empty content after all retries")

                return content

        except LLMError:
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            _logging.warning(f"Network error (attempt {attempt+1}/5): {e}")
            if attempt < 4:
                _time.sleep(5 * (attempt + 1))
            else:
                raise LLMError(f"Network failed after 5 attempts: {e}")
        except httpx.HTTPStatusError as e:
            if attempt < 4 and e.response.status_code >= 500:
                _logging.warning(f"HTTP {e.response.status_code} (attempt {attempt+1}/5), retrying")
                _time.sleep(5 * (attempt + 1))
                continue
            raise LLMError(f"HTTP {e.response.status_code}: {e.response.text[:400]}")

    raise LLMError("All 5 retry attempts exhausted")


# ── async path (concurrent fan-out) ─────────────────────────────────────────────

_sem: Optional[asyncio.Semaphore] = None


def _get_sem() -> asyncio.Semaphore:
    """Lazily create the concurrency semaphore on first async call so it binds to
    the running loop (and the env var is read at first use)."""
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(int(os.getenv("LLM_MAX_CONCURRENCY", "6")))
    return _sem


async def acall_llm(system: str, user: str, *, json_mode: bool = False, max_tokens: int = 1024, tier: str = "strong") -> str:
    """Async counterpart to call_llm, bounded by a concurrency semaphore."""
    sem = _get_sem()
    async with sem:
        provider = _provider()
        if provider == "anthropic":
            return await _call_anthropic_async(system, user, max_tokens=max_tokens, tier=tier)
        if provider == "openai_compat":
            return await _call_openai_compat_async(system, user, json_mode=json_mode, max_tokens=max_tokens, tier=tier)
        return await asyncio.to_thread(_mock, system, user, json_mode)


async def _call_anthropic_async(system: str, user: str, max_tokens: int, tier: str = "strong") -> str:
    from anthropic import AsyncAnthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMError("ANTHROPIC_API_KEY not set")
    model = os.getenv(f"ANTHROPIC_MODEL_{tier.upper()}") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    client = AsyncAnthropic(api_key=api_key)
    msg = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


async def _call_openai_compat_async(system: str, user: str, json_mode: bool, max_tokens: int, tier: str = "strong") -> str:
    import re as _re
    import logging as _logging

    base = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    key = os.getenv("OPENAI_COMPAT_API_KEY")
    model = os.getenv(f"OPENAI_COMPAT_MODEL_{tier.upper()}") or os.getenv("OPENAI_COMPAT_MODEL", "google/gemini-2.0-flash-001")
    if not base or not key:
        raise LLMError("OPENAI_COMPAT_BASE_URL or OPENAI_COMPAT_API_KEY not set")

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Tiny Society AI",
    }

    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                r = await c.post(f"{base}/chat/completions", json=payload, headers=headers)

                if r.status_code == 429:
                    wait = float(r.headers.get("Retry-After", 10 * (attempt + 1)))
                    wait = min(wait, 90)
                    _logging.warning(f"Rate limited (attempt {attempt+1}/5), retrying in {wait:.0f}s")
                    await asyncio.sleep(wait)
                    continue

                r.raise_for_status()
                data = r.json()

                # Some providers embed errors inside 200 responses
                if not data.get("choices") and "error" in data:
                    err_msg = data["error"].get("message", str(data["error"]))
                    _logging.warning(f"Provider error in 200 response (attempt {attempt+1}/5): {err_msg[:200]}")
                    if attempt < 4:
                        await asyncio.sleep(5 * (attempt + 1))
                        continue
                    raise LLMError(f"Provider error: {err_msg}")

                msg = data["choices"][0]["message"]
                content = msg.get("content") or ""

                # Strip <think>...</think> blocks (DeepSeek-R1, QwQ, trinity-thinking, etc.)
                content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()

                # Some providers put the answer in reasoning_content when content is empty
                if not content:
                    content = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
                    content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()

                if not content:
                    _logging.warning(f"LLM returned empty content (attempt {attempt+1}/5), retrying")
                    if attempt < 4:
                        await asyncio.sleep(3 * (attempt + 1))
                        continue
                    raise LLMError("LLM returned empty content after all retries")

                return content

        except LLMError:
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            _logging.warning(f"Network error (attempt {attempt+1}/5): {e}")
            if attempt < 4:
                await asyncio.sleep(5 * (attempt + 1))
            else:
                raise LLMError(f"Network failed after 5 attempts: {e}")
        except httpx.HTTPStatusError as e:
            if attempt < 4 and e.response.status_code >= 500:
                _logging.warning(f"HTTP {e.response.status_code} (attempt {attempt+1}/5), retrying")
                await asyncio.sleep(5 * (attempt + 1))
                continue
            raise LLMError(f"HTTP {e.response.status_code}: {e.response.text[:400]}")

    raise LLMError("All 5 retry attempts exhausted")


# ── trait / mood action templates ──────────────────────────────────────────────

_TRAIT_ACTIONS: dict[str, list[tuple]] = {
    "ambitious": [
        ("forge a strategic alliance with", "alliance", 0.3, "ambitious",
         "Their ambition made this alliance feel like a necessary move toward their goals."),
        ("angle for influence over", "influence", 0.25, "confident",
         "They saw an opening and took it — the ambitious always do."),
    ],
    "competitive": [
        ("escalate a rivalry with", "rivalry", -0.25, "excited",
         "Their competitive streak turned a simple disagreement into a contest."),
        ("openly challenge", "conflict", -0.2, "ambitious",
         "The competitive fire in them refused to let the moment pass quietly."),
    ],
    "loyal": [
        ("stand up for", "friendship", 0.25, "content",
         "Their loyalty made walking away from someone in need impossible."),
        ("confide a secret in", "trust", 0.3, "calm",
         "They trust deeply once they've committed — and they had."),
    ],
    "anxious": [
        ("quietly avoid", "conflict", -0.1, "anxious",
         "The anxiety made closeness feel risky, so they kept their distance."),
        ("seek reassurance from", "trust", 0.15, "hopeful",
         "The anxiety pushed them toward someone steady."),
    ],
    "charismatic": [
        ("draw into their circle", "friendship", 0.25, "excited",
         "Their natural charm opened the door before they even knocked."),
        ("rally support from", "alliance", 0.3, "confident",
         "Their magnetism made it easy to get others on board."),
    ],
    "introverted": [
        ("share a quiet moment with", "friendship", 0.15, "calm",
         "They chose depth over breadth, as always — one real connection over many shallow ones."),
        ("observe from a distance before reaching out to", "trust", 0.1, "calm",
         "They watched first, acted second. That's just who they are."),
    ],
    "social": [
        ("spend meaningful time with", "friendship", 0.2, "content",
         "Being around people recharged them. It always had."),
        ("bring together", "alliance", 0.15, "excited",
         "They couldn't help it — they see connection potential everywhere."),
    ],
    "stubborn": [
        ("refuse to back down from", "conflict", -0.2, "frustrated",
         "Their stubbornness turned a small disagreement into something bigger than it needed to be."),
        ("double down on their position with", "rivalry", -0.15, "confident",
         "Once they made up their mind, no one was moving them."),
    ],
    "thoughtful": [
        ("offer unexpected support to", "trust", 0.2, "hopeful",
         "They'd been thinking about this person's situation for days. Today they acted on it."),
        ("have a difficult but honest conversation with", "trust", 0.25, "calm",
         "They chose truth over comfort because they believed the other person deserved it."),
    ],
    "creative": [
        ("collaborate creatively with", "alliance", 0.2, "excited",
         "They saw a creative opportunity and invited someone in to share it."),
        ("pitch an unusual idea to", "influence", 0.15, "hopeful",
         "The idea had been rattling around for a while. Today felt like the right time."),
    ],
    "patient": [
        ("quietly mend fences with", "friendship", 0.2, "calm",
         "They gave the situation time to breathe, then stepped in at exactly the right moment."),
        ("de-escalate tensions between themselves and", "conflict", 0.1, "content",
         "Their patience let them wait until the other person was ready to talk."),
    ],
    "easily annoyed": [
        ("snap at", "conflict", -0.25, "angry",
         "Something small was the final straw. It always is."),
        ("complain openly about", "rivalry", -0.15, "frustrated",
         "They'd been holding this in and finally stopped bothering."),
    ],
}

_MOOD_ACTIONS: dict[str, tuple] = {
    "frustrated": ("vent their frustration at", "conflict", -0.2, "frustrated",
                   "The built-up frustration finally found a direction."),
    "excited":    ("enthusiastically pull into their plans", "friendship", 0.2, "excited",
                   "Their excitement was contagious and they needed someone to share it with."),
    "heartbroken": ("pull away from", "conflict", -0.15, "lonely",
                    "The heartbreak made closeness feel too dangerous right now."),
    "ambitious":  ("make a calculated move toward", "alliance", 0.3, "ambitious",
                   "Every decision they make traces back to what they're trying to build."),
    "lonely":     ("reach out hesitantly to", "friendship", 0.1, "hopeful",
                   "The loneliness finally got loud enough that they had to do something."),
    "angry":      ("confront directly", "conflict", -0.3, "angry",
                   "The anger had been building and today it broke through the surface."),
    "hopeful":    ("extend an olive branch to", "trust", 0.2, "hopeful",
                   "Hope has a way of making people brave enough to try."),
    "confident":  ("openly mentor and guide", "influence", 0.25, "confident",
                   "The confidence made stepping into a guiding role feel natural."),
    "anxious":    ("check in nervously with", "trust", 0.1, "anxious",
                   "The anxiety drove them to seek some kind of certainty."),
    "calm":       ("have a grounding conversation with", "friendship", 0.15, "calm",
                   "The calm gave them space to connect without an agenda."),
    "content":    ("strengthen their bond with", "friendship", 0.2, "content",
                   "When things are good, you want to share it with the people who matter."),
}


def _mock(system: str, user: str, json_mode: bool) -> str:
    """Deterministic contextual mock so the engine runs end-to-end without API keys."""
    seed = int(hashlib.sha256((system + "|" + user).encode()).hexdigest(), 16) % (2 ** 32)
    rng = random.Random(seed)

    # ── filler agent generation ────────────────────────────────────────────────
    if "FILLER_AGENT_GENERATION" in system:
        ctx = user.lower()
        is_fantasy  = any(w in ctx for w in ("kingdom", "magic", "medieval", "realm", "wizard", "elf", "sword", "throne", "castle", "knight"))
        is_scifi    = any(w in ctx for w in ("space", "colony", "starship", "android", "station", "planet", "galaxy", "crew", "mission"))
        is_corp     = any(w in ctx for w in ("office", "company", "startup", "corporate", "workplace", "firm", "ceo", "employee"))
        is_school   = any(w in ctx for w in ("school", "university", "college", "campus", "student", "class", "dorm", "professor"))

        if is_fantasy:
            first_names = ["Aldric", "Mira", "Theron", "Seren", "Cael", "Lyra", "Davan", "Nia",
                           "Oswin", "Fen", "Talia", "Bran", "Isolde", "Corvin", "Willa", "Emrys",
                           "Rowan", "Vesper", "Cormac", "Aelys", "Dorin", "Fenna", "Hadrik", "Sable"]
            last_names  = ["Ashveil", "Dawnbrook", "Ironwood", "Stormcrest", "Nighthollow",
                           "Goldthorn", "Ravenmoor", "Cinderpeak", "Saltmarsh", "Greywood"]
            roles_pool  = ["disgraced knight", "village healer with a secret", "ambitious court scholar",
                           "exiled noble", "wandering mercenary", "reluctant heir", "temple acolyte",
                           "guild enforcer", "traveling bard hiding their past", "former spy"]
            groups_pool = ["The Iron Accord", "Merchants' Syndicate", "Temple of the Seven",
                           "King's Council", "The Unseen Hand", "Blackwood Company",
                           "Rebel Faction", "City Guard"]
        elif is_scifi:
            first_names = ["Kael", "Zara", "Mox", "Lyra", "Dex", "Nova", "Cid", "Sable",
                           "Orion", "Vex", "Aria", "Juno", "Rael", "Pell", "Siv", "Tane"]
            last_names  = ["Voss", "Kaine", "Orin", "Mercer", "Vale", "Cross", "Hale",
                           "Stroud", "Nyx", "Callum", "Dray", "Fell"]
            roles_pool  = ["burned-out navigation officer", "black-market medic", "propaganda analyst",
                           "rogue engineer", "colony overseer with divided loyalties",
                           "trauma surgeon turned soldier", "communications specialist hiding a signal",
                           "retired admiral adjusting to civilian life", "cargo runner who's seen too much"]
            groups_pool = ["Command Deck", "Engineering Bay", "Medical Corps",
                           "Civilian Sector", "Security Division", "The Resistance",
                           "Colonial Authority", "Dock Workers Union"]
        elif is_corp:
            first_names = ["Marcus", "Priya", "Derek", "Yuki", "Aisha", "Connor", "Zoe",
                           "Reza", "Nadia", "Sam", "Elena", "Omar", "Jin", "Clara", "Felix"]
            last_names  = ["Chen", "Vasquez", "Park", "Okafor", "Reyes", "Nakamura",
                           "Ibrahim", "Petrov", "Santos", "Johansson", "Mbeki", "Walsh"]
            roles_pool  = ["middle manager who knows where the bodies are buried",
                           "new hire with too much ambition", "HR director with a personal agenda",
                           "burned-out senior engineer", "VP who peaked five years ago",
                           "junior analyst gunning for a promotion", "external consultant no one trusts",
                           "long-timer who's seen three regimes", "finance director with a leak problem"]
            groups_pool = ["Executive Team", "Product Division", "Engineering", "Sales",
                           "Legal & Compliance", "HR", "The Old Guard", "The New Cohort"]
        else:  # school / generic default
            first_names = ["Marcus", "Yuki", "Aisha", "Leo", "Priya", "Finn", "Zoe", "Reza",
                           "Nadia", "Sam", "Ines", "Theo", "Mara", "Jin", "Clara", "Omar",
                           "Vera", "Eli", "Leila", "Noah", "Cleo", "Dani", "Ren", "Skye"]
            last_names  = ["Chen", "Vasquez", "Park", "Okafor", "Reyes", "Nakamura",
                           "Ibrahim", "Petrov", "Santos", "Johansson", "Mbeki", "Walsh",
                           "Kowalski", "Diallo", "Russo", "Kim"]
            roles_pool  = ["second-year student on academic probation",
                           "overachieving freshman quietly falling apart",
                           "TA who knows everyone's secrets",
                           "mature student who left a career to come here",
                           "scholarship student from a different world than their peers",
                           "former high school star adjusting to being average",
                           "campus activist burning out on causes",
                           "thesis student who hasn't slept properly in months",
                           "transfer student still figuring out who they are here",
                           "student athlete hiding an injury"]
            groups_pool = ["Dorm Council", "Debate Society", "Student Research Lab",
                           "Varsity Team", "The Late-Night Crew", "Campus Politics",
                           "Study Group A", "Off-Campus Clique", "Arts Collective",
                           "Graduate Lounge"]

        # ── Rich psychological archetypes ──────────────────────────────────────
        archetypes = [
            {
                "traits": ["relentlessly hardworking", "terrified of failure", "struggles to accept help"],
                "goals": ["outperform everyone without showing the effort it costs"],
                "memories": [
                    "I got the top score in the last evaluation. I couldn't enjoy it — I spent the next day waiting for someone to find a mistake.",
                    "A mentor once called me 'naturally gifted.' I've been working twice as hard ever since to prove that wrong, and to prove them right.",
                    "I turned down three social invitations this week to prepare. I don't know if that makes me disciplined or just scared of being found out.",
                    "Someone cried in the hallway after the results were posted. I felt guilty — not because I did something wrong, but because I wasn't surprised by my score.",
                ],
                "mood": "ambitious",
            },
            {
                "traits": ["socially magnetic", "emotionally unavailable", "expert at deflection"],
                "goals": ["stay connected to everyone without letting anyone too close"],
                "memories": [
                    "People call me the glue of the group. What they don't know is that I feel most alone in a crowd.",
                    "I made everyone laugh at the gathering last week. Walked home alone and didn't speak to anyone for two days.",
                    "Someone once said I was the person they'd call in a crisis but not someone they really knew. I've been thinking about that since.",
                    "I ended a close friendship last year because they started to see through my deflections. I told myself they were the problem.",
                ],
                "mood": "content",
            },
            {
                "traits": ["deeply principled", "uncompromising", "privately exhausted by their own standards"],
                "goals": ["hold the line on what's right even when it costs them"],
                "memories": [
                    "I reported a superior for cutting corners. The process took eight months, nothing changed, and I'm still the one people look at sideways.",
                    "I gave honest feedback that wasn't asked for and it ended a working relationship I valued. I don't regret it. I also haven't recovered from it.",
                    "Someone asked me why I bother. I said 'because someone has to.' I meant it. I also didn't sleep that night.",
                    "I've started to wonder if integrity without power is just self-punishment. I hate that I'm wondering that.",
                ],
                "mood": "frustrated",
            },
            {
                "traits": ["quietly observant", "loyal to a fault", "slow to trust but immovable once they do"],
                "goals": ["find one person who actually means what they say"],
                "memories": [
                    "I watched two people I thought were close friends talk about a third behind their back. I didn't say anything. I started watching everyone differently after that.",
                    "I helped someone through a crisis that nobody else knew about. They've barely spoken to me since. I've learned to expect that.",
                    "There's one person here who's never once performed for my approval. I think about that more than I should.",
                    "I keep a short list of people I'd actually call if things went badly. Right now it has two names on it.",
                ],
                "mood": "calm",
            },
            {
                "traits": ["charismatic", "strategically generous", "territorial about status"],
                "goals": ["consolidate influence before anyone realizes how hard I'm working at it"],
                "memories": [
                    "I introduced two people specifically because I thought they'd like each other less than they liked me individually. It worked.",
                    "Someone called me a natural leader last month. I've been carefully managing their perception of me for the last six months.",
                    "I did a genuine favor for someone last week, and I'm irritated that I can't tell whether it was actually genuine.",
                    "There's a person here who doesn't respond to my usual moves. I find myself thinking about them constantly.",
                ],
                "mood": "confident",
            },
            {
                "traits": ["idealistic", "prone to disappointment", "still trying despite everything"],
                "goals": ["find evidence that people are better than their worst moments"],
                "memories": [
                    "I organized something I really believed in. Three people showed up. I told myself it was a start.",
                    "I trusted someone with something real and they used it in an argument a month later. I forgave them. I don't know why.",
                    "I keep starting conversations about things that matter and watching people's eyes glaze over. I haven't stopped starting them.",
                    "Someone told me I was naive. They were probably right. I'd rather be that than the alternative.",
                ],
                "mood": "hopeful",
            },
            {
                "traits": ["cynical on the surface", "desperate for connection underneath", "pushes people away then resents them for leaving"],
                "goals": ["stop sabotaging relationships long enough to see if one works"],
                "memories": [
                    "I said something cruel to someone I cared about because they were getting too close. They gave me exactly the distance I asked for and I've been miserable since.",
                    "I dismissed a genuine offer of friendship by making a joke. The person laughed. Then didn't try again.",
                    "I've been telling myself I prefer being alone. I'm not sure that's true anymore.",
                    "Someone called me 'a lot to deal with.' They said it kindly. That somehow made it worse.",
                ],
                "mood": "lonely",
            },
            {
                "traits": ["volatile under pressure", "intensely perceptive", "capable of great warmth in rare moments"],
                "goals": ["prove that the anger comes from somewhere real, not just from being difficult"],
                "memories": [
                    "I said something I meant but said it wrong, and now the thing I meant is buried under the way I said it.",
                    "Someone flinched at my tone last week. I noticed. I didn't apologize. I haven't stopped thinking about it.",
                    "There are exactly two people who don't treat my anger like a liability. I'd do anything for either of them.",
                    "I was passed over for something I earned. I reacted badly. The reaction became the story.",
                ],
                "mood": "angry",
            },
            {
                "traits": ["pragmatic", "quietly carrying more than they show", "underestimated by everyone"],
                "goals": ["make it through without anyone figuring out how close to the edge they are"],
                "memories": [
                    "I solved a problem last month that three other people had given up on. Nobody asked how I did it. I'm not sure I could explain.",
                    "I've been running on four hours of sleep for two weeks. I keep telling people I'm fine. They keep believing me.",
                    "Someone described me as 'reliable' and 'low-maintenance' in the same sentence. I smiled. Later I sat with how hollow that felt.",
                    "I have a plan for getting through this period. It depends on nothing going wrong. Things keep going wrong.",
                ],
                "mood": "anxious",
            },
            {
                "traits": ["intellectually restless", "easily bored", "searches for meaning in everything"],
                "goals": ["find something worth being genuinely interested in"],
                "memories": [
                    "I got deeply interested in something and then couldn't figure out what to do with that interest, so I let it fade. That's happened four times now.",
                    "I had a conversation that changed how I see something fundamental. The other person doesn't know that. I've been looking for an excuse to talk to them again.",
                    "I read three things this week that contradicted each other. Instead of resolving it, I've been sitting with all three.",
                    "Someone asked what I care about and I couldn't answer. That scared me more than I expected.",
                ],
                "mood": "calm",
            },
            {
                "traits": ["competitive", "generous to allies", "ruthless about perceived threats"],
                "goals": ["win — but only if the winning means something"],
                "memories": [
                    "I lost to someone I'd underestimated. Instead of congratulating them, I immediately started planning how to beat them next time.",
                    "I shared something that gave a rival an advantage because it was the right thing to do. I've been angrier about that than I expected.",
                    "There's someone here who competes with me and actually makes me better. I haven't told them because I don't want them to know I need it.",
                    "I was asked to mentor someone who might one day surpass me. I said yes. I'm still not sure why.",
                ],
                "mood": "ambitious",
            },
            {
                "traits": ["warmhearted", "avoids conflict at personal cost", "takes on others' problems to ignore their own"],
                "goals": ["help everyone around them until it becomes impossible to avoid themselves"],
                "memories": [
                    "I talked someone through a breakdown last month. They're doing better now. I haven't told anyone what it cost me to hold that.",
                    "I avoided a difficult conversation for six weeks by staying busy with other people's problems. The conversation still happened. It was worse for the delay.",
                    "Someone told me I was the most caring person they knew. I wanted to ask if they'd noticed I've been falling apart.",
                    "I apologized for something that wasn't my fault because the tension was unbearable. They accepted it. The thing they'd done never got addressed.",
                ],
                "mood": "content",
            },
            {
                "traits": ["adaptable", "uncertain who they are without an audience", "genuinely good at becoming what others need"],
                "goals": ["figure out which version of themselves is actually real"],
                "memories": [
                    "I was different people in three different conversations yesterday. All of them were technically honest. None of them felt like me.",
                    "Someone said 'you're always so easy to be around' and I didn't know whether to feel seen or erased.",
                    "I caught myself performing an emotion I actually felt, and couldn't tell where the feeling stopped and the performance began.",
                    "I agreed with someone I completely disagreed with because the room was reading it as the right answer. I've been unsettled since.",
                ],
                "mood": "anxious",
            },
            {
                "traits": ["grieving something they haven't named", "still functional", "changed in ways others haven't noticed"],
                "goals": ["get to the other side of whatever this is"],
                "memories": [
                    "Something ended recently that I haven't processed. I keep acting like it didn't happen. It works until it doesn't.",
                    "A person I relied on is no longer in my life in the way they used to be. The gap is in everything.",
                    "I went through the motions of a normal week and felt nothing. Then one small thing happened and I felt too much.",
                    "Someone asked if I was okay. I said yes. There's no shorter version of the truth.",
                ],
                "mood": "heartbroken",
            },
            {
                "traits": ["quietly ambitious", "reads people with unsettling accuracy", "plays a longer game than anyone realizes"],
                "goals": ["position themselves without anyone realizing they've been positioned"],
                "memories": [
                    "I've been watching the dynamics in this group for weeks. I know who defers to whom, who resents whom, and who's pretending not to care.",
                    "I did something helpful that cost me nothing but built significant goodwill. I'm not ashamed of that math.",
                    "Someone outmaneuvered me last month. I was impressed. I'm also not going to let it happen again.",
                    "I have a clear picture of where I'll be in a year. Nobody else in this room does. That asymmetry is an advantage.",
                ],
                "mood": "confident",
            },
        ]

        # Extract world-informed groups from prompt if possible
        extracted_groups: list[str] = []
        for line in user.splitlines():
            if any(g.lower() in line.lower() for g in groups_pool):
                extracted_groups = groups_pool
                break
        active_groups = extracted_groups or groups_pool

        used_names: set[str] = set()
        agents = []
        n = 25
        archetype_order = rng.sample(archetypes, min(len(archetypes), n))
        archetype_cycle = archetype_order + [rng.choice(archetypes) for _ in range(max(0, n - len(archetypes)))]

        for i in range(n):
            arch = archetype_cycle[i]
            first = rng.choice(first_names)
            last  = rng.choice(last_names)
            name  = f"{first} {last}"
            # Avoid duplicates
            attempt = 0
            while name in used_names and attempt < 10:
                first = rng.choice(first_names)
                last  = rng.choice(last_names)
                name  = f"{first} {last}"
                attempt += 1
            used_names.add(name)

            agents.append({
                "name": name,
                "role": rng.choice(roles_pool),
                "traits": arch["traits"],
                "goals": arch["goals"],
                "mood": arch["mood"],
                "groups": rng.sample(active_groups, min(rng.randint(1, 2), len(active_groups))),
                "memories": arch["memories"],
            })
        return json.dumps({"agents": agents})

    # ── world knowledge graph extraction ───────────────────────────────────────
    if "WORLD_GRAPH_EXTRACTION" in system:
        ctx = user.lower()
        # Derive a few entity-ish nouns from the premise, plus genre-flavored stakes.
        _STOPWORDS = {
            "the", "and", "for", "with", "that", "this", "from", "into", "they",
            "their", "will", "who", "what", "where", "when", "a", "an", "of", "to",
            "in", "on", "is", "are", "be", "as", "by", "or", "it", "one", "only",
            "world", "premise", "prediction", "question", "return", "graph", "json",
            "now", "can", "must",
        }
        import re as _re_wg
        words = _re_wg.findall(r"[A-Za-z]{4,}", user)
        seen: set[str] = set()
        nouns: list[str] = []
        for w in words:
            lw = w.lower()
            if lw in _STOPWORDS or lw in seen:
                continue
            seen.add(lw)
            nouns.append(w)
            if len(nouns) >= 4:
                break

        is_fantasy = any(w in ctx for w in ("kingdom", "magic", "realm", "throne", "castle", "knight"))
        is_scifi = any(w in ctx for w in ("space", "colony", "starship", "station", "planet", "crew"))
        is_corp = any(w in ctx for w in ("office", "company", "startup", "corporate", "firm", "ceo"))
        is_school = any(w in ctx for w in ("school", "university", "college", "campus", "student", "dorm"))

        if is_fantasy:
            place, authority = "The Realm", "the Crown"
            topics = ["loyalty to the crown", "use of forbidden magic", "war vs. diplomacy", "old blood vs. new power"]
        elif is_scifi:
            place, authority = "The Station", "Command"
            topics = ["mission vs. survival", "trust in Command", "resource rationing", "staying vs. leaving"]
        elif is_corp:
            place, authority = "The Company", "Executive leadership"
            topics = ["loyalty vs. ambition", "speed vs. caution", "old guard vs. new cohort", "transparency vs. secrecy"]
        else:  # school / generic
            place, authority = "The Campus", "the selection committee"
            topics = ["competition vs. cooperation", "merit vs. need", "individual vs. group", "honesty vs. advantage"]

        entities = [{"name": place, "kind": "place", "description": "the central setting"}]
        entities.append({"name": authority, "kind": "institution", "description": "holds decision power"})
        for n in nouns[:3]:
            entities.append({"name": n.capitalize(), "kind": "stake", "description": "a contested element of the premise"})

        relationships = [
            {"source": authority, "target": place, "relation": "governs"},
        ]
        if len(entities) > 2:
            relationships.append({"source": entities[2]["name"], "target": authority, "relation": "is decided by"})

        power_structures = [
            f"{authority} controls the central stake and outcomes.",
            f"Influence within {place} is informal and shifts through alliances.",
        ]

        # 3-6 topics
        topics = topics[:5]
        return json.dumps({
            "entities": entities,
            "relationships": relationships,
            "power_structures": power_structures,
            "topics": topics,
        })

    # ── perception narration ───────────────────────────────────────────────────
    if "PERCEPTION_NARRATION" in system:
        perceiver_name, actor_name, rel_type, raw_delta_str = "", "", "trust", "0.1"
        existing_rel = ""
        memories: list[str] = []
        _section = ""
        for line in user.splitlines():
            stripped = line.strip()
            if stripped == "YOUR CHARACTER":
                _section = "char"
            elif stripped == "INCOMING EVENT":
                _section = "event"
            elif stripped.startswith("YOUR EXISTING RELATIONSHIP WITH"):
                _section = "rel"
            elif stripped == "YOUR MEMORIES MOST RELEVANT TO THIS PERSON":
                _section = "mems"
            elif _section == "char" and line.startswith("Name: "):
                perceiver_name = line[6:].strip()
            elif _section == "event" and line.startswith("Acting character: "):
                actor_name = line[18:].split("(")[0].strip()
            elif _section == "event" and line.startswith("Raw social signal"):
                parts_sig = line.split("magnitude")
                if len(parts_sig) > 1:
                    raw_delta_str = parts_sig[1].split("—")[0].strip().rstrip(",")
                if "negative" in line:
                    raw_delta_str = f"-{raw_delta_str}"
                if "relationship type:" in line:
                    rel_type = line.split("relationship type:")[-1].strip()
            elif _section == "rel" and stripped and not stripped.startswith("("):
                existing_rel = stripped
            elif _section == "mems" and stripped.startswith("- "):
                memories.append(stripped[2:])

        try:
            base = float(raw_delta_str)
        except ValueError:
            base = 0.1

        # Generate a contextually varied perceived_delta from the mock rng
        perceived = round(base * rng.uniform(0.3, 1.2), 3)
        perceived = max(-1.0, min(1.0, perceived))

        has_conflict = any(w in existing_rel for w in ("conflict", "rivalry"))
        has_trust = any(w in existing_rel for w in ("trust", "friendship", "alliance"))
        if has_conflict and base > 0:
            perceived = round(base * rng.uniform(0.1, 0.4), 3)
        elif has_trust and base > 0:
            perceived = round(base * rng.uniform(0.8, 1.15), 3)
        perceived = round(max(-1.0, min(1.0, perceived)), 3)

        actor_first = actor_name.split("-")[0] if actor_name else "them"
        perceiver_first = perceiver_name.split("-")[0] if perceiver_name else "they"

        if has_conflict and base > 0:
            narratives = [
                f"{perceiver_first} acknowledged {actor_first}'s gesture with guarded eyes — the history between them made warmth feel like a gamble.",
                f"The overture landed with less weight than intended; {perceiver_first} had learned not to read too much into {actor_first}'s moments of goodwill.",
                f"{perceiver_first} noticed the shift in {actor_first}'s tone but held back — old wounds don't close overnight.",
            ]
            trait = "slow to forgive"
        elif has_trust and base > 0:
            narratives = [
                f"{perceiver_first} felt {actor_first}'s gesture land more deeply than the moment might have warranted — trust amplifies everything.",
                f"Because the foundation was solid, {perceiver_first} let {actor_first}'s move in without questioning the motive.",
                f"{perceiver_first} received it warmly; with {actor_first}, there was nothing to second-guess.",
            ]
            trait = None
        elif base < 0:
            narratives = [
                f"{perceiver_first} absorbed the friction quietly, filing it away without drama — confrontation wasn't worth it yet.",
                f"The negative signal registered, but {perceiver_first} held their reaction close rather than showing it.",
                f"{perceiver_first} felt the sting of {actor_first}'s move but chose not to react — at least not visibly.",
            ]
            trait = "internalizes conflict"
        else:
            narratives = [
                f"{perceiver_first} processed {actor_first}'s action through the lens of their own uncertainty, unsure what to make of it.",
                f"The signal was clear enough, but {perceiver_first} hadn't yet decided what it meant for them.",
            ]
            trait = None

        return json.dumps({
            "perceived_delta": perceived,
            "narrative": rng.choice(narratives),
            "revealed_trait": trait,
        })

    # ── reflection synthesis ───────────────────────────────────────────────────
    if "REFLECTION_SYNTHESIS" in system:
        agent_name = ""
        agent_traits: list[str] = []
        agent_goals: list[str] = []
        rel_names: list[str] = []
        recent_mems: list[str] = []
        section = ""
        for line in user.splitlines():
            stripped = line.strip()
            if stripped == "YOUR RELATIONSHIPS":
                section = "rels"
            elif stripped == "YOUR RECENT MEMORIES":
                section = "mems"
            elif stripped in ("YOUR CHARACTER", ""):
                if stripped == "YOUR CHARACTER":
                    section = "char"
            elif line.startswith("Name: "):
                agent_name = line[6:].strip()
            elif line.startswith("Traits: "):
                agent_traits = [t.strip() for t in line[8:].split(",") if t.strip() and t.strip() != "(none)"]
            elif line.startswith("Goals: "):
                agent_goals = [g.strip() for g in line[7:].split(",") if g.strip() and g.strip() != "(none)"]
            elif section == "rels" and stripped.startswith("- "):
                nm = stripped[2:].split(":", 1)[0].strip()
                if nm:
                    rel_names.append(nm)
            elif section == "mems" and stripped.startswith("- "):
                recent_mems.append(stripped[2:].strip())

        # Detect the dominant theme of the recent memories to ground the insight.
        joined = " ".join(recent_mems).lower()
        person = rel_names[0] if rel_names else None
        goal = agent_goals[0] if agent_goals else "find my place here"

        insight_pool: list[str] = []
        if any(w in joined for w in ("conflict", "fight", "fought", "confront", "tension", "argument", "rival")):
            insight_pool.append(
                "I keep ending up in conflict, and I'm starting to think I provoke it more than I admit."
            )
            insight_pool.append("When something matters to me, I'd rather avoid confrontation than risk losing it.")
        if any(w in joined for w in ("trust", "friend", "alliance", "steady", "confide")):
            insight_pool.append("The people who stay steady with me are the ones I should be investing in.")
        if any(w in joined for w in ("alone", "lonely", "distance", "pull away", "withdraw")):
            insight_pool.append("I pull away when I'm scared of being close, and it leaves me lonelier than before.")
        if any(w in joined for w in ("win", "won", "lost", "lose", "compete", "ambition", "prove")):
            insight_pool.append("My need to come out ahead is shaping every relationship I have here.")
        if person:
            insight_pool.append(f"My history with {person} is changing who I'm becoming, whether I like it or not.")
        # Always have at least one grounded fallback.
        insight_pool.append(f"What I really want is to {goal}, and my recent choices haven't all served that.")

        # Deterministically pick 1-3 distinct insights for this agent/memory set.
        k = 1 + (seed % 3)
        chosen: list[str] = []
        for ins in insight_pool:
            if ins not in chosen:
                chosen.append(ins)
            if len(chosen) >= k:
                break

        return json.dumps({"insights": chosen})

    # ── theatrical vignette (Slice E) ──────────────────────────────────────────
    if "VIGNETTE_GENERATION" in system:
        agent_name = ""
        agent_mood = ""
        world_event = ""
        section = ""
        for line in user.splitlines():
            stripped = line.strip()
            if stripped == "YOUR CHARACTER":
                section = "char"
            elif stripped == "CURRENT WORLD EVENT":
                section = "event"
            elif section == "char" and line.startswith("Name: "):
                agent_name = line[6:].strip()
            elif section == "char" and line.startswith("Mood: "):
                agent_mood = line[6:].strip()
            elif section == "event" and stripped and not stripped.startswith("("):
                world_event = stripped

        world_event = _clean_mock_event(world_event)
        first = agent_name.split()[0] if agent_name else "Someone"
        evt = world_event.rstrip(".").lower() if world_event else "everything"
        pools = {
            "dream": [
                f"I dreamt I was the only one left in the room, and somehow that felt like winning.",
                f"Last night I dreamt about {evt} again — I woke up certain it had already happened.",
                f"In my dream everyone finally listened to me. Then I woke up. Typical.",
            ],
            "catchphrase": [
                f"As I always say: hesitation is just defeat wearing a polite smile.",
                f"You know my motto — never blink first.",
                f"If it's not on fire, I'm not interested.",
            ],
            "announcement": [
                f"I, {first}, hereby declare that {evt} will not break me. Watch.",
                f"Attention everyone: the era of underestimating me ends today.",
                f"Mark my words — by the end of this, you'll all remember my name.",
            ],
        }
        # Mood loosely picks the kind, then deterministic rng picks the line.
        if agent_mood in ("anxious", "heartbroken", "lonely", "calm", "content"):
            kind = "dream"
        elif agent_mood in ("confident", "ambitious", "angry"):
            kind = "announcement"
        else:
            kind = rng.choice(["dream", "catchphrase", "announcement"])
        text = rng.choice(pools[kind])
        return json.dumps({"kind": kind, "text": text})

    # ── prophecy grading (Slice E) ─────────────────────────────────────────────
    if "PROPHECY_GRADING" in system:
        prediction = ""
        report_text = ""
        section = ""
        for line in user.splitlines():
            stripped = line.strip()
            if stripped == "PLAYER PREDICTION":
                section = "pred"
            elif stripped == "FINAL NARRATIVE REPORT":
                section = "report"
            elif stripped.startswith("FINAL BELIEF MEANS"):
                section = ""
            elif section == "pred" and stripped:
                prediction = stripped
                section = ""
            elif section == "report" and stripped:
                report_text += " " + stripped

        pred_l = prediction.lower()
        report_l = report_text.lower()
        # Deterministic verdict: token overlap between prediction and outcome report.
        pred_tokens = {w for w in _re_module.findall(r"[a-z]{4,}", pred_l)}
        report_tokens = {w for w in _re_module.findall(r"[a-z]{4,}", report_l)}
        overlap = len(pred_tokens & report_tokens)
        conflict_signal = any(w in pred_l for w in ("conflict", "fight", "war", "rival", "break", "split"))
        report_conflict = any(w in report_l for w in ("rivalr", "conflict", "fracture", "fought", "tension"))

        if not report_text:
            verdict, confidence = "unresolved", 0.3
        elif conflict_signal and report_conflict:
            verdict, confidence = "correct", 0.78
        elif overlap >= 3:
            verdict, confidence = "partly", 0.6
        elif conflict_signal and not report_conflict:
            verdict, confidence = "incorrect", 0.55
        else:
            verdict, confidence = "partly", 0.5

        explanation = (
            f"Judged against the run's outcome, the prediction ('{prediction[:80]}') is rated "
            f"{verdict}: the final report's dynamics show {'matching' if verdict == 'correct' else 'partial-to-divergent'} "
            f"alignment with what was foreseen. (Mock grading — set a real LLM_PROVIDER for nuanced judgment.)"
        )
        return json.dumps({
            "verdict": verdict,
            "confidence": confidence,
            "explanation": explanation,
        })

    # ── goal-driven plan formation (Slice D ④) ─────────────────────────────────
    if "PLAN_FORMATION" in system:
        agent_name = ""
        agent_goals: list[str] = []
        agent_mood = ""
        world_event = ""
        recent_mems: list[str] = []
        section = ""
        for line in user.splitlines():
            stripped = line.strip()
            if stripped == "YOUR CHARACTER":
                section = "char"
            elif stripped == "YOUR RECENT MEMORIES":
                section = "mems"
            elif stripped == "CURRENT WORLD EVENT":
                section = "event"
            elif section == "char" and line.startswith("Name: "):
                agent_name = line[6:].strip()
            elif section == "char" and line.startswith("Goals: "):
                agent_goals = [g.strip() for g in line[7:].split(",") if g.strip() and g.strip() != "(none)"]
            elif section == "char" and line.startswith("Mood: "):
                agent_mood = line[6:].strip()
            elif section == "mems" and stripped.startswith("- "):
                recent_mems.append(stripped[2:].strip())
            elif section == "event" and stripped and not stripped.startswith("("):
                world_event = stripped

        world_event = _clean_mock_event(world_event)
        goal = agent_goals[0] if agent_goals else "find my footing here"
        # Pull a name mentioned in recent memories to make the plan concrete & relational.
        ref_name = None
        agent_first = agent_name.split()[0] if agent_name else ""
        for mem in reversed(recent_mems):
            for cand in _re_plan.findall(mem):
                if cand and cand not in _PLAN_NAME_STOP and cand not in (agent_name, agent_first):
                    ref_name = cand
                    break
            if ref_name:
                break

        _MOOD_VERB = {
            "ambitious": "make a decisive move to",
            "confident": "press my advantage and",
            "frustrated": "stop holding back and",
            "angry": "confront what's in my way so I can",
            "anxious": "carefully line things up so I can",
            "hopeful": "take the first real step to",
            "lonely": "reach out to someone so I can",
            "calm": "steadily work to",
            "content": "build on what's working to",
            "excited": "seize the moment to",
            "heartbroken": "find a way to refocus and",
        }
        verb = _MOOD_VERB.get(agent_mood, "find a way to")
        if ref_name and world_event:
            plan = f"I want to {verb} {goal}, starting by getting {ref_name} on my side about the {world_event.rstrip('.').lower()}."
        elif ref_name:
            plan = f"I want to {verb} {goal}, and dealing with {ref_name} is my next step."
        elif world_event:
            plan = f"I want to {verb} {goal} by responding to the {world_event.rstrip('.').lower()} before anyone else does."
        else:
            plan = f"I want to {verb} {goal} with a concrete step this week."
        return json.dumps({"plan": plan})

    # ── agent daily reasoning ──────────────────────────────────────────────────
    if "AGENT_REASONING" in system:
        lines = user.splitlines()
        agent_name = ""
        agent_role = ""
        agent_traits: list[str] = []
        agent_mood = ""
        agent_goals: list[str] = []
        relationships: dict[str, str] = {}
        world_event = ""
        world_topics: list[str] = []
        agent_plan = ""
        section = ""

        for line in lines:
            stripped = line.strip()
            if stripped == "YOUR CURRENT PLAN":
                section = "PLAN"
                continue
            if section == "PLAN" and stripped and stripped != "YOUR SHORT-TERM MEMORY (today so far)":
                agent_plan = stripped
                section = ""
                continue
            if stripped.startswith("WORLD TOPICS"):
                section = "WORLD TOPICS"
                continue
            if section == "WORLD TOPICS" and stripped.startswith("- "):
                # Format: "- topic name (your current stance: +0.12)"
                topic = stripped[2:].split(" (your current stance")[0].strip()
                if topic and topic != "(none)":
                    world_topics.append(topic)
                continue
            if line.startswith("Name: "):
                agent_name = line[6:].strip()
            elif line.startswith("Role: "):
                agent_role = line[6:].strip()
            elif line.startswith("Traits: "):
                agent_traits = [t.strip() for t in line[8:].split(",") if t.strip() and t.strip() != "(none)"]
            elif line.startswith("Mood: "):
                agent_mood = line[6:].strip()
            elif line.startswith("Goals: "):
                agent_goals = [g.strip() for g in line[7:].split(",") if g.strip() and g.strip() != "(none)"]
            elif stripped in ("YOUR RELATIONSHIPS", "CURRENT WORLD EVENT", "OTHER AGENTS IN THE WORLD",
                              "YOUR SHORT-TERM MEMORY (today so far)", "YOUR LONG-TERM MEMORY",
                              "RECENT WORLD LOG (last few entries)"):
                section = stripped
            elif stripped.startswith("YOUR FEED"):
                # New ranked-feed section header (Phase 2 #4) — switch section so its
                # entry lines don't get mis-captured as the world event.
                section = "YOUR FEED"
            elif section == "YOUR RELATIONSHIPS" and stripped.startswith("- "):
                parts = stripped[2:].split(":")
                if parts:
                    rel_name = parts[0].strip()
                    rel_desc = parts[1].strip() if len(parts) > 1 else ""
                    relationships[rel_name] = rel_desc
            elif section == "CURRENT WORLD EVENT" and stripped and not stripped.startswith("("):
                world_event = stripped

        # Candidate targets from roster lines
        candidates: list[str] = []
        in_roster = False
        for line in lines:
            if line.strip() == "OTHER AGENTS IN THE WORLD":
                in_roster = True
                continue
            if in_roster and line.startswith("- ") and ":" in line:
                name = line[2:].split(":", 1)[0].strip()
                if name and name[0].isupper() and name != agent_name:
                    candidates.append(name)
        # Also add anyone already in relationships
        for name in relationships:
            if name not in candidates and name != agent_name:
                candidates.append(name)

        # PLAN BIAS (Slice D ④): if the agent's current plan names someone on the
        # roster, prefer them as today's target so the action advances the plan.
        plan_target = None
        if agent_plan:
            for cand in candidates:
                first = cand.split()[0] if cand else cand
                if first and first in agent_plan:
                    plan_target = cand
                    break
        if plan_target is not None:
            target = plan_target
        else:
            target = rng.choice(candidates) if candidates else "a fellow student"

        # Pick action: trait-driven first, mood-driven fallback
        action_pool: list[tuple] = []
        for trait in agent_traits:
            if trait in _TRAIT_ACTIONS:
                action_pool.extend(_TRAIT_ACTIONS[trait])
        if not action_pool and agent_mood in _MOOD_ACTIONS:
            action_pool = [_MOOD_ACTIONS[agent_mood]]
        if not action_pool:
            action_pool = [
                ("check in on", "friendship", 0.1, "calm",
                 "Nothing dramatic — just a quiet check-in that meant more than expected."),
                ("spend some time with", "friendship", 0.15, "content",
                 "The day passed simply but the connection deepened."),
                ("have an honest conversation with", "trust", 0.2, "hopeful",
                 "They decided honesty was better than comfortable silence."),
            ]

        action_verb, rtype, base_delta, new_mood, explanation = rng.choice(action_pool)
        delta = round(base_delta + rng.uniform(-0.05, 0.05), 2)

        # Build a contextual narrative memory sentence
        goal = agent_goals[0] if agent_goals else "find my place here"
        _evt = world_event.strip().rstrip(".")
        # Strip leading article so "The event" doesn't become "The the event"
        for _art in ("A ", "An ", "The "):
            if _evt.startswith(_art):
                _evt = _evt[len(_art):]
                break
        event_clause = f" The {_evt.lower()} made everything feel more charged." if _evt else ""

        rel_desc = relationships.get(target, "")
        if "romance" in rel_desc:
            memory_opts = [
                f"I told {target} something I hadn't said out loud before. It felt fragile and true.{event_clause}",
                f"The tension between me and {target} broke today — in the best way.{event_clause}",
                f"I chose to {action_verb} {target}, and for a moment everything else fell away.{event_clause}",
            ]
        elif any(w in rel_desc for w in ("rival", "conflict")):
            memory_opts = [
                f"Things came to a head with {target}. I said what I'd been holding back.{event_clause}",
                f"I tried to {action_verb} {target}. It didn't go smoothly, but it was honest.{event_clause}",
                f"The friction between me and {target} reached a breaking point today.{event_clause}",
            ]
        elif "trust" in rel_desc or "friend" in rel_desc or "alliance" in rel_desc:
            memory_opts = [
                f"I made a point of {action_verb.rstrip('with').strip()} {target} today — they've been steady with me and I wanted to return that.{event_clause}",
                f"Me and {target} had a real conversation. The kind that actually changes something.{event_clause}",
                f"I spent time with {target} and it reminded me why I trust them.{event_clause}",
            ]
        else:
            memory_opts = [
                f"I decided to {action_verb} {target} today. My goal to {goal} doesn't happen on its own.{event_clause}",
                f"Something shifted between me and {target} — I {action_verb.split()[0]}ed them and it changed the dynamic.{event_clause}",
                f"Today I chose to {action_verb} {target}. {explanation.split('.')[0]}.{event_clause}",
            ]

        new_memory = rng.choice(memory_opts)

        # Occasionally shift stance on one of the world topics the agent engaged with.
        stance_shift: dict[str, float] = {}
        if world_topics and rng.random() < 0.6:
            topic = rng.choice(world_topics)
            # Direction loosely tracks the action's valence (positive vs. conflictual).
            mag = round(rng.uniform(0.05, 0.25), 3)
            if rtype in ("conflict", "rivalry") or base_delta < 0:
                mag = -mag
            stance_shift[topic] = mag

        # Real action space (Phase 2 #5): deterministically pick a kind so verification
        # sees variety. Conflictual moves skew private/comment; warm/ambitious moves skew
        # public/amplify; the rest default to interact. Pure logic, no extra LLM call.
        _kind_roll = rng.random()
        if rtype in ("conflict", "rivalry") or base_delta < 0:
            action_kind = "direct" if _kind_roll < 0.5 else "comment"
        elif rtype in ("alliance", "influence") or new_mood in ("confident", "ambitious"):
            action_kind = "post" if _kind_roll < 0.4 else ("amplify" if _kind_roll < 0.7 else "interact")
        else:
            action_kind = "interact" if _kind_roll < 0.6 else ("comment" if _kind_roll < 0.85 else "post")

        return json.dumps({
            "action": action_verb,
            "action_kind": action_kind,
            "target_agents": [target],
            "emotional_reaction": new_mood,
            "relationship_effects": {
                target: {"type": rtype, "strength_delta": delta}
            },
            "influence_effects": {
                "self": round(rng.uniform(-1, 3), 1),
                target: round(rng.uniform(-1, 1), 1),
            },
            "stance_shift": stance_shift,
            "new_memory": new_memory,
            "explanation": explanation,
        })

    # ── final report ───────────────────────────────────────────────────────────
    if "FINAL_REPORT" in system:
        return (
            "Over the simulated period, the society fractured and reformed along unexpected lines. "
            "Several rivalries crystallized from minor friction, a handful of romances formed between "
            "people who started as strangers, and the most isolated agents either drifted further from "
            "the group or — against the odds — seized the social vacuum to claim real influence. "
            "(Mock report — set LLM_PROVIDER=anthropic or openai_compat for real narration.)"
        )

    # ── agent chat (in-character roleplay) ────────────────────────────────────
    # Parse every field from the structured prompt
    import re as _re

    name, role, mood, goals_str, traits_str, groups_str = "", "", "", "", "", ""
    chat_rels: dict[str, dict] = {}   # name -> {type, strength}
    chat_mems: list[str] = []
    world_event_chat = ""
    user_message = ""
    _section = ""

    for line in user.splitlines():
        stripped = line.strip()
        if stripped == "CHARACTER PROFILE":
            _section = "profile"
        elif stripped == "RELATIONSHIPS":
            _section = "rels"
        elif stripped == "MEMORIES":
            _section = "mems"
        elif stripped == "WORLD EVENT":
            _section = "event"
        elif stripped == "USER MESSAGE":
            _section = "msg"
        elif _section == "profile":
            if line.startswith("Name: "):
                name = line[6:].strip()
            elif line.startswith("Role: "):
                role = line[6:].strip()
            elif line.startswith("Current mood: "):
                mood = line[14:].strip()
            elif line.startswith("Goals: "):
                goals_str = line[7:].strip()
            elif line.startswith("Traits: "):
                traits_str = line[8:].strip()
            elif line.startswith("Groups: "):
                groups_str = line[8:].strip()
        elif _section == "rels" and stripped.startswith("- "):
            # Format: "  - Sage: friendship (strength +0.45)"
            m = _re.match(r"-\s+(.+?):\s+(\w+)\s+\(strength ([+-]?\d+\.?\d*)\)", stripped)
            if m:
                chat_rels[m.group(1).strip()] = {
                    "type": m.group(2),
                    "strength": float(m.group(3)),
                }
        elif _section == "mems" and stripped.startswith("- "):
            chat_mems.append(stripped[2:].strip())
        elif _section == "event" and stripped and not stripped.startswith("("):
            world_event_chat = stripped
        elif _section == "msg":
            user_message += line + "\n"

    user_message = user_message.strip()
    q = user_message.lower()

    traits = [t.strip() for t in traits_str.split(",") if t.strip() and t.strip() != "none"]
    goals = [g.strip() for g in goals_str.split(",") if g.strip() and g.strip() != "none"]

    # ── Intent: asking about a specific person ─────────────────────────────────
    mentioned = None
    for rel_name in chat_rels:
        if rel_name.lower() in q:
            mentioned = rel_name
            break

    if mentioned:
        rel = chat_rels[mentioned]
        rtype = rel["type"]
        strength = rel["strength"]
        abs_s = abs(strength)
        intensity = "deeply" if abs_s > 0.7 else ("genuinely" if abs_s > 0.4 else "somewhat")

        _REL_RESPONSES: dict[str, list[str]] = {
            "friendship": [
                f"{mentioned} and I just clicked. I can't always explain it — there's a trust there that built up over time. I value that.",
                f"We've been through enough together that the friendship feels real. Not just surface level.",
                f"I like {mentioned}. They're consistent. That matters more to me than most people realize.",
            ],
            "romance": [
                f"That's... a complicated thing to talk about. {mentioned} means something to me. More than I usually let on.",
                f"There's something between me and {mentioned} that I haven't figured out how to name yet. But I feel it.",
                f"I care about {mentioned} in a way that's different from everyone else. I'm still working out what to do with that.",
            ],
            "rivalry": [
                f"{mentioned} and I see the world differently. Fundamentally differently. And neither of us is backing down.",
                f"I don't hate {mentioned}. I just think we want the same things and only one of us can have them.",
                f"It's competitive. It's been competitive for a while. {mentioned} pushes me, and I can't decide if I resent that or need it.",
            ],
            "conflict": [
                f"Things between me and {mentioned} have been rough. Something happened that I haven't fully let go of.",
                f"I'm trying not to make it worse, but {mentioned} and I are not in a good place right now.",
                f"There's real tension there. I know it, they know it. Neither of us has fixed it yet.",
            ],
            "trust": [
                f"I trust {mentioned}. That's not something I say lightly.",
                f"There's a reason I confide in {mentioned} when I wouldn't with others. They've earned that.",
                f"{mentioned} has never given me a reason to doubt them. That means a lot in a place like this.",
            ],
            "alliance": [
                f"{mentioned} and I are aligned on what we're trying to accomplish. It makes sense to work together.",
                f"We're on the same side. For now, at least. And that's been useful for both of us.",
                f"It's strategic, but it's also real. I respect what {mentioned} brings to the table.",
            ],
            "influence": [
                f"{mentioned} has shifted how I think about things. I'm not always sure that's comfortable to admit.",
                f"There's an influence there — whether it's me on them or them on me, I'm honestly not sure anymore.",
                f"I've started noticing how often {mentioned}'s perspective finds its way into my thinking.",
            ],
            "group_membership": [
                f"We're in the same world, {mentioned} and me. That creates a kind of connection whether you plan for it or not.",
                f"The shared context with {mentioned} means we understand things about each other's situation that outsiders don't.",
                f"Being in the same group gives us common ground. What we do with that is another question.",
            ],
        }

        responses = _REL_RESPONSES.get(rtype, [
            f"My relationship with {mentioned} is... complicated. I don't think I can sum it up easily.",
        ])

        # Check if the question is specifically "why"
        if "why" in q:
            _WHY: dict[str, list[str]] = {
                "friendship": [
                    f"{mentioned} showed up when it counted. That's really the whole reason.",
                    f"Some friendships just happen. Ours did. I stopped questioning it.",
                    f"We have shared history and I trust them. That's the short version.",
                ],
                "romance": [
                    f"Because they see something in me that most people miss. And I see it in them too.",
                    f"I tried not to feel this way. It didn't work.",
                    f"There's no clean answer to that. But I keep coming back to them.",
                ],
                "rivalry": [
                    f"Because we want the same things and we're both unwilling to step aside.",
                    f"It started small — a disagreement, then another. Now it's just what we are.",
                    f"Honestly? {mentioned} is good. And I hate that I have to compete with someone that good.",
                ],
                "conflict": [
                    f"Something happened between us that didn't get resolved. And it's been sitting there since.",
                    f"I said something, or they said something — I'm not even sure anymore who started it. But here we are.",
                    f"We just don't see eye to eye on things that matter. That has a way of creating friction.",
                ],
                "trust": [
                    f"They've never given me a reason not to. That's actually pretty rare.",
                    f"Because I tested it — not deliberately, but I did — and they didn't let me down.",
                    f"Trust builds slowly with me. But with {mentioned}, it built.",
                ],
            }
            responses = _WHY.get(rtype, responses)

        return f"{rng.choice(responses)} [{intensity} {rtype}, strength {strength:+.2f}]"

    # ── Intent: asking about all relationships / social life ──────────────────
    if any(w in q for w in ("relationship", "friend", "people", "social", "who do you know", "connections", "know here")):
        if chat_rels:
            closest = max(chat_rels.items(), key=lambda x: abs(x[1]["strength"]))
            cname, crel = closest
            return (
                f"I've got a few connections here. The one that stands out most right now is {cname} — "
                f"we have a {crel['type']} that's been pretty significant. "
                f"Whether that's good or complicated depends on the day."
            )
        return "I haven't built many connections yet. I'm still figuring out who in this place I actually trust."

    # ── Intent: asking about traits / identity ────────────────────────────────
    # Use word boundary check so "who are your friends" doesn't hit "who are you"
    _intro_triggers = ("trait", "personality", "like you", "describe yourself", "tell me about yourself")
    _who_are_you = q.rstrip("?").strip() in ("who are you", "who r you", "what are you like", "what are you")
    if _who_are_you or any(w in q for w in _intro_triggers):
        trait_str = ", ".join(traits[:3]) if traits else "hard to pin down"
        goal = goals[0] if goals else "find my place"
        return (
            f"I'm a {role or 'person'} — {trait_str}. "
            f"Right now I'm feeling {mood}. "
            f"What drives me most is trying to {goal}. "
            f"That probably explains most of what you see from me."
        )

    # ── Intent: asking about memories / what happened ─────────────────────────
    if any(w in q for w in ("remember", "memory", "happened", "what did you do", "tell me what", "lately", "recently")):
        if chat_mems:
            mem = chat_mems[-1]
            return f"The thing that's most on my mind right now: {mem}"
        return "Honestly, the days have been blurring together lately. Nothing I can point to clearly."

    # ── Intent: asking about the world event ──────────────────────────────────
    if any(w in q for w in ("event", "happening", "going on", "situation", "what's")):
        if world_event_chat:
            return f"You mean {world_event_chat.lower().rstrip('.')}? Yeah. That's been affecting everyone here, including me."
        return "Things are relatively quiet right now. Which, honestly, I don't fully trust."

    # ── Intent: asking about goals ────────────────────────────────────────────
    if any(w in q for w in ("goal", "want", "trying to", "ambition", "plan")):
        goal = goals[0] if goals else "figure things out"
        return f"What I'm working toward? Trying to {goal}. That's what gets me up in the morning."

    # ── Fallback: contextual response built from character's actual data ──────
    # For very short/unclear messages, ask for clarification in-character
    if len(q.split()) <= 2:
        clarify_opts = [
            f"I'm not sure what you're asking. Can you be more specific?",
            f"What do you mean exactly? I don't want to assume.",
            f"Say more — I don't know what you're getting at.",
            f"You'll have to give me more than that.",
        ]
        return rng.choice(clarify_opts)

    # Build a situational response from real character data
    parts: list[str] = []
    if mood:
        _MOOD_OPENER = {
            "frustrated": "Things haven't been easy lately.",
            "excited": "There's a lot going on and I'm trying to keep up.",
            "lonely": "It's been a quieter stretch than I'd like.",
            "ambitious": "I've been focused — head down, working toward something.",
            "heartbroken": "I'm dealing with some things. It's been heavy.",
            "confident": "Things are actually going well right now.",
            "anxious": "There's a lot on my mind that I haven't sorted out yet.",
            "hopeful": "I'm in a decent place, honestly. Cautiously.",
            "angry": "I'm not going to pretend I'm fine with how some things have gone.",
            "calm": "I'm steady. Not much to complain about.",
            "content": "Things feel settled, which is rare for me.",
        }
        parts.append(_MOOD_OPENER.get(mood, f"I'm feeling {mood} right now."))

    if chat_rels:
        strongest = max(chat_rels.items(), key=lambda x: abs(x[1]["strength"]))
        sname, srel = strongest
        _REL_SNIPPET = {
            "friendship": f"My friendship with {sname} has been one of the more grounding things lately.",
            "romance": f"There's something between me and {sname} that's been taking up more of my thinking than I expected.",
            "rivalry": f"The tension with {sname} hasn't gone away. If anything it's sharpened.",
            "conflict": f"Things with {sname} are unresolved. That's weighing on me.",
            "trust": f"I've been leaning on {sname} more than usual — they've been solid.",
            "alliance": f"{sname} and I have been moving in the same direction lately. That helps.",
            "influence": f"{sname} has been on my mind. They've shifted how I'm thinking about a few things.",
            "group_membership": f"Being connected to {sname} through our shared world has made things interesting.",
        }
        parts.append(_REL_SNIPPET.get(srel["type"], f"My situation with {sname} has been significant lately."))

    if chat_mems:
        parts.append(f"The last thing that really stuck with me: {chat_mems[-1]}")

    if parts:
        return " ".join(parts)

    return f"Honestly, I'm not sure how to answer that. Ask me something more specific."
