# MemV4 Live-Derived Goldens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the beta MemV4 observations into reviewable deterministic goldens and opt-in DeepEval live-judge cases, while documenting behavioural gaps without changing agent behaviour.

**Architecture:** Extend the existing `MemoryCaptureGolden` fixture set and its deterministic contract tests. Add a focused Discuss golden family using the existing DeepEval `GEval` pattern. Keep live calls opt-in; the always-on layer validates fixture intent, target/scope rules, and the issue ledger links.

**Tech Stack:** Python, pytest, Pydantic fixtures, DeepEval `GEval`, existing in-process FastAPI eval harness, Markdown documentation.

## Global Constraints

- Do not alter production capture, executive-guard, or Discuss prompt behaviour in this change.
- Preserve the beta boundary: private trace bundles and raw reasoning never enter Git.
- Live LLM-judge tests must be opt-in and skipped without API credentials.
- Deterministic tests must run without OpenAI calls.
- Use the canonical memory homes: `copilot_profile.md` for class working agreements, `teaching_patterns.md` for observed learning evidence, and `planning_brief.md` for immediate planning pressure.

---

### Task 1: Memory-capture live-derived golden fixtures

**Files:**
- Modify: `backend/tests/evals/goldens/memory_capture.py`
- Modify: `backend/tests/evals/test_memory_capture_golden_contract.py`

**Interfaces:**
- Consumes: `MemoryCaptureGolden` and the live runner in `test_klassenpilot_memory_capture_live.py`.
- Produces: golden IDs that identify the beta-derived scope, target, and false-positive cases.

- [ ] **Step 1: Write failing deterministic assertions**

Add assertions requiring these fixture IDs and contracts:

```python
assert _by_id("mbb_session_then_general_style_boundary").expected_targets == (
    "teacher_profile.md",
)
assert "teacher_profile.md" in _by_id("five_minute_review_no_global_leakage").forbidden_targets
assert _by_id("light_orbital_preference_class_fast_lane").target == "copilot_profile.md"
```

- [ ] **Step 2: Run the focused contract test and verify RED**

Run:

```powershell
cd backend
<python> -m pytest tests/evals/test_memory_capture_golden_contract.py -q
```

Expected: failure because the three beta-derived golden IDs do not yet exist.

- [ ] **Step 3: Add minimal fixture definitions**

Add the following cases to `MEMORY_CAPTURE_GOLDENS`:

```python
"mbb_session_then_general_style_boundary"
"light_orbital_preference_class_fast_lane"
"phenomenon_first_instruction_and_evidence"
"five_minute_review_no_global_leakage"
"unknown_scope_no_durable_capture"
```

Use exact expected targets/forbidden targets from the design and leave current known failures as live-eval findings, not production fixes.

- [ ] **Step 4: Run deterministic memory-capture tests and verify GREEN**

Run:

```powershell
cd backend
<python> -m pytest tests/evals/test_memory_capture_golden_contract.py tests/evals/test_klassenpilot_memory_capture_stub.py -q
```

Expected: all deterministic tests pass.

### Task 2: Discuss task-anchor DeepEval golden

**Files:**
- Modify: `backend/tests/evals/goldens/chat_plan.py` or create `backend/tests/evals/goldens/discussion.py`
- Modify: `backend/tests/evals/test_klassenpilot_chat_live.py` or create a focused Discuss live test
- Modify: `backend/tests/evals/metrics/chat_metrics.py`
- Test: focused deterministic fixture-contract test

**Interfaces:**
- Consumes: `run_chat_scenario`, `Golden`, and `GEval` criteria from `GroundedChatGEval`.
- Produces: an opt-in LLM judge that receives the active lesson task and a Dota detour.

- [ ] **Step 1: Write a failing fixture-contract test**

Assert that the Discuss scenario has an active teacher task, a Dota/Legion Commander detour, and criteria requiring a concise natural answer plus a return to the lesson task.

- [ ] **Step 2: Run it and verify RED**

Run the new focused test with pytest; expected failure is the absent Discuss golden.

- [ ] **Step 3: Add fixture and reuse existing opt-in GEval runner**

Define a single Discuss live golden with `workflow="discussion"`. Its LLM criteria must assess teacher-visible reply only: answer the detour briefly, avoid invented game facts, and explicitly return to the active lesson-planning topic.

- [ ] **Step 4: Run deterministic contract test and the existing live test in skipped mode**

Run:

```powershell
cd backend
<python> -m pytest tests/evals/test_klassenpilot_chat_live.py <focused-contract-test> -q
```

Expected: deterministic test passes; live test is skipped unless `RUN_LIVE_AGENT_EVALS=1`.

### Task 3: Live-eval ledger and runbook

**Files:**
- Create: `docs/mem_v4/mem_v4_live_eval_ledger.md`
- Modify: `backend/docs/evals.md`
- Modify: `implementation_plans/mem_v4_live_goldens_plan.md`
- Test: `backend/tests/evals/test_memory_capture_golden_contract.py`

**Interfaces:**
- Consumes: committed golden IDs and beta trace timestamps only.
- Produces: a handoff ledger linking each observed case to its automated coverage and proposed owning branch.

- [ ] **Step 1: Write a failing documentation-presence assertion**

Add a deterministic test that reads the ledger and requires every new golden ID and the schema-envelope issue ID to be present.

- [ ] **Step 2: Run it and verify RED**

Run the focused test; expected failure is the missing ledger document.

- [ ] **Step 3: Add the ledger and evals runbook link**

Document observed outcome, desired behaviour, golden ID, test tier, likely code area, and follow-up branch for:

```text
M4-LIVE-01 style scope boundary
M4-LIVE-02 orbital preference omission
M4-LIVE-03 phenomenon-first evidence decomposition
M4-LIVE-04 five-minute-review global leakage
M4-LIVE-05 unknown speech_act/scope admission
M4-LIVE-06 Discuss task anchoring
M4-LIVE-07 required nullable structured envelope
```

Add a `MemV4 live-derived goldens` section to `backend/docs/evals.md` with deterministic and opt-in live commands.

- [ ] **Step 4: Run all focused deterministic tests**

Run:

```powershell
cd backend
<python> -m pytest tests/evals/test_memory_capture_golden_contract.py tests/evals/test_klassenpilot_memory_capture_stub.py <discussion-contract-test> -q
```

Expected: all pass without OpenAI calls.

- [ ] **Step 5: Update this plan’s checkboxes and commit**

Commit the goldens, ledger, test, runbook, and completed plan together with:

```text
test: add MemV4 live-derived golden ledger
```
