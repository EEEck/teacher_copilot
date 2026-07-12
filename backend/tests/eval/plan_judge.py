"""Optional LLM-as-judge for lesson-plan quality (opt-in only).

Enable with RUN_LLM_PLAN_JUDGE=1 when running live eval tests. Uses the existing
OpenAI client from backend settings — not run in default CI.
"""

from __future__ import annotations

import json
import os
from typing import Any

from tests.eval.model_config import resolve_eval_model
from tests.eval.plan_trace_scorer import ScoreResult

RUBRIC = """You are reviewing a Gymnasium chemistry lesson plan draft.
Return JSON only: {"pass": true|false, "score": 0-100, "issues": ["...", ...]}

Pass only if ALL are true:
- Grounded in class memory (mentions prior lessons or class-specific confusion)
- 45-minute structure with clear lesson flow
- Covers FCKW/CFC redox AND environmental impact (ozone/Montreal Protocol)
- Addresses oxidation number vs charge misconception
- Includes homework/practice and safe lab note (no real CFCs)
- After revisions: includes a short active-recall recap
- Practical for Chemie 9b, not generic boilerplate
"""


def score_lesson_plan_with_llm_judge(artifact_md: str, *, model: str | None = None) -> ScoreResult:
    if os.getenv("RUN_LLM_PLAN_JUDGE") != "1":
        return ScoreResult(passed=True, warnings=["LLM judge skipped (set RUN_LLM_PLAN_JUDGE=1 to enable)"])

    try:
        from openai import OpenAI

        from app.config import get_settings

        settings = get_settings()
        api_key = settings.openai_api_key.get_secret_value()
        if not api_key:
            return ScoreResult(passed=True, warnings=["LLM judge skipped (no OPENAI_API_KEY)"])

        client = OpenAI(api_key=api_key)
        model_config = resolve_eval_model(model)
        response = client.chat.completions.create(
            model=model_config.model,
            reasoning_effort=model_config.reasoning_effort,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RUBRIC},
                {"role": "user", "content": artifact_md[:12000]},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        payload: dict[str, Any] = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — opt-in diagnostic path
        return ScoreResult(passed=True, warnings=[f"LLM judge skipped (error: {exc})"])

    if payload.get("pass"):
        return ScoreResult(passed=True)

    issues = payload.get("issues") or []
    score = payload.get("score")
    failures = [f"LLM judge failed (score={score}): {issue}" for issue in issues]
    return ScoreResult(passed=False, failures=failures)
