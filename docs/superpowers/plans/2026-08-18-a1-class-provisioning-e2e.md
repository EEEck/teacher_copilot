# PR A1 Class Provisioning Implementation and End-to-End Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the deterministic Chemie 8/9 NTG class-provisioning slice from the Claude branch and prove it through both the live HTTP API and the teacher-facing browser form, without an LLM call or premature course-network adoption.

**Architecture:** Port only `class_provisioning.py`, its FastAPI contracts, and the design-system class form from `claude/class-generator-setup-wizard-70c68b`; do not merge the branch or copy its Physics/source-ingestion scope. Add transport-level pytest coverage, a repeatable live-API runner, and a browser HITL runbook. One fresh non-beta sandbox is used end to end: the API runner creates Chemie 8a and the browser creates Chemie 9a, while the seeded Chemie 9b is captured before both phases and compared afterwards.

**Tech Stack:** FastAPI `TestClient`, pytest, Python 3.12, `httpx`, the existing worktree Docker helper, Next.js 15, and the Codex in-app browser.

**Spec:** `docs/superpowers/specs/2026-08-17-class-course-network-design.md`; implements the PR A1 boundary in `docs/superpowers/plans/2026-08-18-course-network-foundation.md`.

## Global Constraints

- A1 is deterministic class provisioning only; it must make no OpenAI or Mistral call.
- The offered route set is exactly Chemie 8 NTG and Chemie 9 NTG.
- The API phase creates `chemie_8a_2026_27`; the browser phase creates `chemie_9a_2026_27`.
- Use fake roster names only: `Ada Beispiel`, `Ben Beispiel`, `Clara Beispiel`, and `David Beispiel`.
- A created class starts with no lessons, commits, open loops, misconceptions, active workflow drafts, or adopted `course_network/network.json`.
- Prior learning is written to `course_state.md`; it is never converted into a lesson or timeline entry.
- Duplicate and unsupported requests return 422 and leave the wiki byte-for-byte unchanged.
- The tracked `backend/teacher_wiki/` baseline is read-only during acceptance; only `backend/teacher_wiki_sandbox/` may change.
- Run with beta disabled in development/economy mode. Beta authentication and beta data are not part of A1.
- The final browser gate requires no browser console errors and no backend 5xx/traceback during class creation or first class-home load.
- The existing concurrent `MemoryCandidateLedger.initialize()` duplicate-column race is not waived. If it appears in the final log gate, fix it as a separate baseline prerequisite before declaring A1 green.

---

### Task 1: Port deterministic backend provisioning and API contracts

**Files:**
- Create: `backend/app/services/class_provisioning.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/schemas/api.py`
- Create: `backend/tests/test_api_class_provisioning.py`
- Create: `backend/tests/test_class_provisioning.py`
- Create: `backend/tests/test_multi_class_isolation.py`

**Interfaces:**
- Consumes: `GET /api/classes/curriculum-routes`, `POST /api/classes`, `GET /api/classes`, `GET /api/classes/{class_id}/snapshot`, and `GET /api/classes/{class_id}/timeline`.
- Produces: `CurriculumRoute`, `ClassSpec`, `available_routes(store)`, `create_class(store, spec)`, `GET /api/classes/curriculum-routes`, `POST /api/classes`, and deterministic transport coverage for the live runner and browser form.

- [ ] **Step 1: Write the failing service, isolation, route-list, and create/read-back tests**

Port the Chemie-relevant cases from the Claude branch's
`backend/tests/test_class_provisioning.py` and
`backend/tests/test_multi_class_isolation.py`; exclude Physics expectations and
pin the offered routes to Chemie 8/9 NTG. Create
`backend/tests/test_api_class_provisioning.py` with the shared payload and these
assertions:

```python
from copy import deepcopy


CLASS_8A = "chemie_8a_2026_27"
SEEDED_9B = "chemie_9b_2026_27"

CREATE_8A = {
    "label": "Chemie 8a — 2026/27",
    "subject": "chemie",
    "grade": 8,
    "section": "a",
    "school_year": "2026_27",
    "branch": "NTG",
    "school_type": "Gymnasium",
    "state": "BY",
    "prior_learning": "Atombau und Periodensystem wurden bereits wiederholt.",
    "student_names": ["Ada Beispiel", "Ben Beispiel"],
}


def test_curriculum_routes_are_exactly_chemie_8_and_9_ntg(client):
    response = client.get("/api/classes/curriculum-routes")
    assert response.status_code == 200
    assert response.json() == {
        "routes": [
            {"subject": "chemie", "grade": 8, "branch": "NTG"},
            {"subject": "chemie", "grade": 9, "branch": "NTG"},
        ]
    }


def test_create_class_is_visible_and_starts_empty(client):
    response = client.post("/api/classes", json=CREATE_8A)
    assert response.status_code == 201
    assert response.json() == {
        "id": CLASS_8A,
        "label": "Chemie 8a — 2026/27",
        "subject": "chemie",
    }

    classes = client.get("/api/classes").json()["classes"]
    assert {item["id"] for item in classes} >= {SEEDED_9B, CLASS_8A}

    snapshot = client.get(f"/api/classes/{CLASS_8A}/snapshot")
    assert snapshot.status_code == 200
    data = snapshot.json()
    assert data["class_id"] == CLASS_8A
    assert data["current_unit"] == "Not set"
    assert data["last_lesson_date"] is None
    assert data["last_committed_date"] is None
    assert data["open_loop_count"] == 0
    assert data["top_misconceptions"] == []
    assert data["recent_lessons"] == []

    timeline = client.get(f"/api/classes/{CLASS_8A}/timeline")
    assert timeline.status_code == 200
    assert timeline.json()["entries"] == []
    assert timeline.json()["months"] == []
```

Use explicit field assertions instead of snapshots that hide a changed contract. If the exact route order is not deterministic, fix `available_routes()` rather than sorting in the test.

- [ ] **Step 2: Run the transport tests and verify they fail before A1 exists**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_class_provisioning.py -v
```

Expected: FAIL with 404 for `/api/classes/curriculum-routes` and method-not-allowed for `POST /api/classes`.

- [ ] **Step 3: Port only the deterministic Chemie provisioning service and routes**

Read these files from `claude/class-generator-setup-wizard-70c68b` as reference:

```powershell
git show claude/class-generator-setup-wizard-70c68b:backend/app/services/class_provisioning.py
git diff HEAD...claude/class-generator-setup-wizard-70c68b -- backend/app/api/routes.py backend/app/schemas/api.py
```

Port the service with these scope rulings:

```python
SUPPORTED_SUBJECTS = ("chemie",)
SUPPORTED_BRANCH = "NTG"
SUPPORTED_SCHOOL_TYPE = "Gymnasium"
SUPPORTED_STATE = "BY"
```

`available_routes()` must derive routes from the already-reviewed Chemie framework index and return only grades 8 and 9. `create_class()` must write the deterministic skeleton from the Claude implementation, including `teaching_framework_adjustments.md` for legacy compatibility, rebuild the wiki index, and make no model call. Do not port Physics, grade 10/11 sources, source-ingestion scripts, agent changes, or unrelated wiki refactors from the Claude branch.

Add `CurriculumRouteOption`, `CurriculumRoutesResponse`, and `CreateClassRequest` to `backend/app/schemas/api.py`. Add:

```python
@router.get("/classes/curriculum-routes", response_model=CurriculumRoutesResponse)
def list_curriculum_routes(
    wiki: WikiStore = Depends(get_wiki),
) -> CurriculumRoutesResponse:
    return CurriculumRoutesResponse(
        routes=[
            CurriculumRouteOption(subject=item.subject, grade=item.grade, branch=item.branch)
            for item in class_provisioning.available_routes(wiki)
        ]
    )


@router.post("/classes", response_model=ClassSummary, status_code=201)
def create_class(
    body: CreateClassRequest,
    wiki: WikiStore = Depends(get_wiki),
) -> ClassSummary:
    try:
        return class_provisioning.create_class(
            wiki,
            class_provisioning.ClassSpec(
                label=body.label,
                subject=body.subject,
                grade=body.grade,
                section=body.section,
                school_year=body.school_year,
                branch=body.branch,
                school_type=body.school_type,
                state=body.state,
                prior_learning=body.prior_learning,
                student_names=tuple(body.student_names),
            ),
        )
    except class_provisioning.ClassProvisioningError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
```

Map `ClassProvisioningError` to HTTP 422 with `detail=str(exc)`. No other exception is converted to a successful response.

- [ ] **Step 4: Add rejection and atomicity tests**

Add tests that capture the created directory digest and the seeded-class API state before invalid writes:

```python
import hashlib


def _tree_digest(root) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_duplicate_and_unsupported_requests_do_not_mutate_wiki(client, wiki):
    assert client.post("/api/classes", json=CREATE_8A).status_code == 201
    created_root = wiki.class_dir(CLASS_8A)
    before_created = _tree_digest(created_root)
    before_seeded_snapshot = client.get(f"/api/classes/{SEEDED_9B}/snapshot").json()
    before_seeded_timeline = client.get(f"/api/classes/{SEEDED_9B}/timeline").json()

    duplicate = client.post("/api/classes", json=CREATE_8A)
    assert duplicate.status_code == 422
    assert "already exists" in duplicate.json()["detail"]
    assert _tree_digest(created_root) == before_created

    unsupported = deepcopy(CREATE_8A)
    unsupported.update({
        "label": "Chemie 8c — 2026/27",
        "section": "c",
        "branch": "SG",
    })
    rejected = client.post("/api/classes", json=unsupported)
    assert rejected.status_code == 422
    assert "NTG" in rejected.json()["detail"]
    assert not wiki.class_dir("chemie_8c_2026_27").exists()

    assert client.get(f"/api/classes/{SEEDED_9B}/snapshot").json() == before_seeded_snapshot
    assert client.get(f"/api/classes/{SEEDED_9B}/timeline").json() == before_seeded_timeline
```

- [ ] **Step 5: Extend service assertions for required files and A1/A2 separation**

In `backend/tests/test_class_provisioning.py`, keep the required Markdown-file assertion and add:

```python
def test_a1_does_not_adopt_a_course_network(wiki):
    summary = cp.create_class(
        wiki,
        _spec(label="Chemie 8a — 2026/27", grade=8, section="a"),
    )
    assert not (wiki.class_dir(summary.id) / "course_network" / "network.json").exists()


def test_prior_learning_and_roster_do_not_create_history(wiki):
    summary = cp.create_class(
        wiki,
        _spec(
            label="Chemie 8a — 2026/27",
            grade=8,
            section="a",
            prior_learning="Atombau und Periodensystem wurden bereits wiederholt.",
            student_names=("Ada Beispiel", "Ben Beispiel"),
        ),
    )
    course_state = wiki.read_text(wiki.class_dir(summary.id) / "course_state.md")
    students = wiki.read_text(wiki.class_dir(summary.id) / "students.md")
    assert "Atombau und Periodensystem" in course_state
    assert "S-001 | Ada Beispiel" in students
    assert "S-002 | Ben Beispiel" in students
    assert wiki.get_timeline(summary.id).entries == []
    assert wiki.get_snapshot(summary.id).recent_lessons == []
```

- [ ] **Step 6: Run focused A1 backend tests**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_class_provisioning.py tests\test_class_provisioning.py tests\test_multi_class_isolation.py -v
```

Expected: PASS with no network access and no model calls.

- [ ] **Step 7: Commit the backend and transport gate**

```powershell
git add backend/app/services/class_provisioning.py backend/app/api/routes.py backend/app/schemas/api.py backend/tests/test_api_class_provisioning.py backend/tests/test_class_provisioning.py backend/tests/test_multi_class_isolation.py
git commit -m "feat: add deterministic chemistry class provisioning"
```

---

### Task 2: Port the class-creation UI through the design system

**Files:**
- Create: `frontend/src/components/klassenpilot/create-class-card.tsx`
- Create: `frontend/src/components/klassenpilot/create-class-card.test.ts`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `contracts/openapi.yaml`

**Interfaces:**
- Consumes: `GET /api/classes/curriculum-routes` and `POST /api/classes` from Task 1.
- Produces: a secondary `New class` form on the existing landing page and navigation to `/classes/{created.id}`.

- [ ] **Step 1: Write the failing frontend contract test**

Create `create-class-card.test.ts`:

```typescript
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  fileURLToPath(new URL("./create-class-card.tsx", import.meta.url)),
  "utf8",
);

describe("CreateClassCard", () => {
  it("uses reviewed routes, the shared API client, and design-system fields", () => {
    expect(source).toContain("getCurriculumRoutes");
    expect(source).toContain("createClass");
    expect(source).toContain("NativeSelect");
    expect(source).toContain("FieldLabel");
    expect(source).not.toContain("fetch(");
    expect(source).not.toContain("physik");
  });
});
```

- [ ] **Step 2: Run the test and verify the component is missing**

```powershell
cd frontend
npm run test -- create-class-card.test.ts
```

Expected: FAIL because `create-class-card.tsx` does not exist.

- [ ] **Step 3: Port the component and API client methods**

Use the Claude branch versions as reference:

```powershell
git show claude/class-generator-setup-wizard-70c68b:frontend/src/components/klassenpilot/create-class-card.tsx
git diff HEAD...claude/class-generator-setup-wizard-70c68b -- frontend/src/app/page.tsx frontend/src/lib/api.ts
```

Keep only Chemie labels and routes. Reuse `Card`, `Field`, `NativeSelect`, `Input`, `Textarea`, `Alert`, and `Button`. The form defaults to section `a` and school year `2026_27`, accepts optional prior learning and one fake-or-real roster name per line, derives the visible label, calls the shared API client, shows handled API errors inline, and navigates to the created class.

- [ ] **Step 4: Mount the form without replacing the landing page**

Keep `HomeLanding` and the current seeded-class experience. Rename the lower class section to `Your classes`, add an outline `New class`/`Cancel` toggle, mount `CreateClassCard` as a secondary section, and refresh/navigate through the existing client patterns. Do not add a wizard, setup agent, graph UI, or new design tokens.

- [ ] **Step 5: Update the OpenAPI contract**

Add the two A1 endpoints and the exact `CurriculumRouteOption`, `CurriculumRoutesResponse`, `CreateClassRequest`, `ClassSummary`, 201, and 422 schemas to `contracts/openapi.yaml`. The contract must expose only the A1 fields already implemented in Task 1.

- [ ] **Step 6: Run frontend checks**

```powershell
cd frontend
npm run typecheck
npm run test -- create-class-card.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit the frontend slice**

```powershell
git add frontend/src/components/klassenpilot/create-class-card.tsx frontend/src/components/klassenpilot/create-class-card.test.ts frontend/src/app/page.tsx frontend/src/lib/api.ts contracts/openapi.yaml
git commit -m "feat: add chemistry class setup form"
```

---

### Task 3: Add the live API acceptance runner

**Files:**
- Create: `scripts/run_a1_class_provisioning_e2e.py`
- Modify: `scripts/README.md`

**Interfaces:**
- Consumes: a running A1 backend through `--api-base` and the matching mutable wiki through `--wiki-root`.
- Produces: `.worktree-stack/a1-api-report.json` and exit code 0 only when every A1 API invariant passes.

- [ ] **Step 1: Implement explicit HTTP and digest helpers**

Use `httpx.Client`, fail on unexpected status before parsing JSON, and keep mutation checks local to the sandbox:

```python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import httpx


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def expect_status(response: httpx.Response, status: int) -> dict:
    if response.status_code != status:
        raise AssertionError(
            f"{response.request.method} {response.request.url} returned "
            f"{response.status_code}, expected {status}: {response.text[:1000]}"
        )
    return response.json()
```

- [ ] **Step 2: Implement the live scenario in one fresh sandbox**

The runner must execute in this order:

```python
SUPPORTED_ROUTES = [
    {"subject": "chemie", "grade": 8, "branch": "NTG"},
    {"subject": "chemie", "grade": 9, "branch": "NTG"},
]

CREATE_8A = {
    "label": "Chemie 8a — 2026/27",
    "subject": "chemie",
    "grade": 8,
    "section": "a",
    "school_year": "2026_27",
    "branch": "NTG",
    "school_type": "Gymnasium",
    "state": "BY",
    "prior_learning": "Atombau und Periodensystem wurden bereits wiederholt.",
    "student_names": ["Ada Beispiel", "Ben Beispiel"],
}


def run(api_base: str, wiki_root: Path) -> dict:
    class_8a = "chemie_8a_2026_27"
    seeded_9b = "chemie_9b_2026_27"
    classes_root = wiki_root / "wiki" / "classes"
    with httpx.Client(base_url=api_base, timeout=30.0) as client:
        assert expect_status(client.get("/api/health"), 200)["status"] == "ok"
        initial = expect_status(client.get("/api/classes"), 200)["classes"]
        initial_ids = {item["id"] for item in initial}
        assert seeded_9b in initial_ids
        assert class_8a not in initial_ids

        routes = expect_status(
            client.get("/api/classes/curriculum-routes"), 200
        )["routes"]
        assert routes == SUPPORTED_ROUTES

        seeded_snapshot = expect_status(
            client.get(f"/api/classes/{seeded_9b}/snapshot"), 200
        )
        seeded_timeline = expect_status(
            client.get(f"/api/classes/{seeded_9b}/timeline"), 200
        )

        created = expect_status(client.post("/api/classes", json=CREATE_8A), 201)
        assert created == {
            "id": class_8a,
            "label": "Chemie 8a — 2026/27",
            "subject": "chemie",
        }

        fresh_snapshot = expect_status(
            client.get(f"/api/classes/{class_8a}/snapshot"), 200
        )
        fresh_timeline = expect_status(
            client.get(f"/api/classes/{class_8a}/timeline"), 200
        )
        assert fresh_snapshot["current_unit"] == "Not set"
        assert fresh_snapshot["last_committed_date"] is None
        assert fresh_snapshot["open_loop_count"] == 0
        assert fresh_snapshot["recent_lessons"] == []
        assert fresh_timeline["entries"] == []
        assert fresh_timeline["months"] == []

        class_root = classes_root / class_8a
        required = {
            "class_config.md", "course_state.md", "curriculum_profile.md",
            "misconceptions.md", "open_loops.md", "students.md",
            "timeline.md", "trusted_sources.md",
            "memory/planning_brief.md", "memory/teaching_patterns.md",
            "memory/copilot_profile.md", "memory/session_summaries.md",
            "memory/teaching_framework_adjustments.md",
            "students/S-001.md", "students/S-002.md",
        }
        assert all((class_root / rel).is_file() for rel in required)
        assert not (class_root / "course_network" / "network.json").exists()
        assert "Atombau und Periodensystem" in (
            class_root / "course_state.md"
        ).read_text(encoding="utf-8")

        before_duplicate = tree_digest(class_root)
        duplicate = expect_status(client.post("/api/classes", json=CREATE_8A), 422)
        assert "already exists" in duplicate["detail"]
        assert tree_digest(class_root) == before_duplicate

        unsupported = CREATE_8A | {
            "label": "Chemie 8c — 2026/27",
            "section": "c",
            "branch": "SG",
        }
        rejected = expect_status(client.post("/api/classes", json=unsupported), 422)
        assert "NTG" in rejected["detail"]
        assert not (classes_root / "chemie_8c_2026_27").exists()

        assert expect_status(
            client.get(f"/api/classes/{seeded_9b}/snapshot"), 200
        ) == seeded_snapshot
        assert expect_status(
            client.get(f"/api/classes/{seeded_9b}/timeline"), 200
        ) == seeded_timeline

        for suffix in ("brief", "memory/sweep/review"):
            expect_status(client.get(f"/api/classes/{class_8a}/{suffix}"), 200)

    return {
        "status": "passed",
        "created_class": class_8a,
        "preserved_class": seeded_9b,
        "routes": SUPPORTED_ROUTES,
    }
```

The `main()` function must resolve `--wiki-root`, reject a path outside the repository unless `--allow-external-wiki-root` is explicitly passed, call `run()`, write UTF-8 JSON to `--report`, print the report, and return zero only after all assertions pass.

- [ ] **Step 3: Document the exact invocation**

Add to `scripts/README.md`:

```powershell
$backendUrl = Read-Host "Paste the backend URL printed by worktree-stack.cmd up"
.\backend\.venv\Scripts\python .\scripts\run_a1_class_provisioning_e2e.py `
  --api-base $backendUrl `
  --wiki-root .\backend\teacher_wiki_sandbox `
  --report .\.worktree-stack\a1-api-report.json
```

The backend port is copied from the successful `worktree-stack.cmd up` output. Do not hardcode a port from another worktree.

- [ ] **Step 4: Run the script against a fresh A1 stack**

From the worktree root:

```powershell
.\scripts\worktree-stack.cmd down
.\scripts\worktree-stack.cmd up --fresh-wiki --app-env development --model-profile economy
```

Record the printed project name and URLs, wait for `/api/health`, then run the acceptance script. Expected report:

```json
{
  "status": "passed",
  "created_class": "chemie_8a_2026_27",
  "preserved_class": "chemie_9b_2026_27",
  "routes": [
    {"subject": "chemie", "grade": 8, "branch": "NTG"},
    {"subject": "chemie", "grade": 9, "branch": "NTG"}
  ]
}
```

- [ ] **Step 5: Commit the live runner**

```powershell
git add scripts/run_a1_class_provisioning_e2e.py scripts/README.md
git commit -m "test: add live class provisioning acceptance"
```

---

### Task 4: Add and execute the browser HITL runbook

**Files:**
- Create: `scripts/a1_class_provisioning_browser_e2e.md`

**Interfaces:**
- Consumes: the same running sandbox after Task 3, where the API has created Chemie 8a.
- Produces: browser proof that the teacher can create Chemie 9a, see the correct empty dashboard, and receive a usable duplicate error.

- [ ] **Step 1: Write the browser runbook with exact visible assertions**

The runbook must use the frontend URL printed by the same `up` invocation and perform these steps in the Codex in-app browser:

1. Open `/` and verify the seeded Chemie 9b and API-created Chemie 8a are both visible.
2. Click `New class` and inspect `Curriculum route`.
3. Verify the only options are `Chemie 8 NTG` and `Chemie 9 NTG`; `Physik`, `Biologie`, and `SG` must not appear.
4. Select `Chemie 9 NTG` and enter:
   - Section: `a`
   - School year: `2026_27`
   - Prior learning: `Atombau, Periodensystem und einfache Ionen wurden bereits behandelt.`
   - Roster: `Clara Beispiel` and `David Beispiel`, one per line.
5. Verify the preview says `Creates Chemie 9a — 2026/27`, then click `Create class`.
6. Verify navigation to `/classes/chemie_9a_2026_27` and the heading `Chemie 9a`.
7. Verify the dashboard shows an empty new class: unit `Not set`, zero open loops, zero logged lessons, and no timeline lessons.
8. Verify none of the seeded 9b content appears: `Redox with ion`, `21 open loops`, and the seeded April/May lesson titles must be absent.
9. Open `Browse class files`; verify `course_state.md`, `curriculum_profile.md`, `students.md`, `trusted_sources.md`, and the memory pages are discoverable.
10. Verify no `course_network/network.json` is present; A2 owns network adoption.
11. Return home and confirm Chemie 8a, Chemie 9a, and Chemie 9b are all listed.
12. Attempt to create Chemie 9a again. Verify an inline error contains `already exists`, the browser stays on the creation form, and no duplicate class card appears.

- [ ] **Step 2: Require browser and network cleanliness**

At the end of the browser run:

- Browser console warnings/errors: none.
- Failed requests: none except the intentional duplicate `POST /api/classes` returning 422.
- No unexpected 401/403/404/500 response.
- No LLM reasoning UI, running-agent job, or model-generated copy appears during class creation.
- Keep the final all-classes page open as the HITL deliverable.

- [ ] **Step 3: Check Docker logs without following indefinitely**

Use the project name printed by `up`:

```powershell
$composeProject = Read-Host "Paste COMPOSE_PROJECT_NAME printed by worktree-stack.cmd up"
docker compose -p $composeProject logs --tail 300 backend frontend
```

Acceptance fails if the class-creation interval contains `500 Internal Server Error`, `Traceback`, `Unhandled error`, `duplicate column name`, or a model-provider request. The intentional duplicate request must appear only as a handled 422.

- [ ] **Step 4: Commit the runbook**

```powershell
git add scripts/a1_class_provisioning_browser_e2e.md
git commit -m "docs: define A1 browser acceptance"
```

---

### Task 5: Run and report the complete A1 gate

**Files:**
- Modify: `docs/superpowers/plans/2026-08-18-course-network-foundation.md`
- Modify: `implementation_plans/product_backlog.md` only after the gate passes and A1 merges.
- Modify: `docs/pm_hub.md` only after the gate passes and A1 merges.

**Interfaces:**
- Consumes: Tasks 1–4 and the complete A1 implementation.
- Produces: one merge decision backed by deterministic tests, a live API report, browser evidence, and clean logs.

- [ ] **Step 1: Run the deterministic A1 suite**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_class_provisioning.py tests\test_class_provisioning.py tests\test_multi_class_isolation.py tests\test_wiki_indexing.py tests\test_wiki_store.py -v

cd ..\frontend
npm run typecheck
npm run test -- create-class-card.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run the repository regression gate**

```powershell
cd ..
.\scripts\test.ps1
```

Expected: PASS with no OpenAI or Mistral calls.

- [ ] **Step 3: Run the live API phase and browser phase in the same fresh sandbox**

Start once with `--fresh-wiki`, run `run_a1_class_provisioning_e2e.py`, then immediately execute `scripts/a1_class_provisioning_browser_e2e.md`. Do not reset the wiki between phases.

- [ ] **Step 4: Report exact evidence**

The A1 completion report must include:

- worktree and branch;
- Compose project, backend URL, and frontend URL;
- deterministic commands and pass counts;
- `.worktree-stack/a1-api-report.json` result;
- browser result for Chemie 9a creation and duplicate handling;
- confirmation that Chemie 9b snapshot/timeline remained unchanged;
- confirmation that neither new class has `course_network/network.json`;
- log scan result, including whether the pre-existing ledger race appeared;
- wiki files created in the sandbox;
- statement that tracked `backend/teacher_wiki/` was unchanged.

- [ ] **Step 5: Update product state only after merge readiness**

When every gate above is green, mark deterministic Chemie 8/9 class creation shipped in `docs/pm_hub.md` and `implementation_plans/product_backlog.md`. Do not mark the course network, adoption, or materials library shipped; those remain A2/A3/C scope.

## Final Acceptance Matrix

| Requirement | Automated pytest | Live API | Browser HITL |
|---|---:|---:|---:|
| Exact Chemie 8/9 NTG routes | Yes | Yes | Yes |
| Create Chemie 8a | Yes | Yes | Listed |
| Create Chemie 9a | Service coverage | Reserved for browser | Yes |
| Required empty wiki skeleton | Yes | Yes | Browse key pages |
| Prior learning is not a lesson | Yes | Yes | Empty timeline |
| Fake roster creates student pages | Yes | Yes | Browse students page |
| Duplicate rejected atomically | Yes | Yes | Yes |
| Unsupported route rejected | Yes | Yes | Hidden from picker |
| Seeded Chemie 9b remains isolated | Yes | Yes | No 9b content in new class |
| No adopted network in A1 | Yes | Yes | Yes |
| No model call | Stub/no network | Log gate | No agent UI |
| No browser/backend errors | N/A | HTTP status gate | Console + Docker log gate |
