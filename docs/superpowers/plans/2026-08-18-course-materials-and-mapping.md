# Course Materials and Network Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a teacher upload textbook chapters or teacher materials independently of lesson planning, review the extracted document, approve it into the class wiki, then review and approve how its sections map to the adopted course network.

**Architecture:** Extract the reusable OCR/package policy from the plan-session upload path into a class-owned ingestion service. Each upload creates a durable structured import draft with two explicit gates: document review and network-mapping review. Approval promotes the reviewed package through the existing class material arms under `wiki/classes/{class_id}/materials/{textbooks|personal}/{material_id}/`; mapping approval atomically updates typed mappings in the class network. Existing lesson-planning uploads continue to work through the shared OCR service and retain save-time promotion semantics.

**Tech Stack:** FastAPI, Pydantic 2, existing Mistral OCR pipeline, existing workflow-draft SQLite store and executive review lifecycle, stdlib filesystem/JSON, Next.js 15, React 19, TypeScript, shared KlassenPilot UI, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-17-class-course-network-design.md`

## Global Constraints

- C1/C2 start after the foundation plan. C3 starts after Epic B so it can reuse
  typed network operations and exact operation review.
- Upload and graph generation are quarterly/as-needed course maintenance, never a per-lesson requirement.
- Only PDF is accepted in this MVP because the existing runtime OCR contract is PDF-only.
- Mistral remains the only runtime OCR provider; do not present OpenAI vision as a fallback.
- OCR and model output never directly write canonical material or network files.
- A teacher approves the extracted document before mapping begins.
- A teacher separately approves the section-to-node mappings before they become canonical.
- Questions and exercises remain ordinary material content. Do not extract a question bank, question entities, answers, or rubrics in this plan.
- Future structured questions must carry a fixed, versioned rubric, but that is documented future scope only.
- Existing lesson-plan material upload and plan-save promotion remain behaviorally compatible.
- No new package or graph database is added.

## Canonical Material Contract

```text
wiki/classes/{class_id}/materials/{textbooks|personal}/{material_id}/
  material.json
  document.agent.md
  summary.md
  provenance.json
  page_structure.json
  assets/*
```

```python
class MaterialSection(BaseModel):
    id: str
    heading: str
    level: int = Field(ge=1, le=6)
    parent_id: str | None = None
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    content_markdown: str
    summary: str = ""

class MaterialDocument(BaseModel):
    schema_version: Literal[1] = 1
    material_id: str
    class_id: str
    title: str
    kind: Literal["textbook", "teacher_material"]
    authors: list[str] = Field(default_factory=list)
    publisher: str = ""
    edition: str = ""
    language: str = "de"
    source_filename: str
    content_hash: str
    sections: list[MaterialSection]

class CanonicalMaterial(MaterialDocument):
    approved_at: datetime
```

`material.json` is the approved identity and section hierarchy.
`document.agent.md`, assets, page structure, and provenance retain the existing
OCR package roles. The Markdown parser remains available for retrieval, but
new course workflows use stable section IDs from `material.json`. The existing
internal `personal` arm is shown to teachers as Teacher material; this plan does
not migrate or duplicate already-promoted packages.

---

## PR C1 - Shared OCR Policy and Durable Course Imports

### Task 1: Characterize the existing plan-session material behavior

**Files:**
- Test: `backend/tests/test_materials_plan_api.py`
- Test: `backend/tests/test_materials_scratch.py`
- Test: `backend/tests/test_materials_ocr_packaging.py`

- [ ] **Step 1: Add compatibility tests before refactoring**

Pin PDF-only validation, scratch package shape, material ID stability, asset
resolution, context registry behavior, save-time promotion, and
`lessons/{lesson}/materials.json` output. Also assert OCR never writes MemV4,
`course_state.md`, timeline, diary, or a course network.

- [ ] **Step 2: Run the characterization suite**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_materials_plan_api.py tests\test_materials_scratch.py tests\test_materials_ocr_packaging.py tests\test_api_plan.py -v
```

Expected: PASS before the refactor.

- [ ] **Step 3: Commit the tests**

```powershell
git add backend/tests/test_materials_plan_api.py backend/tests/test_materials_scratch.py backend/tests/test_materials_ocr_packaging.py
git commit -m "test: pin plan material ingestion behavior"
```

### Task 2: Extract a shared OCR/package service

**Files:**
- Create: `backend/app/services/material_ingestion.py`
- Modify: `backend/app/services/materials_ocr.py`
- Modify: `backend/app/services/materials_ocr_packaging.py`
- Modify: `backend/app/services/materials_scratch.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_material_ingestion.py`
- Test: `backend/tests/test_materials_plan_api.py`

**Interfaces:**

```python
class OcrPackageRequest(BaseModel):
    class_id: str
    source_filename: str
    content_type: Literal["application/pdf"]
    content: bytes
    scratch_root: Path

class OcrPackageResult(BaseModel):
    material_id: str
    package_dir: Path
    source_filename: str
    content_hash: str
    page_count: int

async def create_ocr_package(request: OcrPackageRequest) -> OcrPackageResult: ...
```

- [ ] **Step 1: Write failing service tests**

Mock the OCR provider at the service boundary. Assert path containment,
filename sanitization, hash-derived identity, byte/page limits, cancellation
cleanup, complete package files, and no canonical writes.

- [ ] **Step 2: Move orchestration behind the shared service**

Keep OCR prompts and package assembly where they are. Move request validation,
scratch directory lifecycle, and result normalization to
`material_ingestion.py`. Change the existing plan route and
`materials_scratch.py` to call the service without changing response schemas.

- [ ] **Step 3: Run compatibility and service tests**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_material_ingestion.py tests\test_materials_plan_api.py tests\test_materials_scratch.py tests\test_materials_ocr_packaging.py -v
```

- [ ] **Step 4: Commit**

```powershell
git add backend/app/services/material_ingestion.py backend/app/services/materials_ocr.py backend/app/services/materials_ocr_packaging.py backend/app/services/materials_scratch.py backend/app/api/routes.py backend/tests/test_material_ingestion.py backend/tests/test_materials_plan_api.py
git commit -m "refactor: share material OCR packaging"
```

### Task 3: Define import artifacts and section identity

**Files:**
- Create: `backend/app/course_materials/__init__.py`
- Create: `backend/app/course_materials/models.py`
- Create: `backend/app/course_materials/sections.py`
- Test: `backend/tests/test_course_material_sections.py`

**Interfaces:**

```python
class MaterialImportArtifact(BaseModel):
    class_id: str
    material_id: str
    stage: Literal["extracting", "document_review", "mapping_review"]
    document: MaterialDocument | None = None
    proposed_enrichment: MaterialEnrichmentChangeSet | None = None

def build_sections(
    *,
    material_id: str,
    document_markdown: str,
    page_structure: dict[str, Any],
) -> list[MaterialSection]: ...

def section_id(
    material_id: str,
    heading_path: tuple[str, ...],
    page_start: int,
) -> str: ...
```

- [ ] **Step 1: Write failing section tests**

Cover nested headings, duplicated headings on different pages, headingless
pages, empty summaries, page boundaries, normalized but stable IDs, and
questions/exercises remaining inside `content_markdown`.

- [ ] **Step 2: Implement deterministic section construction**

Use OCR page structure when present and heading parsing as a bounded fallback.
Section IDs derive from material ID, normalized heading path, and first source
page. Do not let an LLM assign canonical IDs.

- [ ] **Step 3: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_material_sections.py -v
git add backend/app/course_materials/__init__.py backend/app/course_materials/models.py backend/app/course_materials/sections.py backend/tests/test_course_material_sections.py
git commit -m "feat: model course material imports"
```

### Task 4: Create class-owned import drafts and background extraction

**Files:**
- Create: `backend/app/course_materials/import_service.py`
- Create: `backend/app/api/course_material_routes.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/schemas/api.py`
- Modify: `backend/app/services/workflow_drafts.py`
- Test: `backend/tests/test_course_material_import_service.py`
- Test: `backend/tests/test_api_course_material_import.py`
- Test: `backend/tests/test_api_workflow_active.py`

**Routes:**

```text
POST   /api/classes/{class_id}/course/material-imports
GET    /api/classes/{class_id}/course/material-imports/{draft_id}
PUT    /api/classes/{class_id}/course/material-imports/{draft_id}/document
DELETE /api/classes/{class_id}/course/material-imports/{draft_id}
```

- [ ] **Step 1: Write failing API and service tests**

Cover multipart PDF validation, active-draft identity, extraction state,
failure recovery, cross-class access, structured artifact revision/hash,
editable document fields, immutable source filename/hash/pages, and discard
cleanup limited to the exact scratch package.

- [ ] **Step 2: Implement import draft creation**

Use mode `course_material`, intent `import`, and target kind `pdf`. Save a
minimal `extracting` artifact before starting OCR. Update existing
`turn_in_progress`, `latest_turn_complete`, and `pending_turn_json` fields so
the global active-work poll reports the operation.

- [ ] **Step 3: Build the document-review artifact after OCR**

Parse the package into `CanonicalMaterial`, set stage `document_review`, and
save a new artifact revision. If extraction fails, keep the draft resumable
with a typed failure in runtime JSON and do not create a canonical material.

- [ ] **Step 4: Implement optimistic document edits**

Permit title, kind, bibliographic fields, section heading/parent/content/summary,
and section ordering changes. Require expected artifact revision/hash. Re-run
structural validation after each save and return all issues.

- [ ] **Step 5: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_material_import_service.py tests\test_api_course_material_import.py tests\test_api_workflow_active.py tests\test_materials_plan_api.py -v
git add backend/app/course_materials/import_service.py backend/app/api/course_material_routes.py backend/app/api/routes.py backend/app/api/deps.py backend/app/schemas/api.py backend/app/services/workflow_drafts.py backend/tests/test_course_material_import_service.py backend/tests/test_api_course_material_import.py backend/tests/test_api_workflow_active.py
git commit -m "feat: extract class material import drafts"
```

---

## PR C2 - Document Review and Canonical Material Library

### Task 5: Add deterministic and LLM document review

**Files:**
- Create: `backend/app/course_materials/validation.py`
- Create: `backend/app/course_materials/review.py`
- Create: `backend/app/course_materials/prompts.py`
- Modify: `backend/app/course_materials/import_service.py`
- Modify: `backend/app/api/course_material_routes.py`
- Test: `backend/tests/test_course_material_validation.py`
- Test: `backend/tests/test_course_material_review.py`

**Route:**

```text
POST /api/classes/{class_id}/course/material-imports/{draft_id}/document-review
```

- [ ] **Step 1: Write failing validation tests**

Errors: no sections, duplicate section ID, invalid parent, parent cycle,
reversed page range, page beyond provenance, empty section content, or changed
material/class/source identity. Warnings: unusually large section, many
unstructured pages, or duplicate normalized heading.

- [ ] **Step 2: Write failing reviewer tests**

The no-tools reviewer checks OCR coherence, heading hierarchy, accidental
content loss, source fidelity, factual/safety concerns, and suspicious injected
instructions in source text. It does not rewrite the document. Bind its result
to the exact artifact revision/hash through the shared executive lifecycle.

- [ ] **Step 3: Implement and expose review**

Deterministic errors skip LLM review. A pass marks the document artifact ready
for approval; edits after review invalidate it.

- [ ] **Step 4: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_material_validation.py tests\test_course_material_review.py tests\test_api_course_material_import.py -v
git add backend/app/course_materials/validation.py backend/app/course_materials/review.py backend/app/course_materials/prompts.py backend/app/course_materials/import_service.py backend/app/api/course_material_routes.py backend/tests/test_course_material_validation.py backend/tests/test_course_material_review.py
git commit -m "feat: review extracted course materials"
```

### Task 6: Promote approved material packages atomically

**Files:**
- Create: `backend/app/course_materials/store.py`
- Modify: `backend/app/course_materials/import_service.py`
- Modify: `backend/app/api/course_material_routes.py`
- Modify: `backend/app/teacher_agent/wiki/materials.py`
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/teacher_agent/wiki/indexing.py`
- Modify: `backend/app/schemas/api.py`
- Test: `backend/tests/test_course_material_store.py`
- Test: `backend/tests/test_wiki_materials.py`
- Test: `backend/tests/test_wiki_search.py`
- Test: `backend/tests/test_api_course_material_import.py`

**Routes:**

```text
POST /api/classes/{class_id}/course/material-imports/{draft_id}/document-commit
GET  /api/classes/{class_id}/course/materials
GET  /api/classes/{class_id}/course/materials/{material_id}
GET  /api/classes/{class_id}/course/materials/{material_id}/assets/{filename}
```

- [ ] **Step 1: Write failing promotion and retrieval tests**

Require exact review, artifact revision/hash, and no existing conflicting
material ID. Assert a temporary sibling directory is fully assembled before
rename; a failure leaves no partial canonical directory; source package files
are retained; canonical `material.json` equals the reviewed artifact; assets
cannot escape the material directory; and the material becomes searchable by
title, heading, and body text.

- [ ] **Step 2: Implement canonical material store**

Expose list/read/search/asset methods through `WikiStore`. Extend the existing
materials registry to union canonical course materials with plan scratch and
lesson-linked packages without duplicate IDs. Course-library materials are
available to planning even before a lesson references them.

- [ ] **Step 3: Implement document commit**

Evaluate the exact write gate, promote atomically, mark the draft stage
`mapping_review`, retain the reviewed document and source package reference,
and leave `proposed_mappings` empty until generated. If the class has no adopted
network, return the canonical material plus `mapping_available=false`; the
teacher can map it after adoption.

- [ ] **Step 4: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_material_store.py tests\test_wiki_materials.py tests\test_wiki_search.py tests\test_api_course_material_import.py tests\test_materials_plan_api.py -v
git add backend/app/course_materials/store.py backend/app/course_materials/import_service.py backend/app/api/course_material_routes.py backend/app/teacher_agent/wiki/materials.py backend/app/teacher_agent/wiki/store.py backend/app/teacher_agent/wiki/indexing.py backend/app/schemas/api.py backend/tests/test_course_material_store.py backend/tests/test_wiki_materials.py backend/tests/test_wiki_search.py backend/tests/test_api_course_material_import.py
git commit -m "feat: promote reviewed course materials"
```

### Task 7: Build the course materials pages and extraction review

**Files:**
- Create: `frontend/src/app/classes/[classId]/course/materials/page.tsx`
- Create: `frontend/src/app/classes/[classId]/course/materials/import/[draftId]/page.tsx`
- Create: `frontend/src/components/klassenpilot/course/course-material-library.tsx`
- Create: `frontend/src/components/klassenpilot/course/course-material-upload.tsx`
- Create: `frontend/src/components/klassenpilot/course/material-document-review.tsx`
- Create: `frontend/src/components/klassenpilot/course/material-section-editor.tsx`
- Create: `frontend/src/features/course-materials/import-state.ts`
- Create: `frontend/src/features/course-materials/import-state.test.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/material-asset-urls.ts`
- Modify: `frontend/src/lib/running-jobs.ts`
- Modify: `frontend/src/lib/running-jobs.test.ts`
- Modify: `frontend/src/components/klassenpilot/pending-turn-notifier.tsx`
- Test: `frontend/src/components/klassenpilot/course/material-document-review.test.ts`
- Test: `frontend/src/lib/material-asset-urls.test.ts`

- [ ] **Step 1: Write import-state and document-review tests**

Cover uploading, extracting, extraction failed, document editing, dirty,
reviewing, review blocked, ready to approve, approving, mapping available, and
canonical-only states. Verify exact-revision requests and safe asset URLs.

- [ ] **Step 2: Build the material library**

Show title, kind, source filename, section count, import date, and mapping
coverage. Upload is a course action. Support repeated quarterly uploads and
multiple concurrent completed materials; each active draft has its own route.

- [ ] **Step 3: Build extraction review**

Compose `ReviewChrome` for status/actions. Render editable metadata and an
ordered section outline beside a source-page/Markdown preview. Make page spans
and parent relationships visible. The teacher can edit extracted content but
cannot alter source identity or provenance.

- [ ] **Step 4: Connect background extraction status**

Extend `RunningJobMode` with `course_material` and map it to the import route.
When a course-material job stops, `PendingTurnNotifier` fetches the import draft
through its course endpoint instead of casting it to `ArtifactMode` or hydrating
the assistant-ui draft store. A teacher may leave the page and return without
losing the draft.

- [ ] **Step 5: Run and commit**

```powershell
cd frontend
npm test -- --run src/features/course-materials/import-state.test.ts src/components/klassenpilot/course/material-document-review.test.ts src/lib/material-asset-urls.test.ts src/lib/api.test.ts
npm run lint
git add frontend/src/app/classes/[classId]/course/materials/page.tsx frontend/src/app/classes/[classId]/course/materials/import/[draftId]/page.tsx frontend/src/components/klassenpilot/course/course-material-library.tsx frontend/src/components/klassenpilot/course/course-material-upload.tsx frontend/src/components/klassenpilot/course/material-document-review.tsx frontend/src/components/klassenpilot/course/material-section-editor.tsx frontend/src/features/course-materials/import-state.ts frontend/src/features/course-materials/import-state.test.ts frontend/src/lib/api.ts frontend/src/lib/material-asset-urls.ts frontend/src/lib/running-jobs.ts frontend/src/lib/running-jobs.test.ts frontend/src/components/klassenpilot/pending-turn-notifier.tsx frontend/src/components/klassenpilot/course/material-document-review.test.ts frontend/src/lib/material-asset-urls.test.ts
git commit -m "feat: review course material extraction"
```

---

## PR C3 - Section-to-Network Mapping

### Task 8: Define canonical mappings and coverage

**Files:**
- Modify: `backend/app/course_network/models.py`
- Create: `backend/app/course_network/mappings.py`
- Modify: `backend/app/course_network/validation.py`
- Test: `backend/tests/test_course_network_mappings.py`

**Interfaces:**

```python
class MaterialMapping(BaseModel):
    id: str
    material_id: str
    section_id: str
    node_id: str
    relation: Literal["explains", "practices", "assesses", "extends"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    teacher_note: str = ""
    origin: Literal["agent", "teacher"]

class MappingCoverage(BaseModel):
    total_sections: int
    mapped_sections: int
    unmapped_section_ids: list[str]
    nodes_with_material: int
```

- [ ] **Step 1: Write failing mapping tests**

Reject unknown material/section/node, duplicate material-section-node relation,
invalid relation, or a section from another material. Allow a section to map to
multiple nodes and a node to receive multiple sections. Derive coverage
deterministically without treating unmapped sections as errors.

- [ ] **Step 2: Implement mappings in `network.json`**

Mappings live in the class course network as external links; do not copy
material content into nodes. Canonical mapping IDs derive from material,
section, node, and relation. Remove mappings automatically only when their node
is explicitly deleted through reviewed graph operations.

- [ ] **Step 3: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_network_mappings.py tests\test_course_network_validation.py tests\test_course_network_operations.py -v
git add backend/app/course_network/models.py backend/app/course_network/mappings.py backend/app/course_network/validation.py backend/tests/test_course_network_mappings.py
git commit -m "feat: model material network mappings"
```

### Task 9: Generate bounded mapping and graph-enrichment proposals

**Files:**
- Create: `backend/app/course_materials/mapping_agent.py`
- Modify: `backend/app/course_materials/prompts.py`
- Modify: `backend/app/course_materials/import_service.py`
- Modify: `backend/app/api/course_material_routes.py`
- Modify: `backend/app/schemas/api.py`
- Test: `backend/tests/test_course_material_mapping_agent.py`
- Test: `backend/tests/test_api_course_material_mapping.py`

**Route:**

```text
POST /api/classes/{class_id}/course/material-imports/{draft_id}/mapping-generate
```

**Artifact:**

```python
class MaterialEnrichmentChangeSet(BaseModel):
    class_id: str
    material_id: str
    base_network_revision: int
    summary: str
    node_operations: list[GraphOperation] = Field(default_factory=list)
    mappings: list[MaterialMapping] = Field(default_factory=list)
```

For this workflow, `node_operations` permits `add_node`, `update_node`,
`add_edge`, and `delete_edge`. It does not permit deleting a Lernbaustein.
Material-origin additions carry an approved `material_id`/`section_id`
provenance reference; new nodes carry status `proposed` until commit, and new
edges carry origin `material`.

- [ ] **Step 1: Write failing mapping-agent tests**

The model receives approved section summaries/content excerpts and the adopted
network node summaries. It returns a typed `MaterialEnrichmentChangeSet` with
reasoning omitted from canonical data. Assert batching by section, bounded
context, deterministic ID replacement, invalid-reference rejection, grounded
missing-node proposals, relationship proposals, duplicate-title handling, and
no question extraction.

- [ ] **Step 2: Implement proposal generation**

Use a no-tools structured-output agent. For large books, batch sections within
central context limits, merge candidates by canonical mapping/operation ID,
validate against the exact approved material and current network revision, and
save into the existing import artifact as a new revision. New nodes are allowed
only when no existing node adequately represents the approved section; they
must include material provenance. Store the base network revision in runtime
JSON.

- [ ] **Step 3: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_material_mapping_agent.py tests\test_api_course_material_mapping.py -v
git add backend/app/course_materials/mapping_agent.py backend/app/course_materials/prompts.py backend/app/course_materials/import_service.py backend/app/api/course_material_routes.py backend/app/schemas/api.py backend/tests/test_course_material_mapping_agent.py backend/tests/test_api_course_material_mapping.py
git commit -m "feat: propose course material enrichment"
```

### Task 10: Support teacher edits and exact enrichment review

**Files:**
- Create: `backend/app/course_materials/mapping_review.py`
- Modify: `backend/app/course_materials/import_service.py`
- Modify: `backend/app/api/course_material_routes.py`
- Test: `backend/tests/test_course_material_mapping_review.py`
- Test: `backend/tests/test_api_course_material_mapping.py`

**Routes:**

```text
PUT  /api/classes/{class_id}/course/material-imports/{draft_id}/enrichment
POST /api/classes/{class_id}/course/material-imports/{draft_id}/enrichment-review
POST /api/classes/{class_id}/course/material-imports/{draft_id}/enrichment-commit
```

- [ ] **Step 1: Write failing edit/review/commit tests**

Cover adding, changing, and removing mappings; accepting/editing/rejecting
missing-node and edge operations; teacher-origin attribution; deterministic
reference errors; LLM review of implausible or unsafe links; edited-after-review
invalidation; stale network revision; exact artifact hash; atomic canonical
network update; overview rebuild; and terminal imported status.

- [ ] **Step 2: Implement enrichment edits**

Replace the proposed enrichment change set as a structured artifact update.
Preserve agent versus teacher origin per mapping and material provenance on
new nodes. Each request carries expected artifact revision/hash; edits clear
the active review.

- [ ] **Step 3: Implement enrichment review**

Reuse the exact executive lifecycle with a material-enrichment no-tools
reviewer. Check semantic fit, whether a proposed node is genuinely missing,
learning-goal quality, prerequisite plausibility, relation choice, suspicious
source instructions, and broad over-mapping. The reviewer cannot change nodes,
sections, operations, or mappings.

- [ ] **Step 4: Implement canonical enrichment commit**

Lock and reload the canonical network, verify base revision, apply the reviewed
node/edge operations, validate mappings against the resulting network and
canonical material, replace this material's mapping set, convert accepted node
status to `adopted`, and increment the network revision once. Atomically replace
`network.json` as the commit point, then regenerate the rebuildable overview
and mark the import draft `committed`. On staleness, retain the proposal and
return enough state for regeneration or teacher correction.

- [ ] **Step 5: Run and commit**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_course_material_mapping_review.py tests\test_api_course_material_mapping.py tests\test_course_network_mappings.py tests\test_course_network_store.py -v
git add backend/app/course_materials/mapping_review.py backend/app/course_materials/import_service.py backend/app/api/course_material_routes.py backend/tests/test_course_material_mapping_review.py backend/tests/test_api_course_material_mapping.py
git commit -m "feat: review and commit material enrichment"
```

### Task 11: Build visual mapping review

**Files:**
- Create: `frontend/src/components/klassenpilot/course/material-mapping-review.tsx`
- Create: `frontend/src/components/klassenpilot/course/material-section-list.tsx`
- Create: `frontend/src/components/klassenpilot/course/material-mapping-inspector.tsx`
- Modify: `frontend/src/components/klassenpilot/course/course-network-canvas.tsx`
- Modify: `frontend/src/components/klassenpilot/course/learning-block-node.tsx`
- Modify: `frontend/src/features/course-materials/import-state.ts`
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/components/klassenpilot/course/material-mapping-review.test.ts`
- Test: `frontend/src/features/course-materials/import-state.test.ts`

- [ ] **Step 1: Write mapping interaction tests**

Assert section selection highlights proposed/existing nodes, node selection
filters sections, new-node and edge operations have accept/edit/reject controls,
relation edits are keyboard reachable, unmapped sections remain visible,
confidence is labeled as a suggestion, review status is exact-revision bound,
and commit is disabled until review passes.

- [ ] **Step 2: Implement a split mapping workspace**

Desktop: searchable section outline left, proposed-result network canvas
center, selected mapping/operation inspector right. Narrow layout: section
cards with node combobox, relation select, and proposed node/edge cards; the
full canvas becomes optional inspection. Reuse network node/canvas and typed
operation-review components plus semantic tokens.

- [ ] **Step 3: Connect generate, edit, review, and commit**

After document approval, present Generate mapping. The teacher may accept,
edit, or reject mapping and graph-enrichment operations before Review changes.
Final action says Apply to course network and returns to the material library
with coverage status.

- [ ] **Step 4: Run and commit**

```powershell
cd frontend
npm test -- --run src/components/klassenpilot/course/material-mapping-review.test.ts src/features/course-materials/import-state.test.ts src/lib/api.test.ts
npm run lint
git add frontend/src/components/klassenpilot/course/material-mapping-review.tsx frontend/src/components/klassenpilot/course/material-section-list.tsx frontend/src/components/klassenpilot/course/material-mapping-inspector.tsx frontend/src/components/klassenpilot/course/course-network-canvas.tsx frontend/src/components/klassenpilot/course/learning-block-node.tsx frontend/src/features/course-materials/import-state.ts frontend/src/lib/api.ts frontend/src/components/klassenpilot/course/material-mapping-review.test.ts frontend/src/features/course-materials/import-state.test.ts
git commit -m "feat: review material network mappings"
```

### Task 12: Update contracts and run Epic C acceptance

**Files:**
- Modify: `docs/agent_contracts.md`
- Modify: `docs/memory_hierarchy.md`
- Modify: `docs/agent_architecture.md`
- Modify: `docs/context_management.md`
- Modify: `frontend/ARCHITECTURE.md`
- Modify: `backend/app/api/README.md`
- Modify: `implementation_plans/product_backlog.md`
- Modify: generated OpenAPI artifact used by the repository

- [ ] **Step 1: Document material and mapping contracts**

Record the two review gates, canonical package files, stable section IDs,
mapping ownership, OCR provider limit, planning visibility, and question/rubric
scope boundary. Explain how the old plan upload delegates to the shared OCR
service while keeping save-time promotion behavior.

- [ ] **Step 2: Run deterministic suites**

```powershell
.\scripts\test.ps1
```

Expected: PASS without live OCR or OpenAI calls.

- [ ] **Step 3: Run HITL acceptance**

```powershell
.\scripts\worktree-stack.cmd up --beta --fresh-beta-data
```

For Chemie 8 NTG, upload a multi-chapter PDF; leave during extraction; resume;
correct title and one section; invalidate and repeat review; approve the
document; generate mappings; remove one weak mapping and add one manually;
review; commit; inspect mapping coverage; search for section text; and verify a
new plan can cite the canonical material. Confirm an existing plan-only upload
still promotes on plan save.

- [ ] **Step 4: Commit documentation**

```powershell
git add docs/agent_contracts.md docs/memory_hierarchy.md docs/agent_architecture.md docs/context_management.md frontend/ARCHITECTURE.md backend/app/api/README.md implementation_plans/product_backlog.md
git commit -m "docs: define course material ingestion"
```

## PR C1 Exit Criteria

- Existing plan uploads use the shared OCR/package service without behavior changes.
- Course uploads survive navigation and expose a resumable document-review draft.
- Extraction creates no canonical wiki write.

## PR C2 Exit Criteria

- Teachers can inspect and correct extracted document structure and content.
- Exact deterministic and LLM review gates material approval.
- Approved materials are class-owned, searchable, and available to planning.

## PR C3 Exit Criteria

- The agent proposes section-to-node links and genuinely missing nodes/edges
  without directly modifying canonical sources.
- Teachers can review and edit mappings and graph operations with canvas and narrow-layout controls.
- Enrichment writes are exact-revision, atomic at canonical JSON, class-owned, and independently approved.
- Questions remain material content and no question-bank schema is introduced.
