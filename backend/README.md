# KlassenPilot backend

FastAPI app under `app/`. Run the API **through** `app.main` so OpenAI is configured for the Agents SDK.

## Run

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e .
uvicorn app.main:app --reload --port 8010
```

Health: `GET http://127.0.0.1:8010/api/health` — includes `openai_configured` (true when `OPENAI_API_KEY` is set in `backend/.env`).

## OpenAI API key

1. Copy `../.env.example` to `backend/.env` and set `OPENAI_API_KEY`.
2. On startup, [`app/main.py`](app/main.py) calls [`configure_openai_from_settings`](app/openai_bootstrap.py), which copies the key into `os.environ` and `set_default_openai_key()` for the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/config/).

Scripts or REPL code that construct `AgentRunner` without importing `app.main` must call `configure_openai_from_settings(get_settings())` first, or chat will fail with missing-key errors.

## Agent runtime settings

The default chat model is `OPENAI_CHAT_MODEL=gpt-5.5` with
`OPENAI_REASONING_EFFORT=medium`. mem_v3 PR4 makes durable capture an explicit
`remember(...)` tool call during the planning/ingest turn, and the live judge
eval showed the `-mini` tier both under-emits and calls tools unreliably — so
the capture turn runs on the stronger tier. Override via `OPENAI_CHAT_MODEL` in
`backend/.env` (e.g. back to `gpt-5.4-mini`) for cheaper local smoke runs where
capture reliability does not matter.

Complex lesson-planning turns can browse wiki memory, reason over evidence, and
stream a full artifact. The default `AGENT_TIMEOUT_SECONDS=240` gives those
turns enough room before the backend emits a timeout SSE event. For faster local
smoke checks, lower `OPENAI_REASONING_EFFORT` or `AGENT_TIMEOUT_SECONDS` in
`backend/.env`.

## Chat sessions and memory targets (prototype)

Ingest and plan sessions are stored **in memory** (`ArtifactSessionService`). Restarting uvicorn clears server-side session state. The frontend recreates a session and restores the draft markdown when the API returns “unknown session”; chat history in the tab is not restored.

**SQLite is not required for the prototype.** Session persistence is deferred until multi-worker deploys or durable server-side history are needed. Current product direction lives in [`product_backlog.md`](../implementation_plans/product_backlog.md).

Update Memory starts in free-agent target discovery unless the frontend passes a
typed start hint to `POST /api/classes/{id}/ingest/sessions`. Timeline/detail
buttons pass `lesson_date`, `lesson_title`, `intent`, `target_kind`, and
`source=timeline_hint`. The backend confirms the target only when canonical
lesson detail exists; unknown hinted dates seed a draft but stay in
`identify_target` with `needs_confirmation=true`.

Both planning and Update Memory use the same app-owned conversation strategy:
`ArtifactSessionService` stores messages, the current markdown artifact, and a
workflow runtime object. Planning uses `PlanRuntime`; Update Memory uses
`MemoryRuntime`. Future artifact chats should register an `ArtifactSpec` with
runtime, prompt trace, stream, final-event, and trace-contract hooks instead of
adding mode-specific branches to the session core.

## Beta identity, telemetry, and workspace roots

Beta mode keeps one FastAPI app process but resolves each request to a
`RequestIdentity(tester_id, workspace_id, role, wiki_root)`. In local beta,
invite-code login writes an opaque HTTP-only session cookie; the API dependency
resolves that cookie to a workspace-scoped wiki root under `BETA_DATA_ROOT`.

Current beta storage shape:

- `beta.sqlite3` stores testers, workspaces, sessions, visible chat messages,
  app events, artifact snapshots, and wiki commit/diff metadata.
- `workspaces/{workspace_id}/teacher_wiki/` stores the tester's copied markdown
  wiki.
- `app.services.beta_cli` provisions testers and renders Markdown operator
  reports.
- Route handlers record telemetry at workflow boundaries, but durable wiki
  writes still go only through teacher-approved apply/commit endpoints.

The production path should preserve the `RequestIdentity` boundary. AWS hosting
can move workspace roots to EFS, metadata/telemetry to Postgres/Aurora, and
exports to S3 without changing route-level access patterns. Later OAuth/OIDC
providers such as Cognito, Auth.js, Clerk, or Auth0 should replace only the
invite-code/session resolver, then map provider users back into
`RequestIdentity` before class data is accessed.

## Memory Sweep review contract

Memory Sweep is the slow consolidation layer between captured session signals
and durable wiki memory. Captured candidates live in the SQLite candidate
ledger; the sweep proposer groups active candidates into teacher-reviewable
cards and never writes wiki files directly.

Decision semantics:

- `Add memory` writes supported targets, then marks represented rows `applied`.
- `Already in memory` marks rows `applied` without a file write.
- `Not needed` marks rows `rejected`.
- `Remove` marks rows `deleted`.
- `Review later` marks rows `snoozed` and sets `snoozed_until` to seven days
  after review.

Normal sweep proposals include active rows plus snoozed rows only when either
their `snoozed_until` time has passed or a newer candidate appears in the same
memory lane after the snooze. This keeps the review loop short after submit
while still letting deferred signals compound when more evidence arrives.

## Agent debug CLI

Interactive multi-turn chat against the real `AgentRunner` (no FastAPI). Shows reasoning, wiki tool calls, and **full** tool results (not capped like browser SSE).

```bash
cd backend
.venv\Scripts\activate
python -m app.cli chat --mode ingest --class chemie_9b_2026_27
```

Useful flags:

- `--show-context` — print the ingest/plan memory pack at startup
- `--trace runs/debug.jsonl` — append compact JSONL (session, user messages, context pack if `--show-context`, tool calls/results, finals; no per-token reasoning unless `--trace-reasoning`)
- `--message "We covered redox today"` — one turn, then exit
- `--tool-limit 2000` — cap tool output size (default: unlimited in CLI)

REPL commands: `/context`, `/draft`, `/tools`, `/propose` (ingest only), `/help`, `/quit`.

Requires `OPENAI_API_KEY` in `backend/.env`. Not run in CI (live model calls).

## Plan trace bundle

Use this when debugging lesson-planning behavior, prompt assembly, tool calls, or
context selection. It runs the default three-turn FCKW/CFC planning scenario
against the local FastAPI backend and writes a complete run bundle under
`backend/runs/{timestamp}-fckw-plan-3turn/`.

Prerequisites:

- Backend is running on `http://localhost:8010`.
- `backend/.env` contains `OPENAI_API_KEY`.
- The agent trace endpoint is enabled. It is enabled by default in development
  and disabled by default when `APP_ENV=production`; set
  `AGENT_TRACE_ENABLED=true` to override for a local production-mode debug run.
  `PLAN_TRACE_ENABLED=true` remains supported as a backward-compatible alias.
- The target class exists in `backend/teacher_wiki/`.

PowerShell from repo root:

```powershell
.\scripts\run_plan_trace_bundle.ps1
```

Python from repo root:

```powershell
.\backend\.venv\Scripts\python .\scripts\run_plan_trace_bundle.py
```

Useful overrides:

```powershell
.\scripts\run_plan_trace_bundle.ps1 `
  -ApiBase "http://localhost:8010" `
  -ClassId "chemie_9b_2026_27" `
  -OutputRoot "backend/runs" `
  -RunName "manual-fckw-debug"

.\backend\.venv\Scripts\python .\scripts\run_plan_trace_bundle.py `
  --api-base "http://localhost:8010" `
  --class-id "chemie_9b_2026_27" `
  --output-root "backend/runs" `
  --run-name "manual-fckw-debug"
```

To test a custom prompt while keeping the same debug bundle format:

```powershell
.\backend\.venv\Scripts\python .\scripts\run_plan_trace_bundle.py `
  --prompt1-file ".\tmp\prompt1.txt" `
  --prompt2-file ".\tmp\prompt2.txt"
```

The three default teacher turns are:

1. Full 45-minute FCKW/redox lesson plan (structure, homework, misconception note).
2. Add a 5-minute review of the last four lectures using class confusion from wiki.
3. Final refinement: 2-minute active-recall recap; agent should move to `finalize`.

The bundle includes:

- `00-run-meta.json` - run metadata and the exact three prompts.
- `02-trace-before-first-message.json` - prompt stack before any chat.
- `NN-turnX-sse.txt` - raw streamed events per turn.
- `NN-trace-after-turnX.json` - trace after each teacher prompt.
- `NN-final-lessonplan.md` - final teacher-facing plan artifact.
- `NN-tool-calls-and-results.md` - readable tool call/result report.
- `prompt-*-sections.md` - section-by-section view of what the model saw.
- `snapshot-*` - exact prompt stack before/after each turn.
- `raw-evidence/` - full captured tool outputs by `raw_ref`.

Recommended debugging flow:

1. Open the run folder `README.md`.
2. Inspect `prompt-02-plan_chat-sections.md` or the latest
   `prompt-*-sections.md` to see exact prompt context.
3. Inspect `NN-tool-calls-and-results.md` to verify browsing behavior.
4. Inspect `NN-final-lessonplan.md` to compare the final artifact against the
   evidence and prompt instructions.

Expected plan prompt sections include `Teacher layer`, `Active class core`,
`Session state`, `Lesson planning state`, `Current lesson artifact`, and
`Evidence briefs`. Full lessons, full student files, and full roll-ups should
come from tools, not the default prompt.

## Update Memory trace bundle

Use this when debugging Update Memory target selection, prompt assembly, tool
calls, runtime state, or lesson-results diary output. It runs the default
three-turn `2026-05-29` lesson-results scenario against the local FastAPI
backend and writes a bundle under `backend/runs/{timestamp}-memory-update-3turn/`.

PowerShell from repo root:

```powershell
.\scripts\run_memory_update_trace_bundle.ps1
```

Python from repo root:

```powershell
.\backend\.venv\Scripts\python .\scripts\run_memory_update_trace_bundle.py
```

The bundle includes raw SSE per turn, trace JSON after each turn, exact prompt
instructions and user input, section-by-section context, tool call/result
report, `raw-evidence/`, and the final `NN-final-diary.md`.

Expected Update Memory prompt sections include `Teacher layer`, `Active class
core`, `Update Memory task context`, `Memory target state`, `Memory session
state`, `Lesson result state`, and `Memory evidence briefs`. The prompt should
not inject `teacher_wiki/AGENTS.md`, full roll-ups, full student files, or full
lesson files by default.

The default turns:

1. Log lesson results for `2026-05-29`, including named student observations.
2. Add participation details and update the `2026-05-25` open-loop status.
3. Ask the agent to make the lesson results ready to save memory.

The plan and memory trace bundle scripts currently share a lot of behavior
(start session, stream turns, fetch trace, write bundle files). If more
artifact workflows are added, consolidate them into one scenario-driven trace
runner before adding another near-copy script.

## Memory Sweep merge trace

Use this when changing Memory Sweep prompts, alignment/card contracts, target
canonicalization, ledger status handling, or the `/memory/sweep/propose` and
`/memory/sweep/apply` routes. It seeds three temporary ledger rows into the
local backend: two MBB-style planning-communication signals and one
executive-style communication signal. The expected result is one consolidated
`teacher_profile.md / Communication` review card, not one card per row.

PowerShell from repo root:

```powershell
.\backend\.venv\Scripts\python .\scripts\trace_memory_mbb_executive_consolidation.py `
  --run-name manual-mbb-executive-merge
```

Run the current-memory variants when touching `adjust` or `already_covered`
behavior:

```powershell
.\backend\.venv\Scripts\python .\scripts\trace_memory_mbb_executive_consolidation.py `
  --current-memory none `
  --run-name manual-mbb-executive-add

.\backend\.venv\Scripts\python .\scripts\trace_memory_mbb_executive_consolidation.py `
  --current-memory narrow-mbb `
  --run-name manual-mbb-executive-adjust

.\backend\.venv\Scripts\python .\scripts\trace_memory_mbb_executive_consolidation.py `
  --current-memory generalized `
  --run-name manual-mbb-executive-covered
```

Passing shape:

- `passed=true`
- `full_merge_cards=1`
- one card represents all three seeded candidate IDs
- expected operation is `add`, `adjust`, or `already_covered` depending on
  `--current-memory`

The trace is a live-model drift signal and writes a run bundle under
`backend/runs/`. The active production prompts should still avoid hardcoded
MBB/McKinsey/executive communication examples; deterministic prompt tests cover
that contract.

## Wiki memory

The class wiki includes compact memory pages under `wiki/classes/{class_id}/memory/`:
`planning_brief.md`, `teaching_patterns.md`, `copilot_profile.md`, and `session_summaries.md`.
(`class_state.md` / `taught_so_far.md` were retired in mem_v3 PR2 — current unit
and taught sequence are derived from the canonical `course_state.md` /
`timeline.md` rollups, so every such fact has one home.)

Planning and ingest prompt layers are derived from those pages plus the current
artifact/runtime state. `search_memory` is the deterministic pathfinder; use
`read_memory_page` or `read_lesson_range` when the snippet is not enough.

Durable memory is captured through the explicit `remember(...)` tool the model
calls when the teacher gives a standing instruction (mem_v3 PR4); every memory
write goes through one typed contract (`app/services/memory_skills.py`).

## Tests

```bash
pytest
```

From repo root: `.\scripts\test.ps1`

**Agent evals (DeepEval):** deterministic goldens live under `tests/evals/`. Run
from a **host/CI venv** with dev deps — not inside the running uvicorn/docker
container. Full guide: [`docs/evals.md`](docs/evals.md).

Quick deterministic eval run:

```powershell
cd backend
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_layers.py tests/evals/test_klassenpilot_context.py tests/evals/test_klassenpilot_chat_stub.py -v
```

Live agent + LLM judge (opt-in, uses `OPENAI_API_KEY` from `backend/.env`):

```powershell
$env:RUN_LIVE_AGENT_EVALS="1"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_chat_live.py -v
```

See also [`tests/README.md`](tests/README.md).
