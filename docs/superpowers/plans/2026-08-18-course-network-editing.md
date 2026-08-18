# Course Network Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a teacher safely edit an adopted class course network at any time, either directly or with agent assistance, while preserving explicit review, deterministic validation, LLM checking, and stale-write protection.

**Architecture:** Treat every change as typed graph operations against a base network revision. Store the proposal as stable JSON in the existing `WorkflowDraftStore`, render the proposed graph without changing canonical wiki files, run deterministic and no-tools LLM review against the exact proposal fingerprint, then atomically replace `network.json` only after teacher approval. The frontend uses React Flow as an editor view and a dedicated operation-review panel composed with the existing review chrome.

**Tech Stack:** FastAPI, Pydantic 2, OpenAI Agents SDK, existing `ExecutiveRuntime` and `WorkflowDraftStore`, stdlib JSON, Next.js 15, React 19, TypeScript, Zustand, `@xyflow/react`, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-17-class-course-network-design.md`

## Global Constraints

- This plan starts after `2026-08-18-course-network-foundation.md` is merged.
- The editor is a permanent course-workspace capability, not part of lesson planning.
- Canonical writes happen only after explicit teacher approval.
- One node type remains `Lernbaustein`; `learning_goal` is optional.
- Allowed edge relations remain `builds_on` and `related_to`.
- The operation list is the review contract; do not turn operations into fake Markdown file diffs.
- A proposal is bound to `base_revision`, `artifact_revision`, and `artifact_hash`.
- Agent assistance proposes operations only; it cannot approve or commit them.
- Every accepted write rebuilds `course_network/overview.md` atomically with `network.json`.
- No new frontend or backend dependency is introduced in this plan.

---

## PR B1 - Typed Operations, Review, and Atomic Commit

### Task 1: Define the graph-operation contract and pure application function

**Files:**
- Create: `backend/app/course_network/operations.py`
- Modify: `backend/app/course_network/models.py`
- Test: `backend/tests/test_course_network_operations.py`

**Interfaces:**

```python
class AddNode(BaseModel):
    op: Literal["add_node"]
    node: LearningBlock

class UpdateNode(BaseModel):
    op: Literal["update_node"]
    node_id: str
    changes: LearningBlockPatch

class DeleteNode(BaseModel):
    op: Literal["delete_node"]
    node_id: str

class AddEdge(BaseModel):
    op: Literal["add_edge"]
    edge: NetworkEdge

class DeleteEdge(BaseModel):
    op: Literal["delete_edge"]
    edge_id: str

GraphOperation = Annotated[
    AddNode | UpdateNode | DeleteNode | AddEdge | DeleteEdge,
    Field(discriminator="op"),
]

class NetworkChangeSet(BaseModel):
    class_id: str
    base_revision: int
    summary: str
    operations: list[GraphOperation]

def apply_change_set(
    current: CourseNetworkDocument,
    change_set: NetworkChangeSet,
) -> CourseNetworkDocument: ...
```

- [ ] **Step 1: Write failing operation tests**

Cover add/update/retire node, add/delete edge, cascading active edge and mapping
removal when a node is retired, stable operation order, unknown identifiers,
duplicate identifiers, empty changes, and a mismatched class or base revision.

```python
def test_delete_node_retires_node_and_removes_incident_edges(network):
    changed = apply_change_set(
        network,
        NetworkChangeSet(
            class_id=network.class_id,
            base_revision=network.revision,
            summary="Remove obsolete block",
            operations=[DeleteNode(op="delete_node", node_id="stoffmenge")],
        ),
    )
    retired = next(node for node in changed.nodes if node.id == "stoffmenge")
    assert retired.status == "retired"
    assert all(
        "stoffmenge" not in {edge.source_id, edge.target_id}
        for edge in changed.edges
    )
```

- [ ] **Step 2: Run the focused test and confirm failure**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_network_operations.py -v
```

Expected: import failure for `app.course_network.operations`.

- [ ] **Step 3: Implement discriminated operations and pure application**

Copy the input document before applying operations. `DeleteNode` is a
teacher-facing delete but creates a retired tombstone so historical lesson
references remain resolvable; remove its active edges, mappings, and position.
Increment the network revision exactly once per accepted change set, not once
per operation. Preserve the existing node position unless `position` is
explicitly supplied. Reject an empty operation list.

- [ ] **Step 4: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest tests\test_course_network_operations.py -v
git add backend/app/course_network/models.py backend/app/course_network/operations.py backend/tests/test_course_network_operations.py
git commit -m "feat: define course network operations"
```

### Task 2: Add deterministic semantic validation

**Files:**
- Modify: `backend/app/course_network/validation.py`
- Create: `backend/app/course_network/impact.py`
- Test: `backend/tests/test_course_network_validation.py`
- Test: `backend/tests/test_course_network_impact.py`

**Interfaces:**

```python
class NetworkValidationIssue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)

class NetworkValidationResult(BaseModel):
    valid: bool
    issues: list[NetworkValidationIssue]

def validate_network(document: CourseNetworkDocument) -> NetworkValidationResult: ...

class NetworkChangeImpact(BaseModel):
    material_mapping_ids: list[str] = Field(default_factory=list)
    lesson_dates: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)

def analyze_change_impact(
    store: WikiStore,
    current: CourseNetworkDocument,
    change_set: NetworkChangeSet,
) -> NetworkChangeImpact: ...
```

- [ ] **Step 1: Write failing validator tests**

Errors: duplicate IDs, dangling edges, active references to retired nodes,
self-referential `builds_on`, direct two-node `builds_on` cycles, empty title,
invalid source span, and oversized node content. Warnings: isolated node,
duplicate normalized title, and a longer `builds_on` cycle. `related_to` cycles
are allowed. Separately assert that delete-impact analysis returns affected
mapping IDs, edges, and lesson dates without treating historical references as
dangling graph data.

- [ ] **Step 2: Implement deterministic checks**

Use stable issue ordering by severity, code, and first affected identifier.
Keep size limits in `backend/app/context_limits.py` so runtime and tests use one
source. Return all issues in one pass. Implement impact analysis as a read-only
scan of canonical mappings and lesson sidecars; include it in every proposed
result and require explicit `impact_acknowledged` on commit when non-empty.

- [ ] **Step 3: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_network_validation.py tests\test_course_network_impact.py tests\test_context_limits.py -v
git add backend/app/course_network/validation.py backend/app/course_network/impact.py backend/app/context_limits.py backend/tests/test_course_network_validation.py backend/tests/test_course_network_impact.py backend/tests/test_context_limits.py
git commit -m "feat: validate course network changes"
```

### Task 3: Reuse the executive review lifecycle with a graph-specific reviewer

**Files:**
- Modify: `backend/app/course_network/review.py`
- Modify: `backend/app/course_network/prompts.py`
- Modify: `backend/app/teacher_agent/executive_verification.py`
- Modify: `backend/app/teacher_agent/agents.py`
- Modify: `backend/app/teacher_agent/models.py`
- Test: `backend/tests/test_course_network_review.py`
- Test: `backend/tests/test_executive_verification.py`

**Interfaces:**

```python
class NetworkReviewOutput(BaseModel):
    decision: Literal["pass", "revise", "block"]
    summary: str
    findings: list[NetworkReviewFinding]

class NetworkReviewSnapshot(BaseModel):
    base_revision: int
    artifact_revision: int
    artifact_hash: str
    deterministic: NetworkValidationResult
    llm: NetworkReviewOutput

async def review_change_set(
    *,
    current: CourseNetworkDocument,
    change_set: NetworkChangeSet,
    artifact_revision: int,
    artifact_hash: str,
) -> NetworkReviewSnapshot: ...
```

- [ ] **Step 1: Write failing tests for the exact-artifact review gate**

Assert that deterministic errors skip LLM review and block; warnings still run
review; LLM `revise` or `block` prevents commit; a changed artifact hash clears
the active review; and the reviewer receives only current network, proposed
operations, proposed result, and provenance excerpts.

- [ ] **Step 2: Extract only generic lifecycle helpers**

Keep `ExecutiveRuntime`, `artifact_fingerprint`, active-review identity, and
`evaluate_write_gate` generic. Do not reuse the generic Markdown review prompt
for graph semantics. Add a small protocol or callback so both plan/memory and
course review use the same revision/fingerprint lifecycle without branching on
course modes inside existing prompts.

- [ ] **Step 3: Implement the bounded no-tools reviewer**

The system prompt checks curriculum fidelity, factual safety, coherent
prerequisites, accidental deletion, source grounding, and harmful or
inappropriate content. It must not invent operations and must return the typed
`NetworkReviewOutput`. Follow the same configured reviewer model policy used by
plan verification.

- [ ] **Step 4: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_network_review.py tests\test_executive_verification.py tests\test_plan_verification.py -v
git add backend/app/course_network/review.py backend/app/course_network/prompts.py backend/app/teacher_agent/executive_verification.py backend/app/teacher_agent/agents.py backend/app/teacher_agent/models.py backend/tests/test_course_network_review.py backend/tests/test_executive_verification.py
git commit -m "feat: review course network proposals"
```

### Task 4: Persist structured edit drafts through `WorkflowDraftStore`

**Files:**
- Modify: `backend/app/services/workflow_drafts.py`
- Create: `backend/app/course_network/edit_service.py`
- Test: `backend/tests/test_course_network_edit_service.py`
- Test: `backend/tests/test_workflow_drafts.py`

**Interfaces:**

```python
def open_structured_draft(
    store: WorkflowDraftStore,
    identity: WorkflowDraftIdentity,
    *,
    default_status: str,
    artifact: BaseModel | dict[str, Any],
    runtime_json: dict[str, Any] | None = None,
) -> OpenWorkflowDraftResult: ...

def save_structured_draft(
    store: WorkflowDraftStore,
    *,
    draft_id: str,
    status: str,
    artifact: BaseModel | dict[str, Any],
    runtime_json: dict[str, Any] | None,
    executive_json: dict[str, Any] | None = None,
) -> WorkflowDraftRow: ...
```

- [ ] **Step 1: Write failing stable-serialization and edit-service tests**

Serialize with sorted keys and compact separators into the existing
`artifact_markdown` column. Assert semantically identical objects keep the same
revision/hash; a real operation change increments revision; mode is
`course_network`; intent is `edit`; and opening a second active edit returns the
existing draft.

- [ ] **Step 2: Implement structured helpers without a database migration**

Keep the existing column name for compatibility. Parsing errors must include
the draft ID and never fall back to an empty operation list.

- [ ] **Step 3: Implement edit draft orchestration**

`open_edit`, `replace_change_set`, `review_edit`, and `discard_edit` must verify
class ownership. Replacing operations clears the active review while retaining
previous messages and runtime data.

- [ ] **Step 4: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_network_edit_service.py tests\test_workflow_drafts.py -v
git add backend/app/services/workflow_drafts.py backend/app/course_network/edit_service.py backend/tests/test_course_network_edit_service.py backend/tests/test_workflow_drafts.py
git commit -m "feat: persist course network edit drafts"
```

### Task 5: Add edit, review, and commit endpoints with optimistic concurrency

**Files:**
- Create: `backend/app/api/course_network_routes.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/schemas/api.py`
- Modify: `backend/app/course_network/edit_service.py`
- Test: `backend/tests/test_api_course_network_edit.py`

**Routes:**

```text
POST   /api/classes/{class_id}/course/network/edits
GET    /api/classes/{class_id}/course/network/edits/{draft_id}
PUT    /api/classes/{class_id}/course/network/edits/{draft_id}
POST   /api/classes/{class_id}/course/network/edits/{draft_id}/review
POST   /api/classes/{class_id}/course/network/edits/{draft_id}/commit
DELETE /api/classes/{class_id}/course/network/edits/{draft_id}
```

- [ ] **Step 1: Write failing API contract tests**

Cover ownership 404, missing adopted network 409, malformed operations 422,
review-required 409, review-blocked 422, stale base revision 409, stale artifact
hash 409, successful atomic commit, overview rebuild, and terminal draft status.

- [ ] **Step 2: Implement request and response schemas**

Every mutation request after draft creation carries
`expected_artifact_revision` and `expected_artifact_hash`. Commit also carries
`expected_network_revision`. Return a normalized `CourseNetworkEditDraftView`
containing current network, proposed result, operations, validation, review,
and allowed actions.

- [ ] **Step 3: Implement atomic commit**

Acquire the existing wiki store write lock, reload the current document, check
its revision, reapply the reviewed change set, convert accepted node status to
`adopted`, revalidate, evaluate the exact review gate, and atomically replace
`network.json`. That JSON replacement is the commit point. Regenerate the
rebuildable overview afterward; if rendering fails, keep the canonical JSON,
mark overview repair as required, and keep reads able to rebuild it. If the
canonical replacement fails, leave the prior network unchanged and the draft
active. On success, append the affected canonical paths and proposal summary to
the existing class wiki `log.md` with an empty lesson date so course maintenance
does not alter latest-lesson rollups.

- [ ] **Step 4: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_course_network_edit.py tests\test_course_network_edit_service.py tests\test_course_network_store.py -v
git add backend/app/api/course_network_routes.py backend/app/api/routes.py backend/app/api/deps.py backend/app/schemas/api.py backend/app/course_network/edit_service.py backend/tests/test_api_course_network_edit.py
git commit -m "feat: expose reviewed course network edits"
```

---

## PR B2 - Direct Editor and Agent-Assisted Proposals

### Task 6: Define a pure frontend draft reducer and API adapter

**Files:**
- Create: `frontend/src/features/course-network/edit-draft.ts`
- Create: `frontend/src/features/course-network/edit-draft.test.ts`
- Create: `frontend/src/features/course-network/api-types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/api.test.ts`

**Interfaces:**

```ts
export type NetworkEditAction =
  | { type: "node-added"; node: LearningBlock }
  | { type: "node-updated"; nodeId: string; changes: LearningBlockPatch }
  | { type: "node-deleted"; nodeId: string }
  | { type: "edge-added"; edge: NetworkEdge }
  | { type: "edge-deleted"; edgeId: string }
  | { type: "server-replaced"; draft: CourseNetworkEditDraftView };

export function reduceEditDraft(
  state: CourseNetworkEditState,
  action: NetworkEditAction,
): CourseNetworkEditState;
```

- [ ] **Step 1: Write reducer tests**

Assert operation coalescing: add then edit remains one add, add then delete
removes both, repeated updates merge, deleting a node removes pending incident
edges, and `server-replaced` resets local dirty state.

- [ ] **Step 2: Implement typed API methods**

Add open/get/update/review/commit/discard methods. Map 409s through the existing
workflow-error conventions and retain the server's recovery action.

- [ ] **Step 3: Run and commit**

```powershell
cd frontend
npm test -- --run src/features/course-network/edit-draft.test.ts src/lib/api.test.ts
git add frontend/src/features/course-network/edit-draft.ts frontend/src/features/course-network/edit-draft.test.ts frontend/src/features/course-network/api-types.ts frontend/src/lib/api.ts frontend/src/lib/api.test.ts
git commit -m "feat: model course network edit drafts"
```

### Task 7: Build accessible node and edge editing controls

**Files:**
- Create: `frontend/src/components/klassenpilot/course/course-network-editor.tsx`
- Create: `frontend/src/components/klassenpilot/course/learning-block-form.tsx`
- Create: `frontend/src/components/klassenpilot/course/network-edge-form.tsx`
- Create: `frontend/src/components/klassenpilot/course/course-network-toolbar.tsx`
- Modify: `frontend/src/components/klassenpilot/course/learning-block-node.tsx`
- Modify: `frontend/src/features/course-network/to-react-flow.ts`
- Test: `frontend/src/components/klassenpilot/course/course-network-editor.test.ts`

- [ ] **Step 1: Write source-contract and reducer-level interaction tests**

Verify semantic design tokens, accessible labels, keyboard-reachable add/edit
actions, explicit relation selection, unsaved-change status, and that deleting a
node requires confirmation listing affected connections, material mappings,
and lesson references.

- [ ] **Step 2: Implement controlled editing**

React Flow callbacks dispatch typed reducer actions. The side panel owns forms;
nodes do not embed free-form editors. Keep canvas position changes local until
save, then encode changed positions as node updates. Do not allow custom edge
labels.

- [ ] **Step 3: Implement mobile and reduced-motion behavior**

Below the existing desktop breakpoint, switch to the ordered outline editor.
Respect `prefers-reduced-motion`; preserve focus when side panels open and
close; announce validation errors through the shared form-error component.

- [ ] **Step 4: Run and commit**

```powershell
cd frontend
npm test -- --run src/components/klassenpilot/course/course-network-editor.test.ts src/features/course-network/edit-draft.test.ts
npm run lint
git add frontend/src/components/klassenpilot/course/course-network-editor.tsx frontend/src/components/klassenpilot/course/learning-block-form.tsx frontend/src/components/klassenpilot/course/network-edge-form.tsx frontend/src/components/klassenpilot/course/course-network-toolbar.tsx frontend/src/components/klassenpilot/course/learning-block-node.tsx frontend/src/features/course-network/to-react-flow.ts frontend/src/components/klassenpilot/course/course-network-editor.test.ts
git commit -m "feat: edit course networks visually"
```

### Task 8: Build operation review by composing existing review primitives

**Files:**
- Create: `frontend/src/components/klassenpilot/course/network-operation-row.tsx`
- Create: `frontend/src/components/klassenpilot/course/network-operation-review.tsx`
- Create: `frontend/src/components/klassenpilot/course/network-review-findings.tsx`
- Modify: `frontend/src/components/klassenpilot/review/index.ts`
- Test: `frontend/src/components/klassenpilot/course/network-operation-review.test.ts`

- [ ] **Step 1: Write review-state tests**

Cover deterministic errors, warnings, LLM findings, in-progress review,
approved exact revision, changed-after-review, commit blocked, and commit
enabled. Assert teachers see plain German verbs such as Hinzufuegen, Aendern,
Verknuepfen, and Entfernen rather than JSON operation names.

- [ ] **Step 2: Compose `ReviewChrome` and shared status components**

Use `ReviewChrome` for title, summary, status, errors, and action placement.
Render typed rows for node/edge changes with before/after fields. Do not reuse
`FileChangeReviewPanel`, `WikiProposalEditor`, or Markdown line diffs.

- [ ] **Step 3: Run and commit**

```powershell
cd frontend
npm test -- --run src/components/klassenpilot/course/network-operation-review.test.ts
npm run lint
git add frontend/src/components/klassenpilot/course/network-operation-row.tsx frontend/src/components/klassenpilot/course/network-operation-review.tsx frontend/src/components/klassenpilot/course/network-review-findings.tsx frontend/src/components/klassenpilot/review/index.ts frontend/src/components/klassenpilot/course/network-operation-review.test.ts
git commit -m "feat: review course network operations"
```

### Task 9: Add agent-assisted operation generation

**Files:**
- Create: `backend/app/course_network/assistant.py`
- Modify: `backend/app/course_network/prompts.py`
- Modify: `backend/app/course_network/edit_service.py`
- Modify: `backend/app/api/course_network_routes.py`
- Modify: `backend/app/schemas/api.py`
- Test: `backend/tests/test_course_network_assistant.py`
- Test: `backend/tests/test_api_course_network_edit.py`

**Route:**

```text
POST /api/classes/{class_id}/course/network/edits/{draft_id}/assist
```

**Request:**

```python
class NetworkAssistRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)
    selected_node_ids: list[str] = Field(default_factory=list)
    expected_artifact_revision: int
    expected_artifact_hash: str
```

- [ ] **Step 1: Write failing assistant tests**

Assert the model sees the current network, current pending operations, teacher
instruction, selected nodes, and bounded source excerpts. Reject operations
outside the allowed union, unknown nodes, and malformed relations. Preserve the
teacher's current proposal if generation or validation fails.

- [ ] **Step 2: Implement a no-tools typed proposal agent**

The assistant returns `NetworkChangeSet` operations only. Apply and validate
them server-side, save them as a new artifact revision, clear the previous
review, and return the full draft view. Add the job to the existing
`WorkflowDraftStore` running-turn fields so `/api/workflow/active` can surface
it without a second job system.

- [ ] **Step 3: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_network_assistant.py tests\test_api_course_network_edit.py tests\test_api_workflow_active.py -v
git add backend/app/course_network/assistant.py backend/app/course_network/prompts.py backend/app/course_network/edit_service.py backend/app/api/course_network_routes.py backend/app/schemas/api.py backend/tests/test_course_network_assistant.py backend/tests/test_api_course_network_edit.py
git commit -m "feat: assist course network editing"
```

### Task 10: Connect editor, review, recovery, and background status

**Files:**
- Modify: `frontend/src/app/classes/[classId]/course/page.tsx`
- Create: `frontend/src/components/klassenpilot/course/course-network-edit-workspace.tsx`
- Create: `frontend/src/components/klassenpilot/course/network-assist-box.tsx`
- Create: `frontend/src/features/course-network/use-network-edit.ts`
- Modify: `frontend/src/components/klassenpilot/pending-turn-notifier.tsx`
- Modify: `frontend/src/lib/running-jobs.ts`
- Modify: `frontend/src/lib/running-jobs.test.ts`
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/features/course-network/use-network-edit.test.ts`
- Test: `frontend/src/components/klassenpilot/course/course-network-edit-workspace.test.ts`

- [ ] **Step 1: Write state-machine tests**

Model states: inspecting, editing-clean, editing-dirty, saving, needs-review,
reviewing, review-blocked, ready-to-commit, committing, stale, and failed.
Assert leaving with dirty edits warns, a stale response reloads canonical state
without discarding the server draft, and commit returns to read-only inspection.

- [ ] **Step 2: Implement the edit workspace**

Use a single Edit network action from read-only inspection. Save draft and
Review changes are distinct. Agent assistance edits the same proposal and is
labeled as a suggestion. The final action says Apply to class wiki and shows
the affected node/edge count.

- [ ] **Step 3: Reuse running-job notifications**

Extend `RunningJobMode` with `course_network` and route it to the Course
destination. In `PendingTurnNotifier`, fetch the course edit endpoint when such
a draft stops instead of casting it to `ArtifactMode` or hydrating the
assistant-ui draft store. Extend the active-work API type and display helpers
rather than adding route-specific notification JSX. Do not register a new
assistant-ui chat runtime.

- [ ] **Step 4: Run and commit**

```powershell
cd frontend
npm test -- --run src/features/course-network/use-network-edit.test.ts src/components/klassenpilot/course/course-network-edit-workspace.test.ts
npm run lint
git add frontend/src/app/classes/[classId]/course/page.tsx frontend/src/components/klassenpilot/course/course-network-edit-workspace.tsx frontend/src/components/klassenpilot/course/network-assist-box.tsx frontend/src/features/course-network/use-network-edit.ts frontend/src/components/klassenpilot/pending-turn-notifier.tsx frontend/src/lib/running-jobs.ts frontend/src/lib/running-jobs.test.ts frontend/src/lib/api.ts frontend/src/features/course-network/use-network-edit.test.ts frontend/src/components/klassenpilot/course/course-network-edit-workspace.test.ts
git commit -m "feat: connect course network review flow"
```

### Task 11: Update contracts and perform Epic B acceptance

**Files:**
- Modify: `docs/agent_contracts.md`
- Modify: `docs/memory_hierarchy.md`
- Modify: `docs/agent_architecture.md`
- Modify: `frontend/ARCHITECTURE.md`
- Modify: `backend/app/api/README.md`
- Modify: generated OpenAPI artifact used by the repository

- [ ] **Step 1: Document write boundaries and review identity**

Record typed operations, structured-draft serialization, exact-revision review,
atomic canonical write, assistant proposal-only behavior, and the permanent
editor route. State explicitly that lesson planning stays read-only.

- [ ] **Step 2: Run deterministic suites**

```powershell
.\scripts\test.ps1
```

Expected: PASS with no OpenAI calls.

- [ ] **Step 3: Run HITL acceptance**

```powershell
.\scripts\worktree-stack.cmd up --beta --fresh-beta-data
```

Adopt Chemie 8 NTG; edit a title manually; add a `builds_on` edge; ask the
assistant to split one block; inspect operations; trigger review; change the
proposal and verify the old review is invalid; re-review; commit; reload; and
confirm `network.json` and `overview.md` agree. Repeat at narrow width using the
outline editor.

- [ ] **Step 4: Commit documentation**

```powershell
git add docs/agent_contracts.md docs/memory_hierarchy.md docs/agent_architecture.md frontend/ARCHITECTURE.md backend/app/api/README.md
git commit -m "docs: define course network editing contracts"
```

## PR B1 Exit Criteria

- Typed operations are validated and stored as stable structured drafts.
- Exact-revision deterministic and LLM review gates canonical writes.
- Commits are optimistic, atomic, teacher-approved, and rebuild the overview.
- Canonical graph files remain unchanged when a proposal fails or is stale.

## PR B2 Exit Criteria

- Teachers can inspect and edit the network outside planning or ingestion.
- Canvas and outline editors expose the same operation contract.
- Agent assistance changes only the reviewable draft.
- The operation review is understandable without exposing storage JSON.
- Desktop, narrow layout, keyboard, stale-recovery, and background-job paths pass acceptance.
