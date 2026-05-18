from __future__ import annotations

from models import DaySnapshot, MacroMetrics
from llm import call_llm

REPORT_SYSTEM = """FINAL_REPORT
You are a social-dynamics analyst writing a concise narrative report on a multi-agent simulation.
You will be given before/after macro metrics and the day-by-day highlights.
Write a 4-6 paragraph summary in plain prose covering:
- how the injected event reshaped the society
- which agents gained or lost influence and why
- which factions, romances, rivalries, or alliances formed
- any surprising emergent dynamics
- the final social shape compared to Day 0

Do not invent agent names that weren't in the data. Keep tone analytical, not gamey.
"""


def generate_final_report(
    initial: MacroMetrics,
    final: MacroMetrics,
    snapshots: list[DaySnapshot],
    world_prompt: str,
    starting_event: str | None,
) -> str:
    highlights_blob = []
    for s in snapshots:
        if not s.highlights:
            continue
        line = f"Day {s.day}: " + "; ".join(
            f"{h.agent}: {h.summary}" for h in s.highlights[:4]
        )
        highlights_blob.append(line)

    user = (
        f"WORLD: {world_prompt}\n\n"
        f"STARTING EVENT: {starting_event or '(none)'}\n\n"
        f"INITIAL METRICS (Day 0):\n{initial.model_dump_json(indent=2)}\n\n"
        f"FINAL METRICS (Day {snapshots[-1].day if snapshots else 0}):\n"
        f"{final.model_dump_json(indent=2)}\n\n"
        f"DAILY HIGHLIGHTS:\n" + "\n".join(highlights_blob[:30])
    )
    try:
        return call_llm(REPORT_SYSTEM, user, max_tokens=1500)
    except Exception as e:
        return f"(Report generation failed: {e})"
