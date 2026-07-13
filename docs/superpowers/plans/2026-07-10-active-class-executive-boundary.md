# Active-Class Executive Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep executive verification and teacher-facing recovery strictly within the active class.

**Architecture:** Add one shared prompt rule used by planning and ingest. Extend the existing golden model with teacher-facing forbidden signals and use the live contract plus LLM judge to check it.

**Tech Stack:** Python, pytest, OpenAI Agents SDK live evals, DeepEval.

## Global Constraints

- Do not add cross-class reads, writes, or a class-switching workflow.
- The active `class_id` remains session-owned and immutable.
- Preserve the existing known valid-input live-eval failure as a separate calibration finding.

---

### Task 1: Pin the active-class prompt contract

**Files:**
- Modify: `backend/tests/test_prompts.py`
- Modify: `backend/app/teacher_agent/prompts.py`

**Interfaces:**
- Consumes: `EXECUTIVE_ASSISTANT_POLICY`.
- Produces: shared instructions injected into both planning and ingest assemblies.

- [ ] **Step 1: Write the failing regression test**

```python
def test_executive_assistant_policy_keeps_sessions_in_the_active_class():
    policy = EXECUTIVE_ASSISTANT_POLICY.lower()
    assert "strictly limited to its active class" in policy
    assert "must never search, suggest, or offer to move work to another class" in policy
    assert "question about what the class covered is an evidence request" in policy
```

- [ ] **Step 2: Run the regression test and verify it fails**

Run: `backend\\.venv\\Scripts\\python -m pytest backend/tests/test_prompts.py -q`

Expected: FAIL because the active-class sentence is absent.

- [ ] **Step 3: Add the minimal shared policy**

```text
Each workflow session is strictly limited to its active class; the copilot may
verify that a reference does not belong to that class, but must never search,
suggest, or offer to move work to another class.
```

Add the history-question sentence immediately after the conflict behavior.

- [ ] **Step 4: Run the prompt test**

Run: `backend\\.venv\\Scripts\\python -m pytest backend/tests/test_prompts.py -q`

Expected: PASS.

### Task 2: Add active-class goldens and judge criteria

**Files:**
- Modify: `backend/tests/evals/goldens/executive_verification.py`
- Modify: `backend/tests/evals/test_klassenpilot_executive_verification.py`
- Modify: `backend/tests/evals/metrics/executive_verification_metrics.py`

**Interfaces:**
- Consumes: `ExecutiveVerificationGolden`, live SSE final payloads.
- Produces: deterministic golden coverage and opt-in live/judge assertions.

- [ ] **Step 1: Write the failing definition test**

```python
assert "memory_unknown_student_stays_in_active_class" in ids
assert "memory_unsupported_history_stays_in_active_class" in ids
```

- [ ] **Step 2: Run it and verify it fails**

Run: `backend\\.venv\\Scripts\\python -m pytest backend/tests/evals/test_klassenpilot_executive_verification.py -q`

Expected: FAIL because neither golden exists.

- [ ] **Step 3: Add two ingest goldens**

Use the 9b planned lesson target. Require `S-006` to block and be excluded
without `9a`/`other class` wording. Require the Hartree--Fock history question
to answer from the active record, exclude it from the artifact, and never
mention a different class.

- [ ] **Step 4: Make the LLM judge require active-class-only behavior**

```text
- It treats the active class as an immutable session boundary and never offers another class as a resolution.
- A question about prior coverage is answered from active-class evidence and does not become a candidate update.
```

- [ ] **Step 5: Run deterministic eval checks**

Run: `backend\\.venv\\Scripts\\python -m pytest backend/tests/evals/test_klassenpilot_executive_verification.py -q`

Expected: PASS with live tests skipped unless opted in.

### Task 3: Run live verification and prepare commit

**Files:**
- Verify only.

- [ ] **Step 1: Run focused deterministic tests**

Run: `backend\\.venv\\Scripts\\python -m pytest backend/tests/test_prompts.py backend/tests/evals/test_klassenpilot_executive_verification.py -q`

Expected: PASS.

- [ ] **Step 2: Run opt-in live contract and LLM judge**

Run: `$env:RUN_LIVE_AGENT_EVALS='1'; $env:RUN_LLM_EXECUTIVE_VERIFICATION_JUDGE='1'; backend\\.venv\\Scripts\\python -m pytest backend/tests/evals/test_klassenpilot_executive_verification.py -q -rA`

Expected: new active-class goldens pass; report the pre-existing valid messy-input readiness calibration result separately.

- [ ] **Step 3: Commit after review**

Run: `git add backend/app/teacher_agent/prompts.py backend/tests/test_prompts.py backend/tests/evals docs/superpowers/specs/2026-07-10-active-class-executive-boundary-design.md docs/superpowers/plans/2026-07-10-active-class-executive-boundary.md && git commit -m "Calibrate active-class executive verification"`
