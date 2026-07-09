"""Runtime contracts that must hold before live Agents SDK calls."""

from __future__ import annotations

from agents.agent_output import AgentOutputSchema

from app.teacher_agent.agent import chat_model_settings
from app.teacher_agent.models import IngestTurnOutput, PlanTurnOutput


def test_plan_and_ingest_outputs_are_agents_sdk_strict_schema_compatible():
    AgentOutputSchema(PlanTurnOutput)
    AgentOutputSchema(IngestTurnOutput)


def test_minimal_reasoning_effort_is_normalized_before_model_settings():
    settings = chat_model_settings("minimal")

    assert settings is not None
    assert settings.reasoning is not None
    assert settings.reasoning.effort == "low"
