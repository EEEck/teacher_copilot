"""Contracts for registered artifact workflows."""

from __future__ import annotations

import inspect

from app.services.artifact_session_service import ArtifactSessionService
from app.services.artifact_spec import default_specs


def test_registered_workflows_declare_runtime_trace_and_stream_contracts():
    specs = default_specs()
    assert {"ingest", "plan"} <= set(specs)

    for spec in specs.values():
        assert spec.runtime_factory is not None
        assert spec.prompt_trace is not None
        assert spec.stream_turn is not None
        assert spec.final_event_to_turn_result is not None
        assert spec.workflow_contract is not None
        assert spec.workflow_contract.trace.expected_sections
        assert "Executive state" in spec.workflow_contract.trace.expected_sections
        assert spec.workflow_contract.history.conversation_turns_setting
        assert spec.workflow_contract.executive_verification is True
        assert spec.workflow_contract.history.artifact_location in {
            "system_prompt",
            "user_input",
        }


def test_artifact_session_streaming_uses_workflow_spec_not_mode_branch():
    source = inspect.getsource(ArtifactSessionService._execute_chat_stream_turn)
    assert 'session.mode == "ingest"' not in source
    assert "spec.stream_turn" in source
    assert "spec.final_event_to_turn_result" in source
