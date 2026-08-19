"""Eval harness for layer traces and workflow startup traces."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.teacher_agent.wiki_store import WikiStore


@dataclass
class ChatTurnResult:
    class_id: str
    session_id: str
    workflow: str
    message: str
    events: list[dict[str, Any]] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)
    final: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowScenarioResult:
    class_id: str
    session_id: str
    workflow: str
    messages: tuple[str, ...]
    turns: list[ChatTurnResult] = field(default_factory=list)

    @property
    def final_turn(self) -> ChatTurnResult:
        if not self.turns:
            raise ValueError("WorkflowScenarioResult has no turns")
        return self.turns[-1]


def _parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in body.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def _workflow_paths(workflow: str, class_id: str) -> tuple[str, str, str]:
    normalized = workflow.strip().lower()
    if normalized == "plan":
        base = f"/api/classes/{class_id}/plan/sessions"
        return normalized, base, f"{base}/{{session_id}}/trace"
    if normalized in {"ingest", "memory", "update_memory"}:
        base = f"/api/classes/{class_id}/ingest/sessions"
        return "ingest", base, f"{base}/{{session_id}}/trace"
    if normalized in {"discussion", "discuss"}:
        base = f"/api/classes/{class_id}/discussion/sessions"
        return "discussion", base, f"{base}/{{session_id}}/trace"
    raise ValueError(f"Unknown workflow: {workflow!r}")


def start_session(client: TestClient, *, workflow: str, class_id: str) -> str:
    _, base, _ = _workflow_paths(workflow, class_id)
    start = client.post(base)
    if start.status_code != 200:
        raise RuntimeError(
            f"Failed to start {workflow} session: {start.status_code} {start.text}"
        )
    return start.json()["session_id"]


_MATERIALS_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "materials"


def seed_plan_material_fixture(
    client: TestClient,
    *,
    class_id: str,
    session_id: str,
    fixture_name: str,
) -> str:
    """Copy a prebuilt OCR package into the plan session (live/offline goldens)."""
    plan_svc = getattr(client, "plan_service", None)
    if plan_svc is None:
        raise RuntimeError("TestClient missing plan_service (eval fixture)")
    package = _MATERIALS_FIXTURES / fixture_name
    if not package.is_dir():
        raise FileNotFoundError(f"materials fixture missing: {package}")
    summary = plan_svc.attach_prebuilt_material(
        class_id,
        session_id,
        package_dir=package,
        arm="textbook",
    )
    return summary.material_id


def run_chat_turn(
    client: TestClient,
    *,
    workflow: str,
    class_id: str,
    session_id: str,
    message: str,
    attachments: tuple[tuple[str, str], ...] = (),
) -> ChatTurnResult:
    normalized, base, trace_path = _workflow_paths(workflow, class_id)
    payload: dict[str, Any] = {"message": message}
    if attachments:
        payload["attachments"] = [
            {"filename": filename, "content": content}
            for filename, content in attachments
        ]
    stream = client.post(
        f"{base}/{session_id}/chat/stream",
        json=payload,
    )
    if stream.status_code != 200:
        raise RuntimeError(f"Chat stream failed: {stream.status_code} {stream.text}")

    events = _parse_sse(stream.text)
    finals = [event for event in events if event.get("type") == "final"]
    final = finals[-1] if finals else {}

    trace_res = client.get(trace_path.format(session_id=session_id))
    if trace_res.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch trace: {trace_res.status_code} {trace_res.text}"
        )

    return ChatTurnResult(
        class_id=class_id,
        session_id=session_id,
        workflow=normalized,
        message=message,
        events=events,
        trace=trace_res.json(),
        final=final,
    )


def run_chat_scenario(
    client: TestClient,
    *,
    workflow: str,
    class_id: str,
    prior_messages: tuple[str, ...],
    message: str,
    attachments: tuple[tuple[str, str], ...] = (),
    seed_material_fixture: str = "",
) -> ChatTurnResult:
    session_id = start_session(client, workflow=workflow, class_id=class_id)
    if seed_material_fixture:
        seed_plan_material_fixture(
            client,
            class_id=class_id,
            session_id=session_id,
            fixture_name=seed_material_fixture,
        )
    for prior in prior_messages:
        run_chat_turn(
            client,
            workflow=workflow,
            class_id=class_id,
            session_id=session_id,
            message=prior,
        )
    return run_chat_turn(
        client,
        workflow=workflow,
        class_id=class_id,
        session_id=session_id,
        message=message,
        attachments=attachments,
    )


def run_workflow_scenario(
    client: TestClient,
    *,
    workflow: str,
    class_id: str,
    messages: tuple[str, ...],
) -> WorkflowScenarioResult:
    session_id = start_session(client, workflow=workflow, class_id=class_id)
    turns = [
        run_chat_turn(
            client,
            workflow=workflow,
            class_id=class_id,
            session_id=session_id,
            message=message,
        )
        for message in messages
    ]
    normalized, _, _ = _workflow_paths(workflow, class_id)
    return WorkflowScenarioResult(
        class_id=class_id,
        session_id=session_id,
        workflow=normalized,
        messages=messages,
        turns=turns,
    )


def tool_names_from_events(events: list[dict[str, Any]]) -> list[str]:
    return [
        str(event.get("name", ""))
        for event in events
        if event.get("type") == "tool_call"
    ]


def build_retrieval_context(
    result: ChatTurnResult, *, max_chars: int = 12000
) -> list[str]:
    """Compact evidence packet for LLM judge metrics."""
    chunks: list[str] = []
    stack = result.trace.get("prompt_stack") or {}
    for key in ("teacher_context", "active_class_core"):
        text = str(stack.get(key) or "").strip()
        if text:
            chunks.append(f"## Startup {key}\n{text[:3000]}")

    for event in result.events:
        if event.get("type") == "tool_result":
            name = event.get("name", "tool")
            output = str(event.get("output") or "")[:2500]
            chunks.append(f"## Tool result: {name}\n{output}")

    raw_evidence = result.trace.get("raw_evidence") or {}
    if isinstance(raw_evidence, dict):
        for ref, payload in list(raw_evidence.items())[:8]:
            chunks.append(f"## Raw evidence {ref}\n{str(payload)[:2500]}")

    runtime = result.trace.get("runtime") or {}
    briefs = (
        runtime.get("evidence_briefs") or runtime.get("memory_evidence_briefs") or []
    )
    if briefs:
        chunks.append(
            f"## Evidence briefs\n{json.dumps(briefs, ensure_ascii=False)[:3000]}"
        )

    joined = "\n\n".join(chunks)
    if len(joined) > max_chars:
        return [joined[:max_chars]]
    return chunks or ["(no retrieval context captured)"]


def actual_output_text(result: ChatTurnResult) -> str:
    reply = str(result.final.get("reply") or "")
    artifact = str(
        result.final.get("artifact_markdown")
        or result.final.get("plan_markdown")
        or result.trace.get("artifact_markdown")
        or ""
    )
    if artifact:
        return f"Reply:\n{reply}\n\nArtifact:\n{artifact}"
    return reply


def check_artifact_patterns(text: str, patterns: tuple[str, ...]) -> list[str]:
    failures: list[str] = []
    haystack = text or ""
    for pattern in patterns:
        if not re.search(pattern, haystack, flags=re.IGNORECASE):
            failures.append(f"artifact missing pattern /{pattern}/")
    return failures


def fetch_layer_traces(wiki: WikiStore, class_id: str) -> dict[str, Any]:
    """Build the three plan-startup layer traces via their pack builders."""
    return {
        "class_id": class_id,
        "teacher_trace": wiki.build_teacher_context_trace(),
        "core_trace": wiki.build_active_class_core_context_trace(class_id),
        "subject_trace": wiki.build_active_subject_expert_context_trace(
            class_id, purpose="plan"
        ),
    }


def fetch_startup_trace(
    client: TestClient, *, workflow: str, class_id: str
) -> dict[str, Any]:
    """Start a session and return the trace snapshot before the first teacher message."""
    normalized = workflow.strip().lower()
    if normalized == "plan":
        start = client.post(f"/api/classes/{class_id}/plan/sessions")
        trace_path = f"/api/classes/{class_id}/plan/sessions/{{session_id}}/trace"
    elif normalized in {"ingest", "memory", "update_memory"}:
        start = client.post(f"/api/classes/{class_id}/ingest/sessions")
        trace_path = f"/api/classes/{class_id}/ingest/sessions/{{session_id}}/trace"
    else:
        raise ValueError(f"Unknown workflow for startup trace: {workflow!r}")

    if start.status_code != 200:
        raise RuntimeError(
            f"Failed to start {workflow} session: {start.status_code} {start.text}"
        )

    session_id = start.json()["session_id"]
    trace = client.get(trace_path.format(session_id=session_id))
    if trace.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch {workflow} trace: {trace.status_code} {trace.text}"
        )

    payload = trace.json()
    payload["golden_workflow"] = normalized
    payload["golden_class_id"] = class_id
    payload["session_id"] = session_id
    return payload
