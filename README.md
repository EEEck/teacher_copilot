# KlassenPilot

Private teacher copilot for Gymnasium teachers. Log lessons through chat, review structured memory with human-in-the-loop approval, and plan the next lesson from accumulated class wiki memory.

## For developers and AI agents

Start with [`AGENTS.md`](AGENTS.md) when changing agent behavior or onboarding a
new coding agent. It points to the current behavior contracts, design plans, wiki
schema rules, and the local AutoSci reference repo.

Current durable product and agent docs live in [`docs/`](docs/). The
[`implementation_plans/`](implementation_plans/) folder is for the backlog and
concrete implementation plans only.

- [`product_vision.md`](docs/product_vision.md) - current product
  vision, product scope, and teacher-facing copilot behavior.
- [`pm_hub.md`](docs/pm_hub.md) - PM source of truth: north star, current product
  state, gaps, roadmap themes, and prioritization.
- [`product_backlog.md`](implementation_plans/product_backlog.md) - engineering-facing
  roadmap with version themes and likely implementation touchpoints.
- [`agent_architecture.md`](docs/agent_architecture.md) - agent
  architecture, memory/retrieval learnings, and implementation map.
- [`agent_contracts.md`](docs/agent_contracts.md) - reviewable
  read/write/tool/output contracts for the teacher agents.
- [`memory_hierarchy.md`](docs/memory_hierarchy.md) - file-by-file
  memory scope, loading behavior, and update rules.
- [`agent_learning_guide.md`](docs/agent_learning_guide.md) -
  optional learning guide for agent concepts, reference repos, and best practices.

For common agent debug motions, use the trace bundle scripts documented in
[`backend/README.md`](backend/README.md): FCKW lesson planning, the three-turn
Update Memory lesson-results scenario, and the Memory Sweep MBB/executive merge
trace that checks the core backend memory-consolidation behavior.

MemV4 is the active memory contract: chat stages review-only candidates through
`remember(...)`, the ledger folds and gates them, Memory Sweep makes one bounded
consolidation judgment, and the teacher-first review flow is the only durable
write boundary. Chemie 9 NTG planning uses an adapted Anthropic open K–12
procedure (Apache-2.0; not a live plug-in), LehrplanPLUS/KMK trusted sources,
and immutable shared teaching frameworks with class
`teaching_framework_adjustments.md`. The next trust gaps are input-to-wiki
reconciliation (including roster corrections), date awareness, and
browser-visible chat-turn resilience.
See [`docs/mem_v4/`](docs/mem_v4/) for the active design/evaluation ledger and
[`implementation_plans/product_backlog.md`](implementation_plans/product_backlog.md)
for the prioritized queue.

## Architecture

- **Backend:** FastAPI + OpenAI Agents SDK (`backend/`)
- **Frontend:** Next.js + Tailwind (`frontend/`)
- **Memory:** Karpathy-style markdown wiki (`backend/teacher_wiki/`)
- **Contracts:** OpenAPI + JSON Schemas (`contracts/`)

## Quick start

### Option A - Docker Compose (simplest)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose).

**1. Backend env** - copy and add your OpenAI key:

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

#### Multi-worktree Docker stacks

When several Codex agents or developers work in parallel, run one isolated
Compose stack per Git worktree. The helper script derives a stable Compose
project name and free host ports from the worktree path, creates an ignored wiki
sandbox when requested, and prints the URLs to use:

```powershell
.\scripts\worktree-stack.cmd config
.\scripts\worktree-stack.cmd up --fresh-wiki
```

Equivalent Python entry point:

```bash
python scripts/worktree_stack.py up --fresh-wiki
```

By default the helper uses:

- ignored wiki sandbox: `backend/teacher_wiki_sandbox/`
- ignored beta data sandbox when `--beta` is set: `backend/beta_data_sandbox/`
- app environment: `development`
- model profile derived from `APP_ENV` unless `--model-profile` is set

Common options:

```powershell
.\scripts\worktree-stack.cmd up --task-name plan-evidence --model-profile economy
.\scripts\worktree-stack.cmd up --beta --fresh-beta-data
.\scripts\worktree-stack.cmd up --app-env production --model-profile production
.\scripts\worktree-stack.cmd up --wiki baseline --backend-port 8111 --frontend-port 3111
.\scripts\worktree-stack.cmd down
```

The script is the preferred path for human-in-the-loop worktree testing because
it avoids accidental port reuse and keeps mutable memory out of the tracked
baseline wiki. Direct Compose still works and keeps the original defaults:

```bash
COMPOSE_PROJECT_NAME=kp_plan_evidence \
BACKEND_PORT=8111 \
FRONTEND_PORT=3111 \
WIKI_HOST_DIR=./backend/teacher_wiki_sandbox \
docker compose up --build
```

For direct Compose, create the sandbox first if you want mutable HITL memory
isolated from the baseline fixture:

```bash
cp -R backend/teacher_wiki backend/teacher_wiki_sandbox
```

Model IDs and per-call reasoning overrides stay in `backend/.env`:
`OPENAI_STRONG_MODEL`, `OPENAI_CHEAP_MODEL`,
`OPENAI_CHAT_REASONING_EFFORT`, `OPENAI_IMPORTANT_REASONING_EFFORT`, and
`OPENAI_UTILITY_REASONING_EFFORT`. The helper only sets `MODEL_PROFILE` when
you pass `--model-profile economy` or `--model-profile production`; otherwise
the backend derives the profile from `APP_ENV`.

### Option B - dev scripts (host venv + Node)

Best when you already have Python and Node installed and want logs in `scripts/.logs/`.

**Windows (Cursor terminal / PowerShell)** - use the PowerShell script (do not type `bash`; that often opens WSL, which may not be installed):

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

### Option C - manual (two terminals)

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

Both backend and frontend use **hot reload** in dev - you usually do not restart after code edits.

| What changed | Backend | Frontend | Docker |
|--------------|---------|----------|--------|
| Python in `backend/app/` | Auto (`uvicorn --reload`) | - | No action |
| React/TS in `frontend/src/` | - | Auto HMR (`next dev`) | No action |
| `backend/.env` | Restart backend | - | `docker compose restart backend` |
| `frontend/.env.local` | - | Restart frontend | `docker compose restart frontend` |
| `pyproject.toml` / new pip deps | `pip install -e .` then restart | - | `docker compose up --build backend` |
| `package.json` / new npm deps | - | `npm install` then restart | `docker compose up --build frontend` |
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

**Sessions / drafts:** Plan and Update Memory use backend-owned workflow drafts
under the wiki `workflow/` directory. Reopening the same class workflow resumes
the draft (messages, artifact, revision). Navigating away does not cancel an
accepted model turn. See [backend/README.md](backend/README.md) and
[`docs/agent_contracts.md`](docs/agent_contracts.md).

## Workflows (v1)

1. **Landing** -> select a class
2. **Class home** -> lesson timeline + status
3. **Update memory** -> chat + diary draft (right panel) -> review wiki proposals and memory suggestions -> save
4. **Create lesson plan** -> chat + plan draft (same layout) -> optional **PDF
   class material** (Textbook / Personal; OCR into session scratch) -> save to a
   lesson date (promotes materials into the class wiki)
5. **Memory Sweep** -> open/resume a saved review of accumulated durable-memory
   signals, decide in Simple or Detailed view, then apply teacher-approved writes

Both chat flows share the same UI shell (`ArtifactSessionWorkspace`: thread left, markdown draft right) and the same backend workflow-draft path.
Update Memory can start free-form from the class header, or from a lesson
timeline/detail action with a typed date/intent hint. Known planned/taught
lessons skip most target discovery; unknown hinted dates still require
confirmation in the agent runtime before saving.

## Wiki layout

```text
teacher_wiki/
  raw/classes/{class_id}/           # immutable approved diaries
  wiki/classes/{class_id}/
    lessons/{YYYY-MM-DD}/
      lesson_results.md
      lesson_plan.md
      materials.json                # lesson → promoted material_ids
    materials/{textbooks|personal}/{id}/  # OCR package (promote on plan save)
    memory/
      planning_brief.md
      teaching_patterns.md
      copilot_profile.md
      session_summaries.md
    course_state.md, student_notes.md, misconceptions.md, open_loops.md
```

Plan-session OCR scratch lives **outside** the wiki (`MATERIALS_SCRATCH_DIR`)
until the teacher saves the plan.

## Environment

| Variable | Where | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | `backend/.env` | OpenAI API (required for chat & plan) |
| `MISTRAL_API_KEY` | `backend/.env` | Mistral OCR for in-plan PDF class materials; required for live OCR / extraction |
| `MISTRAL_OCR_MODEL` | `backend/.env` | OCR model id. Default `mistral-ocr-latest` |
| `MATERIALS_SCRATCH_DIR` | `backend/.env` | Plan-session OCR scratch (outside wiki) until promote-on-save. Default `backend/data/materials_scratch` |
| `MATERIALS_INDEX_CHARS` | `backend/.env` | Compact materials TOC injected into plan chat (summaries only). Default `1200` |
| `OPENAI_STRONG_MODEL` | `backend/.env` | Production strong model. Default `gpt-5.6-terra` (~½ GPT-5.5/Sol API rate). Use `gpt-5.6-sol` for flagship at GPT-5.5 pricing. Runs IMPORTANT always + CHAT/UTILITY in the production profile |
| `OPENAI_CHEAP_MODEL` | `backend/.env` | The small model. Default `gpt-5.4-mini`. Runs CHAT/UTILITY in the economy profile |
| `MODEL_PROFILE` | `backend/.env` | Routes three call classes — CHAT (plan+ingest), IMPORTANT (Memory Sweep only), UTILITY (one-shots). `production`: strong high / strong xhigh / strong minimal (one model, reasoning-tiered). `economy`: cheap medium / strong high / cheap minimal. Unset derives from `APP_ENV` (production→production, else economy) |
| `OPENAI_CHAT_REASONING_EFFORT` / `OPENAI_IMPORTANT_REASONING_EFFORT` / `OPENAI_UTILITY_REASONING_EFFORT` | `backend/.env` | Per-call-class reasoning effort (`none`/`minimal`/`low`/`medium`/`high`/`xhigh`); unset = profile default (production: chat high / important xhigh / utility minimal; economy: chat medium / important high / utility minimal). `OPENAI_REASONING_EFFORT` is a legacy alias for the chat one |
| `WIKI_ROOT` | `backend/.env` | Path to `teacher_wiki` (Docker: set in `compose.yaml` as `/data/teacher_wiki`) |
| `BETA_ENABLED` | `backend/.env` | Enables invite-code beta auth and workspace-scoped wiki roots. Default `false` |
| `BETA_DATA_ROOT` | `backend/.env` | Local SQLite telemetry DB and per-workspace wiki copies. Default `beta_data` |
| `BETA_COOKIE_NAME` | `backend/.env` | HTTP-only session cookie name. Default `kp_beta_session` |
| `BETA_SESSION_DAYS` | `backend/.env` | Session cookie/token lifetime in days. Default `30` |
| `BETA_COOKIE_SECURE` | `backend/.env` | Set `true` behind HTTPS. Keep `false` for localhost |
| `NEXT_PUBLIC_API_BASE_URL` | `frontend/.env.local` | Backend URL for browser (default `http://localhost:8010`) |
| `APP_ENV` | `backend/.env` / Compose | `development` keeps raw local stream diagnostics; `production` strips streamed reasoning text, tool args, and tool outputs before they reach the browser. |
| `INTERNAL_API_BASE_URL` | Docker / SSR only | Server-side fetches in frontend container (`http://backend:8010` in Compose) |

### Beta testers

Beta mode keeps one app process but resolves each request to a separate
`tester_id`, `workspace_id`, and copied wiki root. The login page is
`/beta/login`; the backend sets an opaque HTTP-only cookie, so a browser refresh
keeps the tester session.

Provision invite codes from a backend shell for now:

```powershell
docker compose exec backend python -m app.services.beta_cli `
  provision `
  --tester-id t_anna `
  --workspace-id w_anna_chem9b `
  --invite-code replace-with-random-code `
  --display-label Anna
```

Telemetry is stored in `beta.sqlite3`: app sessions, visible user/assistant
messages, draft snapshots, app events, teacher feedback notes (Give feedback
form), and per-file wiki diffs for approved writes.

Generate a tester review report from telemetry and wiki diffs:

```powershell
docker compose exec backend python -m app.services.beta_cli `
  report `
  --tester t_anna `
  --workspace w_anna_chem9b `
  --out beta_data/reports/t_anna.md
```

For the hosted beta path, keep this same `tester_id` / `workspace_id` identity
contract and move the backing services to AWS: Amplify for the frontend,
ECS/Fargate + ALB for the backend, EFS for per-workspace wiki roots,
Postgres/Aurora for telemetry metadata, and S3 for exports/backups. Later
production auth should replace only the invite-code resolver behind
`RequestIdentity` with Cognito, Auth.js, Clerk, Auth0, or another OAuth/OIDC
provider. See the AWS hosting and auth entries in
[`implementation_plans/product_backlog.md`](implementation_plans/product_backlog.md#cross-cutting-platform-track).

### OpenAI API key (required for chat & plan)

Two layers read the key:

1. **`backend/.env`** - loaded by FastAPI `Settings` (`pydantic-settings`).
2. **OpenAI Agents SDK** - used for ingest/plan chat; expects `OPENAI_API_KEY` in the **process environment**. See [Agents SDK configuration](https://openai.github.io/openai-agents-python/config/).

This repo bridges them via **`app/openai_bootstrap.configure_openai_from_settings()`**, called from **`app/main.py`** on startup. Always run the API as `uvicorn app.main:app` (or Docker/restart-dev, which do the same).

- **`scripts/restart-dev.ps1`** - also loads `backend/.env` into the backend shell before `uvicorn`.
- **`compose.yaml`** - `env_file: backend/.env` for the backend service.

Check `GET /api/health` - field `openai_configured` should be `true` when the key is set.

**If misconfigured:** Create lesson plan may hang on "Starting session..." or return 500; Update memory opens without AI, but the first chat message fails.

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
- [`docs/pm_hub.md`](docs/pm_hub.md) - PM source of truth and roadmap themes
- [`docs/product_vision.md`](docs/product_vision.md) - product scope
- [`implementation_plans/product_backlog.md`](implementation_plans/product_backlog.md) - roadmap
- [`docs/agent_architecture.md`](docs/agent_architecture.md) - agent architecture and learnings
- [`docs/agent_contracts.md`](docs/agent_contracts.md) - behavior contracts
- [`docs/memory_hierarchy.md`](docs/memory_hierarchy.md) - memory scope, loading behavior, and update rules
- [`docs/context_management.md`](docs/context_management.md) - prompt assembly and context limits
- [`docs/agent_learning_guide.md`](docs/agent_learning_guide.md) - optional agent learning/reference notes
- [`backend/docs/evals.md`](backend/docs/evals.md) - agent eval tiers, how to run, container vs venv
- [`backend/teacher_wiki/AGENTS.md`](backend/teacher_wiki/AGENTS.md) - wiki schema and workflow rules

## Testing

Offline, deterministic tests - no OpenAI calls by default.

```powershell
.\scripts\test.ps1
```

Runs backend `pytest` (agent stub + tmp wiki copy) and frontend `tsc` + Vitest.
From `backend/` only:

```powershell
cd backend
.\.venv\Scripts\pip install -e ".[dev]"   # first time: includes deepeval
.\.venv\Scripts\python -m pytest
```

### Agent evals (DeepEval)

Evals run from a **separate host/CI venv**, not inside the running app
container. They import the FastAPI app in-process (`TestClient`) - you do **not**
need `docker compose up` for CI goldens.

| Run | Command |
|-----|---------|
| CI-safe evals | `pytest tests/evals/test_klassenpilot_layers.py tests/evals/test_klassenpilot_context.py tests/evals/test_klassenpilot_chat_stub.py` |
| Live agent + LLM judge | `$env:RUN_LIVE_AGENT_EVALS="1"; pytest tests/evals/test_klassenpilot_chat_live.py` |
| Live API smoke (needs `:8010`) | `$env:RUN_LIVE_API_TESTS="1"; pytest tests/test_live_api_plan_trace.py` |

Live agent evals pin the app agent runner to the production model profile by
default, independent of local `MODEL_PROFILE` / reasoning-effort settings. Use
`LIVE_AGENT_EVAL_MODEL_PROFILE=economy` only for an explicit model-profile
comparison run.

Full documentation: [`backend/docs/evals.md`](backend/docs/evals.md),
[`backend/tests/README.md`](backend/tests/README.md).

### Completion report for agent work

When a Codex agent finishes a task, it should report:

- worktree/branch used
- tests/evals run
- whether a Docker app stack was started
- frontend URL if HITL testing was used
- any wiki files changed
- known limitations or follow-up needed

## Workflow drafts and background jobs

Plan / Update Memory chat and Memory Sweep reviews are backend-owned under the
wiki `workflow/` store. The frontend mirrors drafts in
`frontend/src/features/workflow-drafts/` and tracks durable jobs
(chat turns, sweep generation) with a small Running box plus one completion
toast. Restarting the backend does not wipe an already-persisted draft or saved
sweep review; an interrupted in-flight turn resumes when the draft is reopened
(see [`docs/agent_contracts.md`](docs/agent_contracts.md)).

## UI architecture

| Layer | Location | Purpose |
|---|---|---|
| Design tokens | `src/app/globals.css` | shadcn CSS variables |
| Primitives | `src/components/ui/` | Button, Card, SegmentedToggle, … |
| Features | `src/features/workflow-drafts/` | Draft store + ExternalStore chat runtime |
| Layout | `src/components/layout/` | AppShell, PageHeader |
| Domain | `src/components/klassenpilot/` | Timeline, review briefs, Running box |
| Chat | `src/components/assistant-ui/` | Thread UI + artifact session integration |

## Roadmap

Product strategy and prioritization live in [`docs/pm_hub.md`](docs/pm_hub.md).
The engineering-facing roadmap lives in
[`implementation_plans/product_backlog.md`](implementation_plans/product_backlog.md).

Near-term themes:

- **v1.1:** make the core memory/planning loop trustworthy with evidence UI,
  class-home briefing, plan review, assessment generation, and visible memory
  suggestions.
- **v1.2:** in-plan PDF class materials (Textbook/Personal, Mistral OCR 4,
  promote on plan save) shipped; remaining: class wiki factory, guided setup,
  year-start library / chapterize, OCR backups (OpenAI VLM skeleton, Docling).
- **v1.3:** expand knowledge safely with trusted search, source cards, resource
  adaptation, and a narrow subject teaching-practice library.
- **v1.4+:** proactive suggested tasks, voice/messaging capture, and broader
  teaching logistics after the core workflow is validated.
