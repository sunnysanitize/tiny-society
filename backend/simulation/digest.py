from __future__ import annotations

from models import DaySnapshot

# How many punchy cards a daily digest surfaces.
MAX_DIGEST_CARDS = 5


def build_digest(snapshot: DaySnapshot) -> list[str]:
    """Return 3-5 punchy one-line "what happened" cards for a day, combining the
    most notable highlights and vignettes. Pure logic — no LLM call.

    Vignettes (theatrical moments) lead because they're the charming hook; the most
    substantial highlights fill the rest. Each line is trimmed to a single sentence-ish
    snippet so the frontend can render them as digest cards directly.
    """
    cards: list[str] = []

    for v in snapshot.vignettes:
        cards.append(f"{v.agent}: {_one_line(v.text)}")

    # Highlights sorted by how "substantial" the summary looks (longer = more detail).
    highlights = sorted(snapshot.highlights, key=lambda h: len(h.summary), reverse=True)
    for h in highlights:
        if len(cards) >= MAX_DIGEST_CARDS:
            break
        cards.append(f"{h.agent}: {_one_line(h.summary)}")

    # Fall back to raw event-log lines if there were no highlights/vignettes at all.
    if not cards:
        for line in snapshot.event_log[:MAX_DIGEST_CARDS]:
            cards.append(_one_line(line))

    return cards[:MAX_DIGEST_CARDS]


def _one_line(text: str) -> str:
    """Collapse to a single punchy sentence, capped in length."""
    text = (text or "").strip().replace("\n", " ")
    # Keep up to the first sentence terminator for punchiness.
    for sep in (". ", "! ", "? "):
        idx = text.find(sep)
        if 0 < idx < 140:
            return text[: idx + 1].strip()
    return text[:140].strip()
