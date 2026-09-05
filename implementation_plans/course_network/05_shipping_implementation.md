# Course Knowledge Map End-to-End Implementation Plan

## Execution record

The implemented MVP and fresh evidence are recorded in
[06 — shipping validation](06_shipping_validation.md). The task breakdown below
is the original detailed engineering plan; its unchecked boxes are not a claim
that the implementation is absent. Use 06 for the current handoff.

Implemented: Course entry and source inspection; reviewed seed revision/adoption;
typed reviewed map changes with publication recovery; standalone PDF extraction,
editable stable sections and approval; separate mapping review; backend-owned
graph procedure; ordinary planning context; explicit saved plan citations; and
read-only use of approved lesson results in subsequent context.

MVP shortcuts: bounded model HTTP calls instead of a new general job runner;
hash-guarded idempotent plan sidecars instead of broad publication infrastructure;
derived result context instead of another results/progress store. OCR remains
durable and resumable. These choices preserve the two teacher approval boundaries.

Browser access became available in the follow-up session. The realistic chapter
upload, map approval, lesson save and approved-results workflow was exercised in
the browser; see [07 — browser acceptance](07_browser_acceptance.md), including
the provenance bug found and corrected during that run.

## Original task breakdown

> **For agentic workers:** Use `superpowers:executing-plans` to implement task-by-task in the course-network worktree. Steps use checkboxes. Do not implement the old B/C/D plans wholesale or start delegated work without session authorization.

**Goal:** Ship the connected curriculum → concept map ← course materials → lesson planning → lesson results workflow for one teaching block.

**Architecture:** Retain the class-wiki graph and existing viewer. Add a small reviewed-change service, standalone material imports with stable section references, a backend-owned generation/enrichment procedure, and bounded retrieval in the existing planner. Persist lesson associations through the current approval boundaries; reuse current drafts, OCR, evidence handling, and frontend components.

**Tech Stack:** Existing FastAPI/Pydantic, OpenAI Agents SDK model routing, Mistral OCR, SQLite workflow drafts, wiki JSON/Markdown, Next.js/React Flow, pytest/Vitest. No new infrastructure or runtime libraries are planned.

**Spec:** [04_shipping_scope.md](04_shipping_scope.md), refining [01_product_design.md](01_product_design.md).

## Global constraints

- Class-owned network; one node type, `Lernbaustein`; `builds_on` and `related_to` relationships.
- `source_id builds_on target_id` means the source concept depends on the target concept.
- Planning and ingest chat cannot write the graph or canonical material packages.
- Approve extracted material first; approve graph mappings/changes separately in the same import workflow.
- Preserve node IDs; retirement retains historical references. No ID rename or node merge migration.
- Material manifests contain metadata and stable content pointers, not duplicated full text.
- Keep existing pedagogy/framework context when a graph is adopted; deduplicate the new course layer.
- Course imports are PDF-only, one upload at a time per import, at most 30 selected pages within existing byte limits. Use existing model routing and Mistral runtime.
- Use shared design-system components and semantic tokens. The canvas remains an inspection view.
- No whole-book editor, question bank, scheduler, mastery scoring, cross-class reuse, graph database, embeddings, or new chat engine.
- All new APIs retain the canonical error envelope and update `contracts/openapi.yaml` in the same task.
- API failures must leave approved data intact. Retry of an approved operation must not duplicate writes.

## Baseline and execution order

Inspected `codex/class-course-network-design` at `9e4df80` in `C:/Users/matth/.codex/worktrees/849f/teacher_agent_v2`. At inspection it contained main (`0a21e32`) plus 43 commits; no merge from main was then needed. Recheck at execution time and preserve unrelated local files and sandbox data.

Implemented: provisioning, seed loading/review/adoption, JSON/overview/index publication, structured draft opening and exact review snapshots, graph viewer/outline/inspector. The README's historical test results are not fresh acceptance evidence.

Important actual-code gaps:

- `skills/loader.py` loads production procedures, but has no graph-generation procedure.
- `CourseNetworkService` only publishes initial seed adoption; it rejects an already-adopted graph.
- `WorkflowDraftStore.open_structured_draft` exists; a generic `save_structured_draft` does not yet exist.
- `wiki/materials.py` discovers scratch and lesson-linked packages. Heading-derived section IDs are unsuitable for durable edited mappings.
- `PlanService.save` currently saves the plan before promoting PDFs, and records newly promoted IDs. Adding sidecars requires a coherent publication/recovery boundary and inclusion of consulted library material IDs.
- The Grade 8 seed covers the reactions section. Do not label it a complete annual curriculum.

Execute Tasks 1–8 sequentially. Each task has a focused acceptance boundary; only Task 8 establishes the full feature as shippable. Original plans are implementation references where explicitly cited below.

## File ownership map

| Area | Files and responsibility |
| --- | --- |
| Graph contracts | `backend/app/course_network/{models,operations,validation,review,edit_service}.py`: typed changes, integrity, exact review, publication |
| Generation | `backend/app/course_network/generation.py`, `backend/app/teacher_agent/skills/course_network_procedure.md`, `skills/loader.py`: evidence packets and bounded structured proposals |
| Materials | `backend/app/course_materials/{models,sections,store,import_service}.py`: manifest, stable references, approved library, import lifecycle |
| Existing OCR | `backend/app/services/materials_scratch.py`, `materials_ocr.py`, `materials_ocr_packaging.py`: reuse packaging and promotion primitives with explicit class/workspace ownership |
| Retrieval | `backend/app/course_network/retrieval.py`, `backend/app/teacher_agent/wiki/{materials,store,context_packs}.py`, agent tools: compact context and progressive reads |
| Lesson links | `backend/app/course_network/lesson_refs.py`, `backend/app/services/course_lesson_publication.py`, Plan/Ingest services and runtime models: validated sidecars and publication recovery |
| UI | Existing `components/klassenpilot/course/`, new `features/course-materials/`, existing review/error/job components: two review steps and source inspection |

New filenames below are proposed files, not claims that they already exist. Use existing types at the boundary and explicitly convert domain dataclasses versus API Pydantic models; do not silently replace the current `wiki.materials.MaterialSection` everywhere.

## Task 1 — Close the foundation and fix graph semantics

**Modify:** `frontend/src/app/classes/[classId]/page.tsx` (or its current action composition), existing course workspace/inspector, `backend/app/course_network/validation.py`, seed fixtures, `frontend/ARCHITECTURE.md`, `docs/agent_contracts.md`, and both the source design and its promoted copy for relationship wording.
**Test:** existing `test_course_network_models.py`, `test_course_network_seeds.py`, `test_course_network_store.py`, `test_course_network_api.py`; existing canvas/workspace rendered tests.

**Consumes:** adopted `CourseNetworkDocument` and existing adoption API.
**Produces:** reachable, accurately labelled graph workspace and a single relationship-direction contract.

- [ ] Add regression cases showing `catalysis → activation-energy` renders “Builds on Activation energy” and the inverse selection renders “Used by Catalysis”; reversed `related_to` duplicates are rejected. Pin partial curriculum coverage without imposing a fake annual-completeness assertion.
- [ ] Add the single Course action beside Browse class files; preserve existing Plan and Update Memory entry points. Show source scope in the course workspace. Correct the original `builds_on` wording, not the already-consistent seed direction.
- [ ] Run focused backend and existing rendered frontend tests, then typecheck. Resolve new failures before the full Epic A gate. Record pre-existing failures separately with evidence; they do not count as passing acceptance.
- [ ] Run the full deterministic suite once to establish the execution baseline; perform the outstanding adoption/inspection HITL gate in the worktree sandbox. Commit only this task's source/docs changes.

```powershell
# From worktree root; backend commands use its environment.
cd backend
.\.venv\Scripts\python -m pytest tests/test_course_network_models.py tests/test_course_network_seeds.py tests/test_course_network_store.py tests/test_course_network_api.py
cd ../frontend
npm test -- --run src/components/klassenpilot/course/course-network-canvas.rendered.test.ts src/components/klassenpilot/course/course-network-workspace.rendered.test.ts
npm run typecheck
cd ..
.\scripts\test.ps1
```

## Task 2 — Add the small reviewed graph-change boundary

**Create:** `backend/app/course_network/operations.py`, `edit_service.py`.
**Modify:** network models/validation/review, `backend/app/services/workflow_drafts.py`, `backend/app/api/course_network_routes.py`, `backend/app/api/deps.py`, API schemas/OpenAPI, `docs/agent_contracts.md`.
**Test:** new `test_course_network_operations.py`, `test_course_network_edits.py`; existing review/store/draft tests.

**Consumes:** current graph; approved materials when referenced; existing structured draft/review snapshots.
**Produces:** one proposal/review/commit service used by corrections and material enrichment. Reuse original Epic B's pure operation model; skip its canvas editor and generic chat-assist workspace.

Task 2 must be independently testable before Task 3 exists: inject a material-reference resolver into validation/review, typed as `(class_id: str, material_id: str, section_id: str) -> dict`, returning approved manifest hash and source excerpt or raising `ValueError`. Use a fixture resolver in tests; the API rejects material-bearing changes until Task 3 wires its approved registry resolver. Empty/no-material graph edits remain available.

```python
# operations.py; existing LearningBlock, NetworkEdge and MaterialMapping are reused.
class NetworkChangeSet(BaseModel):
    class_id: str
    base_revision: int
    summary: str
    operations: list[GraphOperation]
    material_id: str | None = None
    replacement_mappings: list[MaterialMapping] | None = None

def apply_change_set(current: CourseNetworkDocument,
                     changes: NetworkChangeSet) -> CourseNetworkDocument: ...

# GraphOperation is a discriminated union: AddNode(node), UpdateNode(node_id,
# title/description/learning_goal/curriculum_refs/material_refs patch),
# RetireNode(node_id), AddEdge(edge), RemoveEdge(edge_id). No arbitrary field patch.
# EditService methods: open(class_id, changes), update(draft_id, changes,
# expected_revision, expected_hash), review(draft_id), commit(draft_id,
# expected_revision, expected_hash). Resolve class/workspace from authenticated DI.
```

- [ ] Write pure-operation tests before implementation: source object unchanged; stale base rejected; IDs and class scope validated; retirement retains a tombstone but removes active incident edges/mappings; relation cycles blocked; revision increments once. For `replacement_mappings`, require `material_id`, permit only that material, and validate all section/node references.
- [ ] Implement operations on a copied document. Validate the full selected result after teacher decisions; rejecting a new node while keeping its mappings is an actionable validation error, not an automatic acceptance of the node. Retrying a committed draft returns its receipt without another revision increment.
- [ ] Extend structured draft updates with compare-and-swap revision/hash and review invalidation. Preserve adoption semantics. Add `/course/network/edits` POST and `/{draft_id}` GET/PUT, `/{draft_id}/review` POST, and `/{draft_id}/commit` POST under the existing class prefix.
- [ ] Bind review to the exact selected changes, current graph revision, and referenced material manifest hashes. Add material excerpts to the existing course-review packet for material-origin changes. Commit under the existing scoped publication lock; revalidate snapshots, publish JSON/overview/index, log, and mark the draft committed. Reuse the existing rollback/recovery pattern rather than adding a general transaction framework.
- [ ] On 409 preserve the teacher's pending proposal, show that the graph changed, and require explicit regeneration/review against the new base; never silently rebase and commit. A restart during a reserved commit must be reconciled to completed or retryable before another write.
- [ ] Run the task's tests plus existing adoption/review/store/draft tests; update contracts and commit the bounded change service.

```python
def test_rejecting_new_node_cannot_leave_its_mapping(current, proposal):
    proposal.operations = []
    # Fixture mapping targets a node only present in the removed AddNode operation.
    with pytest.raises(ValueError):
        apply_change_set(current, proposal)
```

## Task 3 — Make approved course materials independently available

**Create:** `backend/app/course_materials/models.py`, `sections.py`, `store.py`, `import_service.py`, `backend/app/api/course_material_routes.py`.
**Modify:** OCR scratch/promotion helpers only as needed, `wiki/materials.py`, API DI/router/schemas/OpenAPI, `context_limits.py`, `config.py`, `workflow_drafts.py` and existing active-workflow routes.
**Test:** new `test_course_material_sections.py`, `test_course_material_import.py`, `test_api_course_materials.py`; existing `test_materials_plan_api.py`, `test_materials_scratch.py`, `test_materials_ocr_packaging.py`.

**Consumes:** existing OCR package, authenticated workspace wiki, structured drafts.
**Produces:** approved standalone material library and immutable post-approval section IDs usable by mapping and planner retrieval.

```python
class CourseMaterialSection(BaseModel):
    id: str
    title: str
    page_start: int
    page_end: int
    content_anchor: str
    summary: str = ""

class CourseMaterialManifest(BaseModel):
    schema_version: Literal[1] = 1
    class_id: str
    material_id: str
    title: str
    arm: Literal["textbook", "personal"]
    source_hash: str
    source_filename: str
    sections: list[CourseMaterialSection]
    approved_at: datetime | None = None

# manifest: material.json; reviewed section bodies with stable anchors:
# document.agent.md; existing provenance/page_structure/assets are preserved.
def list_course_materials(wiki, class_id: str) -> list[CourseMaterialManifest]: ...
def read_course_material_section(wiki, class_id: str, material_id: str,
                                section_id: str) -> dict: ...
```

- [ ] Pin current session PDF upload/removal, page numbering, assets, and save-time promotion behavior. Add tests with duplicate headings: IDs must be unique and survive title/text edits and reload. Assign IDs once during extraction; split/merge assigns new IDs before approval. Validate positive original-page bounds, unique anchors, nonempty included text, and original source/class identity.
- [ ] Add a course-import wrapper around the existing OCR/package functions. Persist authenticated workspace/class ownership before starting work; never accept client-provided scratch paths. Keep scratch isolated by workspace/class/draft. Cap selected pages at `course_import_max_pages=30`, reuse existing byte/PDF limits, and preserve original page numbering and source PDF for inspection.
- [ ] Persist stages `extracting`, `document_review`, `mapping_review`, `complete`, `failed`. Work survives browser navigation through backend ownership and `/workflow/active`; on process restart mark unfinished generation/extraction retryable, retaining available source/draft data. Retry must use the same import identity and cannot destroy an approved package.
- [ ] Add material list/detail/section/asset GETs and import POST/GET/PUT/document-review/document-approve routes under `/classes/{class_id}/course`. Upload creates the draft; GET resumes; PUT edits the extraction snapshot; review validates and LLM-checks the exact content/provenance; approval promotes it. Source/asset reads validate class/workspace and path containment independently of plan sessions.
- [ ] Promote a complete package from staging only after approval; freeze its section IDs/content for this release. Corrected reimports create a new material version/ID, never overwrite mapped sections. Recognize a repeated successful approval and return its existing package. A material can be approved while mapping is pending; it stays visible in the library.
- [ ] Extend material discovery to scratch ∪ approved course manifests ∪ legacy lesson-linked packages, deduped by material ID. Preserve session exclusion/removal semantics: excluded material stays out of that plan's injected and read context. Do not auto-promote or retroactively map legacy packages merely because they are discovered.
- [ ] Run import/section/API tests and the existing PDF compatibility suite. Document manifests, approval stages, and class-source authorization; commit the material backend.

```python
def test_approved_import_is_visible_before_any_lesson_exists(wiki, approved_import):
    manifests = list_course_materials(wiki, approved_import.class_id)
    assert [m.material_id for m in manifests] == [approved_import.material_id]
    assert not list(wiki.class_dir(approved_import.class_id).glob("lessons/*/materials.json"))
```

## Task 4 — Add a focused graph-generation and enrichment procedure

**Create:** `backend/app/teacher_agent/skills/course_network_procedure.md`, `backend/app/course_network/generation.py`, `backend/tests/test_course_network_generation.py`.
**Modify:** `skills/loader.py`, network prompts/review, course network/material routes and schemas, `course_materials/import_service.py`, `docs/agent_contracts.md`.

**Consumes:** authorized curriculum sections, current graph/seed draft, approved material section summaries and excerpts, teacher scope/correction, base revision.
**Produces:** typed `NetworkChangeSet` plus noncanonical review rationale, coverage notes, and warnings. It never writes canonical data.

```python
class CourseGenerationRequest(BaseModel):
    purpose: Literal["curriculum_draft", "material_enrichment", "correction"]
    teacher_request: str
    material_id: str | None = None

class CourseGenerationResult(BaseModel):
    changes: NetworkChangeSet
    rationale_by_item: dict[str, str]
    coverage_notes: list[str]
    warnings: list[str]

async def generate_course_changes(wiki, class_id: str,
    request: CourseGenerationRequest, base: CourseNetworkDocument,
    model_runner) -> CourseGenerationResult: ...
```

- [ ] Define the procedure in reviewable Markdown: scope the teaching block; distinguish official expectations from pedagogical inference; reuse existing nodes; produce consistent teachable granularity; add sparse `builds_on`/`related_to` edges; map sections to nodes; attach source refs; report gaps. Explicitly treat source text as evidence, not instructions. Do not produce experiment procedures or a question bank in the graph.
- [ ] Register the named procedure in `load_skill`; call it only from the explicit course generation entry point. Build source-bearing packets from authorized backend reads. Use existing model routing and one structured proposal call per bounded request; use existing independent review on the resulting exact draft. Persist results in the draft before displaying them.
- [ ] Initially bound generation to 20 proposed concepts per scoped curriculum request and 8 new concepts per material import, through central settings. For 30-page imports, batch section evidence within existing material/context limits and merge by stable references before one teacher review. Report omitted/oversized evidence; do not imply complete coverage when content was skipped.
- [ ] For initial generation, revise the unadopted seed draft and use the existing adoption gate; no initial-generation path may replace an already-adopted graph. For enrichment/corrections, use Task 2's changes service. Expose a scope/request field and Generate/Revise action; this is not a new transcript-based chat mode.
- [ ] Keep draft artifact revision separate from canonical network revision: initial generated previews use `CourseNetworkDocument.for_draft_seed`, retain proposed statuses and network revision 1, and increment only the workflow artifact revision until adoption. Applied edits to an adopted network increment its canonical revision once. Do not route proposed seed nodes through canonical-write validation before adoption.
- [ ] Add generation endpoints: POST `/course/network/generate` for seed or correction requests, and POST `/course/material-imports/{draft_id}/mapping-generate` for the approved material. Resolve the current draft/base server-side. Preserve the original draft on model failure; never commit automatically after generation.
- [ ] Test with stubbed model packets: reuse activation-energy instead of duplicating it; preserve existing IDs; reject unknown or cross-class sections; reject unsupported official claims through review; surface sparse evidence; map one section to several nodes and several sections to one node. Include a relationship-direction golden and an injected-instruction fixture. No provider call is required in CI.
- [ ] Update the generation/review contract and commit the production procedure and bounded caller.

```python
def test_enrichment_reuses_existing_concept(generated_changes, existing_network):
    existing_ids = {node.id for node in existing_network.nodes}
    added_ids = {op.node.id for op in generated_changes.operations if op.op == "add_node"}
    assert not (added_ids & existing_ids)
    assert any(m.node_id == "activation-energy"
               for m in generated_changes.replacement_mappings)
```

## Task 5 — Connect a small course/material review workspace

**Create:** `frontend/src/app/classes/[classId]/course/materials/page.tsx`, `materials/import/[draftId]/page.tsx`; domain components `course-material-library.tsx`, `course-material-import.tsx`, `course-section-review.tsx`, `course-change-review.tsx` under `components/klassenpilot/course/`; `features/course-materials/use-course-import.ts`.
**Modify:** existing course workspace/adoption/inspector, `lib/api.ts`, `lib/running-jobs.ts`, PendingTurnNotifier, frontend architecture/design docs.
**Test:** new rendered import/change-review/inspector tests and import resume-state tests; existing course workspace tests.

**Consumes:** Tasks 2–4 routes, revision/hash snapshots, approved source/section/asset endpoints.
**Produces:** teacher-visible upload → document approval → mapping approval → inspect flow.

- [ ] Use a flat section list and preview with title/text/page correction, exclude, split, and merge actions before document approval. Every mutation saves a new draft snapshot and invalidates its old review. Keep only one primary action for the current stage.
- [ ] Display proposed mappings and additions as reusable review rows. Allow accept/reject and inline field/target correction; expose dependent-selection errors from validation. Show source pages and short reasons. Approved material remains available if mapping is postponed or fails.
- [ ] Reuse the existing canvas to highlight the selected concept and proposed result. Do not add drag-to-connect or a second graph state store. Add scope/request and Generate/Revise controls using the generation API; edits still go through review rows.
- [ ] Extend the node inspector to show mapped sections with page ranges and class-authorized content/assets. Group by material and distinguish curriculum evidence from teaching material. Clear stale section/source selection when the node changes; allow opening the material from the inspector.
- [ ] Integrate course jobs with the existing Running box and persisted snapshots. Browser navigation and refresh resume the active import; stale requests preserve pending work. On narrow screens, use the existing outline plus section/detail views instead of three squeezed columns.
- [ ] Test a real rendered interaction through both approvals, excluding a mapping, correcting a section, navigating away/back, opening a mapped asset, and rejecting a stale commit. Run typecheck and affected rendered tests; update frontend docs and commit the connected UI.

```tsx
// Transport remains in lib/api.ts; components receive snapshots and callbacks.
<CourseChangeReview
  draft={draft}
  onChange={saveSelectedChanges}
  onReview={reviewCurrentSnapshot}
  onApprove={commitReviewedSnapshot}
/>
// onApprove sends the reviewed artifact_revision/hash, never just draft_id.
```

## Task 6 — Make ordinary planning use the map and material sections

**Create:** `backend/app/course_network/retrieval.py`, `backend/tests/test_course_network_retrieval.py`.
**Modify:** `wiki/store.py`, `wiki/materials.py`, `wiki/context_packs.py`, `wiki/search.py`, `teacher_agent/tools.py`, `agents.py`, `prompt_assembly.py`, `planning_state.py`, `models.py`, `skills/lesson_planning_procedure.md`, central context settings.
**Test:** retrieval/context/tool tests, existing plan/prompt/evidence tests, new graph-aware planning golden fixtures.

**Consumes:** adopted graph, approved material registry, teacher request, existing class state/history.
**Produces:** bounded traceable course context, progressive tools, and validated proposed lesson associations for Task 7.

```python
class CourseSlice(BaseModel):
    class_id: str
    network_revision: int
    nodes: list[LearningBlock]
    edges: list[NetworkEdge]
    mappings: list[MaterialMapping]
    warnings: list[str]

def retrieve_course_slice(wiki, class_id: str, query: str, *,
                         primary_limit: int = 6,
                         total_limit: int = 12) -> CourseSlice: ...

# Planner read-only tool names:
# search_course_network(query), read_course_nodes(node_ids),
# read_node_material_sections(node_ids, purpose).
```

- [ ] Rank active nodes lexically using existing German normalization and source titles/goals. Use explicit teacher request first and current unit/recent lessons as context. Expand one hop of prerequisites and at most two relevant related nodes within the total cap. An unmatched query returns empty results plus a warning, not arbitrary nearest nodes.
- [ ] Inject a compact orientation only when an adopted graph exists, deduplicated against the active class slice. Include IDs/revision, learning goals, relationship labels, material section summaries and page refs; expose complete text only through tools. Keep framework/pedagogy and original no-network behavior intact.
- [ ] Implement the tools through the existing evidence/raw_ref capture path. Use task-filtered material visibility from Task 3, enforce class scope, and return missing/stale section warnings. Keep curriculum/material authority distinct. Record consulted nodes, material IDs, and section IDs in runtime evidence for later validation.
- [ ] Extend planner instructions to use relevant graph/material evidence automatically without requiring node selection. A prompt like “Plan the next lesson on catalysis” should retrieve its prerequisites and mapped pages, then consult class history before choosing recap or new content. Do not interpret a prerequisite edge as proof that this class has learned it.
- [ ] Measure trace section sizes and inspect chosen evidence in deterministic goldens for direct topics, prerequisites, ambiguous/no match, unavailable materials, teacher exclusions, sparse history, and no-network fallback. Assert correct source selection; do not claim token or quality improvement from graph presence alone.
- [ ] Run focused retrieval, tools, context, and prompt tests. Update agent architecture/contracts/context docs and commit planner retrieval.

```python
def test_catalysis_reads_its_prerequisite_and_mapped_pages(wiki, course_class):
    result = retrieve_course_slice(wiki, course_class, "Katalyse")
    ids = {node.id for node in result.nodes}
    assert {"catalysis", "activation-energy"} <= ids
    assert any(m.node_id == "catalysis" for m in result.mappings)
    assert len(result.nodes) <= 12
```

## Task 7 — Save lesson associations and ground result continuity

**Create:** `backend/app/course_network/lesson_refs.py`, `backend/app/services/course_lesson_publication.py`, `backend/tests/test_lesson_course_refs.py`, `test_course_lesson_publication.py`.
**Modify:** planning/memory runtime and output models, `artifact_spec.py`, `plan_service.py`, `ingest_service.py`, their reviewed proposal/save paths, existing material-link helper, lesson detail API and course inspector.
**Test:** new refs/publication tests; existing Plan/Ingest/API save/stream tests and runtime resume tests.

**Consumes:** Task 6 consulted evidence plus model-proposed associations, exact approved plan/results, current graph.
**Produces:** `lessons/{date}/course_refs.json`, consulted material IDs in existing `materials.json`, inspectable graph-to-lesson backlinks derived from those sidecars.

```python
class LessonCourseReference(BaseModel):
    node_id: str
    role: Literal["primary", "supporting", "prerequisite"]
    state: Literal["planned", "taught", "revisit"]
    evidence_quote: str = ""  # Exact approved result excerpt for taught/revisit.

class LessonCourseReferences(BaseModel):
    schema_version: Literal[1] = 1
    class_id: str
    lesson_date: date
    network_revision: int
    references: list[LessonCourseReference]
    updated_at: datetime

def validate_lesson_references(network: CourseNetworkDocument,
    refs: LessonCourseReferences, *, approved_results: str | None
    ) -> LessonCourseReferences: ...
```

- [ ] Add `course_alignment` to planning state/output with merge/dedupe and resume serialization. Validate proposed node IDs and consulted material/section IDs against the current class/network. Old drafts deserialize with empty alignment. Keep references visible as a compact part of the normal plan save review, without a separate tagging gate.
- [ ] Bind the sidecar payload to the same reviewed plan snapshot: store a companion refs hash/revision with the existing review snapshot, invalidate it when associations change, and revalidate it at save. Do not weaken the existing Markdown/date-stamp fingerprint gate. If graph revision changed, resolve still-valid IDs and require a fresh reviewed association snapshot before saving; never save unknown/retired nodes as new planned work.
- [ ] Prevalidate and stage the plan, new material promotions, consulted-plus-promoted material IDs, and refs. Add a narrow class/lesson-scoped publication helper with lock, snapshots/staging, and persisted recovery receipt. Finish or roll back interrupted publication before another save; return saved only when all required files and metadata agree. Preserve existing no-network paths and plan date normalization.
- [ ] For Update Memory, propose taught/revisit associations from the current approved-results draft and known course IDs. Show them in its existing review; freeze them to that draft snapshot. Require an exact supporting quote and semantic match to the concept in the bounded review. Simply carrying a planned node forward keeps state `planned`; do not mark every plan node taught. Never infer mastery.
- [ ] Publish result associations within the existing approved ingest commit's staged/rollback boundary, not as an unguarded post-commit append. Preserve the existing wiki/raw/rollup approval behavior; validate before writing. Unsupported concepts or sparse evidence leave associations unconfirmed with a visible warning, without inventing coverage.
- [ ] Derive node-to-lesson links by scanning class lesson sidecars (small MVP dataset), without duplicating lesson content in the graph. Show planned versus evidenced taught/revisit links in the inspector. Feed relevant results/history into subsequent course retrieval; missing sidecars on old lessons are valid.
- [ ] Test restart/failure between staged writes, retry idempotency, draft edits after review, graph revision drift, consulted library material IDs, unplanned results, partial actual coverage, old-draft compatibility, and cross-class requests. Run affected Plan/Ingest/API/runtime suites; update memory hierarchy/wiki/agent contracts and commit the completed continuity loop.

```python
def test_taught_reference_requires_approved_result_evidence(network, planned_refs):
    proposed = planned_refs.model_copy(deep=True)
    proposed.references[0].state = "taught"
    proposed.references[0].evidence_quote = ""
    with pytest.raises(ValueError):
        validate_lesson_references(network, proposed,
            approved_results="We covered activation energy; catalysis was postponed.")
# Also test the full propose/review/commit path with these partial results:
# activation-energy may become taught; catalysis must stay planned.
```

## Task 8 — Prove the full workflow and prepare the release

**Create:** `backend/tests/test_course_network_end_to_end.py`, a small text/figure PDF fixture with redistribution permission, and `implementation_plans/course_network/06_release_evidence.md` during execution.
**Modify:** `docs/pm_hub.md`, `docs/product_vision.md`, `implementation_plans/product_backlog.md`, agent contracts/architecture/context/memory docs, frontend docs, this folder's README.

**Consumes:** all previous tasks. **Produces:** reproducible evidence for the release scenario and a scoped integration-ready branch.

- [ ] Add an offline integration test using stubbed OCR/proposer/reviewer/planner boundaries: provision → adopt → upload → correct section → approve material → generate/review/approve mappings → retrieve during plan → save refs → approve partial results → retrieve next lesson. Assert that before each approval canonical data remains unchanged and that the generated plan cites the mapped material section.
- [ ] Add negative cases for another workspace/class, missing source/asset, unchanged graph after failed review, stale approval, retry without duplicate publication, and no-network fallback. Keep generated-question extraction and mastery inference absent.
- [ ] Run focused tests as each task lands. At release run the full deterministic backend/frontend suite and frontend typecheck once; rerun after fixes only. Review the actual final diff and check that interfaces/docs describe implemented behavior rather than planned features.
- [ ] Start a worktree-scoped fresh sandbox for final HITL, preserving the existing manually used sandbox. Use the helper's available isolation options or a separate verified sandbox path; never reset the teacher's current Chemie 8a data without explicit instruction. Use the URLs printed by the helper, not stale README ports.
- [ ] Perform the scope document's acceptance scenario with actual OCR and generation/planning calls when credentials are available and the live run is authorized. Record model/profile, source fixture, evidence excerpts, selected material pages, and failures. If live validation cannot run, state the release is awaiting that gate; stub tests alone are not evidence of pedagogical usefulness.
- [ ] Verify desktop selection/source navigation and narrow outline/material review, browser navigation during OCR/generation, and process-restart failure/retry. Verify that the next lesson responds to the approved partial-results evidence rather than assuming the saved plan was taught.
- [ ] Record exact tested commit(s), test commands/results, worktree/branch, stack/URLs, sandbox/wiki changes, known limitations, and acceptance disposition in `06_release_evidence.md`. Mark shipped only after integration/deployment is actually completed under the execution session's authorization.

```powershell
# Worktree root, after task-focused tests are green:
.\scripts\test.ps1
cd frontend
npm run typecheck
cd ..
git diff --check
# Inspect helper options and existing sandbox before choosing a fresh HITL path:
.\scripts\worktree-stack.cmd --help
```

## Verification and completion rules

For each implementation task, write the named behavior tests, run them to establish the missing behavior, implement the bounded change, run the focused tests, and commit only relevant files. Where existing tests already prove a behavior, reuse them instead of duplicating them. Run each new test file with `backend/.venv/Scripts/python -m pytest tests/<named-file>.py`; frontend rendered tests use the existing Vitest setup.

Self-review this plan against the scope before execution: upload independent of lessons (3/5), correction/approval (2/3/5), generated concepts and relationships (4), inspect sources/materials (1/5), automatic planning use (6), saved links/results (7), and complete acceptance (8). No first-release requirement depends on the deferred canvas or whole-book editor.

## Execution handoff

Start with Task 1 in the existing course-network branch. Recheck Git state and available runtime/test environments before changes. Proceed task-by-task using this scope; consult the old B/C/D plans for reusable detail only. This planning change does not implement, merge, deploy, start Docker, or modify wiki fixtures.
