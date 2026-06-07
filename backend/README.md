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

## Chat sessions (prototype)

Ingest and plan sessions are stored **in memory** (`ArtifactSessionService`). Restarting uvicorn clears server-side session state. The frontend recreates a session and restores the draft markdown when the API returns “unknown session”; chat history in the tab is not restored.

**SQLite is not required for the prototype.** Session persistence is deferred until multi-worker deploys or durable server-side history are needed. Current product direction lives in [`product_backlog.md`](../implementation_plans/product_backlog.md).

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
context selection. It runs the default two-turn FCKW/CFC planning scenario
against the local FastAPI backend and writes a complete run bundle under
`backend/runs/{timestamp}-fckw-plan-2turn/`.

Prerequisites:

- Backend is running on `http://localhost:8010`.
- `backend/.env` contains `OPENAI_API_KEY`.
- The plan trace endpoint is enabled. It is enabled by default in development
  and disabled by default when `APP_ENV=production`; set
  `PLAN_TRACE_ENABLED=true` to override for a local production-mode debug run.
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

The bundle includes:

- `00-run-meta.json` - run metadata and the exact two prompts.
- `03-turn1-sse.txt`, `05-turn2-sse.txt` - raw streamed events.
- `06-trace-after-turn2.json` - final trace with prompt assemblies, tool calls,
  evidence, and artifact state.
- `07-final-lessonplan.md` - final teacher-facing plan.
- `08-tool-calls-and-results.md` - readable tool call/result report.
- `prompt-*-sections.md` - section-by-section view of what the model saw.
- `raw-evidence/` - full captured tool outputs by `raw_ref`.

Recommended debugging flow:

1. Open the run folder `README.md`.
2. Inspect `prompt-02-plan_chat-sections.md` or the latest
   `prompt-*-sections.md` to see exact prompt context.
3. Inspect `08-tool-calls-and-results.md` to verify browsing behavior.
4. Inspect `07-final-lessonplan.md` to compare the final artifact against the
   evidence and prompt instructions.

## Wiki memory

The class wiki now includes compact memory pages under `wiki/classes/{class_id}/memory/`:
`taught_so_far.md`, `planning_brief.md`, `teaching_patterns.md`, `copilot_profile.md`, and `session_summaries.md`.

Planning and ingest context packs are derived from those pages plus the current lesson artifacts.
`search_memory` is the deterministic pathfinder; use `read_memory_page` or `read_lesson_range` when the snippet is not enough.

## Tests

```bash
pytest
```

From repo root: `.\scripts\test.ps1`
