# Railway beta deploy checklist

One-page operator sequence. Details and rationale: [`README.md`](README.md).

## Before deploy

- [ ] GitHub repo `EEEck/teacher_copilot` connected; beta branch selected
- [ ] DNS planned: `beta.klassenpilot.ai`, `api.klassenpilot.ai`
- [ ] `OPENAI_API_KEY` ready (backend only)

## Project setup

- [ ] Create Railway project (e.g. `klassenpilot-beta`)
- [ ] Add **backend** service — Root Directory `.`, Config-as-Code `deploy/railway/backend/railway.toml`
- [ ] Add **frontend** service — Root Directory `.`, Config-as-Code `deploy/railway/frontend/railway.toml`
- [ ] Backend **replicas = 1**

## Backend

- [ ] Volume mounted at **`/data`**
- [ ] Variables from [`backend/env.example`](backend/env.example) (see matrix below)
- [ ] Custom domain **`api.klassenpilot.ai`**
- [ ] Deploy → `GET /api/health` → `openai_configured: true`

## Frontend

- [ ] `NEXT_PUBLIC_API_BASE_URL=https://api.klassenpilot.ai` (**build-time** variable)
- [ ] Custom domain **`beta.klassenpilot.ai`**
- [ ] Deploy / rebuild after API URL is final

## Provision

```bash
railway ssh -s backend
python -m app.services.beta_cli provision \
  --tester-id t_anna \
  --workspace-id w_anna_chem9b \
  --invite-code "YOUR-SECRET-INVITE-CODE" \
  --display-label "Anna (Chemie 9b beta)"
```

- [ ] Share invite code out of band
- [ ] Tester opens `https://beta.klassenpilot.ai/beta/login`

## Smoke test

- [ ] Health, beta login, class list (`chemie_9b_2026_27`)
- [ ] Update Memory shows **real reasoning text** in chat (not placeholder only)
- [ ] Memory commit + plan workflow
- [ ] Backend restart → data persists on volume

## Ongoing ops

```bash
railway ssh -s backend
python -m app.services.beta_cli report-all
```

- [ ] Periodic `report-all`; backup `/data/beta_data/reports/` and volume snapshots

## Env matrix (copy/paste)

**Backend**

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

**Frontend** (build-time)

```env
NEXT_PUBLIC_API_BASE_URL=https://api.klassenpilot.ai
```
