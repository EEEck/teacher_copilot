# Memory V4 Beta Debug Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add an opt-in beta-development recorder that saves inspectable Memory V4 trace bundles for real app chat, Sweep, and Apply operations.

**Architecture:** A small recorder is disabled by default. When beta, development, and the explicit capture flag are enabled, it writes a compact SQLite index and one readable JSON bundle under `BETA_DATA_ROOT`. Routes observe existing service traces and SSE lines; domain behavior and production stream safety stay unchanged.

**Tech Stack:** FastAPI, Pydantic settings, SQLite, JSON, pytest.

## Global Constraints

- Enable only when `BETA_ENABLED=true`, `APP_ENV=development`, and `MEMORY_V4_DEBUG_CAPTURE=true`.
- `MODEL_PROFILE=economy` is a local runtime setting, never a code override.
- Full raw payload stays in beta-data JSON; ordinary beta events/reports remain compact.
- Recorder errors are best-effort and cannot fail chat, Sweep, or Apply.
- Do not commit `backend/.env`, beta data, or credentials.

---

## File structure

- `backend/app/config.py`: explicit setting and guard predicate.
- `backend/app/services/beta.py`: compact `memory_v4_debug_trace` index table.
- `backend/app/services/memory_v4_debug_capture.py`: trace IDs, JSON bundles, index writes, no-op/error isolation.
- `backend/app/api/routes.py`: captures chat traces/SSE, Sweep and Apply results.
- `backend/app/services/memory_sweep.py`: exposes optional observational debug events.
- `scripts/inspect_memory_v4_debug_capture.py`: list and render bundle timelines.
- `backend/tests/test_memory_v4_debug_capture.py`: guard and persistence coverage.
- `backend/tests/test_beta_auth_telemetry.py`: beta route integration.
- `backend/tests/test_memory_v4_sweep.py`: observation does not change cards.

## Task 1: Add guarded recorder persistence

**Files:** Modify `backend/app/config.py`, `backend/app/services/beta.py`; create `backend/app/services/memory_v4_debug_capture.py` and `backend/tests/test_memory_v4_debug_capture.py`.

**Interfaces:** `Settings.is_memory_v4_debug_capture_enabled() -> bool`; `MemoryV4DebugRecorder.capture_turn(identity, *, class_id, session_id, workflow, turn_index, payload) -> str | None`; `append(trace_id, event_type, payload) -> None`; `capture_operation(identity, *, class_id, operation, payload) -> str | None`.

- [ ] **Step 1: Write failing tests**

```python
def test_capture_requires_beta_development_and_explicit_flag():
    assert not Settings(beta_enabled=True, memory_v4_debug_capture=True, app_env="production").is_memory_v4_debug_capture_enabled()
    assert Settings(beta_enabled=True, memory_v4_debug_capture=True, app_env="development").is_memory_v4_debug_capture_enabled()

def test_recorder_writes_index_and_readable_bundle(tmp_path):
    recorder = MemoryV4DebugRecorder(tmp_path / "beta.sqlite3", tmp_path / "beta_data")
    trace_id = recorder.capture_turn(identity, class_id="chemie_9b_2026_27", session_id="s1", workflow="ingest", turn_index=1, payload={"message": "Remember this."})
    recorder.append(trace_id, "completed", {"candidate_count": 1})
    assert recorder.bundle_path(trace_id).is_file()
```

- [ ] **Step 2: Verify failure** — run `cd backend; .\.venv\Scripts\python -m pytest tests/test_memory_v4_debug_capture.py -q`; expect missing setting/recorder.

- [ ] **Step 3: Implement the recorder**

```python
class MemoryV4DebugRecorder:
    def capture_turn(self, identity: RequestIdentity, *, class_id: str, session_id: str, workflow: str, turn_index: int, payload: dict[str, Any]) -> str | None: ...
    def append(self, trace_id: str | None, event_type: str, payload: dict[str, Any]) -> None: ...
```

Create an index row and write `<beta_data_root>/memory_v4_debug_traces/<trace_id>.json` as `{"trace_id": ..., "events": [...]}`. Catch/log serialization and filesystem failures.

- [ ] **Step 4: Verify and commit** — run `cd backend; .\.venv\Scripts\python -m pytest tests/test_memory_v4_debug_capture.py tests/test_beta_auth_telemetry.py -q`; expect PASS. Commit `backend/app/config.py`, `backend/app/services/beta.py`, the recorder, and its test as `Add beta-only Memory V4 debug recorder`.

## Task 2: Capture real chat turns at the existing route boundary

**Files:** Modify `backend/app/api/routes.py` and `backend/tests/test_beta_auth_telemetry.py`.

**Interfaces:** consumes Task 1 recorder and existing `PlanService.trace`, `IngestService.trace`, and `DiscussionService.trace`; produces `turn_started`, `stream_event`, `workflow_trace`, and terminal events per bundle.

- [ ] **Step 1: Write the failing integration test**

```python
def test_beta_debug_stream_bundle_contains_context_and_raw_sse(...):
    # Login, start an ingest session, stub reasoning + final SSE, then stream it.
    bundle = load_only_debug_bundle(tmp_path)
    assert bundle["workflow"] == "ingest"
    assert any(event["type"] == "stream_event" for event in bundle["events"])
    assert any(event["type"] == "workflow_trace" for event in bundle["events"])
```

- [ ] **Step 2: Verify failure** — run `cd backend; .\.venv\Scripts\python -m pytest tests/test_beta_auth_telemetry.py -k debug_stream_bundle -q`; expect no bundle.

- [ ] **Step 3: Implement only in route helpers** — extend `_stream_chat_with_beta_telemetry` with optional callbacks. Append parsed original SSE JSON for every line. At final/error append the existing workflow `trace(...).model_dump(mode="json")`. Wire Discuss, Plan, and Ingest stream routes; record non-stream trace after normal response. Instantiate only under the explicit guard and non-local beta identity.

- [ ] **Step 4: Verify and commit** — run `cd backend; .\.venv\Scripts\python -m pytest tests/test_beta_auth_telemetry.py tests/test_api_stream.py tests/test_api_plan.py -q`; expect PASS and no bundle with flag off. Commit route/test changes as `Capture beta Memory V4 chat traces`.

## Task 3: Capture Sweep/Apply and provide a local inspector

**Files:** Modify `backend/app/services/memory_sweep.py`, `backend/app/api/routes.py`, `backend/tests/test_memory_v4_sweep.py`, `backend/tests/test_beta_auth_telemetry.py`, and `docs/mem_v4/README.md`; create `scripts/inspect_memory_v4_debug_capture.py`.

**Interfaces:** `propose_memory_sweep_review(..., debug_events: list[dict[str, Any]] | None = None)` appends `sweep_input`, `sweep_model_output`, `sweep_validation_error`, and `sweep_result`. Inspector invocation: `python scripts/inspect_memory_v4_debug_capture.py --beta-data-root backend/beta_data --latest`.

- [ ] **Step 1: Write failing behavior tests**

```python
async def test_sweep_debug_events_do_not_change_cards(...):
    events: list[dict] = []
    traced = await propose_memory_sweep_review(..., debug_events=events)
    plain = await propose_memory_sweep_review(...)
    assert traced.cards_by_queue == plain.cards_by_queue
    assert events[0]["type"] == "sweep_input"

def test_beta_debug_apply_bundle_contains_ledger_and_wiki_result(...):
    client.post(f"/api/classes/{CLASS_ID}/memory/apply", json=body)
    assert "updated_candidate_ids" in load_latest_bundle()["events"][-1]["payload"]
```

- [ ] **Step 2: Verify failure** — run `cd backend; .\.venv\Scripts\python -m pytest tests/test_memory_v4_sweep.py tests/test_beta_auth_telemetry.py -k debug -q`; expect no diagnostics.

- [ ] **Step 3: Add observational integration and inspector** — append actual Sweep claims/target excerpts before model execution, structured output after execution, validation retries, and cards/warnings. Route code stores this list as a Sweep operation bundle. Apply stores request items, paths, warnings, updated ledger IDs, and existing diff metadata. Inspector lists indexed bundles; `--trace-id` prints JSON and `--latest` renders compact lifecycle counts.

- [ ] **Step 4: Verify, document, and commit** — run `cd backend; .\.venv\Scripts\python -m pytest tests/test_memory_v4_admission.py tests/test_memory_v4_batch.py tests/test_memory_v4_sweep.py tests/test_memory_sweep_backend.py tests/test_beta_auth_telemetry.py -q`; expect PASS. Document untracked `.env` values, `scripts\worktree-stack.cmd up --beta --fresh-beta-data`, inspector use, and the manual-to-golden flow. Commit as `Trace Memory V4 sweep and apply in beta`.

## Task 4: Run the manual beta diagnostic cycle

**Files:** Create locally only `backend/.env` and `backend/beta_data/`.

- [ ] **Step 1: Prepare local runtime configuration** — copy the main repo `backend/.env` into this worktree, then set `APP_ENV=development`, `MODEL_PROFILE=economy`, `BETA_ENABLED=true`, and `MEMORY_V4_DEBUG_CAPTURE=true`.

- [ ] **Step 2: Start and exercise the stack** — run `scripts\worktree-stack.cmd up --beta --fresh-beta-data`. Exercise direct preference, marker-word observation, unknown speech act/scope, multi-claim message, repeated evidence, Sweep merge/downgrade, and teacher Apply. After each, use `--latest`.

- [ ] **Step 3: Verify boundaries and extract goldens** — confirm selected bundles contain context/prompt, API-exposed events, candidate/ledger fields, and outcome. Promote only stable expected decisions into existing deterministic capture/Sweep goldens; never commit raw beta bundles or live model output.
