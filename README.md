# KlassenPilot

Private teacher copilot for Gymnasium teachers. Log lessons through chat, review structured memory with human-in-the-loop approval, and plan the next lesson from accumulated class wiki memory.

## Architecture

- **Backend:** FastAPI + OpenAI Agents SDK (`backend/`)
- **Frontend:** Next.js + Tailwind (`frontend/`)
- **Memory:** Karpathy-style markdown wiki (`backend/teacher_wiki/`)
- **Contracts:** OpenAPI + JSON Schemas (`contracts/`)

## Quick start

### Option A — dev script (recommended on Windows)

From the repo root:

```powershell
.\scripts\restart-dev.ps1
```

Starts backend on **8001** and frontend on **3000** in separate windows. The script loads `backend/.env` into the backend process so the Agents SDK can reach OpenAI.

### Option B — manual

**1. Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
copy ..\.env.example .env     # add OPENAI_API_KEY (see below)
uvicorn app.main:app --reload --port 8001
```

API docs: http://127.0.0.1:8001/docs

**2. Frontend**

Requires **Node.js 18+** with npm. Uses [assistant-ui](https://github.com/assistant-ui/assistant-ui) for chat and **shadcn-style** shared components (`components/ui/`).

```bash
cd frontend
copy ..\.env.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
npm install
npm run dev
```

App: http://localhost:3000

## Workflows (v1)

1. **Landing** → select a class
2. **Class home** → lesson timeline + status
3. **Update memory** → chat + diary draft (right panel) → review wiki proposals → save
4. **Create lesson plan** → chat + plan draft (same layout) → save to a lesson date

Both chat flows share the same UI shell (`ArtifactSessionWorkspace`: thread left, markdown draft right).

## Wiki layout

```text
teacher_wiki/
  raw/classes/{class_id}/           # immutable approved diaries
  wiki/classes/{class_id}/
    lessons/{YYYY-MM-DD}/
      lesson_results.md
      lesson_plan.md
    course_state.md, student_notes.md, misconceptions.md, open_loops.md
```

## Environment

| Variable | Where | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | `backend/.env` | OpenAI API (required for chat & plan) |
| `OPENAI_MODEL` | `backend/.env` | Default `gpt-4o-mini` |
| `WIKI_ROOT` | `backend/.env` | Path to `teacher_wiki` |
| `NEXT_PUBLIC_API_BASE_URL` | `frontend/.env.local` | Backend URL (default `http://localhost:8001`) |

### OpenAI API key (required for chat & plan)

Two layers read the key:

1. **`backend/.env`** — loaded by FastAPI `Settings` (`pydantic-settings`).
2. **OpenAI Agents SDK** — used for ingest/plan chat; expects `OPENAI_API_KEY` in the **process environment**. See [Agents SDK configuration](https://openai.github.io/openai-agents-python/config/).

This repo bridges them in two places:

- **`app/main.py`** — `set_default_openai_key()` from Settings on startup.
- **`scripts/restart-dev.ps1`** — loads `backend/.env` into the backend shell before `uvicorn`.

**If misconfigured:** Create lesson plan may hang on “Starting session…” or return 500; Update memory opens without AI, but the first chat message fails.

**Manual workaround** (backend PowerShell window):

```powershell
cd backend
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
    Set-Item "env:$($matches[1].Trim())" $matches[2].Trim()
  }
}
.\.venv\Scripts\uvicorn app.main:app --reload --port 8001
```

## UI architecture

| Layer | Location | Purpose |
|---|---|---|
| Design tokens | `src/app/globals.css` | shadcn CSS variables |
| Primitives | `src/components/ui/` | Button, Card, Textarea, Checkbox, … |
| Layout | `src/components/layout/` | AppShell, PageHeader |
| Domain | `src/components/klassenpilot/` | Timeline, checklist, wiki cards |
| Chat | `src/components/assistant-ui/` | Shared artifact session runtime → FastAPI |

## v1.1 (planned)

- Test questions and exam generation
- Chat-driven wiki personalization (`class_config.md` custom sections)

## v1.2 (planned)

- **Docker Compose** for backend + frontend (`env_file: backend/.env`, wiki volume mounts)
- Health checks and a “Run with Docker” section in this README
- Single compose-based local entrypoint (keep `restart-dev.ps1` for bare-metal dev)
