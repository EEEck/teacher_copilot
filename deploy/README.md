# Deployment configs

Platform-specific deployment artifacts live here, one folder per cloud provider.
Application code stays in `backend/` and `frontend/`; this tree holds Dockerfiles,
Railway/Terraform stubs, env examples, and operator runbooks.

## Layout

| Path | Purpose |
|------|---------|
| [`railway/`](railway/) | **Active** — Railway beta stack for invited testers (Option A: SQLite + file wikis, one backend replica). |
| [`aws/`](aws/) | Placeholder for the AWS beta path documented in [`implementation_plans/beta_push.md`](../implementation_plans/beta_push.md) (Amplify + ECS + EFS + Postgres). |
| [`azure/`](azure/) | Placeholder for a future Azure deployment. |

## Conventions

- **Build context** is the **repository root** unless a provider README says otherwise.
- **Production Dockerfiles** for hosted beta live under `deploy/<provider>/` (not `Dockerfile.dev` in app folders, which are for local Compose hot reload).
- **Seed wiki** for beta provisioning is the tracked fixture at `backend/teacher_wiki/`. Hosted backend images must include it so `beta_cli provision` can `copytree` into per-workspace roots on the persistent volume.
- **Secrets** (`OPENAI_API_KEY`, invite codes) are set in the provider dashboard or secret store — never committed.

## Beta environment quick reference

Hosted beta testers need **production models** but **visible chat reasoning traces**. Those are controlled by different env vars:

| Goal | Variable | Recommended beta value |
|------|----------|------------------------|
| Production model routing | `MODEL_PROFILE` | `production` |
| Raw reasoning + tool panels in chat SSE | `APP_ENV` | `development` (not `production`) |
| Invite-code auth + isolated wikis | `BETA_ENABLED` | `true` |
| HTTPS session cookie | `BETA_COOKIE_SECURE` | `true` |
| Operator prompt-assembly HTTP traces | `AGENT_TRACE_ENABLED` | `false` (optional hardening; chat reasoning still visible) |

See [`railway/README.md`](railway/README.md) for the full operator runbook and env matrix. Quick checklist: [`railway/CHECKLIST.md`](railway/CHECKLIST.md).

## Dev → staging (beta) → production cycle

Honest status today: **one Railway project** is the hosted **beta / staging** path (`beta.klassenpilot.ai` + `api.klassenpilot.ai`). There is not yet a separate production Railway (or AWS) stack. Treat “prod” below as the *next* environment when real teachers leave invite-only beta.

### Environments

| Layer | Where | Purpose | Data |
|-------|--------|---------|------|
| **Local** | Worktree Compose (`.\scripts\worktree-stack.cmd`) | Day-to-day coding, HITL | Worktree-local wiki / optional `--beta` data; disposable |
| **Staging / beta** | Current Railway project (this folder) | Invited testers, deploy smoke, operator reports | Persistent volume at `/data` — **never share with prod** |
| **Production** | Later: second Railway project *or* AWS ([`aws/`](aws/)) | Real teacher traffic | Separate volume / DB / domains |

### Branch & promote

1. **Feature work** on a worktree branch (e.g. `cursor/…`); validate with local stack + focused tests.
2. **Staging deploy** — Railway watches a deploy branch (today: often the beta feature branch, later `main` or `staging`). Merge/PR when ready; Railway rebuilds both services.
3. **Promote to prod** — only after staging smoke (login, chat, memory commit, restart persistence). Prefer promoting a **known-good commit** (tag or merge to a prod-tracking branch), not hot-editing Railway env on the beta project.
4. When prod exists: use a **second Railway project** (or AWS) with its own volume, secrets, and domains — do not flip the beta volume into “prod mode.”

### Env knobs that differ by layer

| Variable | Local HITL | Staging / beta (Railway now) | Future production |
|----------|------------|------------------------------|-------------------|
| `APP_ENV` | `development` (see reasoning) | `development` so testers see **raw reasoning** | Usually `production` (collapsed reasoning / stripped tool panels) |
| `MODEL_PROFILE` | unset or `economy` | `production` | `production` |
| `BETA_ENABLED` | optional (`--beta`) | `true` | Product decision — invite beta off, or keep until auth ships |
| `BETA_DATA_ROOT` | worktree path | `/data/beta_data` (staging volume) | Separate root / DB — never reuse beta SQLite |
| `BETA_COOKIE_SECURE` | `false` locally | `true` | `true` |
| `CORS_ORIGINS` / `NEXT_PUBLIC_API_BASE_URL` | localhost ports | `beta` / `api` domains | prod frontend / API domains |
| `AGENT_TRACE_ENABLED` | as needed | `false` | `false` |

Reasoning visibility is driven by **`APP_ENV`**, not `MODEL_PROFILE`. Staging intentionally pairs `APP_ENV=development` + `MODEL_PROFILE=production`.

### Data isolation

- Local sandbox ≠ Railway `/data` ≠ future prod storage.
- Do not copy beta tester wikis into prod; re-provision or migrate deliberately.
- Operator `beta_cli report-all` reads the **mounted** staging DB only.

### When to promote

Promote when: staging smoke checklist passes, no open P0 on memory/auth/deploy, and you accept the cost/model profile for broader traffic. Until a second stack exists, “promote” means **merge to the long-lived branch** and plan the prod project — not renaming the beta service.
