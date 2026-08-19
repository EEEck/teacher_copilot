# Course Network Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a teacher create a Chemie 8/9 NTG class, review and adopt a curriculum-seeded class network, and inspect it in a read-only course workspace.

**Architecture:** Port only the deterministic class-provisioning slice from the unmerged Claude branch, then add a Pydantic network document stored atomically as class-wiki JSON with a compiled Markdown overview. Seed adoption uses structured `WorkflowDraftStore` snapshots; the frontend renders an API view model through React Flow with a mobile outline fallback.

**Tech Stack:** FastAPI, Pydantic 2, stdlib JSON, existing WikiStore and WorkflowDraftStore, Next.js 15, React 19, TypeScript, `@xyflow/react`, Tailwind, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-17-class-course-network-design.md`

## Global Constraints

- Class-owned network only; no export/import or shared runtime network.
- Canonical graph file: `wiki/classes/{class_id}/course_network/network.json`.
- Compiled inspection file: `wiki/classes/{class_id}/course_network/overview.md`.
- A missing `network.json` means the class has not adopted a network.
- The seed is immutable shared input; adoption copies reviewed content into the class.
- One node type: `Lernbaustein`; relationships: `builds_on`, `related_to`.
- React Flow is not a persistence schema.
- Only `@xyflow/react@^12.11.3` is added.
- Legacy framework adjustment behavior remains active when no adopted network exists.
- Update OpenAPI and durable docs in the PR that introduces each contract.

---

## PR A1 — Deterministic Chemie Class Provisioning

> **Verification status (2026-08-19): A1 awaiting final remediation verification — not merged or shipped.** The prior root and live gates remain historical evidence, but final-review findings required backend remediation. Merge readiness may be restored only after scoped re-review and fresh proportionate root/live gates. A2/A3/C remain pending.

### Task 1: Port the class-provisioning backend without unrelated branch scope

**Files:**
- Create: `backend/app/services/class_provisioning.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/schemas/api.py`
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/test_class_provisioning.py`
- Test: `backend/tests/test_multi_class_isolation.py`

**Interfaces:**
- Consumes: reviewed Chemie entries from
  `app.teacher_agent.wiki.subject_frameworks.load_framework_index(store, subject)`.
- Produces: `available_routes(store) -> list[CurriculumRoute]`, `create_class(store, spec) -> ClassSummary`, `GET /api/classes/curriculum-routes`, `POST /api/classes`.

- [ ] **Step 1: Write the failing route and creation tests**

Port the Chemie-relevant assertions from branch
`claude/class-generator-setup-wizard-70c68b`, and pin the MVP route set:

```python
def test_offered_routes_are_chemie_8_and_9_ntg(wiki):
    routes = class_provisioning.available_routes(wiki)
    assert routes == [
        class_provisioning.CurriculumRoute("chemie", 8, "NTG"),
        class_provisioning.CurriculumRoute("chemie", 9, "NTG"),
    ]


def test_created_class_has_route_and_empty_history(wiki):
    result = class_provisioning.create_class(
        wiki,
        class_provisioning.ClassSpec(
            label="Chemie 8a — 2026/27",
            subject="chemie",
            grade=8,
            section="a",
            school_year="2026_27",
        ),
    )
    assert result.id == "chemie_8a_2026_27"
    assert wiki.get_curriculum_profile(result.id).branch == "NTG"
    assert wiki.get_timeline(result.id).entries == []
```

- [ ] **Step 2: Run the tests and verify the missing service failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_class_provisioning.py tests\test_multi_class_isolation.py -v
```

Expected: collection/import failure for `app.services.class_provisioning`.

- [ ] **Step 3: Port the deterministic service with Chemie-only scope**

Use the branch implementation as the source, with this public contract:

```python
SUPPORTED_SUBJECTS = ("chemie",)

@dataclass(frozen=True)
class CurriculumRoute:
    subject: str
    grade: int
    branch: str

@dataclass(frozen=True)
class ClassSpec:
    label: str
    subject: str
    grade: int
    section: str = ""
    school_year: str = ""
    branch: str = "NTG"
    school_type: str = "Gymnasium"
    state: str = "BY"
    prior_learning: str = ""
    student_names: tuple[str, ...] = ()
```

Keep class creation deterministic. Do not call an LLM and do not copy Physics
framework/source additions from the branch. Continue creating
`teaching_framework_adjustments.md` until PR D2 adds the adopted-network
compatibility switch.

- [ ] **Step 4: Add transport schemas and routes**

Add `CurriculumRouteOption`, `CurriculumRoutesResponse`, and
`CreateClassRequest` to `schemas/api.py`; add the two routes using the branch's
422 mapping for `ClassProvisioningError`.

- [ ] **Step 5: Run provisioning and existing wiki tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests\test_class_provisioning.py tests\test_multi_class_isolation.py tests\test_wiki_indexing.py tests\test_wiki_store.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the backend slice**

```powershell
git add backend/app/services/class_provisioning.py backend/app/api/routes.py backend/app/schemas/api.py backend/tests/test_class_provisioning.py backend/tests/test_multi_class_isolation.py
git commit -m "feat: add deterministic chemistry class provisioning"
```

### Task 2: Port the class-creation UI through the design system

**Files:**
- Create: `frontend/src/components/klassenpilot/create-class-card.tsx`
- Create: `frontend/src/components/klassenpilot/create-class-card.test.ts`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `contracts/openapi.yaml`
- Modify: `docs/pm_hub.md`
- Modify: `implementation_plans/product_backlog.md`

**Interfaces:**
- Consumes: `GET /classes/curriculum-routes`, `POST /classes`.
- Produces: home-page class-creation form and navigation to the created class.

- [ ] **Step 1: Add a failing source contract test**

```typescript
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  fileURLToPath(new URL("./create-class-card.tsx", import.meta.url)),
  "utf8",
);

describe("CreateClassCard", () => {
  it("uses reviewed curriculum routes and shared fields", () => {
    expect(source).toContain("getCurriculumRoutes");
    expect(source).toContain("createClass");
    expect(source).toContain("NativeSelect");
    expect(source).not.toContain("fetch(");
  });
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run `cd frontend; npm run test -- create-class-card.test.ts`.
Expected: FAIL because the component is missing.

- [ ] **Step 3: Port the branch component and API types**

Port `CreateClassCard` and its `CurriculumRoute`/`CreateClassRequest` client
methods. Reuse `Card`, `Field`, `NativeSelect`, `Input`, `Textarea`, `Alert`, and
`Button`; keep roster optional and redirect to `/classes/{created.id}`.

- [ ] **Step 4: Mount the form on the existing landing page**

Keep class selection first. Add the create card as a secondary section; do not
replace `HomeLanding` or introduce a wizard shell in this PR.

- [ ] **Step 5: Update OpenAPI and product state**

Document the two endpoints in `contracts/openapi.yaml`. Move deterministic
Chemie 8/9 class creation from backlog language to shipped state only after the
PR is merged.

- [ ] **Step 6: Run frontend checks**

```powershell
cd frontend
npm run typecheck
npm run test
```

Expected: PASS.

- [ ] **Step 7: Commit and open PR A1**

```powershell
git add frontend/src/components/klassenpilot/create-class-card.tsx frontend/src/components/klassenpilot/create-class-card.test.ts frontend/src/app/page.tsx frontend/src/lib/api.ts contracts/openapi.yaml docs/pm_hub.md implementation_plans/product_backlog.md
git commit -m "feat: add chemistry class setup form"
```

PR A1 acceptance: execute
`docs/superpowers/plans/2026-08-18-a1-class-provisioning-e2e.md`. The live API
phase creates Chemie 8a; the browser phase creates Chemie 9a. Together they
reject duplicates and unsupported routes, verify every required empty-class
artifact, and prove the pre-existing Chemie 9b remains isolated.

---

## PR A2 — Canonical Network, Seed Draft, and Adoption API

### Task 3: Define the canonical network models

**Files:**
- Create: `backend/app/course_network/__init__.py`
- Create: `backend/app/course_network/models.py`
- Test: `backend/tests/test_course_network_models.py`

**Interfaces:**
- Produces: `CourseNetworkDocument`, `LearningBlock`, `NetworkEdge`, `MaterialMapping`, `CanvasPosition`, and stable JSON serialization.

- [ ] **Step 1: Write failing model invariants**

```python
def test_network_document_rejects_duplicate_node_ids():
    with pytest.raises(ValueError, match="duplicate node id"):
        CourseNetworkDocument(
            class_id="chemie_8a_2026_27",
            route=CurriculumRouteRef(subject="chemie", grade=8, branch="NTG"),
            nodes=[_node("c8-energy"), _node("c8-energy")],
        )


def test_network_json_is_stable():
    document = _network()
    assert canonical_network_json(document) == canonical_network_json(document)
```

- [ ] **Step 2: Run the test and verify it fails**

Run `cd backend; .\.venv\Scripts\python -m pytest tests\test_course_network_models.py -v`.
Expected: import failure.

- [ ] **Step 3: Implement the model contract**

```python
RelationType = Literal["builds_on", "related_to"]
NodeOrigin = Literal["curriculum", "teacher", "material"]

class CurriculumReference(BaseModel):
    source_id: str
    section_id: str

class MaterialSectionReference(BaseModel):
    material_id: str
    section_id: str
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)

class CanvasPosition(BaseModel):
    x: float
    y: float

class LearningBlock(BaseModel):
    id: str
    title: str
    description: str = ""
    learning_goal: str = ""
    curriculum_refs: list[CurriculumReference] = Field(default_factory=list)
    material_refs: list[MaterialSectionReference] = Field(default_factory=list)
    origin: NodeOrigin = "teacher"
    status: Literal["proposed", "adopted", "retired"] = "adopted"

class NetworkEdge(BaseModel):
    id: str
    source_id: str
    target_id: str
    relation: RelationType
    curriculum_refs: list[CurriculumReference] = Field(default_factory=list)
    material_refs: list[MaterialSectionReference] = Field(default_factory=list)
    origin: NodeOrigin = "teacher"

class MaterialMapping(BaseModel):
    id: str
    material_id: str
    section_id: str
    node_id: str
    relation: Literal["explains", "practices", "assesses", "extends"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    teacher_note: str = ""
    origin: Literal["agent", "teacher"]

class CourseNetworkDocument(BaseModel):
    schema_version: Literal[1] = 1
    class_id: str
    route: CurriculumRouteRef
    revision: int = 1
    nodes: list[LearningBlock] = Field(default_factory=list)
    edges: list[NetworkEdge] = Field(default_factory=list)
    material_mappings: list[MaterialMapping] = Field(default_factory=list)
    positions: dict[str, CanvasPosition] = Field(default_factory=dict)
    updated_at: datetime
```

Validate slugs, unique IDs, edge endpoints, no self-edge, unique mappings, and
positions only for existing nodes. A material-origin node requires at least one
material reference. Seed and edit drafts may contain `proposed` nodes;
canonical store writes permit `adopted` and historical `retired` nodes but
reject `proposed` nodes. Retired nodes remain resolvable for old lesson
references and are excluded from normal canvas and planning retrieval. Keep
chemistry judgement outside the model.

- [ ] **Step 4: Run model tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/course_network backend/tests/test_course_network_models.py
git commit -m "feat: define class course network schema"
```

### Task 4: Add atomic storage and compiled overview

**Files:**
- Create: `backend/app/teacher_agent/wiki/course_network.py`
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/teacher_agent/wiki/search.py`
- Modify: `backend/app/teacher_agent/wiki/indexing.py`
- Test: `backend/tests/test_course_network_store.py`
- Test: `backend/tests/test_wiki_search.py`

**Interfaces:**
- Consumes: `CourseNetworkDocument`.
- Produces: `load_course_network`, `write_course_network`, `render_course_network_overview`, wiki kind `course_network`.

- [ ] **Step 1: Write failing atomic-store tests**

```python
def test_write_network_round_trips_and_compiles_overview(wiki):
    saved = wiki.write_course_network("chemie_8a_2026_27", _network())
    loaded = wiki.load_course_network("chemie_8a_2026_27")
    assert loaded == saved
    assert "Aktivierungsenergie" in wiki.read_text(
        wiki.class_dir("chemie_8a_2026_27") / "course_network" / "overview.md"
    )


def test_missing_network_returns_none(wiki):
    assert wiki.load_course_network("chemie_9b_2026_27") is None
```

- [ ] **Step 2: Run and verify failure**

Run `cd backend; .\.venv\Scripts\python -m pytest tests\test_course_network_store.py -v`.

- [ ] **Step 3: Implement same-directory atomic replacement**

```python
def write_course_network(store, class_id: str, document: CourseNetworkDocument):
    target = course_network_dir(store, class_id) / "network.json"
    temporary = target.with_suffix(".json.tmp")
    store.write_text(temporary, canonical_network_json(document) + "\n")
    temporary.replace(target)
    store.write_text(target.parent / "overview.md", render_course_network_overview(document))
    return document
```

Resolve the class first, require matching `document.class_id`, increment
revisions in the service rather than implicitly in storage, and clean a stale
`.tmp` before writing.

- [ ] **Step 4: Index the compiled overview**

Add `course_network` to `list_class_pages`, the wiki viewer kind ordering, and
the deterministic relevance corpus. Never index raw `network.json` as prose.

- [ ] **Step 5: Run store/search regression**

```powershell
.\.venv\Scripts\python -m pytest tests\test_course_network_store.py tests\test_wiki_search.py tests\test_wiki_indexing.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/teacher_agent/wiki/course_network.py backend/app/teacher_agent/wiki/store.py backend/app/teacher_agent/wiki/search.py backend/app/teacher_agent/wiki/indexing.py backend/tests/test_course_network_store.py backend/tests/test_wiki_search.py
git commit -m "feat: persist class course networks"
```

### Task 5: Add reviewed Chemie 8/9 seed files

**Files:**
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/08/course_network_seed.json`
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/course_network_seed.json`
- Create: `backend/app/course_network/seeds.py`
- Test: `backend/tests/test_course_network_seeds.py`

**Interfaces:**
- Produces: `load_seed_for_class(wiki, class_id) -> CourseNetworkDocument` with
  `class_id` rebound, revision `1`, and every node status `proposed`.

- [ ] **Step 1: Write route/provenance tests**

```python
def test_chemie_8_seed_is_route_exact_and_provenanced(wiki):
    seed = load_seed_for_route(wiki, subject="chemie", grade=8, branch="NTG")
    assert seed.route.grade == 8
    assert len(seed.nodes) >= 12
    assert all(node.curriculum_refs for node in seed.nodes)
    assert {edge.relation for edge in seed.edges} <= {"builds_on", "related_to"}
```

- [ ] **Step 2: Run and verify failure**

Run `cd backend; .\.venv\Scripts\python -m pytest tests\test_course_network_seeds.py -v`.

- [ ] **Step 3: Curate the seed from reviewed NTG sources**

Represent the teacher's Miro-aligned Grade 8 spine, including
Massenerhaltung, Reaktionsgleichungen, Energieprofile, Aktivierungsenergie,
Katalyse, Avogadro-Hypothese, Stoffmenge, molare Masse/molaren Volumen, and
Stöchiometrie. Every node must cite an actual section in
`by-lehrplanplus-chemie-8-ntg`; do not derive nodes from the screenshot alone.

Create the Grade 9 file through the same schema so route handling is not
hardcoded, but keep Grade 8 as the first acceptance route.

- [ ] **Step 4: Run seed and trusted-source tests**

```powershell
.\.venv\Scripts\python -m pytest tests\test_course_network_seeds.py tests\test_trusted_sources.py tests\test_subject_framework_profiles.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/08/course_network_seed.json backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/course_network_seed.json backend/app/course_network/seeds.py backend/tests/test_course_network_seeds.py
git commit -m "data: add reviewed chemistry course network seeds"
```

### Task 6: Add structured draft helpers and adoption service

**Files:**
- Modify: `backend/app/services/workflow_drafts.py`
- Create: `backend/app/services/course_network_service.py`
- Create: `backend/app/course_network/validation.py`
- Create: `backend/app/course_network/review.py`
- Create: `backend/app/course_network/prompts.py`
- Create: `backend/app/api/course_network_routes.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/schemas/api.py`
- Test: `backend/tests/test_workflow_drafts.py`
- Test: `backend/tests/test_course_network_api.py`
- Test: `backend/tests/test_course_network_review.py`

**Interfaces:**
- Produces: `GET /api/classes/{class_id}/course/network`, `POST
  /course/network/drafts`, `GET /course/network/drafts/{draft_id}`, `POST
  /course/network/drafts/{draft_id}/review`, and `POST
  /course/network/drafts/{draft_id}/adopt`.

- [ ] **Step 1: Add failing structured-draft tests**

```python
def test_structured_draft_hash_is_order_stable(tmp_path):
    store = WorkflowDraftStore(tmp_path / "drafts.sqlite")
    store.initialize()
    first = store.open_structured_draft(
        _identity(),
        default_status="reviewing",
        artifact={"b": 2, "a": 1},
    )
    assert json.loads(first.row.artifact_markdown) == {"a": 1, "b": 2}


def test_adopt_rejects_stale_snapshot(client, wiki):
    draft = _open_seed_draft(client)
    response = client.post(
        f"/api/classes/{CLASS_ID}/course/network/drafts/{draft['draft_id']}/adopt",
        json={"expected_revision": draft["revision"] + 1, "expected_hash": draft["hash"]},
    )
    assert response.status_code == 409
```

Also assert deterministic provenance errors prevent review, LLM `revise` or
`block` prevents adoption, changing the artifact invalidates the completed
review, and a passing review is bound to the exact artifact revision/hash.

- [ ] **Step 2: Run and verify failure**

Run `cd backend; .\.venv\Scripts\python -m pytest tests\test_workflow_drafts.py tests\test_course_network_api.py -v`.

- [ ] **Step 3: Implement stable structured helpers**

Serialize with `json.dumps(value, ensure_ascii=False, sort_keys=True,
separators=(",", ":"))`. Reuse the existing artifact revision/hash columns and
review snapshot methods; do not add a second draft database.

- [ ] **Step 4: Implement adoption validation and no-tools LLM review**

Deterministic checks cover IDs, endpoints, controlled relations, route match,
cycles, and curriculum provenance. The bounded reviewer checks chemistry and
curriculum plausibility, misleading learning goals, unsupported source claims,
and unsafe content. Return a typed decision/findings report, bind it to the
exact structured artifact through the existing executive fingerprint/snapshot
lifecycle, and never let the reviewer rewrite the seed.

- [ ] **Step 5: Implement adoption service**

```python
class CourseNetworkService:
    def open_seed_draft(self, class_id: str) -> CourseNetworkDraftResponse: ...
    def get_network(self, class_id: str) -> CourseNetworkResponse: ...
    def get_draft(self, class_id: str, draft_id: str) -> CourseNetworkDraftResponse: ...
    async def review_seed(self, class_id: str, draft_id: str) -> CourseNetworkDraftResponse: ...
    def adopt_seed(
        self,
        class_id: str,
        draft_id: str,
        *,
        expected_revision: int,
        expected_hash: str,
    ) -> CourseNetworkResponse: ...
```

`open_seed_draft` fails with 409 if a network already exists. `adopt_seed`
validates the active review snapshot, binds the class ID/route, converts all
accepted node status to `adopted`, writes revision 1, appends a
`course_network_adopt` log entry, rebuilds the index, and marks the draft
committed.

- [ ] **Step 6: Add the focused router and dependencies**

Create `course_network_routes.py` with its own `APIRouter`; include it from the
existing `/api` router. Add a per-wiki-root `CourseNetworkService` cache in
`deps.py` using the existing cache pattern.

- [ ] **Step 7: Run API/draft tests**

```powershell
.\.venv\Scripts\python -m pytest tests\test_course_network_api.py tests\test_course_network_review.py tests\test_workflow_drafts.py tests\test_api_workflow_active.py -v
```

- [ ] **Step 8: Update OpenAPI and wiki contracts**

Modify `contracts/openapi.yaml`, `docs/agent_contracts.md`,
`docs/memory_hierarchy.md`, and `backend/teacher_wiki/AGENTS.md` with the exact
paths and adoption write boundary.

- [ ] **Step 9: Commit and open PR A2**

```powershell
git add backend/app/services/workflow_drafts.py backend/app/services/course_network_service.py backend/app/course_network/validation.py backend/app/course_network/review.py backend/app/course_network/prompts.py backend/app/api/course_network_routes.py backend/app/api/routes.py backend/app/api/deps.py backend/app/schemas/api.py backend/tests/test_workflow_drafts.py backend/tests/test_course_network_api.py backend/tests/test_course_network_review.py contracts/openapi.yaml docs/agent_contracts.md docs/memory_hierarchy.md backend/teacher_wiki/AGENTS.md
git commit -m "feat: add reviewed course network adoption"
```

PR A2 acceptance: no canonical network before adoption, stale adoption returns
409, adopted JSON round-trips, overview/index update, and other classes remain
unchanged.

---

## PR A3 — Read-Only React Flow Workspace

### Task 7: Add React Flow and a pure API-to-canvas adapter

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/src/features/course-network/types.ts`
- Create: `frontend/src/features/course-network/to-react-flow.ts`
- Test: `frontend/src/features/course-network/to-react-flow.test.ts`

**Interfaces:**
- Consumes: `CourseNetwork` API records.
- Produces: `toReactFlowModel(network) -> { nodes, edges }` and deterministic fallback positions.

- [ ] **Step 1: Install the single runtime dependency**

Run:

```powershell
cd frontend
npm install @xyflow/react@^12.11.3
```

- [ ] **Step 2: Write failing adapter tests**

```typescript
it("preserves domain ids and computes fallback positions", () => {
  const model = toReactFlowModel(networkWithoutPositions);
  expect(model.nodes.map((node) => node.id)).toEqual(["a", "b"]);
  expect(model.nodes[0]?.data.learningBlock.id).toBe("a");
  expect(model.edges[0]?.data?.relation).toBe("builds_on");
  expect(model.nodes.every((node) => Number.isFinite(node.position.x))).toBe(true);
});
```

- [ ] **Step 3: Run and verify failure**

Run `npm run test -- to-react-flow.test.ts`.

- [ ] **Step 4: Implement a view-only adapter**

Use domain IDs unchanged. Put the full `LearningBlock` under node `data`; map
edge relation to label/style. For missing positions, assign topological layers
from `builds_on` edges and put cyclic/unconnected nodes into a deterministic
final grid. Do not mutate the API object.

- [ ] **Step 5: Run adapter tests and typecheck**

Run `npm run test -- to-react-flow.test.ts; npm run typecheck`.

- [ ] **Step 6: Commit**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/src/features/course-network
git commit -m "feat: add course network canvas adapter"
```

### Task 8: Build the course workspace, inspector, outline, and adoption screen

**Files:**
- Create: `frontend/src/app/classes/[classId]/course/page.tsx`
- Create: `frontend/src/components/klassenpilot/course/course-network-workspace.tsx`
- Create: `frontend/src/components/klassenpilot/course/course-network-canvas.tsx`
- Create: `frontend/src/components/klassenpilot/course/learning-block-node.tsx`
- Create: `frontend/src/components/klassenpilot/course/learning-block-inspector.tsx`
- Create: `frontend/src/components/klassenpilot/course/course-network-outline.tsx`
- Create: `frontend/src/components/klassenpilot/course/course-network-adoption.tsx`
- Create: `frontend/src/components/klassenpilot/course/course-network-workspace.test.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/globals.css`

**Interfaces:**
- Consumes: foundation network/adoption APIs.
- Produces: `/classes/{classId}/course` read-only graph and seed review/adoption.

- [ ] **Step 1: Add failing UI composition tests**

```typescript
expect(workspaceSource).toContain("CourseNetworkCanvas");
expect(workspaceSource).toContain("CourseNetworkOutline");
expect(workspaceSource).toContain("LearningBlockInspector");
expect(canvasSource).toContain("ReactFlow");
expect(canvasSource).toContain("Background");
expect(canvasSource).toContain("Controls");
```

- [ ] **Step 2: Run and verify failure**

Run `cd frontend; npm run test -- course-network-workspace.test.ts`.

- [ ] **Step 3: Implement transport types and client methods**

Add `LearningBlock`, `NetworkEdge`, `CourseNetwork`,
`CourseNetworkDraftResponse`, `getCourseNetwork`, `openCourseNetworkSeedDraft`,
`getCourseNetworkDraft`, `reviewCourseNetworkSeed`, and
`adoptCourseNetworkSeed` to `lib/api.ts`.

- [ ] **Step 4: Implement the responsive workspace**

Desktop: canvas fills the main area and a 360px inspector sits on the right.
Narrow screen: show the searchable outline and inspector; hide edge handles.
Use a segmented `Network | Materials` navigation header, with Materials linking
to the future route. Dynamically import the canvas with SSR disabled.

- [ ] **Step 5: Implement the custom node**

Render title, truncated learning goal, origin badge, and connection handles with
semantic tokens. Preserve React Flow keyboard selection and provide an explicit
`aria-label` containing the Lernbaustein title.

- [ ] **Step 6: Implement seed adoption**

When `GET /course/network` returns `not_adopted`, open/resume the seed draft and
show the proposed node/relationship counts, curriculum source links, an outline
preview, and review findings. The teacher first runs `Review proposal`; only an
exact passing review enables `Adopt course network`. Adoption uses the draft
revision/hash and routes to the canonical workspace on success. Editing the
seed itself arrives in Epic B; the teacher may reject/discard and keep the
class on the legacy framework in this foundation increment.

- [ ] **Step 7: Run frontend tests**

```powershell
npm run typecheck
npm run test
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/app/classes/[classId]/course frontend/src/components/klassenpilot/course frontend/src/features/course-network frontend/src/lib/api.ts frontend/src/app/globals.css
git commit -m "feat: add course network workspace"
```

### Task 9: Add class-home entry and foundation documentation

**Files:**
- Modify: `frontend/src/app/classes/[classId]/class-home-client.tsx`
- Modify: `frontend/src/lib/class-home-display.ts`
- Modify: `frontend/src/lib/class-home-display.test.ts`
- Modify: `frontend/ARCHITECTURE.md`
- Modify: `frontend/DESIGN.md`
- Modify: `docs/product_vision.md`
- Modify: `docs/pm_hub.md`
- Modify: `implementation_plans/product_backlog.md`

**Interfaces:**
- Produces: one `Course` class-home action linking to `/classes/{classId}/course`.

- [ ] **Step 1: Add hover-copy contract test**

```typescript
expect(CLASS_HOME_HOVER.course).toContain("network");
```

- [ ] **Step 2: Add the class-home action without expanding navigation**

Add one outline `ActionLink` labelled `Course` next to `Browse class files` and
document it in the dismissible help note. The Course workspace owns its own
Network/Materials navigation.

- [ ] **Step 3: Document the canvas boundary and responsive fallback**

Add the route/component layering and semantic-node rules to frontend docs. Mark
the course network as shipped only after adoption and read-only inspection pass
HITL acceptance.

- [ ] **Step 4: Run all Epic A tests**

```powershell
.\scripts\test.ps1
```

Expected: PASS.

- [ ] **Step 5: Run Epic A HITL acceptance**

```powershell
.\scripts\worktree-stack.cmd up --beta --fresh-beta-data
```

Create Chemie 8a, verify no canonical network before approval, adopt the seed,
inspect keyboard selection, resize to the outline fallback, and open the
compiled overview through Browse class files.

- [ ] **Step 6: Commit and open PR A3**

```powershell
git add frontend/src/app/classes/[classId]/class-home-client.tsx frontend/src/lib/class-home-display.ts frontend/src/lib/class-home-display.test.ts frontend/ARCHITECTURE.md frontend/DESIGN.md docs/product_vision.md docs/pm_hub.md implementation_plans/product_backlog.md
git commit -m "docs: publish course network foundation"
```
