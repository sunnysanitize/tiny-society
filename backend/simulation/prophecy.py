from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models import Forecast, MacroMetrics, ProphecyVerdict
from llm import call_llm

PROPHECY_SYSTEM = """PROPHECY_GRADING
You are an impartial judge grading a player's free-text PREDICTION about how a
multi-agent social simulation would turn out, against the ACTUAL OUTCOME (the final
narrative report, the population belief means/confidence, the pivotal days, and notable
day highlights).

Return STRICT JSON only — no prose, no markdown:
{
  "verdict": "correct" | "partly" | "incorrect" | "unresolved",
  "confidence": 0.0-1.0,
  "explanation": "2-3 sentences justifying the verdict against the actual outcome"
}

RULES:
- "correct": the prediction clearly matches what happened.
- "partly": some of it happened or it was directionally right but missed details.
- "incorrect": what happened contradicts the prediction.
- "unresolved": the outcome doesn't give enough to judge.
- Reference real outcome details in the explanation. Output only JSON.
"""


def grade_prophecy(
    prediction: str,
    final_metrics: MacroMetrics,
    forecast: Optional[Forecast],
    final_report: str,
    notable_highlights: Optional[list[str]] = None,
) -> Optional[ProphecyVerdict]:
    """Grade a player's free-text prediction with one LLM call. Returns a
    ProphecyVerdict, or a safe "unresolved" verdict if the LLM/parse fails."""
    prediction = (prediction or "").strip()
    if not prediction:
        return None

    user = _build_prompt(prediction, final_metrics, forecast, final_report, notable_highlights or [])
    try:
        raw = call_llm(PROPHECY_SYSTEM, user, json_mode=True, max_tokens=400, tier="strong")
    except Exception as e:
        logging.warning(f"Prophecy grading LLM call failed: {e}")
        return ProphecyVerdict(
            prediction=prediction,
            verdict="unresolved",
            confidence=0.0,
            explanation="Grading was unavailable for this run.",
        )

    data = _safe_json(raw)
    verdict = str(data.get("verdict", "unresolved")).strip().lower()
    if verdict not in ("correct", "partly", "incorrect", "unresolved"):
        verdict = "unresolved"
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    explanation = str(data.get("explanation", "")).strip()[:600]

    return ProphecyVerdict(
        prediction=prediction,
        verdict=verdict,
        confidence=confidence,
        explanation=explanation,
    )


def _build_prompt(
    prediction: str,
    final_metrics: MacroMetrics,
    forecast: Optional[Forecast],
    final_report: str,
    notable_highlights: list[str],
) -> str:
    parts = [
        "PLAYER PREDICTION",
        prediction,
        "",
        "FINAL NARRATIVE REPORT",
        final_report or "(none)",
        "",
        "FINAL BELIEF MEANS (per topic):",
        json.dumps(final_metrics.topic_means) if final_metrics.topic_means else "(none)",
        f"OVERALL CONFIDENCE (1=consensus, 0=split): {final_metrics.belief_confidence}",
    ]
    if forecast is not None:
        parts.append(f"FORECAST QUESTION: {forecast.question or '(none)'}")
        parts.append(f"PIVOTAL DAYS: {forecast.pivotal_days}")
    if notable_highlights:
        parts.append("")
        parts.append("NOTABLE HIGHLIGHTS:")
        parts.extend(f"- {h}" for h in notable_highlights[:10])
    parts.append("")
    parts.append("Grade the prediction and return your verdict as JSON now.")
    return "\n".join(parts)


def _safe_json(raw: str) -> dict:
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw).strip()
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}
