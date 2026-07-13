# Executive Verification Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every KlassenPilot artifact workflow proactively reconcile teacher input with committed class state, interrupt only for consequential decisions, and prevent unresolved or stale drafts from being written durably.

**Architecture:** Add a workflow-independent `ExecutiveRuntime` to `ArtifactSession`, alongside the existing plan/ingest runtime. The chat agent uses compact authority-labeled wiki context plus existing read/search tools and one general reference resolver; it records structured findings under a stable verification ontology. A separate write-boundary verification pass checks the exact current artifact fingerprint before plan save or memory proposal/commit, so manual edits and model omissions cannot bypass the durable-write gate.

**Tech Stack:** Python 3, FastAPI, Pydantic, OpenAI Agents SDK structured outputs/function tools, pytest, Next.js/TypeScript, assistant-ui.

## Product Contract

### Core idea: executive assistant, not passive chatbot

KlassenPilot completes the teacher's foreground task while carrying the
background mental load of checking details, catching slips, comparing new input
with the class wiki, and surfacing only decisions the teacher must make.

The teacher remains the decision-maker for important class-state changes. The
assistant is highly proactive in verification and careful about irreversible
decisions.

> Do the busywork invisibly. Surface only the decisions.

Teachers will naturally give messy, fast, and occasionally inconsistent input.
They may mix up classes, reference the wrong student, introduce a concept from
another lesson sequence, or casually express a possible teaching preference.
This is expected product input, not teacher failure.

The agent therefore:

1. pursues the foreground task first;
2. retrieves relevant class state when needed;
3. compares consequential claims with committed wiki state;
4. distinguishes routine/local adaptation from durable changes;
5. gathers evidence and citations;
6. interrupts only when the teacher owns a consequential decision.

The wiki is the committed factual baseline. Teacher input is a useful signal
and may be a correction, but it is not silently promoted to canonical state.
Aligned input proceeds smoothly; new non-conflicting information is
incorporated; conflicts are surfaced with concise options.

The operating rule is:

> Verify continuously. Interrupt selectively.

## Global Constraints

- Preserve the teacher-approved write flows; chat never writes wiki files directly.
- Do not create a validator or tool per observed failure case.
- Keep verification in the common artifact-session foundation so future workflows inherit it.
- Use the injected context pack before calling retrieval tools.
- Ask at most one consolidated clarification per turn.
- Allow useful drafting when safe; block only artifact correctness or durable actions.
- Treat committed wiki facts as the baseline, not as immutable truth.
- Treat teacher intent as authoritative and teacher factual claims as candidate updates until reconciled.
- Keep real student names out of broad memory; continue using pseudonymous student IDs.
- Do not introduce multi-agent handoffs, a general skill framework, a graph engine, or autonomous writes.
- Production targets GPT-5.5 or better, but deterministic tests must make no OpenAI calls.

---

## Critical Design Decisions

### 1. The authority model replaces the current blanket precedence rule

`PLAN_MEMORY_POLICY` currently says “the teacher's latest message wins.” That is correct for task intent (“make this more hands-on”) but unsafe for claims about existing class state (“S-021 in 9b”). Replace it with:

| Input | Authority |
|---|---|
| Current task goal, requested style, explicit correction | Teacher controls the current interaction |
| Existing class, roster, lesson sequence, taught concepts | Committed wiki is the baseline |
| New observation or possible correction | Teacher-provided candidate until reconciled |
| Teacher/class profiles and inferred preferences | Advisory defaults |
| Uploaded/external content | Evidence, never class-state authority |

A teacher can correct stale wiki state. The assistant must present the discrepancy and obtain the teacher's decision rather than declaring either side wrong.

### 2. Verification is an ontology plus primitives, not a catalog of cases

The stable verification categories are:

- `scope`: active class or cross-class ambiguity
- `identity`: student/class/lesson reference resolution
- `time_state`: date, sequence, current unit, taught/planned status
- `grounding`: artifact claim lacks supporting wiki/teacher evidence
- `persistence`: one-off instruction may be mistaken for durable memory
- `consequence`: the ambiguity materially changes the artifact or durable write

Existing `search_memory`, `read_memory_page`, `list_lessons`, `read_lesson`, and `read_lesson_range` remain the broad evidence primitives. Add only:

- `resolve_wiki_references(...)`: deterministic exact/normalized resolution of class, student, and lesson references in the active class or workspace.
- `report_verification_finding(...)`: explicit state capture, analogous to `remember(...)`, so important findings are not lost in prose.

Do not add `check_roster`, `check_unit`, `check_preference`, and similar one-off tools.

### 3. Three outcomes, with one interruption budget

- `invisible`: evidence aligns or a safe local preference can be applied.
- `advisory`: work can continue; mention one assumption or discrepancy after the artifact.
- `blocking`: one consolidated teacher decision is required before the artifact is considered ready or can be written.

The agent asks before drafting only when all plausible resolutions would materially change the artifact. Otherwise it produces the useful portion first and asks once at the end.

### 4. Chat verification and write verification serve different purposes

Chat verification catches issues early and makes the interaction feel proactive. It is not a sufficient write gate because:

- the model may omit a check;
- the teacher may manually edit the draft after the last agent turn;
- structural readiness currently ignores class-state integrity.

At the natural write boundary, run a focused verification pass over the exact draft plus compact wiki state. Store the artifact SHA-256 fingerprint and verification result. `save` and `commit` check the fingerprint and open findings immediately next to the side effect.

### 5. Prompt content stays compact

Keep from the candidate prompt:

- dual job and motto;
- authority/decision-right principle;
- selective interruption;
- conflict handling;
- concise, non-accusatory tone.

Move elsewhere:

- workflow-specific duties stay in `PLAN_SKILL` / `MEMORY_SKILL`;
- retrieval details stay in tool descriptions and context assembly;
- preference capture stays in `DURABLE_MEMORY_CANDIDATE_POLICY` and `remember`;
- long examples become eval fixtures;
- write enforcement lives in backend gates.

The runtime, tools, structured state, and gates must carry the contract; the prompt alone must not.

---

## File Structure

### New production files

- `backend/app/teacher_agent/executive_verification.py` — the only new production backend module; finding models, runtime state, merge rules, artifact fingerprint, and write-gate result.

Reference resolution belongs in the existing
`backend/app/teacher_agent/wiki/search.py`; tool wiring belongs in the existing
`tools.py`. This avoids creating a new module for each verification capability.

### New test/eval files

- `backend/tests/test_executive_state.py` — state merging, invalidation, interruption, and write-gate unit tests.
- `backend/tests/test_reference_resolution.py` — active-class and cross-class deterministic resolution tests.
- `backend/tests/evals/goldens/executive_verification.yaml` — sanitized behavior cases adapted from beta telemetry plus synthetic cross-class cases.

### Modified backend files

- `backend/app/teacher_agent/prompts.py` — compact shared product contract and write-verifier prompt; replace unsafe precedence wording.
- `backend/app/teacher_agent/prompt_assembly.py` — inject executive state and authority-labeled context in plan and ingest.
- `backend/app/teacher_agent/wiki/context_packs.py` — add authority metadata and visible source labels to trace sections.
- `backend/app/teacher_agent/wiki/search.py` — deterministic class/student/lesson reference resolution using existing indexes.
- `backend/app/teacher_agent/wiki/store.py` — expose reference resolution through the wiki facade.
- `backend/app/teacher_agent/tools.py` — add the two shared executive tools to both workflows.
- `backend/app/teacher_agent/models.py` — add `executive_patch` to plan/ingest turn outputs and define verifier output.
- `backend/app/teacher_agent/agent.py` — attach shared tools and define the write-verifier agent.
- `backend/app/teacher_agent/agents.py` — merge executive patches, calculate readiness, and run write verification.
- `backend/app/services/artifact_session_service.py` — own `ExecutiveRuntime`, invalidate verification on edits, normalize state in `TurnResult`.
- `backend/app/services/artifact_spec.py` — pass executive runtime through every workflow spec.
- `backend/app/services/plan_service.py` — verify the current draft before save and enforce the write gate.
- `backend/app/services/ingest_service.py` — verify before proposal and recheck before commit.
- `backend/app/schemas/api.py` — expose executive state and typed blocked-action responses.
- `backend/app/teacher_agent/stream_events.py` — include executive state in final SSE events.
- `backend/app/api/routes.py` — make plan save async and map blocked writes to HTTP 409.
- `backend/tests/conftest.py` — update the stub runner and SSE fixtures.
- `backend/tests/test_prompts.py` — contract and authority-label assertions.
- `backend/tests/test_plan_context_manager.py` — shared state injection and invalidation.
- `backend/tests/test_api_plan.py` — save gate, stale manual edit, and resolved finding coverage.
- `backend/tests/test_api_ingest.py` — proposal/commit gate coverage.
- `backend/tests/test_workflow_contracts.py` — require all artifact workflows to declare executive verification.
- `backend/tests/evals/test_klassenpilot_wiki_reconciliation.py` — replace the narrow roster xfail with the general golden matrix.
- `backend/tests/eval/plan_trace_scorer.py` — score verification evidence, interruption calibration, and write safety.
- `backend/tests/eval/ingest_trace_scorer.py` — same for memory updates.

### Modified frontend and docs

- `frontend/src/lib/api.ts` — executive-state types and 409 response parsing.
- `frontend/src/lib/sse-chat.ts` — parse `executive_state`.
- `frontend/src/components/assistant-ui/artifact-runtime-config.ts` — map executive state from stream and draft responses.
- `frontend/src/components/assistant-ui/artifact-session-runtime.tsx` — hold executive state and disable durable actions while blocked.
- `frontend/src/app/classes/[classId]/plan/page.tsx` — one compact pending-decision/save-check status.
- `frontend/src/app/classes/[classId]/memory/page.tsx` — same shared status, no new wizard.
- `docs/agent_contracts.md` — common executive-verification behavior and write contract.
- `docs/agent_architecture.md` — runtime placement, tool boundary, and future workflow inheritance.
- `docs/product_vision.md` — selective-interruption product promise.
- `docs/pm_hub.md` — mark the product pivot and replace “deterministic roster first” wording with the general foundation.
- `implementation_plans/product_backlog.md` — sequence the implementation slices.

---

### Task 1: Define the Shared Executive State and Gate

**Files:**
- Create: `backend/app/teacher_agent/executive_verification.py`
- Create: `backend/tests/test_executive_state.py`
- Modify: `backend/app/services/artifact_session_service.py:52-67`

**Interfaces:**
- Produces: `ExecutiveFinding`, `ExecutivePatch`, `ExecutiveRuntime`, `WriteGateResult`, `artifact_fingerprint(markdown)`, `apply_executive_patch(runtime, patch)`, and `evaluate_write_gate(runtime, markdown)`.
- Consumes: no workflow-specific state.

- [ ] **Step 1: Write state and gate tests**

```python
from app.teacher_agent.executive_verification import (
    ExecutiveFinding,
    ExecutivePatch,
    ExecutiveRuntime,
    apply_executive_patch,
    artifact_fingerprint,
    evaluate_write_gate,
)


def test_blocking_finding_prevents_write():
    runtime = ExecutiveRuntime()
    apply_executive_patch(
        runtime,
        ExecutivePatch(
            checked_categories=["identity"],
            findings=[
                ExecutiveFinding(
                    finding_id="student-s021",
                    category="identity",
                    severity="blocking",
                    summary="S-021 is not resolved in the active class.",
                    question="Which student or class should receive this note?",
                    evidence_refs=["reference_001"],
                )
            ],
        ),
    )
    runtime.mark_verified("# Lesson Results\n")
    gate = evaluate_write_gate(runtime, "# Lesson Results\n")
    assert gate.allowed is False
    assert gate.reason == "unresolved_blocking_finding"


def test_manual_edit_invalidates_verified_fingerprint():
    runtime = ExecutiveRuntime()
    runtime.mark_verified("# Lesson Plan\nA")
    gate = evaluate_write_gate(runtime, "# Lesson Plan\nB")
    assert gate.allowed is False
    assert gate.reason == "artifact_changed_since_verification"


def test_resolved_finding_and_current_fingerprint_allow_write():
    runtime = ExecutiveRuntime()
    runtime.findings["scope-1"] = ExecutiveFinding(
        finding_id="scope-1",
        category="scope",
        severity="blocking",
        summary="Class was ambiguous.",
        question="Use 9a or 9b?",
        evidence_refs=["reference_001"],
    )
    apply_executive_patch(
        runtime,
        ExecutivePatch(
            resolved_findings={"scope-1": "Teacher confirmed 9b."},
            checked_categories=["scope"],
        ),
    )
    runtime.mark_verified("# Plan\n")
    assert evaluate_write_gate(runtime, "# Plan\n").allowed is True
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_executive_state.py -q
```

Expected: collection fails because `app.teacher_agent.executive_verification` does not exist.

- [ ] **Step 3: Implement the state model**

```python
# backend/app/teacher_agent/executive_verification.py
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, model_validator

VerificationCategory = Literal[
    "scope", "identity", "time_state", "grounding", "persistence", "consequence"
]
FindingSeverity = Literal["advisory", "blocking"]
FindingStatus = Literal["open", "resolved", "dismissed"]


class ExecutiveFinding(BaseModel):
    finding_id: str
    category: VerificationCategory
    severity: FindingSeverity
    summary: str
    question: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    status: FindingStatus = "open"
    resolution: str = ""

    @model_validator(mode="after")
    def blocking_findings_need_a_decision(self):
        if self.severity == "blocking" and not self.question.strip():
            raise ValueError("blocking findings require a teacher question")
        return self


class ExecutivePatch(BaseModel):
    checked_categories: list[VerificationCategory] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    findings: list[ExecutiveFinding] = Field(default_factory=list)
    resolved_findings: dict[str, str] = Field(default_factory=dict)
    verification_summary: str = ""


@dataclass
class ExecutiveRuntime:
    findings: dict[str, ExecutiveFinding] = field(default_factory=dict)
    checked_categories: set[str] = field(default_factory=set)
    assumptions: list[str] = field(default_factory=list)
    verification_summary: str = ""
    verified_artifact_fingerprint: str = ""

    def open_blocking_findings(self) -> list[ExecutiveFinding]:
        return [
            finding
            for finding in self.findings.values()
            if finding.status == "open" and finding.severity == "blocking"
        ]

    def mark_verified(self, markdown: str) -> None:
        self.verified_artifact_fingerprint = artifact_fingerprint(markdown)

    def invalidate_verification(self) -> None:
        self.verified_artifact_fingerprint = ""


@dataclass(frozen=True)
class WriteGateResult:
    allowed: bool
    reason: str = ""


def artifact_fingerprint(markdown: str) -> str:
    normalized = (markdown or "").replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def apply_executive_patch(
    runtime: ExecutiveRuntime, patch: ExecutivePatch
) -> ExecutiveRuntime:
    runtime.checked_categories.update(patch.checked_categories)
    for assumption in patch.assumptions:
        text = " ".join(assumption.split())
        if text and text not in runtime.assumptions:
            runtime.assumptions.append(text)
    for finding in patch.findings:
        runtime.findings[finding.finding_id] = finding
    for finding_id, resolution in patch.resolved_findings.items():
        existing = runtime.findings.get(finding_id)
        if existing and resolution.strip():
            runtime.findings[finding_id] = existing.model_copy(
                update={"status": "resolved", "resolution": resolution.strip()}
            )
    if patch.verification_summary.strip():
        runtime.verification_summary = patch.verification_summary.strip()
    return runtime


def evaluate_write_gate(
    runtime: ExecutiveRuntime, markdown: str
) -> WriteGateResult:
    if runtime.open_blocking_findings():
        return WriteGateResult(False, "unresolved_blocking_finding")
    if runtime.verified_artifact_fingerprint != artifact_fingerprint(markdown):
        return WriteGateResult(False, "artifact_changed_since_verification")
    return WriteGateResult(True)
```

- [ ] **Step 4: Attach one runtime to every artifact session**

Add to `ArtifactSession`:

```python
from app.teacher_agent.executive_verification import ExecutiveRuntime

executive: ExecutiveRuntime = field(default_factory=ExecutiveRuntime)
```

Do not duplicate this field inside `PlanRuntime` or `MemoryRuntime`.

- [ ] **Step 5: Run the focused test**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_executive_state.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/teacher_agent/executive_verification.py backend/app/services/artifact_session_service.py backend/tests/test_executive_state.py
git commit -m "feat: add shared executive verification state"
```

---

### Task 2: Add Authority Labels and the Compact Shared Prompt Contract

**Files:**
- Modify: `backend/app/teacher_agent/prompts.py:1-310`
- Modify: `backend/app/teacher_agent/prompt_assembly.py:190-545`
- Modify: `backend/app/teacher_agent/wiki/context_packs.py:205-390`
- Modify: `backend/tests/test_prompts.py`
- Modify: `backend/tests/test_plan_context_manager.py`

**Interfaces:**
- Consumes: `ExecutiveRuntime` from Task 1.
- Produces: `EXECUTIVE_VERIFICATION_POLICY`, `WRITE_VERIFICATION_SYSTEM`, authority-bearing context trace sections, and `render_executive_runtime(runtime)`.

- [ ] **Step 1: Add failing prompt contract tests**

```python
def test_shared_executive_policy_is_in_plan_and_ingest_prompts():
    for prompt in (rendered_plan_prompt(), rendered_ingest_prompt()):
        lowered = prompt.lower()
        assert "two jobs" in lowered
        assert "committed wiki is the baseline" in lowered
        assert "one consolidated clarification" in lowered
        assert "unresolved blocking finding" in lowered


def test_prompt_distinguishes_teacher_intent_from_teacher_factual_claims():
    policy = EXECUTIVE_VERIFICATION_POLICY.lower()
    assert "teacher controls the current task" in policy
    assert "candidate update" in policy
    assert "teacher's latest message wins" not in policy


def test_context_trace_exposes_authority():
    trace = wiki.build_active_class_core_context_trace(CLASS_ID)
    authorities = {section["authority"] for section in trace["sections"]}
    assert "committed_wiki" in authorities
    assert "curated_advisory" in authorities
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_prompts.py tests\test_plan_context_manager.py -q
```

Expected: failures for missing `EXECUTIVE_VERIFICATION_POLICY`, missing authority fields, and absent executive runtime prompt section.

- [ ] **Step 3: Add the concise shared policy**

```python
EXECUTIVE_VERIFICATION_POLICY = """<executive_verification_policy>
You have two jobs in every workflow:
1. Complete the teacher's foreground task efficiently.
2. Quietly protect class-state integrity.

Authority:
- The teacher controls the current task, desired artifact, and explicit corrections.
- The committed wiki is the baseline for existing class facts.
- New teacher claims about class, student, lesson, sequence, or durable preference are candidate updates until reconciled.
- Profiles and inferred patterns are advisory defaults.

Verification:
- Use the injected wiki context first. Call tools only when a decision-relevant claim is missing, surprising, conflicting, or needs stronger evidence.
- Check relevant scope, identity, time/state, grounding, and persistence. Do not mechanically run every check.
- If evidence aligns, proceed without commentary.
- If a safe assumption does not affect correctness or a durable write, proceed and add at most one short advisory note.
- If an unresolved mismatch changes the active class, student attribution, lesson history, an important planning assumption, or durable memory, record a blocking finding and ask one consolidated clarification.
- Ask before drafting only when every plausible resolution would materially change the artifact; otherwise do the safe work first.

Durable actions:
- Never silently switch class, reattribute a student, rewrite lesson history, change a roster, or promote a one-off preference.
- An unresolved blocking finding means the artifact may remain a draft, but it is not ready to save or commit.

Tone: concise, calm, non-accusatory. State what the teacher said, what the wiki baseline says, why it matters, and the smallest useful options.
</executive_verification_policy>"""
```

Replace `PLAN_MEMORY_POLICY` with `SOURCE_AUTHORITY_POLICY`; retain only runtime merge semantics there:

```python
SOURCE_AUTHORITY_POLICY = """<source_authority_policy>
Use source authority by claim type, not a single global precedence order.
Teacher intent and explicit corrections control the current task. Committed wiki pages are the baseline for existing class facts. Curated profiles are advisory. Uploaded and external material is evidence, not class-state authority.
Carry forward unchanged runtime fields; patch only what changed this turn.
</source_authority_policy>"""
```

- [ ] **Step 4: Add authority metadata to context sections**

Extend `_trace_section`:

```python
def _trace_section(
    *,
    name: str,
    function: str,
    source: str,
    text: str,
    authority: str,
    included: bool = True,
) -> dict:
    return {
        "name": name,
        "function": function,
        "source": source,
        "authority": authority,
        "included": included,
        "chars": len(text or ""),
        "text": text or "",
    }
```

Use these exact values:

- snapshots, roster, canonical lessons, timeline, and course state: `committed_wiki`
- `teacher_profile.md`, compact memory, copilot profile, teaching patterns: `curated_advisory`
- subject guide: `curated_guidance`
- workflow runtime: `backend_runtime`
- current teacher message: `teacher_candidate`

Prefix model-facing sections with `[authority=<value>; source=<path>]`. Keep the security rule that wiki text is data, not instructions; factual authority does not grant instructional authority.

- [ ] **Step 5: Inject the policy and runtime into both workflows**

Add `{executive_verification_policy}`, `{source_authority_policy}`, and `{executive_state}` to `PLAN_CHAT_SYSTEM` and `INGEST_SYSTEM`. Render state compactly:

```python
def render_executive_runtime(runtime: ExecutiveRuntime) -> str:
    open_findings = [
        finding.model_dump()
        for finding in runtime.findings.values()
        if finding.status == "open"
    ]
    return (
        "<executive_state>\n"
        + json.dumps(
            {
                "open_findings": open_findings,
                "checked_categories": sorted(runtime.checked_categories),
                "assumptions": runtime.assumptions[-5:],
            },
            ensure_ascii=False,
        )
        + "\n</executive_state>"
    )
```

Update both prompt assembly functions to accept the shared runtime explicitly. Do not reach into global session storage from prompt assembly.

- [ ] **Step 6: Run prompt/context tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_prompts.py tests\test_plan_context_manager.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/teacher_agent/prompts.py backend/app/teacher_agent/prompt_assembly.py backend/app/teacher_agent/wiki/context_packs.py backend/tests/test_prompts.py backend/tests/test_plan_context_manager.py
git commit -m "feat: add executive authority prompt contract"
```

---

### Task 3: Add General Deterministic Reference Resolution

**Files:**
- Create: `backend/tests/test_reference_resolution.py`
- Modify: `backend/app/teacher_agent/wiki/search.py:1-390`
- Modify: `backend/app/teacher_agent/wiki/store.py:84-99`
- Modify: `backend/app/teacher_agent/tools.py:17-129,348-570`

**Interfaces:**
- Consumes: `WikiStore.list_classes()`, class metadata, timeline, and roster/student index files.
- Produces: `ReferenceQuery`, `ReferenceMatch`, `ReferenceResolution`, `resolve_wiki_references(store, active_class_id, references, scope)`, `resolve_wiki_references` tool, and `report_verification_finding` tool.

- [ ] **Step 1: Write deterministic resolver tests**

```python
def test_student_reference_can_be_missing_active_but_match_other_class(eval_wiki):
    result = resolve_wiki_references(
        eval_wiki,
        active_class_id="chemie_9b_2026_27",
        references=[ReferenceQuery(kind="student", value="S-021")],
        scope="workspace",
    )
    item = result.items[0]
    assert item.status == "cross_class_match"
    assert item.matches[0].class_id == "chemie_9a_2026_27"
    assert item.matches[0].evidence_path.endswith("/students/index.md")


def test_lesson_date_resolves_against_active_timeline(eval_wiki):
    result = resolve_wiki_references(
        eval_wiki,
        active_class_id="chemie_9b_2026_27",
        references=[ReferenceQuery(kind="lesson", value="2026-09-14")],
        scope="active_class",
    )
    assert result.items[0].status == "active_class_match"


def test_unknown_reference_is_not_silently_reinterpreted(eval_wiki):
    result = resolve_wiki_references(
        eval_wiki,
        active_class_id="chemie_9b_2026_27",
        references=[ReferenceQuery(kind="student", value="S-999")],
        scope="workspace",
    )
    assert result.items[0].status == "unresolved"
    assert result.items[0].matches == []
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_reference_resolution.py -q
```

Expected: import or attribute failure because the resolver contracts do not yet
exist in `wiki.search`.

- [ ] **Step 3: Implement the bounded resolver**

Define:

```python
ReferenceKind = Literal["class", "student", "lesson"]
ReferenceScope = Literal["active_class", "workspace"]
ResolutionStatus = Literal[
    "active_class_match", "cross_class_match", "ambiguous", "unresolved"
]


class ReferenceQuery(BaseModel):
    kind: ReferenceKind
    value: str


class ReferenceMatch(BaseModel):
    class_id: str
    canonical_value: str
    label: str
    evidence_path: str


class ResolvedReference(BaseModel):
    query: ReferenceQuery
    status: ResolutionStatus
    matches: list[ReferenceMatch] = Field(default_factory=list)


class ReferenceResolution(BaseModel):
    active_class_id: str
    items: list[ResolvedReference]
```

Resolution rules:

1. Normalize whitespace/case and normalize `S-21` to `S-021`.
2. For a class reference, compare class ID and configured label.
3. For a student reference, parse only roster/index entries and student filenames; do not infer identity from lesson prose.
4. For a lesson reference, match ISO date exactly, then normalized title exactly.
5. Search active class first. Search other classes only for `scope="workspace"`.
6. Return all matches and an evidence path. Never choose among multiple matches.

- [ ] **Step 4: Expose one resolver tool**

```python
@function_tool
def resolve_wiki_references(
    references: list[ReferenceQuery],
    scope: str = "active_class",
) -> str:
    """Resolve class, student, or lesson references against committed wiki indexes.

    Call when a teacher-provided identifier may be unknown, ambiguous, or from
    another class. Use active_class first; use workspace only when cross-class
    mix-up is plausible. This tool resolves identifiers only. Use search/read
    tools for concepts, teaching history, or preferences.
    """
    result = ctx.wiki.resolve_wiki_references(
        ctx.class_id, references=references, scope=scope
    )
    return _capture(ctx.memory or ctx.planning, "reference", result.model_dump_json())
```

Add it to both `create_memory_update_tools` and `create_chat_wiki_tools`.

- [ ] **Step 5: Add explicit finding capture**

```python
@function_tool
def report_verification_finding(
    finding_id: str,
    category: str,
    severity: str,
    summary: str,
    question: str = "",
    evidence_refs: list[str] | None = None,
) -> str:
    """Record a decision-relevant discrepancy found while doing the main task.

    Use blocking only when the unresolved decision changes class scope, student
    attribution, lesson history, an important planning assumption, or a durable
    write. Use advisory when work remains correct and can continue. Do not call
    for aligned facts or harmless uncertainty.
    """
    finding = ExecutiveFinding(
        finding_id=finding_id,
        category=category,
        severity=severity,
        summary=summary,
        question=question,
        evidence_refs=evidence_refs or [],
    )
    ctx.executive.findings[finding.finding_id] = finding
    return f"Recorded {finding.severity} finding {finding.finding_id}."
```

Extend `WikiToolContext` with `executive: ExecutiveRuntime`. Tool-side capture is authoritative for emitted findings; structured output can resolve or summarize them but must not silently delete them.

- [ ] **Step 6: Run resolver and tool tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_reference_resolution.py tests\test_wiki_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/teacher_agent/wiki/search.py backend/app/teacher_agent/wiki/store.py backend/app/teacher_agent/tools.py backend/tests/test_reference_resolution.py backend/tests/test_wiki_tools.py
git commit -m "feat: add composable wiki reference verification"
```

---

### Task 4: Integrate Executive State into Every Artifact Turn

**Files:**
- Modify: `backend/app/teacher_agent/models.py:20-90`
- Modify: `backend/app/teacher_agent/agent.py:56-115`
- Modify: `backend/app/teacher_agent/agents.py:186-690`
- Modify: `backend/app/services/artifact_spec.py:58-115,145-280`
- Modify: `backend/app/services/artifact_session_service.py:189-469`
- Modify: `backend/app/teacher_agent/stream_events.py:34-49`
- Modify: `backend/tests/conftest.py:146-620`
- Modify: `backend/tests/test_workflow_contracts.py`

**Interfaces:**
- Consumes: shared runtime and tools from Tasks 1–3.
- Produces: `executive_patch` on every structured chat output, normalized `executive` payload on `TurnResult`, and `executive_state` on SSE final events.

- [ ] **Step 1: Add failing common-workflow tests**

```python
def test_registered_workflows_receive_shared_executive_runtime(default_specs):
    for spec in default_specs.values():
        assert spec.executive_verification is True


def test_blocking_finding_makes_structurally_complete_artifact_not_ready(client):
    response = chat_with_stub_finding(
        client, mode="plan", severity="blocking", structurally_complete=True
    )
    assert response.status_code == 200
    assert response.json()["ready_to_save"] is False
    assert response.json()["executive_state"]["status"] == "needs_decision"


def test_advisory_finding_does_not_block_ready_artifact(client):
    response = chat_with_stub_finding(
        client, mode="ingest", severity="advisory", structurally_complete=True
    )
    assert response.json()["ready_to_propose"] is True
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_workflow_contracts.py tests\test_api_plan.py tests\test_api_ingest.py -q
```

Expected: failures for missing executive spec/state fields and readiness ignoring findings.

- [ ] **Step 3: Extend structured turn outputs**

Add to both `PlanTurnOutput` and `IngestTurnOutput`:

```python
executive_patch: ExecutivePatch = Field(
    default_factory=ExecutivePatch,
    description=(
        "Verification categories checked, safe assumptions, finding resolutions, "
        "and a compact summary. Important new discrepancies must also be captured "
        "with report_verification_finding during the turn."
    ),
)
```

- [ ] **Step 4: Thread runtime explicitly through the common spec**

Change `ArtifactSpec.run_turn`, `stream_turn`, and `prompt_trace` to accept:

```python
runtime: Any,
executive: ExecutiveRuntime,
```

Add:

```python
executive_verification: bool = True
```

to `ArtifactSpec`. The workflow contract test must reject any future registered artifact workflow that opts out without an explicit documented exception.

- [ ] **Step 5: Merge state and calculate readiness**

In both `_finalize_plan_turn` and `_finalize_ingest_turn`:

```python
apply_executive_patch(executive, parsed.executive_patch)
structurally_ready = self.wiki.is_plan_ready(plan_md)  # diary equivalent for ingest
ready = structurally_ready and not executive.open_blocking_findings()
```

The agent may report an advisory in its reply. For blocking findings, ensure the reply contains one question; if it does not, append the finding's `question` once in finalization.

- [ ] **Step 6: Surface a compact API payload**

Implement:

```python
def executive_api_payload(runtime: ExecutiveRuntime) -> dict:
    open_findings = [
        finding.model_dump()
        for finding in runtime.findings.values()
        if finding.status == "open"
    ]
    return {
        "status": (
            "needs_decision"
            if any(item["severity"] == "blocking" for item in open_findings)
            else "advisory"
            if open_findings
            else "clear"
        ),
        "open_findings": open_findings,
        "assumptions": runtime.assumptions[-5:],
        "checked_categories": sorted(runtime.checked_categories),
        "verification_summary": runtime.verification_summary,
    }
```

Add `executive_state` to `TurnResult` and `SseFinal`.

- [ ] **Step 7: Update stub runners**

Make `StubAgentRunner` accept and return executive state for plan, ingest, and streaming paths. Add fixture controls for advisory/blocking findings instead of embedding a roster-only branch.

- [ ] **Step 8: Run common workflow tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_workflow_contracts.py tests\test_api_plan.py tests\test_api_ingest.py tests\test_api_stream.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```powershell
git add backend/app/teacher_agent/models.py backend/app/teacher_agent/agent.py backend/app/teacher_agent/agents.py backend/app/services/artifact_spec.py backend/app/services/artifact_session_service.py backend/app/teacher_agent/stream_events.py backend/tests/conftest.py backend/tests/test_workflow_contracts.py backend/tests/test_api_plan.py backend/tests/test_api_ingest.py backend/tests/test_api_stream.py
git commit -m "feat: run executive verification in artifact workflows"
```

---

### Task 5: Add Exact-Draft Verification at the Durable-Write Boundary

**Files:**
- Modify: `backend/app/teacher_agent/prompts.py`
- Modify: `backend/app/teacher_agent/models.py`
- Modify: `backend/app/teacher_agent/agent.py`
- Modify: `backend/app/teacher_agent/agents.py`
- Modify: `backend/app/services/artifact_session_service.py:446-469`
- Modify: `backend/app/services/plan_service.py:167-218`
- Modify: `backend/app/services/ingest_service.py:286-310,371-392`
- Modify: `backend/app/api/routes.py:1288-1310,1678-1710`
- Modify: `backend/app/schemas/api.py:327-450`
- Modify: `backend/tests/test_api_plan.py`
- Modify: `backend/tests/test_api_ingest.py`

**Interfaces:**
- Consumes: exact draft markdown, active class ID, authority-labeled context, existing findings, and read-only verification tools.
- Produces: `ArtifactVerificationOutput`, `AgentRunner.verify_artifact_for_write(...)`, and a fingerprint-bound `WriteGateResult`.

- [ ] **Step 1: Add failing write-boundary tests**

```python
def test_plan_save_runs_verification_for_exact_submitted_markdown(client, stub_agents):
    session = start_ready_plan(client)
    stub_agents.write_verification = ArtifactVerificationOutput(
        findings=[], checked_categories=["scope", "time_state"], summary="Clear."
    )
    response = client.post(
        f"/classes/{CLASS_ID}/plan/save",
        json={
            "session_id": session["session_id"],
            "lesson_date": "2026-09-21",
            "plan_markdown": session["plan_markdown"],
        },
    )
    assert response.status_code == 200
    assert stub_agents.verified_markdown == session["plan_markdown"]


def test_plan_save_returns_409_without_writing_for_blocking_finding(
    client, stub_agents, wiki
):
    session = start_ready_plan(client)
    stub_agents.write_verification = blocking_identity_output()
    response = save_plan(client, session)
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "unresolved_blocking_finding"
    assert not wiki.lesson_dir(CLASS_ID, "2026-09-21").exists()


def test_manual_edit_is_verified_instead_of_reusing_old_chat_result(
    client, stub_agents
):
    session = start_ready_plan(client)
    edited = session["plan_markdown"] + "\n- Student S-999 leads the demo.\n"
    save_plan(client, session, markdown=edited)
    assert stub_agents.verified_markdown == edited


def test_ingest_commit_rejects_changed_markdown_after_proposal(client):
    proposal = create_verified_ingest_proposal(client)
    changed = proposal["diary_markdown"] + "\n- S-999: new note\n"
    response = commit_ingest(client, proposal, diary_markdown=changed)
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "artifact_changed_since_verification"
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_plan.py tests\test_api_ingest.py -q
```

Expected: save/propose paths do not call a verifier, writes are not fingerprint-bound, and blocked responses are absent.

- [ ] **Step 3: Define the focused verifier output and prompt**

```python
class ArtifactVerificationOutput(BaseModel):
    findings: list[ExecutiveFinding] = Field(default_factory=list)
    checked_categories: list[VerificationCategory] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    summary: str
```

```python
WRITE_VERIFICATION_SYSTEM = """You verify the exact current teacher artifact before a durable action.

Use the committed wiki as the baseline for existing class facts and the teacher's explicit decisions as authority for corrections. Check only claims in the artifact that could change class scope, student attribution, lesson history/sequence, important planning assumptions, or durable memory.

Use injected context first and read-only tools when evidence is missing. Return blocking findings only when the teacher must decide before writing. Return advisory findings for non-blocking assumptions. Do not rewrite the artifact, infer a correction, or create a finding for harmless missing detail.

Every finding must state the mismatch, why it matters, one concise question for blocking cases, and evidence refs when tools were used."""
```

- [ ] **Step 4: Implement the verifier call**

```python
async def verify_artifact_for_write(
    self,
    *,
    class_id: str,
    mode: str,
    markdown: str,
    executive: ExecutiveRuntime,
) -> ArtifactVerificationOutput:
    ctx = self._wiki_ctx(class_id, executive=executive)
    agent = build_artifact_verifier_agent(
        ctx,
        model=self.chat_model,
        reasoning_effort=self.chat_effort,
    )
    prompt = build_write_verification_prompt(
        self.wiki,
        class_id=class_id,
        mode=mode,
        markdown=markdown,
        executive=executive,
    )
    return await self._run_structured(agent, prompt)
```

Use the same resolver/read tools; do not attach `remember` or any write-capable service.

- [ ] **Step 5: Verify at proposal/save and bind the fingerprint**

For ingest:

1. `propose` compiles/updates the exact diary.
2. Call `verify_artifact_for_write`.
3. Merge findings.
4. If blocking, return HTTP 409 and keep the session in chat/review with findings.
5. If clear/advisory, call `mark_verified(diary_md)` and create the proposal.
6. `commit` calls `evaluate_write_gate` against `req.diary_markdown` immediately before `wiki.commit_ingest`.

For planning:

1. Make `PlanService.save` and the route async.
2. Verify `req.plan_markdown`.
3. If blocking, return HTTP 409 before `save_lesson_plan`.
4. Mark that exact markdown verified.
5. Re-evaluate the gate immediately before the write.

- [ ] **Step 6: Invalidate stale verification on every draft edit**

In `ArtifactSessionService.update_draft` and `set_markdown`:

```python
if markdown != session.partial_markdown:
    session.executive.invalidate_verification()
session.partial_markdown = markdown
```

Do not clear findings; a manual edit may resolve one, but only a teacher message or the verifier can record that resolution.

- [ ] **Step 7: Return typed blocked-action details**

Use HTTP 409:

```json
{
  "detail": {
    "reason": "unresolved_blocking_finding",
    "message": "One class-state decision is needed before saving.",
    "executive_state": {}
  }
}
```

Do not return an internal exception or model trace.

- [ ] **Step 8: Run write-gate tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_plan.py tests\test_api_ingest.py tests\test_executive_state.py -q
```

Expected: all tests pass and no test makes an OpenAI call.

- [ ] **Step 9: Commit**

```powershell
git add backend/app/teacher_agent/prompts.py backend/app/teacher_agent/models.py backend/app/teacher_agent/agent.py backend/app/teacher_agent/agents.py backend/app/services/artifact_session_service.py backend/app/services/plan_service.py backend/app/services/ingest_service.py backend/app/api/routes.py backend/app/schemas/api.py backend/tests/test_api_plan.py backend/tests/test_api_ingest.py
git commit -m "feat: gate durable writes on exact-draft verification"
```

---

### Task 6: Add Minimal Shared UI for Decisions and Save Checks

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/sse-chat.ts:34-88`
- Modify: `frontend/src/components/assistant-ui/artifact-runtime-config.ts:9-135`
- Modify: `frontend/src/components/assistant-ui/artifact-session-runtime.tsx:25-340`
- Modify: `frontend/src/app/classes/[classId]/plan/page.tsx`
- Modify: `frontend/src/app/classes/[classId]/memory/page.tsx`

**Interfaces:**
- Consumes: `executive_state` from REST/SSE and typed HTTP 409 details.
- Produces: shared `ExecutiveState` TypeScript type and one compact status component used by both workflows.

- [ ] **Step 1: Add TypeScript types**

```typescript
export type ExecutiveFinding = {
  finding_id: string;
  category:
    | "scope"
    | "identity"
    | "time_state"
    | "grounding"
    | "persistence"
    | "consequence";
  severity: "advisory" | "blocking";
  summary: string;
  question: string;
  evidence_refs: string[];
  status: "open" | "resolved" | "dismissed";
  resolution: string;
};

export type ExecutiveState = {
  status: "clear" | "advisory" | "needs_decision";
  open_findings: ExecutiveFinding[];
  assumptions: string[];
  checked_categories: string[];
  verification_summary: string;
};
```

- [ ] **Step 2: Thread the state through the existing runtime**

Add `executiveState` next to `memoryState` in `ArtifactChatResult`, provider state, SSE final parsing, and context value. Do not create a second session runtime.

- [ ] **Step 3: Render one compact shared status**

Behavior:

- `clear`: render nothing.
- `advisory`: render one muted line using the first advisory summary.
- `needs_decision`: render “Needs your decision” and the first blocking question; the assistant message remains the main interaction surface.
- While a save/proposal verifier is running: relabel the button “Checking class state…”.
- On HTTP 409: keep the draft, restore chat mode, update executive state, and focus the composer.

Do not add a modal, checklist, separate validation page, or one control per finding.

- [ ] **Step 4: Run frontend checks**

Run:

```powershell
cd frontend
npm run lint
npm run typecheck
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/lib/api.ts frontend/src/lib/sse-chat.ts frontend/src/components/assistant-ui/artifact-runtime-config.ts frontend/src/components/assistant-ui/artifact-session-runtime.tsx frontend/src/app/classes/[classId]/plan/page.tsx frontend/src/app/classes/[classId]/memory/page.tsx
git commit -m "feat: surface executive verification decisions"
```

---

### Task 7: Replace the Single-Failure Eval with a General Behavior Matrix

**Files:**
- Create: `backend/tests/evals/goldens/executive_verification.yaml`
- Modify: `backend/tests/evals/test_klassenpilot_wiki_reconciliation.py`
- Modify: `backend/tests/eval/plan_trace_scorer.py`
- Modify: `backend/tests/eval/ingest_trace_scorer.py`
- Modify: `backend/tests/eval/test_memory_update_contract.py`

**Interfaces:**
- Consumes: trace events, executive state, tool calls, reply, artifact, and write result.
- Produces: deterministic contract checks plus optional live model/judge evaluation.

- [ ] **Step 1: Create the golden matrix**

Build the fixture from two sources:

1. sanitized adaptations of real beta conversations from
   `BETA_DATA_ROOT/beta.sqlite3`;
2. synthetic cases for cross-class combinations not yet present in telemetry.

Never commit raw telemetry, tester/workspace IDs, real names, or verbatim
student observations. Preserve the behavioral shape, replace people with
pseudonymous IDs, shorten incidental content, and add:

```yaml
provenance:
  source: beta_telemetry
  captured_on: 2026-07-08
  transformation: sanitized_semantic_adaptation
  contains_raw_transcript: false
```

The beta-derived scenarios must include:

- a final forgotten teacher note arriving after the last completed agent turn;
- a known student name that should resolve to a pseudonymous student ID without
  an unnecessary question;
- invalid student references that should be held out of the write;
- one messy message containing an artifact update, a local communication
  request, a possible durable teaching preference, and future curriculum ideas;
- a one-off request for a concise/MBB-style artifact that should be applied
  locally and not promoted to durable preference;
- a planned future concept such as hybridization/aromaticity that must not be
  recorded as already taught;
- an explicit transition from one unit to a new unit that should not be blocked
  merely because the wiki still reflects the completed unit;
- a request to ground a plan in the two most recent lessons;
- repeated retry/duplicate messages that must not count as independent
  preference reinforcement.

Include these exact scenario classes:

```yaml
cases:
  - id: aligned_student_reference
    category: identity
    expected: invisible
    must_block: false
    max_questions: 0

  - id: student_in_other_class
    category: scope
    expected: blocking
    must_use_reference_resolution: true
    must_block: true
    max_questions: 1

  - id: unknown_student_reference
    category: identity
    expected: blocking
    must_block: true
    max_questions: 1

  - id: stale_wiki_teacher_explicitly_corrects_class
    category: scope
    expected: blocking_until_confirmed
    teacher_can_override_baseline: true
    max_questions: 1

  - id: lesson_date_conflicts_with_timeline
    category: time_state
    expected: blocking
    must_block: true
    max_questions: 1

  - id: topic_not_yet_taught_but_used_as_review
    category: time_state
    expected: advisory
    must_block: false
    max_questions: 0

  - id: one_off_hands_on_request
    category: persistence
    expected: invisible
    must_capture_durable_preference: false
    max_questions: 0

  - id: repeated_hands_on_preference
    category: persistence
    expected: advisory_candidate
    must_block: false
    max_questions: 0

  - id: harmless_sparse_detail
    category: grounding
    expected: invisible
    must_block: false
    max_questions: 0

  - id: two_related_conflicts
    category: consequence
    expected: one_consolidated_question
    must_block: true
    max_questions: 1

  - id: manual_edit_after_verification
    category: consequence
    expected: reverify_exact_artifact
    must_block_stale_fingerprint: true

  - id: beta_forgotten_final_note
    provenance: beta_telemetry
    category: consequence
    expected: block_until_latest_turn_complete
    must_block: true

  - id: beta_known_name_to_pseudonym
    provenance: beta_telemetry
    category: identity
    expected: invisible_resolution
    must_block: false
    max_questions: 0

  - id: beta_mixed_artifact_and_durable_signals
    provenance: beta_telemetry
    category: persistence
    expected: decompose_and_continue
    must_update_artifact: true
    must_stage_supported_durable_candidates: true
    max_questions: 1

  - id: beta_future_concept_not_taught
    provenance: beta_telemetry
    category: time_state
    expected: preserve_future_scope
    must_not_write_as_taught: true
    max_questions: 0

  - id: beta_one_off_formatting_request
    provenance: beta_telemetry
    category: persistence
    expected: invisible_local_adaptation
    must_capture_durable_preference: false
    max_questions: 0

  - id: beta_explicit_unit_transition
    provenance: beta_telemetry
    category: time_state
    expected: proceed_with_soft_context_note
    must_block: false
    max_questions: 0

  - id: beta_duplicate_retry
    provenance: beta_telemetry
    category: persistence
    expected: dedupe_same_signal
    reinforcement_count: 1

  - id: beta_ground_in_last_two_lessons
    provenance: beta_telemetry
    category: grounding
    expected: retrieve_and_cite
    must_block: false
    max_questions: 0
```

- [ ] **Step 2: Add deterministic assertions**

For every stub scenario assert:

- expected finding category and severity;
- no more than one question mark in the decision request;
- no write when blocking;
- exact evidence ref for tool-backed mismatch;
- no unnecessary tool call for context-pack-resolved facts;
- advisory and clean cases remain ready when structurally complete;
- teacher-confirmed corrections resolve rather than disappear;
- saved/committed fingerprint equals verified fingerprint.

- [ ] **Step 3: Update trace scorers**

Score these independent dimensions from 0–2:

1. `foreground_task_progress`
2. `relevant_verification`
3. `evidence_quality`
4. `interruption_calibration`
5. `decision_rights`
6. `durable_write_safety`

Penalize both missed conflicts and over-interruption. A clean case that asks an unnecessary question cannot receive full credit.

- [ ] **Step 4: Add LLM-as-judge coverage for semantic behavior**

Reuse the existing live-eval and DeepEval/judge path in
`test_klassenpilot_wiki_reconciliation.py`. The judge receives only the
sanitized fixture, wiki evidence, agent reply, tool trace, and resulting
artifact. It scores:

- whether the foreground task was completed;
- whether the important mismatch or temporal distinction was noticed;
- whether the assistant asked only for a teacher-owned decision;
- whether planned concepts stayed distinct from taught concepts;
- whether local style adaptation was kept separate from durable preference;
- whether the tone treated messy input as normal rather than teacher error.

Deterministic tests remain the merge gate. Judge evals are calibration evidence
and should report score changes without making local development depend on an
external model call.

- [ ] **Step 5: Run deterministic evals**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\evals\test_klassenpilot_wiki_reconciliation.py tests\eval\test_memory_update_contract.py -q
```

Expected: all deterministic scenarios pass; live tests remain skipped unless their existing live-eval flag is enabled.

- [ ] **Step 6: Run the optional judge eval bundle**

Use the repository's existing live-eval flag and model routing; do not add a
second judge framework. Expected result: each sanitized case reports dimension
scores and rationale, while local deterministic test runs continue to skip it.

- [ ] **Step 7: Commit**

```powershell
git add backend/tests/evals/goldens/executive_verification.yaml backend/tests/evals/test_klassenpilot_wiki_reconciliation.py backend/tests/eval/plan_trace_scorer.py backend/tests/eval/ingest_trace_scorer.py backend/tests/eval/test_memory_update_contract.py
git commit -m "test: generalize executive verification evals"
```

---

### Task 8: Update Durable Product and Agent Contracts

**Files:**
- Modify: `docs/agent_contracts.md`
- Modify: `docs/agent_architecture.md`
- Modify: `docs/product_vision.md`
- Modify: `docs/pm_hub.md`
- Modify: `implementation_plans/product_backlog.md`

**Interfaces:**
- Consumes: implemented behavior from Tasks 1–7.
- Produces: the reviewable contract future workflows must follow.

- [ ] **Step 1: Document the common foundation**

Add to `docs/agent_contracts.md`:

```markdown
## Executive verification contract

Every class-scoped interaction has two responsibilities:

1. complete the teacher's foreground task;
2. protect class-state integrity in the background.

Teacher intent controls the current task. Committed wiki state is the baseline
for existing class facts. Teacher factual input that differs from the wiki is a
candidate correction, not an automatic overwrite.

All artifact workflows share `ExecutiveRuntime`. They use authority-labeled
base context, retrieve only when a consequential claim needs evidence, and
classify findings as invisible, advisory, or blocking. At most one consolidated
clarification is asked per turn.

Plan save and memory proposal/commit require verification of the exact artifact
fingerprint and no unresolved blocking findings. Validation is repeated next to
the durable side effect. Chat tools remain read-only.
```

- [ ] **Step 2: Document future workflow inheritance**

In `docs/agent_architecture.md`, show:

```text
ArtifactSession
├── ExecutiveRuntime (shared)
├── workflow runtime (PlanRuntime, MemoryRuntime, future runtime)
├── authority-labeled context pack
├── shared verification tools
└── workflow-specific tools and artifact policy
```

State that general class chat should reuse the same foundation even when it has no artifact, with durable-write gating activated only when an action is proposed.

- [ ] **Step 3: Correct roadmap wording**

In `docs/pm_hub.md`, replace the narrow “deterministic conflict detection first, starting with roster” framing with:

> Build a general executive-verification foundation first; roster mismatch is the initial acceptance case, not the architecture.

Retain roster mismatch as a concrete eval and beta signal.

- [ ] **Step 4: Record implementation sequencing**

In `implementation_plans/product_backlog.md`, split delivery into:

1. shared runtime + authority prompt;
2. reference resolver + proactive chat behavior;
3. exact-draft durable-write gate;
4. behavior matrix + beta telemetry.

Do not mix in PR5’s focus-grouped skills/subagent refactor.

- [ ] **Step 5: Commit**

```powershell
git add docs/agent_contracts.md docs/agent_architecture.md docs/product_vision.md docs/pm_hub.md implementation_plans/product_backlog.md
git commit -m "docs: define executive verification product contract"
```

---

### Task 9: Run the Integrated Deterministic Verification

**Files:**
- No production files added in this task.
- Fix only failures caused by Tasks 1–8.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a verified implementation ready for HITL evaluation.

- [ ] **Step 1: Run the focused backend suite**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_executive_state.py tests\test_reference_resolution.py tests\test_wiki_tools.py tests\test_prompts.py tests\test_plan_context_manager.py tests\test_workflow_contracts.py tests\test_api_plan.py tests\test_api_ingest.py tests\test_api_stream.py -q
```

Expected: all tests pass with no OpenAI calls.

- [ ] **Step 2: Run deterministic behavior evals**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\evals\test_klassenpilot_wiki_reconciliation.py tests\eval\test_memory_update_contract.py -q
```

Expected: all deterministic evals pass; explicitly live-marked evals remain skipped.

- [ ] **Step 3: Run frontend validation**

```powershell
cd frontend
npm run lint
npm run typecheck
```

Expected: both commands pass.

- [ ] **Step 4: Run the repo deterministic suite**

```powershell
cd ..
.\scripts\test.ps1
```

Expected: the suite exits successfully.

- [ ] **Step 5: Perform optional HITL only after deterministic success**

```powershell
.\scripts\worktree-stack.cmd up --app-env production --model-profile production --fresh-wiki
```

Exercise:

1. clean plan request — no visible verification bureaucracy;
2. cross-class student mismatch — useful work plus one decision;
3. teacher correction of stale wiki — correction is accepted only after confirmation;
4. manual draft edit introducing an unknown student — save checks the edited draft;
5. one-off hands-on request — adapts without creating a durable preference;
6. memory commit with an unresolved mismatch — no wiki file changes.

- [ ] **Step 6: Report completion evidence**

Report:

- worktree and branch;
- exact tests/evals run and results;
- whether Docker was started and the frontend URL;
- wiki files changed during HITL;
- model profile used for HITL;
- known false-positive/false-negative cases;
- follow-up telemetry needed before broadening reference kinds.

---

## Teacher Sanity and Smoke-Test Checkpoints

Do not wait until the entire project is complete for teacher feedback. Stop at
these checkpoints and run the worktree stack with a fresh sandbox wiki.

### Checkpoint A: Product contract and prompt behavior

Included:

- compact executive-assistant policy;
- authority-labeled context;
- no new durable gate or frontend state yet.

Teacher smoke cases:

1. Ask for a normal grounded lesson plan. Expected: useful plan, no verification
   commentary when nothing is surprising.
2. Add a new planned concept such as the Chapman cycle. Expected: the plan
   changes without recording the concept as already taught.
3. Ask for an MBB-style rewrite. Expected: local adaptation without a durable
   preference proposal.
4. Explicitly start a new unit after the previous unit. Expected: proceed
   without an unnecessary blocking question.

Decision after smoke: confirm that the prompt feels proactive without becoming
skeptical or bureaucratic.

### Checkpoint B: Reference resolution and proactive findings

Included:

- shared executive runtime;
- general class/student/lesson resolver;
- advisory vs blocking findings;
- writes still use the existing teacher review path.

Teacher smoke cases:

1. Use a valid student ID. Expected: no visible check.
2. Use an unknown student ID. Expected: useful draft plus one concise decision,
   depending on whether the observation can safely be held out.
3. Use a student from another class. Expected: the assistant shows both class
   facts and asks which attribution is intended.
4. Give two related inconsistencies. Expected: one consolidated question, not
   two or more.

Decision after smoke: tune the severity threshold and wording before durable
gating is enabled.

### Checkpoint C: Exact-draft durable-write protection

Included:

- pre-write verifier;
- artifact fingerprint;
- plan save and memory propose/commit gates;
- minimal shared status UI.

Teacher smoke cases:

1. Manually add an unknown student after the final chat turn, then save.
   Expected: the edited draft is checked and the write pauses.
2. Resolve the student/class decision, then save. Expected: the same artifact
   writes without another redundant question.
3. Send a final note while a streamed turn is unfinished and immediately try to
   commit. Expected: no commit until the latest turn is incorporated.
4. Create an advisory-only assumption. Expected: save remains possible.

Decision after smoke: confirm that safety does not add an extra review step to
clean workflows.

### Checkpoint D: Beta-derived calibration

Included:

- sanitized beta golden set;
- deterministic behavior assertions;
- optional LLM-as-judge report.

Review:

- missed consequential inconsistencies;
- unnecessary interruptions;
- incorrect durable-preference capture;
- future concepts incorrectly recorded as taught;
- duplicate retries counted as independent evidence;
- foreground task quality degradation.

Decision after smoke: expand reference kinds only when telemetry shows a
repeated gap. Do not add a new tool for each isolated miss.

---

## Delivery Recommendation

Review this as four pull requests, not one large refactor:

1. **Foundation / Checkpoint A:** compact product contract, authority labels,
   and prompt behavior.
2. **Proactive chat / Checkpoint B:** shared runtime, reference resolver,
   findings, and initial deterministic cases.
3. **Durable safety / Checkpoint C:** exact-draft write gate and minimal shared
   UI.
4. **Calibration / Checkpoint D:** sanitized beta cases, LLM-as-judge report,
   remaining docs, and integrated validation.

Each PR leaves the product in a working state. The first acceptance scenario remains the observed roster/class mismatch, but the implementation boundary is the general executive-verification contract.

## Explicit Non-Goals for This Plan

- No focus-grouped agent-skill or subagent-capability refactor from PR5.
- No autonomous wiki correction.
- No semantic “verify every claim” mega-tool.
- No new vector database or cross-class embedding index.
- No separate validation workflow visible to the teacher.
- No mandatory retrieval/tool call on every chat turn.
- No durable preference inferred from a single one-off instruction.
- No replacement of the existing memory candidate/sweep system.

## OpenAI Implementation Guidance Applied

- Function tools remain narrow, structured interfaces; tool descriptions specify when to call them and how to construct arguments.
- The model decides whether evidence tools are needed, while backend code enforces durable side-effect policy.
- Automatic validation and human decision rights are separate controls.
- Validation is placed next to the durable side effect, not only in an agent-level prompt.
- Structured state and traces make missed checks and over-interruption independently evaluable.

Relevant official guidance:

- https://developers.openai.com/api/docs/guides/tools
- https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
