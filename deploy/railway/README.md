# Railway beta deployment runbook

Deploy KlassenPilot for **invited beta testers** on Railway: one backend replica, SQLite telemetry, per-tester wiki copies on a persistent volume, production OpenAI models, and **visible chat reasoning traces**.

Repo: [`EEEck/teacher_copilot`](https://github.com/EEEck/teacher_copilot) — two services from the same repo (Next.js frontend + FastAPI backend).

This matches local **Option A** from [`implementation_plans/beta_push.md`](../../implementation_plans/beta_push.md). It is not a multi-replica production SaaS layout.

Operator quick path: [`CHECKLIST.md`](CHECKLIST.md).

**Role in the deploy ladder:** this Railway project is **staging / invited beta**, not production. Local worktrees → this stack → a future separate prod project (Railway or AWS). See [Dev → staging → production](../README.md#dev--staging-beta--production-cycle) in [`deploy/README.md`](../README.md).

## Architecture

```text
Teacher browser
    │
    ├─► beta.klassenpilot.ai     (Railway frontend — Next.js)
    │         NEXT_PUBLIC_API_BASE_URL ──► api.klassenpilot.ai
    │
    └─► api.klassenpilot.ai      (Railway backend — FastAPI, 1 replica)
              │
              ├─ /app/teacher_wiki          (seed wiki, baked in image)
              └─ /data/beta_data/           (Railway volume, persistent)
                    ├─ beta.sqlite3
                    └─ workspaces/{workspace_id}/teacher_wiki/
```

## Build strategy: use production Dockerfiles (not Nixpacks root dirs)

Railway supports two ways to deploy from this monorepo:

| Approach | Railway settings | Use for beta? |
|----------|------------------|---------------|
| **A — Production Dockerfiles** *(recommended)* | Root Directory = **repo root** (`.`); Config-as-Code → `deploy/railway/{backend,frontend}/railway.toml`; builder = **DOCKERFILE** | **Yes** — seed wiki in backend image, pinned Node/Python, no dev hot-reload |
| **B — Nixpacks per app folder** | Root Directory = `backend` or `frontend`; no custom Dockerfile | **No** — misses seed wiki packaging, uses dev-oriented layouts |

**Use approach A.** The `railway.toml` files set `builder = "DOCKERFILE"` and `dockerfilePath = "deploy/railway/.../Dockerfile"`. Build context is always the **repository root** so Dockerfiles can `COPY backend/...` and `COPY frontend/...`.

Do **not** set Root Directory to `backend` or `frontend` when using these Dockerfiles — paths in the Dockerfiles assume repo-root context.

### Per-service Railway UI settings

Create **two services** from the same connected repo (e.g. deploy branch `cursor/774c1450` or your beta branch):

| Setting | Backend service | Frontend service |
|---------|-----------------|------------------|
| **Root Directory** | `.` (repository root) | `.` (repository root) |
| **Config-as-Code file** | `deploy/railway/backend/railway.toml` | `deploy/railway/frontend/railway.toml` |
| **Builder** | Dockerfile *(from config)* | Dockerfile *(from config)* |
| **Dockerfile path** | `deploy/railway/backend/Dockerfile` *(from config)* | `deploy/railway/frontend/Dockerfile` *(from config)* |
| **Replicas** | **1** *(required)* | 1 |

If Config-as-Code is not wired, set **Settings → Build → Builder = Dockerfile** and **Dockerfile path** manually to the paths above. Do not rely on auto-detected root `Dockerfile` — there is none at repo root.

---

## Environment matrix (what actually changes behavior)

Investigated in code — these are the knobs that matter for hosted beta.

### `APP_ENV` (`development` | `production`)

| Effect | `development` | `production` |
|--------|---------------|--------------|
| **Chat SSE reasoning traces** | Raw reasoning text streamed to the UI | Collapsed to one placeholder: *"Working through the request..."* ([`stream_safety.py`](../../backend/app/services/stream_safety.py), gated in [`artifact_session_service.py`](../../backend/app/services/artifact_session_service.py) L897) |
| **Chat SSE tool args / outputs** | Visible in stream | Stripped (empty strings) |
| **Default `MODEL_PROFILE`** (when unset) | `economy` (cheap chat model) | `production` (strong model) |
| **Agent trace HTTP endpoints** (`/api/.../trace`) | Enabled by default | Disabled by default ([`config.py`](../../backend/app/config.py) `is_agent_trace_enabled`) |
| **Memory V4 debug capture** | Allowed if `BETA_ENABLED` + `MEMORY_V4_DEBUG_CAPTURE=true` | Disabled |

Frontend has **no** `APP_ENV` switch — reasoning UI is driven entirely by what the backend streams ([`sse-chat.ts`](../../frontend/src/lib/sse-chat.ts), [`reasoning.tsx`](../../frontend/src/components/assistant-ui/reasoning.tsx)).

**Output safety** (blocking replies that leak `raw_ref`, API keys, etc.) runs in **both** envs ([`output_safety.py`](../../backend/app/services/output_safety.py)).

### `MODEL_PROFILE` (`production` | `economy`)

Independent of chat trace visibility when set explicitly ([`config.py`](../../backend/app/config.py) `resolved_model_profile`):

| Call class | `production` | `economy` |
|------------|--------------|-----------|
| CHAT (plan + ingest) | strong / high reasoning | cheap / medium |
| IMPORTANT (Memory Sweep) | strong / xhigh | strong / high |
| UTILITY (one-shots) | strong / minimal | cheap / minimal |

### Recommended hosted beta combo (exact values)

| Variable | Service | Value |
|----------|---------|-------|
| `OPENAI_API_KEY` | backend | `sk-...` *(secret)* |
| `BETA_ENABLED` | backend | `true` |
| `BETA_DATA_ROOT` | backend | `/data/beta_data` |
| `BETA_COOKIE_SECURE` | backend | `true` |
| `APP_ENV` | backend | `development` |
| `MODEL_PROFILE` | backend | `production` |
| `WIKI_ROOT` | backend | `/app/teacher_wiki` |
| `CORS_ORIGINS` | backend | `["https://beta.klassenpilot.ai"]` |
| `AGENT_TRACE_ENABLED` | backend | `false` |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | `https://api.klassenpilot.ai` *(build-time)* |

**Do not** use `APP_ENV=production` if testers should see reasoning — there is no separate “show reasoning” flag today.

Local equivalent (Compose):

```powershell
.\scripts\worktree-stack.cmd up --beta --fresh-beta-data --app-env development --model-profile production
```

---

## 1. Create the Railway project

1. New **Railway project** (e.g. `klassenpilot-beta`).
2. **Connect GitHub repo** `EEEck/teacher_copilot`; deploy branch `cursor/774c1450` (or your beta branch).
3. Add **two services** from the same repo — see [Build strategy](#build-strategy-use-production-dockerfiles-not-nixpacks-root-dirs) table above.
4. Backend: **replicas = 1** (SQLite + file wikis are not safe with multiple writers).

## 2. Backend service

### Volume

1. Backend service → **Volumes** → create volume, mount at **`/data`**.
2. Confirm `BETA_DATA_ROOT=/data/beta_data` in Variables (SQLite + workspace wikis live here).

### Variables

Copy from [`backend/env.example`](backend/env.example). Paste into **Railway → backend service → Variables**:

```env
OPENAI_API_KEY=sk-...
BETA_ENABLED=true
BETA_DATA_ROOT=/data/beta_data
BETA_COOKIE_SECURE=true
APP_ENV=development
MODEL_PROFILE=production
WIKI_ROOT=/app/teacher_wiki
CORS_ORIGINS=["https://beta.klassenpilot.ai"]
AGENT_TRACE_ENABLED=false
```

Deploy and confirm **`GET /api/health`** returns `openai_configured: true`.

### Domain

Custom domain: **`api.klassenpilot.ai`** → backend service (HTTPS). Wait for TLS before testers use `BETA_COOKIE_SECURE=true`.

### Seed wiki packaging

[`backend/Dockerfile`](backend/Dockerfile) copies `backend/teacher_wiki/` into the image at `/app/teacher_wiki`. This fixes the gap in `backend/Dockerfile.dev`, which only packages `app/` and relies on Compose bind mounts.

`beta_cli provision` resolves the seed via `WIKI_ROOT` ([`beta_cli.py`](../../backend/app/services/beta_cli.py) `_seed_wiki_root()`), then `copytree`s into `BETA_DATA_ROOT/workspaces/{workspace_id}/teacher_wiki/` ([`beta.py`](../../backend/app/services/beta.py) `provision_tester`).

## 3. Frontend service

### Build variable

In **Railway → frontend service → Variables**, set:

```env
NEXT_PUBLIC_API_BASE_URL=https://api.klassenpilot.ai
```

Mark **`NEXT_PUBLIC_API_BASE_URL` available at build time** (Railway passes it as a Docker `ARG` — declared in [`frontend/Dockerfile`](frontend/Dockerfile)). Rebuild the frontend after changing this value.

See [`frontend/env.example`](frontend/env.example).

### Domain

Custom domain: **`beta.klassenpilot.ai`** → frontend service.

Tester entry: `https://beta.klassenpilot.ai/beta/login` (invite code → HTTP-only `kp_beta_session` cookie). Optional product note: first-time testers may be prompted for a mini-profile after login.

## 4. Provision testers

After backend is healthy and the volume is mounted, **SSH into the running backend container** and run `beta_cli`:

```bash
railway link          # once, from your machine
railway ssh -s backend

python -m app.services.beta_cli provision \
  --tester-id t_anna \
  --workspace-id w_anna_chem9b \
  --invite-code "YOUR-SECRET-INVITE-CODE" \
  --display-label "Anna (Chemie 9b beta)"
```

Requirements inside the container:

- Same env as the running backend (`BETA_DATA_ROOT`, `WIKI_ROOT`, seed wiki at `/app/teacher_wiki`).
- Writable volume at `/data/beta_data`.
- One workspace per tester; mock class **`chemie_9b_2026_27`** is in the seed wiki.

Share the invite code out of band.

### Operator reports

All provisioned testers on the volume (skips `disabled = 1` rows in SQLite):

```bash
railway ssh -s backend
python -m app.services.beta_cli report-all \
  --db /data/beta_data/beta.sqlite3 \
  --reports-dir /data/beta_data/reports
```

Defaults when `--db` / `--reports-dir` are omitted match the running backend env (reports land in `/data/beta_data/reports/{tester_id}.md`).

Single tester:

```bash
python -m app.services.beta_cli report \
  --tester t_anna \
  --workspace w_anna_chem9b \
  --out /data/beta_data/reports/t_anna.md
```

Use `--include-disabled` to regenerate reports for revoked testers. Copy the `reports/` tree off the volume for backups (Railway volume snapshots or `railway ssh` + `tar`).

## 5. Smoke test checklist

1. **`GET https://api.klassenpilot.ai/api/health`** — `openai_configured: true`.
2. **Beta login** — `POST /api/beta/login` with invite code; cookie set (`Secure`, `HttpOnly`, `SameSite=Lax`).
3. **Class list** — authenticated `GET /api/classes` shows `chemie_9b_2026_27`.
4. **Update Memory SSE** — start ingest session, send a turn; UI shows **expandable Reasoning** with real text (not only *"Working through the request..."*).
5. **Memory commit** — approve proposal; wiki files change under workspace root on volume.
6. **Plan workflow** — create/save a lesson plan.
7. **Restart backend** — single replica redeploy; wiki + `beta.sqlite3` persist on volume; session cookie still valid.
8. **Cross-tester isolation** — second provisioned tester cannot see first tester's wiki (different `workspace_id`).

## 6. Operational notes

- **Single replica only** — SQLite and in-process session caches are not safe with multiple backend writers.
- **No `uvicorn --reload`** — production CMD in [`backend/Dockerfile`](backend/Dockerfile); listens on Railway's `PORT` (default 8010).

### Container hardening (Railway Dockerfiles)

Both production images in `deploy/railway/` follow a practical MVP posture:

| Control | Backend | Frontend |
|---------|---------|----------|
| Base image | `python:3.12-slim-bookworm` (Debian slim) | `node:22-alpine` multi-stage |
| Runtime user | `app` (uid 1000), not root | `nextjs` (uid 1001), not root |
| Writable paths | `/data/beta_data` only (Railway volume at `/data`) | none baked in; stateless |
| Process | `uvicorn` without `--reload` | `next start` (not `next dev`) |
| Health check | `GET /api/health` | HTTP GET on `PORT` |
| Build context | root `.dockerignore` excludes `.env*`, credentials, local data |

**Intentional tradeoffs:** images are not distroless (slim/alpine keeps Python/Next tooling simple). Base tags are pinned to major/minor (`3.12`, `22`) rather than image digests — rebuild periodically for security patches. Provisioning (often via root `railway ssh`) always chmod/`chown`s the new workspace so the container `app` user (uid 1000) can create `workflow/` and write SQLite — friendly private beta, not multi-tenant lockdown. If an old volume is still root-only, one-time `chown -R 1000:1000 /data/beta_data` (or re-run provision) still works.
- **SSE timeout** — agent turns up to ~240s (`AGENT_TIMEOUT_SECONDS`); ensure Railway/proxy idle timeouts are sufficient.
- **Secrets** — `OPENAI_API_KEY` only on backend; never on frontend.
- **AWS path later** — see [`deploy/aws/`](../aws/README.md) and `implementation_plans/beta_push.md` for Postgres + EFS when Option A outgrows one VM.

## Pre-deploy blockers (resolve before clicking Deploy)

| Blocker | Action |
|---------|--------|
| DNS not ready | Point `beta.klassenpilot.ai` and `api.klassenpilot.ai` at Railway; wait for TLS |
| `OPENAI_API_KEY` missing | Set on backend before first deploy |
| Backend volume not mounted | Mount at `/data` before provisioning testers |
| Wrong Root Directory | Must be repo root (`.`), not `backend`/`frontend`, when using `deploy/railway/*/Dockerfile` |
| Frontend API URL wrong at build | Set `NEXT_PUBLIC_API_BASE_URL` **before** frontend build; flag as build-time variable |
| Multiple backend replicas | Keep **replicas = 1** |
| Frontend `next build` fails on `/404` | `useSearchParams()` in layout wrappers (e.g. `beta-profile-gate`) must be inside a React `<Suspense>` boundary — fix in frontend before deploy |
