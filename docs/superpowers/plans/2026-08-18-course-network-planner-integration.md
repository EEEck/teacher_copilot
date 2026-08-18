# Course Network Planner Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make lesson planning automatically retrieve the relevant part of an adopted class course network and its mapped materials, then automatically persist validated course-node associations for saved plans and approved lesson results without adding teacher selection steps.

**Architecture:** Add deterministic network retrieval and source-bearing read tools to the existing wiki facade. The planning prompt receives only a compact course orientation; the planner calls network tools when the request exceeds that slice and stores validated node associations in backend-owned `PlanRuntime`. Plan save writes a `course_refs.json` sidecar. The existing Update Memory approval path derives or preserves associations and writes the same sidecar contract without changing the teacher-facing workflow. Classes without an adopted network continue using the current subject-framework path.

**Tech Stack:** FastAPI, Pydantic 2, existing WikiStore search/context tracing, OpenAI Agents SDK tools and structured outputs, current PlanRuntime and memory commit services, stdlib JSON, pytest, existing eval harness, Next.js/TypeScript only for passive association display.

**Spec:** `docs/superpowers/specs/2026-08-17-class-course-network-design.md`

## Global Constraints

- This plan starts after the network foundation; mapped-material retrieval uses the material/mapping plan when present.
- Planning is read-only with respect to canonical network and material files.
- The teacher is not required to select graph nodes before or during planning.
- Network editing remains in the permanent course workspace.
- Automatic associations are backend-validated against the current network revision.
- Plan chat continues to update only its draft and runtime; durable association writes happen on plan save.
- Update Memory keeps its current conversation, proposal, review, and teacher-approved apply flow.
- The course network does not replace timeline, course state, teaching patterns, copilot preferences, or student memory.
- When no network is adopted, current framework and adjustment-memo behavior remains the complete fallback.
- The graph does not become a generic graph engine and no vector store is introduced.
- Questions remain part of retrieved material context; no question bank or rubric entity is added here.

## Lesson Association Contract

```text
wiki/classes/{class_id}/lessons/{lesson_date}/course_refs.json
```

```python
class LessonCourseReference(BaseModel):
    node_id: str
    role: Literal["primary", "supporting", "prerequisite", "assessment"]
    state: Literal["planned", "taught", "revisit"]
    source: Literal["planner", "memory_update", "carry_forward"]
    confidence: float | None = Field(default=None, ge=0, le=1)

class LessonCourseReferences(BaseModel):
    schema_version: Literal[1] = 1
    class_id: str
    lesson_date: date
    network_revision: int
    references: list[LessonCourseReference]
    updated_at: datetime
```

This sidecar links a lesson to canonical nodes without embedding the lesson in
the graph. References to retired nodes remain readable for history, but retired
nodes are never proposed for a new plan. Existing `materials.json` remains
separate. Missing sidecars are valid for old lessons and classes using the
legacy fallback.

---

## PR D1 - Deterministic Retrieval and Planning Runtime Alignment

### Task 1: Add deterministic network ranking

**Files:**
- Create: `backend/app/course_network/retrieval.py`
- Modify: `backend/app/teacher_agent/wiki/course_network.py`
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/teacher_agent/wiki/search.py`
- Test: `backend/tests/test_course_network_retrieval.py`
- Test: `backend/tests/test_wiki_search.py`

**Interfaces:**

```python
class CourseNodeHit(BaseModel):
    node_id: str
    title: str
    learning_goal: str
    score: float
    matched_fields: list[str]
    prerequisite_ids: list[str]
    material_section_refs: list[str]

def rank_course_nodes(
    document: CourseNetworkDocument,
    *,
    query: str,
    limit: int = 8,
) -> list[CourseNodeHit]: ...

def expand_course_neighborhood(
    document: CourseNetworkDocument,
    *,
    node_ids: list[str],
    prerequisite_depth: int = 1,
    related_limit: int = 4,
) -> CourseNetworkSlice: ...
```

- [ ] **Step 1: Write failing retrieval tests using Chemie 8 fixtures**

Queries must rank the expected nodes for Stoffmenge, molare Masse,
Reaktionsgleichung, Aktivierungsenergie, Katalyse, and homologe Reihe. Assert
German normalization, title/term/goal/body weighting, deterministic tie order,
deduplication, prerequisite expansion, mapping references, and strict class
isolation.

- [ ] **Step 2: Implement lexical ranking with existing search primitives**

Reuse normalization/tokenization from wiki search. Weight title and canonical
terms above learning goal and body. Add a small deterministic adjacency bonus
only after direct matches. Exclude retired nodes from new-plan hits. Return zero
hits for an empty query. Do not add embeddings or external indexes.

- [ ] **Step 3: Expose retrieval through `WikiStore`**

Add `has_course_network`, `search_course_network`,
`read_course_network_slice`, and `list_node_material_sections`. Include course
node titles in broad wiki search as source-bearing hits whose path resolves to
the compiled overview or a typed read method.

- [ ] **Step 4: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_network_retrieval.py tests\test_wiki_search.py tests\test_course_network_store.py -v
git add backend/app/course_network/retrieval.py backend/app/teacher_agent/wiki/course_network.py backend/app/teacher_agent/wiki/store.py backend/app/teacher_agent/wiki/search.py backend/tests/test_course_network_retrieval.py backend/tests/test_wiki_search.py
git commit -m "feat: retrieve course network slices"
```

### Task 2: Build a compact course orientation for plan startup

**Files:**
- Modify: `backend/app/teacher_agent/wiki/context_packs.py`
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/context_limits.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_wiki_context_packs.py`
- Test: `backend/tests/test_context_limits.py`

**Interfaces:**

```python
def build_course_orientation_trace(store, class_id: str) -> dict[str, Any]: ...
```

The trace contains `content`, `sources`, `function`, `chars`, and `truncated`
using the same trace shape as existing context builders.

- [ ] **Step 1: Write failing context-pack tests**

For an adopted network, include network revision, likely current nodes derived
from canonical course state/timeline text, immediate prerequisites, and mapped
material titles. Deduplicate content already present in the slim class slice.
For no network, emit no course section and preserve byte-for-byte legacy
framework context.

- [ ] **Step 2: Implement bounded orientation**

Rank nodes using current unit, recent lesson titles, and the planning request
when available. Cap node count and per-node characters through named settings
in central context limits. Source every item with node ID and network revision.

- [ ] **Step 3: Add it to the slim plan context**

Place the course orientation after current course state and before detailed
teaching patterns. Do not inject the whole graph, full materials, or raw OCR.

- [ ] **Step 4: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_wiki_context_packs.py tests\test_context_limits.py tests\test_prompt_assembly.py -v
git add backend/app/teacher_agent/wiki/context_packs.py backend/app/teacher_agent/wiki/store.py backend/app/context_limits.py backend/app/config.py backend/tests/test_wiki_context_packs.py backend/tests/test_context_limits.py
git commit -m "feat: orient planning with course networks"
```

### Task 3: Add progressive course-network and mapped-material tools

**Files:**
- Modify: `backend/app/teacher_agent/tools.py`
- Modify: `backend/app/teacher_agent/agents.py`
- Modify: `backend/app/teacher_agent/planning_state.py`
- Modify: `backend/app/teacher_agent/prompt_assembly.py`
- Test: `backend/tests/test_wiki_tools.py`
- Test: `backend/tests/test_planning_state.py`
- Test: `backend/tests/test_prompt_assembly.py`

**Tools:**

```python
search_course_network(query: str) -> str
read_course_nodes(node_ids: list[str], include_prerequisites: bool = True) -> str
read_node_material_sections(node_ids: list[str], purpose: str) -> str
```

- [ ] **Step 1: Write failing tool tests**

Assert class scoping, adopted-network requirement, result caps, stable source
references, invalid node rejection, material section page/title citations,
questions remaining ordinary excerpt text, and raw payload capture behind a
`raw_ref` with only an `EvidenceBrief` reinjected.

- [ ] **Step 2: Implement tools with the existing planning context wrapper**

Use the same `_capture`/raw-store/evidence-brief discipline as current wiki and
material reads. Register the tools only for planning/discussion contexts that
may read class memory. Do not expose a network mutation tool.

- [ ] **Step 3: Render consulted course sources compactly**

Extend evidence rendering so source refs use `Course node: {node_id}` and
`Material: {material_id}#{section_id}`. Keep full excerpts behind `raw_ref`.

- [ ] **Step 4: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_wiki_tools.py tests\test_planning_state.py tests\test_prompt_assembly.py -v
git add backend/app/teacher_agent/tools.py backend/app/teacher_agent/agents.py backend/app/teacher_agent/planning_state.py backend/app/teacher_agent/prompt_assembly.py backend/tests/test_wiki_tools.py backend/tests/test_planning_state.py backend/tests/test_prompt_assembly.py
git commit -m "feat: browse course evidence during planning"
```

### Task 4: Add automatic course alignment to `PlanRuntime`

**Files:**
- Modify: `backend/app/teacher_agent/planning_state.py`
- Modify: `backend/app/teacher_agent/models.py`
- Modify: `backend/app/services/artifact_spec.py`
- Modify: `backend/app/services/plan_service.py`
- Modify: `backend/app/teacher_agent/prompts.py`
- Test: `backend/tests/test_planning_state.py`
- Test: `backend/tests/test_artifact_spec.py`
- Test: `backend/tests/test_prompts.py`
- Test: `backend/tests/test_api_plan.py`

**Interfaces:**

```python
class CourseAlignment(BaseModel):
    network_revision: int = 0
    references: list[LessonCourseReference] = Field(default_factory=list)

class CourseAlignmentPatch(BaseModel):
    references: list[LessonCourseReference] | None = None

class StatePatch(BaseModel):
    session_state: SessionStatePatch = Field(default_factory=SessionStatePatch)
    lesson_planning_state: LessonPlanningStatePatch = Field(default_factory=LessonPlanningStatePatch)
    course_alignment: CourseAlignmentPatch = Field(default_factory=CourseAlignmentPatch)
```

- [ ] **Step 1: Write failing runtime and API tests**

Assert merge/dedupe by node and role, validation against current network,
unknown-node removal with trace metadata, runtime serialization/resume, response
visibility, no teacher selection requirement, and empty alignment under legacy
fallback.

- [ ] **Step 2: Implement backend-owned alignment**

The model proposes associations through `state_patch`; the backend validates
them and stamps the current network revision. Before each planning call,
deterministically seed likely references from the teacher request/current unit.
After each call, reconcile model proposals with nodes actually cited or read.
Treat direct model choice as primary and deterministic matches as supporting
unless evidence says otherwise.

- [ ] **Step 3: Update planner instructions**

Tell the planner to discover the relevant course slice itself, retrieve mapped
materials only when useful, cite or name sources in the plan, and maintain
course alignment through the structured patch. Explicitly state that it must
not ask the teacher to tag nodes unless genuine ambiguity blocks a safe plan.

- [ ] **Step 4: Persist the new runtime field**

Extend `artifact_spec.py` serialization/deserialization additively. Old drafts
without the field deserialize to an empty alignment. Keep it backend runtime
state until plan save.

- [ ] **Step 5: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_planning_state.py tests\test_artifact_spec.py tests\test_prompts.py tests\test_api_plan.py -v
git add backend/app/teacher_agent/planning_state.py backend/app/teacher_agent/models.py backend/app/services/artifact_spec.py backend/app/services/plan_service.py backend/app/teacher_agent/prompts.py backend/tests/test_planning_state.py backend/tests/test_artifact_spec.py backend/tests/test_prompts.py backend/tests/test_api_plan.py
git commit -m "feat: align plans to course nodes automatically"
```

---

## PR D2 - Durable Lesson Associations and Memory-Update Continuity

### Task 5: Implement lesson course-reference sidecars

**Files:**
- Create: `backend/app/course_network/lesson_refs.py`
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/teacher_agent/wiki/indexing.py`
- Test: `backend/tests/test_lesson_course_refs.py`

**Interfaces:**

```python
def read_lesson_course_refs(
    store: WikiStore,
    class_id: str,
    lesson_date: str,
) -> LessonCourseReferences | None: ...

def write_lesson_course_refs(
    store: WikiStore,
    refs: LessonCourseReferences,
) -> Path: ...
```

- [ ] **Step 1: Write failing storage tests**

Cover missing sidecar, normalized date/class ownership, unknown node rejection,
stable sorted references, atomic replace, safe path resolution, old network
revision retention for audit, and wiki index visibility without copying lesson
content into network nodes.

- [ ] **Step 2: Implement sidecar read/write**

Validate node IDs against the current adopted network at write time. Preserve
the association's reviewed network revision. Compile a short association line
into the class index/timeline detail view, not the network document.

- [ ] **Step 3: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_lesson_course_refs.py tests\test_wiki_indexing.py -v
git add backend/app/course_network/lesson_refs.py backend/app/teacher_agent/wiki/store.py backend/app/teacher_agent/wiki/indexing.py backend/tests/test_lesson_course_refs.py
git commit -m "feat: store lesson course references"
```

### Task 6: Write automatic references on reviewed plan save

**Files:**
- Modify: `backend/app/services/plan_service.py`
- Modify: `backend/app/schemas/api.py`
- Test: `backend/tests/test_api_plan.py`
- Test: `backend/tests/test_plan_service.py`

- [ ] **Step 1: Write failing save tests**

With an adopted network, save a reviewed plan and assert `course_refs.json`
contains validated runtime alignment, state `planned`, current revision, source
`planner`, and stable ordering. Assert canonical library materials actually
consulted by the planner are unioned into the lesson's existing
`materials.json`, not only newly promoted scratch IDs. If runtime alignment is
empty, derive a bounded association from the final reviewed plan text and
consulted course evidence. If no confident match exists, save the plan without
a sidecar rather than forcing a wrong tag. Legacy classes remain unchanged.

- [ ] **Step 2: Add reference persistence after the existing plan write gate**

The plan fingerprint/review behavior stays unchanged. Before writing, construct
and validate references and the union of promoted and consulted material IDs.
After the reviewed plan and existing material links are saved, atomically
replace the sidecar itself. If that derived write fails, return a typed
`association_repair_required` result and make the next lesson read/save rebuild
it from the saved plan and evidence metadata; never claim the association was
persisted when it was not.

- [ ] **Step 3: Return passive association metadata**

Extend `SavePlanResponse` with `course_references`. This is informative UI data,
not an approval step or a required request field.

- [ ] **Step 4: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_plan.py tests\test_plan_service.py tests\test_lesson_course_refs.py tests\test_materials_plan_api.py -v
git add backend/app/services/plan_service.py backend/app/schemas/api.py backend/tests/test_api_plan.py backend/tests/test_plan_service.py
git commit -m "feat: tag saved plans with course nodes"
```

### Task 7: Preserve and refine references through Update Memory apply

**Files:**
- Create: `backend/app/course_network/lesson_alignment.py`
- Modify: `backend/app/services/memory_apply.py`
- Modify: `backend/app/services/memory_skills.py`
- Modify: `backend/app/teacher_agent/wiki/commit.py`
- Test: `backend/tests/test_memory_apply.py`
- Test: `backend/tests/test_memory_skills.py`
- Test: `backend/tests/test_lesson_alignment.py`

**Interfaces:**

```python
def derive_result_references(
    *,
    network: CourseNetworkDocument,
    approved_lesson_markdown: str,
    existing: LessonCourseReferences | None,
) -> LessonCourseReferences | None: ...
```

- [ ] **Step 1: Write failing continuity tests**

Known planned lesson: change supported `planned` refs to `taught`, preserve
untaught prerequisites as supporting, and add `revisit` only when approved
result text identifies an open loop or misconception. Unplanned lesson: derive
bounded `taught` refs from approved result content. Unknown or low-confidence
text: leave absent. Preserve retired-node history but never add a new retired
reference. Assert no new review screen, chat step, proposal file, ledger closure
change, or timeline semantics change.

- [ ] **Step 2: Implement association as a typed post-apply write**

Call derivation only after the normal teacher-approved memory apply has passed
its current checks. Write the sidecar within the same service-level transaction
boundary used for wiki commit outputs; report any failure rather than silently
dropping associations. Mark sources `carry_forward` or `memory_update`.

- [ ] **Step 3: Run regression tests for unchanged Update Memory UX**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_lesson_alignment.py tests\test_memory_apply.py tests\test_memory_skills.py tests\test_api_ingest.py tests\test_wiki_commit.py -v
```

- [ ] **Step 4: Commit**

```powershell
git add backend/app/course_network/lesson_alignment.py backend/app/services/memory_apply.py backend/app/services/memory_skills.py backend/app/teacher_agent/wiki/commit.py backend/tests/test_memory_apply.py backend/tests/test_memory_skills.py backend/tests/test_lesson_alignment.py
git commit -m "feat: align approved lesson results to course nodes"
```

### Task 8: Surface associations without adding planning controls

**Files:**
- Modify: `frontend/src/components/klassenpilot/plan-save-confirm.tsx`
- Modify: `frontend/src/components/klassenpilot/plan-save-confirm.test.ts`
- Modify: `frontend/src/app/classes/[classId]/class-home-client.tsx`
- Modify: `frontend/src/lib/class-home-display.ts`
- Modify: `frontend/src/lib/class-home-display.test.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Write passive-display tests**

Assert saved-plan confirmation can list linked Lernbausteine, timeline details
can show compact course tags, and no node selector, required tag input, or graph
edit action appears in the planning flow.

- [ ] **Step 2: Implement compact course tags**

Use the shared badge component and semantic tokens. Each tag links to
`/classes/{classId}/course?node={nodeId}` for inspection. Editing remains a
separate course-workspace action.

- [ ] **Step 3: Run and commit**

```powershell
cd frontend
npm test -- --run src/components/klassenpilot/plan-save-confirm.test.ts src/lib/class-home-display.test.ts src/lib/api.test.ts
npm run lint
git add frontend/src/components/klassenpilot/plan-save-confirm.tsx frontend/src/components/klassenpilot/plan-save-confirm.test.ts frontend/src/app/classes/[classId]/class-home-client.tsx frontend/src/lib/class-home-display.ts frontend/src/lib/class-home-display.test.ts frontend/src/lib/api.ts
git commit -m "feat: show automatic course associations"
```

---

## PR D3 - Migration, Evals, Documentation, and Release

### Task 9: Make fallback and adoption behavior explicit

**Files:**
- Modify: `backend/app/teacher_agent/wiki/subject_frameworks.py`
- Modify: `backend/app/teacher_agent/wiki/context_packs.py`
- Modify: `backend/app/teacher_agent/prompts.py`
- Test: `backend/tests/test_subject_frameworks.py`
- Test: `backend/tests/test_wiki_context_packs.py`
- Test: `backend/tests/test_prompts.py`

- [ ] **Step 1: Write fallback matrix tests**

No adopted network: load current subject framework and
`memory/teaching_framework_adjustments.md` exactly as today. Adopted network:
use the class network as active course structure while retaining broad trusted
subject guidance for pedagogy/factual grounding; do not stack the old detailed
framework as a competing course outline. Deleting or discarding a draft does
not change the mode; only canonical adoption does.

- [ ] **Step 2: Implement one routing predicate**

Centralize `has_course_network(class_id)` and use it from context construction,
prompts, and retrieval. Do not scatter file-existence checks across agents.

- [ ] **Step 3: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_subject_frameworks.py tests\test_wiki_context_packs.py tests\test_prompts.py -v
git add backend/app/teacher_agent/wiki/subject_frameworks.py backend/app/teacher_agent/wiki/context_packs.py backend/app/teacher_agent/prompts.py backend/tests/test_subject_frameworks.py backend/tests/test_wiki_context_packs.py backend/tests/test_prompts.py
git commit -m "refactor: route adopted classes through course networks"
```

### Task 10: Add Chemie 8/9 retrieval and planning evals

**Files:**
- Create: `backend/evals/course_network/__init__.py`
- Create: `backend/evals/course_network/cases.json`
- Create: `backend/evals/course_network/run_course_network_eval.py`
- Create: `backend/tests/test_course_network_eval_cases.py`
- Modify: `backend/evals/README.md`

**Eval case fields:**

```json
{
  "id": "chemie8-katalyse-plan",
  "grade": 8,
  "teacher_request": "Plane den Einstieg in die Katalyse.",
  "expected_node_ids": ["aktivierungsenergie", "katalyse"],
  "required_source_kinds": ["course_node"],
  "forbidden_behaviors": ["ask_teacher_to_select_node", "write_network"]
}
```

- [ ] **Step 1: Create deterministic case validation**

Include Chemie 8 and 9 cases for direct topics, prerequisite-dependent topics,
mapped textbook chapters, sparse mappings, an ambiguous teacher request, and a
legacy class. Validate unique IDs, known expected nodes, and allowed source
kinds without model calls.

- [ ] **Step 2: Implement the optional model eval runner**

Report retrieval recall, cited-source precision, valid association rate,
unnecessary-teacher-question rate, legacy regression, and forbidden write
attempts. The deterministic CI test validates fixtures; the live runner is
manual and reads normal model configuration.

- [ ] **Step 3: Run deterministic eval validation and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_network_eval_cases.py tests\test_course_network_retrieval.py -v
git add backend/evals/course_network/__init__.py backend/evals/course_network/cases.json backend/evals/course_network/run_course_network_eval.py backend/tests/test_course_network_eval_cases.py backend/evals/README.md
git commit -m "test: add course network planning evals"
```

### Task 11: Update durable product, architecture, and API contracts

**Files:**
- Modify: `docs/pm_hub.md`
- Modify: `docs/product_vision.md`
- Modify: `implementation_plans/product_backlog.md`
- Modify: `docs/agent_architecture.md`
- Modify: `docs/agent_contracts.md`
- Modify: `docs/memory_hierarchy.md`
- Modify: `docs/context_management.md`
- Modify: `backend/teacher_wiki/AGENTS.md`
- Modify: `backend/app/teacher_agent/wiki/README.md`
- Modify: `frontend/ARCHITECTURE.md`
- Modify: generated OpenAPI artifact used by the repository

- [ ] **Step 1: Map product decisions to shipped contracts**

Document class-local MVP ownership, one Lernbaustein type, material separation,
two cadences, automatic retrieval/tagging, permanent editing outside planning,
unchanged Update Memory UX, legacy fallback, and out-of-scope export/import and
question bank. Add explicit future rule: any later structured question must
include a fixed, versioned rubric before it can support autonomous grading.

- [ ] **Step 2: Document file-by-file memory behavior**

Add `course_network/network.json`, compiled `overview.md`, canonical material
packages, `materials.json`, and `course_refs.json` to the hierarchy with read,
write, review, and loading rules. State that graph JSON is canonical and React
Flow state is not.

- [ ] **Step 3: Regenerate and verify OpenAPI**

Use the repository's existing OpenAPI generation/check command. Confirm all new
schemas and routes match frontend API types.

- [ ] **Step 4: Commit**

```powershell
git add docs/pm_hub.md docs/product_vision.md implementation_plans/product_backlog.md docs/agent_architecture.md docs/agent_contracts.md docs/memory_hierarchy.md docs/context_management.md backend/teacher_wiki/AGENTS.md backend/app/teacher_agent/wiki/README.md frontend/ARCHITECTURE.md
git commit -m "docs: publish course network integration contracts"
```

### Task 12: Run release verification and staged HITL

- [ ] **Step 1: Run the full deterministic suite**

```powershell
.\scripts\test.ps1
```

Expected: PASS with no live model or OCR calls.

- [ ] **Step 2: Run a production-profile HITL stack**

```powershell
.\scripts\worktree-stack.cmd up --beta --fresh-beta-data --app-env production --model-profile production
```

- [ ] **Step 3: Complete the end-to-end Chemie 8 scenario**

Create Chemie 8a; review/adopt the seed; upload and approve textbook chapters;
review mappings; request a lesson on Katalyse without selecting nodes; verify
the agent retrieves Aktivierungsenergie/Katalyse and mapped excerpts; save;
inspect passive course tags; record lesson results through the unchanged Update
Memory flow; approve; inspect the updated lesson sidecar; return to the course
workspace and edit the graph through its independent review flow.

- [ ] **Step 4: Complete isolation and fallback scenarios**

Create Chemie 8b and verify 8a materials/network/refs never appear. Create a
class without adoption and verify the existing framework flow. Exercise a
stale mapping/edit commit, failed OCR, blocked LLM review, browser refresh during
a job, keyboard-only editing, and narrow layout.

- [ ] **Step 5: Record release evidence**

In the PR description, report worktree/branch, deterministic commands and
results, live eval command/results if run, frontend URL, wiki files changed in
the sandbox, screenshots for adoption/import/mapping/planning, and known
follow-up work. Do not modify the tracked baseline wiki during HITL.

## PR D1 Exit Criteria

- Planning starts with a bounded course orientation and can progressively retrieve nodes and mapped sections.
- The planner automatically maintains validated runtime associations.
- No graph mutation tool or teacher tagging requirement exists in planning.
- Legacy planning remains unchanged when no network is adopted.

## PR D2 Exit Criteria

- Reviewed plan save writes automatic lesson course references.
- Approved lesson results preserve or refine references without a new teacher step.
- Passive tags link back to network inspection and never become required planning controls.

## PR D3 Exit Criteria

- Chemie 8/9 deterministic cases and manual evals cover retrieval, citations, associations, isolation, and fallback.
- Durable product, agent, wiki, frontend, and API docs agree with shipped behavior.
- End-to-end HITL proves the quarterly build/enrich cadence and weekly use cadence are independent.
