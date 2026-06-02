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
