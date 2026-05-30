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

Ingest and plan sessions are stored **in memory** (`ArtifactSessionService`). Restarting uvicorn clears server-side session state. The frontend recreates a session and restores the draft markdown when the API returns “unknown session”; chat history in the tab is not restored. Persistent session storage is deferred until multi-worker or production needs it.

## Tests

```bash
pytest
```

From repo root: `.\scripts\test.ps1`
