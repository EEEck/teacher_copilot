# Memory Sweep Review Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist Memory Sweep review results so generation runs once per ledger/wiki state, survives navigation, detects stale state, and exposes status on the class-home Memory Sweep button.

**Architecture:** Add a concrete `MemorySweepReviewStore`/service backed by SQLite under `wiki.root / "workflow"`. The backend owns generated cards, teacher edits, decisions, source fingerprints, stale detection, apply validation, discard, and refresh. The frontend opens one saved review, patches edits/decisions, and displays a class-home status badge.

**Tech Stack:** FastAPI, Pydantic, SQLite, existing `MemoryCandidateLedger`, existing `propose_memory_sweep_review`, Next.js React client state, Vitest, Pytest.

## Global Constraints

- Keep Memory Sweep independent of `assistant-ui`.
- Do not use `WorkflowDraft` for sweep reviews.
- Generate once for unchanged ledger/wiki state.
- Auto-refresh stale unedited reviews; preserve stale edited reviews until the teacher chooses refresh/discard.
- Existing `/memory/sweep/propose` and `/memory/sweep/apply` stay available for compatibility.
- Frontend Memory Sweep page must stop making per-queue propose calls.

---

### Task 1: Backend Review Store And Fingerprint

**Files:**
- Create: `backend/app/services/memory_sweep_reviews.py`
- Test: `backend/tests/test_memory_sweep_reviews.py`

**Interfaces:**
- Produces: `MemorySweepReviewStore`, `MemorySweepReviewRecord`, `build_memory_sweep_source_snapshot(...)`, `memory_sweep_source_fingerprint(...)`.
- Consumes: `MemoryCandidateLedger.list_review_candidates`, `WikiStore`, existing `memory_sweep_target_excerpts`.

- [ ] **Step 1: Write failing store tests**

Add tests that create a temp wiki/ledger, open the store, save a ready review, reload the store, and assert the review persists with proposals and decisions.

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_memory_sweep_reviews.py -q
```

Expected: fails because the module does not exist.

- [ ] **Step 2: Implement SQLite store**

Create `MemorySweepReviewStore` with methods:

```python
initialize() -> None
get_active(class_id: str) -> MemorySweepReviewRecord | None
get(review_id: str) -> MemorySweepReviewRecord | None
create_generating(class_id: str, source_fingerprint: str, source: dict) -> MemorySweepReviewRecord
mark_ready(review_id: str, proposals: dict, warnings: list[str]) -> MemorySweepReviewRecord
mark_failed(review_id: str, error: str) -> MemorySweepReviewRecord
save_decisions(review_id: str, decisions: list[dict]) -> MemorySweepReviewRecord
mark_stale(review_id: str) -> MemorySweepReviewRecord
mark_applying(review_id: str) -> MemorySweepReviewRecord
mark_completed(review_id: str) -> MemorySweepReviewRecord
discard(review_id: str) -> MemorySweepReviewRecord
```

- [ ] **Step 3: Implement source fingerprint**

Fingerprint JSON must be sorted and hash stable. Include ledger ids/status/updated_at/target/section/cluster/content hash and relevant wiki target excerpt hashes.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_memory_sweep_reviews.py -q
```

Expected: pass.

---

### Task 2: Backend Review API

**Files:**
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/schemas/api.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_memory_sweep_reviews.py`

**Interfaces:**
- Produces API models: `MemorySweepReviewResponse`, `MemorySweepReviewPatchRequest`, `MemorySweepReviewOpenRequest`, `MemorySweepReviewStatus`.
- Consumes store from Task 1 and existing `propose_memory_sweep_review` / `apply_curated_sweep_decisions`.

- [ ] **Step 1: Add failing API tests**

Test:

- opening twice returns same `review_id`
- opening calls consolidator once
- patch persists decisions
- apply rejects stale review with `409`
- discard prevents resume

- [ ] **Step 2: Add dependency**

Add `get_memory_sweep_review_store(wiki: WikiStore)` in `deps.py` using:

```python
MemorySweepReviewStore(Path(wiki.root) / "workflow" / "memory_sweep_reviews.sqlite")
```

- [ ] **Step 3: Add schemas**

Add response/request schemas in `api.py` using existing `MemorySweepCandidate` and `MemorySweepDecision`.

- [ ] **Step 4: Add routes**

Add:

```text
POST /classes/{class_id}/memory/sweep/review
GET /classes/{class_id}/memory/sweep/review
PATCH /classes/{class_id}/memory/sweep/review/{review_id}
POST /classes/{class_id}/memory/sweep/review/{review_id}/apply
POST /classes/{class_id}/memory/sweep/review/{review_id}/discard
```

Open behavior:

- same fingerprint + active review => return active review
- changed fingerprint + no teacher edits => refresh automatically
- changed fingerprint + teacher edits => mark/return stale
- `refresh=true` => discard active and create new review

- [ ] **Step 5: Run backend tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_memory_sweep_reviews.py tests\test_memory_sweep_backend.py -q
```

Expected: pass.

---

### Task 3: Frontend API Client And Review Page

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/classes/[classId]/memory-sweep/page.tsx`
- Test: add/modify focused Vitest tests if page logic is extracted.

**Interfaces:**
- Consumes backend review endpoints from Task 2.
- Produces client methods: `getMemorySweepReview`, `openMemorySweepReview`, `patchMemorySweepReview`, `applyMemorySweepReview`, `discardMemorySweepReview`.

- [ ] **Step 1: Add API types/client methods**

Add `MemorySweepReviewResponse` with `review_id`, `status`, `source_fingerprint`, `generated_at`, `updated_at`, `is_stale`, `queues`, `decisions`, `warnings`, `error`.

- [ ] **Step 2: Replace per-queue loading**

Remove `MEMORY_SWEEP_QUEUES`, `mergeProposal`, `loadingQueue`, and `loadedQueueCount`. Page mount calls `openMemorySweepReview(classId)`.

- [ ] **Step 3: Restore saved state**

Set `proposal`, `draftByCard`, and `decisionsByCard` from the review response. While `status === "generating"`, poll `getMemorySweepReview`.

- [ ] **Step 4: Persist teacher edits**

Patch backend decisions when a decision changes and after debounced wording edits. Keep local state for snappy UI.

- [ ] **Step 5: Add stale/discard/refresh UI**

Show stale banner with `Refresh sweep`, `Keep reviewing`, and `Discard`. `Refresh sweep` calls open with `refresh: true`.

- [ ] **Step 6: Apply through review id**

Use `applyMemorySweepReview(classId, reviewId)` instead of `memorySweepApply(classId, decisions)`.

- [ ] **Step 7: Run frontend checks**

Run:

```powershell
cd frontend
npm.cmd run typecheck
npm.cmd run test -- memory
```

Expected: pass.

---

### Task 4: Class-Home Memory Sweep Badge

**Files:**
- Modify: `frontend/src/app/classes/[classId]/class-home-client.tsx`
- Modify: `frontend/src/lib/api.ts`
- Optional helper/test: `frontend/src/lib/memory-sweep-review-status.ts`

**Interfaces:**
- Consumes `GET /memory/sweep/review`.
- Produces badge text for the Memory Sweep action.

- [ ] **Step 1: Add status helper**

Map backend status to short text:

```text
generating -> Generating...
ready -> Draft saved <date>
stale -> Stale draft
failed -> Failed
completed/discarded/no review -> no badge
```

- [ ] **Step 2: Fetch status on class home**

Load status alongside timeline/snapshot. Refresh on focus/pageshow using the existing class-home refresh pattern.

- [ ] **Step 3: Render badge inside Memory Sweep action**

Keep the button compact and non-blocking. Badge should be small muted text under or beside `Memory Sweep`.

- [ ] **Step 4: Run checks**

Run:

```powershell
cd frontend
npm.cmd run typecheck
npm.cmd run test -- memory-sweep
```

Expected: pass.

---

### Task 5: Docs And Verification

**Files:**
- Modify: `docs/agent_contracts.md`
- Modify: `backend/README.md` or `backend/app/api/README.md` if present and relevant.

**Interfaces:**
- Documents that Memory Sweep reviews are backend-owned saved review drafts and frontend caches are non-authoritative.

- [ ] **Step 1: Update docs**

Document generate-once, stale validation, discard/refresh, and apply safety.

- [ ] **Step 2: Run focused full checks**

Run:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_memory_sweep_reviews.py tests\test_memory_sweep_backend.py tests\test_api_ingest.py -q
```

Run:

```powershell
cd frontend
npm.cmd run typecheck
```

- [ ] **Step 3: Manual smoke**

1. Open Memory Sweep.
2. Leave during generation and return.
3. Verify saved cards return without repeated queue calls.
4. Edit a card, leave, return.
5. Verify class-home button badge.
6. Discard and verify badge clears.

