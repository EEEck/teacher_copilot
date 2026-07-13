# Executive Write Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent plan and ingest writes unless a fresh, read-only verification of the exact submitted artifact finds no blocking class-state issue.

**Architecture:** Add a typed write-verification result to the shared executive runtime and a small read-only verifier agent. Plan save, ingest proposal, and ingest commit each invoke it using their submitted markdown, then apply a deterministic SHA-256 fingerprint and open-finding gate before side effects. A typed `409` preserves the existing draft and gives the frontend a concise recovery message.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, OpenAI Agents SDK, pytest, Next.js/TypeScript, assistant-ui.

## Global Constraints

- Chat never writes durable wiki state; write verification has no write tools.
- The backend computes fingerprints and decides whether to write.
- A verifier failure fails closed and writes nothing.
- Do not weaken the existing structural readiness checks or the known valid-input live-eval expectation.
- Reuse the existing executive state display; add no validation wizard.
- Default tests make no OpenAI calls.

---

## File Structure

- `backend/app/teacher_agent/executive_verification.py`: fingerprint, write-result, deterministic gate, and teacher-facing block message.
- `backend/app/teacher_agent/models.py`: typed verifier output.
- `backend/app/teacher_agent/prompts.py` and `backend/app/teacher_agent/agent.py`: constrained verifier prompt and agent builder.
- `backend/app/teacher_agent/agents.py`: one runner method that verifies an exact artifact and merges its patch.
- `backend/app/services/plan_service.py` and `backend/app/services/ingest_service.py`: async write-boundary verification before side effects.
- `backend/app/schemas/api.py` and `backend/app/api/routes.py`: typed `409` transport contract.
- `frontend/src/lib/api.ts`, `frontend/src/lib/sse-chat.ts`, and shared artifact runtime: preserve/render blocked-write information without mutating the draft.
- `backend/tests/test_executive_state.py`, `backend/tests/test_api_plan.py`, `backend/tests/test_api_ingest.py`: deterministic unit and API coverage with the stub verifier.

### Task 1: Define the exact-artifact gate

**Files:**
- Modify: `backend/app/teacher_agent/executive_verification.py`
- Modify: `backend/tests/test_executive_state.py`

**Interfaces:**
- Produces `artifact_fingerprint(markdown: str) -> str`, `WriteVerificationResult`, `WriteGateResult`, `apply_write_verification(...)`, and `evaluate_write_gate(...)`.
- Consumes `ExecutivePatch` and `ExecutiveRuntime`.

- [ ] **Step 1: Write failing state tests**

```python
def test_write_gate_requires_current_fingerprint_and_no_blocking_findings():
    runtime = ExecutiveRuntime()
    apply_write_verification(runtime, artifact="# Draft", patch=ExecutivePatch())
    assert evaluate_write_gate(runtime, "# Draft", structurally_ready=True).allowed
    assert not evaluate_write_gate(runtime, "# Changed", structurally_ready=True).allowed


def test_write_gate_blocks_open_finding_even_when_fingerprint_matches():
    runtime = ExecutiveRuntime()
    patch = ExecutivePatch(findings=[blocking_student_finding("S-999")])
    apply_write_verification(runtime, artifact="# Draft", patch=patch)
    gate = evaluate_write_gate(runtime, "# Draft", structurally_ready=True)
    assert gate.reason == "unresolved_blocking_finding"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `C:\Users\matth\teacher_agent_v2\backend\.venv\Scripts\python.exe -m pytest tests\test_executive_state.py -q`

Expected: failure because write-verification interfaces do not exist.

- [ ] **Step 3: Implement the minimal deterministic gate**

```python
def artifact_fingerprint(markdown: str) -> str:
    normalized = (markdown or "").replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def evaluate_write_gate(runtime, markdown, *, structurally_ready):
    if not structurally_ready:
        return WriteGateResult(False, "artifact_not_ready")
    if runtime.write_verification_fingerprint != artifact_fingerprint(markdown):
        return WriteGateResult(False, "artifact_changed_since_verification")
    if runtime.open_blocking_findings():
        return WriteGateResult(False, "unresolved_blocking_finding")
    return WriteGateResult(True)
```

`apply_write_verification` must replace open findings with the verifier's
current exact-artifact findings before recording the fingerprint; it must retain
resolved history only for traceability.

- [ ] **Step 4: Run the focused state test**

Run: `C:\Users\matth\teacher_agent_v2\backend\.venv\Scripts\python.exe -m pytest tests\test_executive_state.py -q`

Expected: all tests pass.

### Task 2: Build the read-only write verifier

**Files:**
- Modify: `backend/app/teacher_agent/models.py`
- Modify: `backend/app/teacher_agent/prompts.py`
- Modify: `backend/app/teacher_agent/agent.py`
- Modify: `backend/app/teacher_agent/agents.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_agent_runtime_contracts.py`

**Interfaces:**
- Produces `WriteVerificationOutput(executive_patch: ExecutivePatch, message: str)` and `AgentRunner.verify_artifact_for_write(class_id, artifact_kind, markdown, executive) -> WriteVerificationResult`.
- Consumes existing class-scoped wiki tools and compact class context.

- [ ] **Step 1: Add a failing stub/runtime contract test**

```python
async def test_write_verifier_receives_exact_artifact_and_has_no_write_tools():
    result = await agents.verify_artifact_for_write(
        CLASS_ID, "plan", "# Lesson Plan\n", ExecutiveRuntime()
    )
    assert result.artifact_fingerprint == artifact_fingerprint("# Lesson Plan\n")
    assert result.message
```

- [ ] **Step 2: Run the focused contract test and verify it fails**

Run: `C:\Users\matth\teacher_agent_v2\backend\.venv\Scripts\python.exe -m pytest tests\test_agent_runtime_contracts.py -q`

Expected: failure because the verifier runner method/output contract is absent.

- [ ] **Step 3: Add the verifier output, prompt, builder, and runner**

The system prompt must state: inspect the exact artifact only; use committed wiki
as factual baseline; return no artifact; report only actionable findings;
never claim a write occurred. Build it with the existing read-only
`WikiToolContext` tools and `output_type=WriteVerificationOutput`.

```python
async def verify_artifact_for_write(self, class_id, artifact_kind, markdown, executive):
    prompt = build_write_verification_input(
        self.wiki, class_id, artifact_kind, markdown, executive
    )
    parsed = await self._run_structured(agent, prompt)
    if not isinstance(parsed, WriteVerificationOutput):
        raise RuntimeError("Failed to verify artifact for write")
    return WriteVerificationResult(
        artifact_fingerprint=artifact_fingerprint(markdown),
        patch=parsed.executive_patch,
        message=parsed.message,
    )
```

Extend `StubAgentRunner` with the same async method. It should flag `S-999`
and otherwise return a clear patch so offline API tests can control behavior.

- [ ] **Step 4: Run the focused contract test**

Run: `C:\Users\matth\teacher_agent_v2\backend\.venv\Scripts\python.exe -m pytest tests\test_agent_runtime_contracts.py -q`

Expected: all tests pass without OpenAI calls.

### Task 3: Enforce the verifier before plan and ingest side effects

**Files:**
- Modify: `backend/app/services/plan_service.py`
- Modify: `backend/app/services/ingest_service.py`
- Modify: `backend/app/schemas/api.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/tests/test_api_plan.py`
- Modify: `backend/tests/test_api_ingest.py`

**Interfaces:**
- Produces async `PlanService.save(...)`, async `IngestService.propose(...)`, and async `IngestService.commit(...)` that either return their existing response or raise `WriteVerificationBlocked`.
- Produces `WriteVerificationBlockedResponse` with `code`, `action`, `artifact_fingerprint`, `executive_state`, and `message`.

- [ ] **Step 1: Write failing API tests**

```python
def test_plan_save_manual_unknown_student_returns_409_without_write(client):
    session_id, plan = ready_plan_session(client)
    edited = plan + "\nStudent note: S-999 needs support.\n"
    response = client.post(plan_save_url, json=save_payload(session_id, edited))
    assert response.status_code == 409
    assert response.json()["code"] == "write_verification_blocked"
    assert "S-999" in response.json()["message"]
    assert saved_plan_does_not_contain("S-999")


def test_ingest_commit_rechecks_exact_manual_diary_before_writing(client):
    session_id, diary, approved = ready_ingest_review(client)
    response = client.post(commit_url, json=commit_payload(session_id, diary + "\nS-999...", approved))
    assert response.status_code == 409
    assert response.json()["action"] == "ingest_commit"
```

Also add success coverage for a manual edit that removes an old issue and for
an ingest proposal block that creates no review proposals.

- [ ] **Step 2: Run API tests and verify they fail**

Run: `C:\Users\matth\teacher_agent_v2\backend\.venv\Scripts\python.exe -m pytest tests\test_api_plan.py tests\test_api_ingest.py -q`

Expected: new tests fail because writes proceed or responses are not typed 409s.

- [ ] **Step 3: Implement service-level verification and typed route mapping**

Before each side effect, call the runner with the exact request markdown,
apply the returned verification to `session.executive`, and call the
deterministic gate using the existing workflow readiness function. On failure,
raise `WriteVerificationBlocked(action, result, gate)`.

Routes must await the changed service methods and map only that exception to:

```python
return JSONResponse(
    status_code=409,
    content=WriteVerificationBlockedResponse(
        code="write_verification_blocked",
        action=exc.action,
        artifact_fingerprint=exc.result.artifact_fingerprint,
        executive_state=executive_api_payload(session.executive),
        message=exc.teacher_message,
    ).model_dump(),
)
```

Do not set session status to `saved`, `reviewing`, or `committed` until after
the corresponding wiki side effect succeeds.

- [ ] **Step 4: Run API tests**

Run: `C:\Users\matth\teacher_agent_v2\backend\.venv\Scripts\python.exe -m pytest tests\test_api_plan.py tests\test_api_ingest.py -q`

Expected: all tests pass offline.

### Task 4: Preserve blocked-write recovery in the artifact UI

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/assistant-ui/artifact-session-runtime.tsx`
- Modify: `frontend/src/components/assistant-ui/artifact-runtime-config.ts`
- Test: existing frontend test file nearest to artifact-session runtime, or create `frontend/src/components/assistant-ui/artifact-session-runtime.test.tsx`.

**Interfaces:**
- Produces `WriteVerificationBlocked` client type and `pendingWriteVerification` runtime state.
- Consumes the backend `409` payload and current draft.

- [ ] **Step 1: Write a failing runtime test**

```tsx
it("keeps the draft and surfaces a blocked write as a recovery message", async () => {
  savePlan.mockRejectedValue(writeVerificationBlocked("S-999 is not in Chemie 9b"));
  render(<ArtifactSessionRuntime />);
  await user.click(screen.getByRole("button", { name: /save/i }));
  expect(screen.getByText(/I didn't save this yet/i)).toBeVisible();
  expect(currentDraft()).toContain("S-999");
});
```

- [ ] **Step 2: Run the frontend test and verify it fails**

Run: `npm test -- artifact-session-runtime`

Expected: failure because `409` is treated as a generic save error.

- [ ] **Step 3: Parse and render the recovery state**

Detect `409` plus `code === "write_verification_blocked"`, retain the draft,
store the payload, and append a system-generated assistant-visible message.
The message must expose the backend reason but have no auto-repair action.
Normal errors retain current handling.

- [ ] **Step 4: Run the frontend test**

Run: `npm test -- artifact-session-runtime`

Expected: all tests pass.

### Task 5: Contract documentation and final verification

**Files:**
- Modify: `docs/agent_contracts.md`
- Modify: `backend/docs/evals.md`

- [ ] **Step 1: Document the write-boundary rule**

Add the exact-fingerprint gate and `409` recovery behavior under the Executive
Verification Contract. Update the eval guide with the new deterministic API
tests and a deferred opt-in manual-edit recovery golden.

- [ ] **Step 2: Run backend verification**

Run: `C:\Users\matth\teacher_agent_v2\backend\.venv\Scripts\python.exe -m pytest tests\test_executive_state.py tests\test_agent_runtime_contracts.py tests\test_api_plan.py tests\test_api_ingest.py -q`

Expected: all tests pass; no OpenAI calls.

- [ ] **Step 3: Run static diff check and commit**

Run: `git diff --check`

Commit: `git commit -m "Add executive write verification gate"`

