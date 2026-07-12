"""Runtime contracts that must hold before live Agents SDK calls."""

from __future__ import annotations

from agents.agent_output import AgentOutputSchema

from app.teacher_agent.agent import chat_model_settings
from app.teacher_agent.models import (
    IngestTurnOutput,
    PlanTurnOutput,
    WriteVerificationOutput,
)


def test_plan_and_ingest_outputs_are_agents_sdk_strict_schema_compatible():
    AgentOutputSchema(PlanTurnOutput)
    AgentOutputSchema(IngestTurnOutput)
    AgentOutputSchema(WriteVerificationOutput)


def test_gpt_5_4_models_normalize_unsupported_minimal_effort():
    settings = chat_model_settings("minimal", model="gpt-5.4-mini")

    assert settings is not None
    assert settings.reasoning is not None
    assert settings.reasoning.effort == "low"


def test_gpt_5_5_models_normalize_unsupported_minimal_effort():
    settings = chat_model_settings("minimal", model="gpt-5.5")

    assert settings is not None
    assert settings.reasoning is not None
    assert settings.reasoning.effort == "low"


def test_other_models_keep_minimal_effort():
    settings = chat_model_settings("minimal", model="o4-mini")

    assert settings is not None
    assert settings.reasoning is not None
    assert settings.reasoning.effort == "minimal"
