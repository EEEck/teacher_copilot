# KlassenPilot

Private teacher copilot for Gymnasium teachers. Log lessons through chat, review structured memory with human-in-the-loop approval, and plan the next lesson from accumulated class wiki memory.

## For developers and AI agents

Start with [`AGENTS.md`](AGENTS.md) when changing agent behavior or onboarding a
new coding agent. It points to the current behavior contracts, design plans, wiki
schema rules, and the local AutoSci reference repo.

Current design and implementation notes live in [`implementation_plans/`](implementation_plans/):

- [`product_vision.md`](implementation_plans/product_vision.md) - current product
  vision, product scope, and teacher-facing copilot behavior.
- [`product_backlog.md`](implementation_plans/product_backlog.md) - v1.1-v1.3 product
  backlog (proactive copilot / suggested tasks in v1.3).
- [`agent_architecture.md`](implementation_plans/agent_architecture.md) - agent
  architecture, memory/retrieval learnings, and implementation map.
- [`agent_contracts.md`](implementation_plans/agent_contracts.md) - reviewable
  read/write/tool/output contracts for the teacher agents.
- [`agent_learning_guide.md`](implementation_plans/agent_learning_guide.md) -
  optional learning guide for agent concepts, reference repos, and best practices.

## Architecture

- **Backend:** FastAPI + OpenAI Agents SDK (`backend/`)
- **Frontend:** Next.js + Tailwind (`frontend/`)
- **Memory:** Karpathy-style markdown wiki (`backend/teacher_wiki/`)
- **Contracts:** OpenAPI + JSON Schemas (`contracts/`)

## Quick start

### Option A â€” Docker Compose (simplest)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose).

**1. Backend env** â€” copy and add your OpenAI key:

```bash
copy .env.example backend\.env    # Windows
# cp .env.example backend/.env     # macOS / Linux
```

**2. Start the stack** (from repo root):

```bash
docker compose up --build
# or (Git Bash / macOS / Linux):
./scripts/docker-dev.sh
```

- App: http://localhost:3000  
- API health: http://localhost:8010/api/health  
- Wiki files: `backend/teacher_wiki/` (bind-mounted; edits persist on the host)

Stop: `Ctrl+C` (foreground), `./scripts/docker-dev.sh down`, or `docker compose down`.

```bash
./scripts/docker-dev.sh down      # stop containers
./scripts/docker-dev.sh logs      # follow logs
./scripts/docker-dev.sh ps        # status
./scripts/docker-dev.sh up-fg     # foreground (see logs in terminal)
./scripts/docker-dev.sh rebuild backend   # after pyproject.toml changes
```

Python and frontend code reload automatically inside the containers (see [Developing & restarting](#developing--restarting)). Rebuild a service after dependency changes: `docker compose up --build backend` or `... frontend`.

If Next.js HMR is flaky on Windows Docker, `WATCHPACK_POLLING=true` is already set in [`compose.yaml`](compose.yaml).

### Option B â€” dev scripts (host venv + Node)

Best when you already have Python and Node installed and want logs in `scripts/.logs/`.

**Windows (Cursor terminal / PowerShell)** â€” use the PowerShell script (do not type `bash`; that often opens WSL, which may not be installed):

```powershell
.\scripts\restart-dev.ps1 -NoNewWindow
.\scripts\restart-dev.ps1 -Stop
.\scripts\restart-dev.ps1 -Status
```

Or from any shell: `scripts\restart-dev.cmd`

**Git Bash / macOS / Linux:**

```bash
./scripts/restart-dev.sh
./scripts/restart-dev.sh stop
./scripts/restart-dev.sh status
```

Starts backend on **8010** and frontend on **3000** (8010 avoids a stuck Windows :8001 ghost listener). Loads `backend/.env` for OpenAI.

```bash
tail -f scripts/.logs/backend.log
```

### Option C â€” manual (two terminals)

**1. Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
copy ..\.env.example .env     # add OPENAI_API_KEY (see below)
uvicorn app.main:app --reload --port 8010
```

API docs: http://127.0.0.1:8010/docs

**2. Frontend**

Requires **Node.js 18+** with npm. Uses [assistant-ui](https://github.com/assistant-ui/assistant-ui) for chat and **shadcn-style** shared components (`components/ui/`).

```bash
cd frontend
copy ..\.env.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
npm install
npm run dev
```

App: http://localhost:3000

## Developing & restarting

Both backend and frontend use **hot reload** in dev â€” you usually do not restart after code edits.

| What changed | Backend | Frontend | Docker |
|--------------|---------|----------|--------|
| Python in `backend/app/` | Auto (`uvicorn --reload`) | â€” | No action |
| React/TS in `frontend/src/` | â€” | Auto HMR (`next dev`) | No action |
| `backend/.env` | Restart backend | â€” | `docker compose restart backend` |
| `frontend/.env.local` | â€” | Restart frontend | `docker compose restart frontend` |
| `pyproject.toml` / new pip deps | `pip install -e .` then restart | â€” | `docker compose up --build backend` |
| `package.json` / new npm deps | â€” | `npm install` then restart | `docker compose up --build frontend` |
| Stuck port / ghost process | `.\scripts\restart-dev.ps1 -Stop` | same | `docker compose down` then `up` |
| Wiki markdown only | No restart | No restart | No action |

**Restart one service (dev scripts):**

```powershell
.\scripts\restart-dev.ps1 -BackendOnly -NoNewWindow
.\scripts\restart-dev.ps1 -FrontendOnly -NoNewWindow
```

```bash
./scripts/restart-dev.sh --backend-only
./scripts/restart-dev.sh --frontend-only
```

**Sessions (prototype):** ingest/plan chat sessions live in backend memory â€” restarting the backend clears server session state. The UI recreates a session and restores your draft; chat history in the tab is cleared. File/SQLite session persistence is deferred â€” see [backend/README.md](backend/README.md).

## Workflows (v1)

1. **Landing** â†’ select a class
2. **Class home** â†’ lesson timeline + status
3. **Update memory** â†’ chat + diary draft (right panel) â†’ review wiki proposals â†’ save
4. **Create lesson plan** â†’ chat + plan draft (same layout) â†’ save to a lesson date

Both chat flows share the same UI shell (`ArtifactSessionWorkspace`: thread left, markdown draft right).

## Wiki layout

```text
teacher_wiki/
  raw/classes/{class_id}/           # immutable approved diaries
  wiki/classes/{class_id}/
    lessons/{YYYY-MM-DD}/
      lesson_results.md
      lesson_plan.md
    memory/
      taught_so_far.md
      planning_brief.md
      teaching_patterns.md
      copilot_profile.md
      session_summaries.md
    course_state.md, student_notes.md, misconceptions.md, open_loops.md
```

## Environment

| Variable | Where | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | `backend/.env` | OpenAI API (required for chat & plan) |
| `OPENAI_MODEL` | `backend/.env` | Default model fallback for legacy settings |
| `OPENAI_CHAT_MODEL` | `backend/.env` | Chat turns (ingest/plan); default `gpt-5.4-mini` for reasoning + streaming |
| `OPENAI_FAST_MODEL` | `backend/.env` | Compile/lint/opening; default `gpt-4o-mini` |
| `OPENAI_REASONING_EFFORT` | `backend/.env` | `none`, `low`, `medium`, `high`, `xhigh` â€” hidden thinking tokens (billed as output). Default `medium`; use `none` or `low` to save cost |
| `WIKI_ROOT` | `backend/.env` | Path to `teacher_wiki` (Docker: set in `compose.yaml` as `/data/teacher_wiki`) |
| `NEXT_PUBLIC_API_BASE_URL` | `frontend/.env.local` | Backend URL for browser (default `http://localhost:8010`) |
| `INTERNAL_API_BASE_URL` | Docker / SSR only | Server-side fetches in frontend container (`http://backend:8010` in Compose) |

### OpenAI API key (required for chat & plan)

Two layers read the key:

1. **`backend/.env`** â€” loaded by FastAPI `Settings` (`pydantic-settings`).
2. **OpenAI Agents SDK** â€” used for ingest/plan chat; expects `OPENAI_API_KEY` in the **process environment**. See [Agents SDK configuration](https://openai.github.io/openai-agents-python/config/).

This repo bridges them via **`app/openai_bootstrap.configure_openai_from_settings()`**, called from **`app/main.py`** on startup. Always run the API as `uvicorn app.main:app` (or Docker/restart-dev, which do the same).

- **`scripts/restart-dev.ps1`** â€” also loads `backend/.env` into the backend shell before `uvicorn`.
- **`compose.yaml`** â€” `env_file: backend/.env` for the backend service.

Check `GET /api/health` â€” field `openai_configured` should be `true` when the key is set.

**If misconfigured:** Create lesson plan may hang on â€œStarting sessionâ€¦â€ or return 500; Update memory opens without AI, but the first chat message fails.

**Manual workaround** (backend PowerShell window):

```powershell
cd backend
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
    Set-Item "env:$($matches[1].Trim())" $matches[2].Trim()
  }
}
.\.venv\Scripts\uvicorn app.main:app --reload --port 8010
```

## Developer docs

The current developer file stack is:

- [`AGENTS.md`](AGENTS.md) - repo onboarding and agent/developer guardrails
- [`implementation_plans/product_vision.md`](implementation_plans/product_vision.md) - product scope
- [`implementation_plans/product_backlog.md`](implementation_plans/product_backlog.md) - roadmap
- [`implementation_plans/agent_architecture.md`](implementation_plans/agent_architecture.md) - agent architecture and learnings
- [`implementation_plans/agent_contracts.md`](implementation_plans/agent_contracts.md) - behavior contracts
- [`implementation_plans/agent_learning_guide.md`](implementation_plans/agent_learning_guide.md) - optional agent learning/reference notes
- [`backend/teacher_wiki/AGENTS.md`](backend/teacher_wiki/AGENTS.md) - wiki schema and workflow rules

## Testing

Offline, deterministic tests â€” no OpenAI calls.

```powershell
.\scripts\test.ps1
```

Runs backend `pytest` (agent stub + tmp wiki copy) and frontend `tsc` + Vitest (`src/lib/sse-chat.test.ts`). From `backend/` only: `pytest`.

## Prototype limitations (sessions)

Ingest/plan **session IDs and chat history** live in server RAM (`ArtifactSessionService`). Restarting uvicorn (or `docker compose restart backend`) drops sessions. The UI recovers by starting a new session and keeping your **draft markdown** in the browser; in-thread chat history is not restored. **SQLite (or any DB) is not required for the prototype** â€” add persistence only when you need multi-worker deploys or durable server-side history.

## UI architecture

| Layer | Location | Purpose |
|---|---|---|
| Design tokens | `src/app/globals.css` | shadcn CSS variables |
| Primitives | `src/components/ui/` | Button, Card, Textarea, Checkbox, â€¦ |
| Layout | `src/components/layout/` | AppShell, PageHeader |
| Domain | `src/components/klassenpilot/` | Timeline, checklist, wiki cards |
| Chat | `src/components/assistant-ui/` | Shared artifact session runtime â†’ FastAPI |

## v1.1 (planned)

- Test questions and exam generation
- Chat-driven wiki personalization (`class_config.md` custom sections)

## v1.2 (planned)

- **Docker Option B:** Caddy reverse proxy (single entry port, same-origin `/api`, SSE-friendly)
- **Lean production images:** Next.js `standalone`, multi-stage slim Dockerfiles (non-dev CMD)
- **`compose.prod.yaml`:** production profile without bind mounts
