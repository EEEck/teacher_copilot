"""Shared model routing for optional LLM-as-judge evaluations."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_EVAL_MODEL = "gpt-5.4-mini"
DEFAULT_EVAL_REASONING_EFFORT = "medium"
VALID_REASONING_EFFORTS = {"none", "low", "medium", "high", "xhigh"}


@dataclass(frozen=True)
class EvalModelConfig:
    model: str
    reasoning_effort: str


def resolve_eval_model(explicit_model: str | None = None) -> EvalModelConfig:
    model = (
        explicit_model
        or os.getenv("DEEPEVAL_MODEL")
        or os.getenv("OPENAI_FAST_MODEL")
        or DEFAULT_EVAL_MODEL
    )
    reasoning_effort = (
        os.getenv("DEEPEVAL_REASONING_EFFORT")
        or DEFAULT_EVAL_REASONING_EFFORT
    ).strip().lower()
    if reasoning_effort not in VALID_REASONING_EFFORTS:
        options = ", ".join(sorted(VALID_REASONING_EFFORTS))
        raise ValueError(
            f"DEEPEVAL_REASONING_EFFORT must be one of: {options}"
        )
    return EvalModelConfig(model=model, reasoning_effort=reasoning_effort)


def build_deepeval_model(explicit_model: str | None = None):
    from deepeval.models import GPTModel

    config = resolve_eval_model(explicit_model)
    return GPTModel(
        model=config.model,
        generation_kwargs={"reasoning_effort": config.reasoning_effort},
    )
