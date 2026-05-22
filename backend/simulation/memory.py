from __future__ import annotations

import math
import re
from typing import Iterable

from models import Memory

# ── Retrieval weights (Stanford "Generative Agents" style) ───────────────────────
# Combined score = RELEVANCE_WEIGHT*relevance + RECENCY_WEIGHT*recency + IMPORTANCE_WEIGHT*importance
# All three components are normalized to [0, 1] before weighting.
RELEVANCE_WEIGHT = 1.0
RECENCY_WEIGHT = 1.0
IMPORTANCE_WEIGHT = 1.0

# Recency decays exponentially with the number of sim days since the memory was
# last accessed. 0.85 ≈ a memory loses ~15% of its recency weight per day.
RECENCY_DECAY = 0.85

# Importance heuristic: keywords that signal an emotionally or relationally loaded
# memory worth recalling. Each hit nudges importance up.
_EMOTIONAL_KEYWORDS = {
    "love", "hate", "afraid", "fear", "betray", "betrayed", "trust", "trusted",
    "angry", "anger", "cried", "cry", "broke", "broken", "heartbroken", "lonely",
    "alone", "secret", "lied", "lie", "fight", "fought", "confront", "rival",
    "alliance", "friend", "friendship", "romance", "kiss", "promise", "regret",
    "guilt", "ashamed", "proud", "win", "won", "lost", "lose", "failed", "failure",
    "death", "died", "kill", "threat", "revenge", "forgive", "apolog", "exposed",
}

_WORD_RE = re.compile(r"[a-z']+")

# Common words ignored when measuring relevance overlap.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "at",
    "for", "with", "as", "is", "was", "were", "be", "been", "it", "its", "this",
    "that", "i", "me", "my", "we", "us", "our", "you", "your", "he", "she", "they",
    "them", "their", "him", "her", "his", "had", "have", "has", "did", "do", "not",
    "so", "than", "then", "from", "by", "about", "into", "out", "up", "down", "no",
}


def _tokenize(text: str) -> set[str]:
    return {
        w for w in _WORD_RE.findall((text or "").lower())
        if w not in _STOPWORDS and len(w) > 1
    }


def score_importance(text: str) -> float:
    """Cheap heuristic importance in [1, 10].

    Combines length (longer, more detailed memories tend to matter more) with the
    density of emotional / relational keywords. Works under the mock provider with
    no LLM call. This is the DEFAULT used everywhere a memory is created.
    """
    if not text:
        return 1.0
    lowered = text.lower()
    keyword_hits = sum(1 for kw in _EMOTIONAL_KEYWORDS if kw in lowered)
    # Length component: ~1 point per 60 chars, capped.
    length_score = min(len(text) / 60.0, 4.0)
    # Keyword component: up to 5 points.
    keyword_score = min(keyword_hits * 1.5, 5.0)
    raw = 1.0 + length_score + keyword_score
    return round(max(1.0, min(10.0, raw)), 2)


def make_memory(text: str, day: int) -> Memory:
    """Construct a Memory with heuristic importance, created on `day`."""
    return Memory(
        text=text,
        importance=score_importance(text),
        day=day,
        last_accessed_day=day,
    )


def _relevance(mem_tokens: set[str], query_tokens: set[str]) -> float:
    """Token-overlap relevance in [0, 1]: shared tokens / query tokens."""
    if not query_tokens or not mem_tokens:
        return 0.0
    overlap = len(mem_tokens & query_tokens)
    return overlap / len(query_tokens)


def _recency(memory: Memory, current_day: int) -> float:
    """Exponential decay on days since last access, in (0, 1]."""
    age = max(0, current_day - (memory.last_accessed_day or memory.day))
    return RECENCY_DECAY ** age


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return values
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [1.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def retrieve(
    memories: Iterable[Memory],
    query: str,
    current_day: int,
    k: int = 8,
) -> list[Memory]:
    """Return the top-k memories most worth recalling for `query` on `current_day`.

    Score = RELEVANCE_WEIGHT*relevance + RECENCY_WEIGHT*recency + IMPORTANCE_WEIGHT*importance,
    with each component min-max normalized across the candidate set. Retrieved
    memories have their `last_accessed_day` bumped to `current_day`.
    """
    mems = list(memories)
    if not mems or k <= 0:
        return []

    query_tokens = _tokenize(query)

    relevance = [_relevance(_tokenize(m.text), query_tokens) for m in mems]
    recency = [_recency(m, current_day) for m in mems]
    importance = [m.importance / 10.0 for m in mems]

    nr = _normalize(relevance)
    nrec = _normalize(recency)
    nimp = _normalize(importance)

    scored = [
        (
            RELEVANCE_WEIGHT * nr[i]
            + RECENCY_WEIGHT * nrec[i]
            + IMPORTANCE_WEIGHT * nimp[i],
            i,
        )
        for i in range(len(mems))
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    top = [mems[i] for _, i in scored[:k]]
    for m in top:
        if current_day > m.last_accessed_day:
            m.last_accessed_day = current_day
    return top
