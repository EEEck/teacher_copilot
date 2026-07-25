# AWS deployment (placeholder)

No AWS infrastructure-as-code lives here yet. The intended stack is documented in the AWS hosting entry of [`implementation_plans/product_backlog.md`](../../implementation_plans/product_backlog.md#cross-cutting-platform-track):

- **Amplify Hosting** — Next.js frontend
- **ECS Fargate + ALB** — FastAPI backend (one task, SSE-friendly idle timeout)
- **EFS** — per-workspace markdown wiki roots
- **RDS Postgres** — beta telemetry (SQLite locally is Option A only)

When this folder is populated, mirror the conventions in [`deploy/railway/`](../railway/):

- Production Dockerfiles under `deploy/aws/backend/` and `deploy/aws/frontend/`
- Env examples with the same beta env matrix (`APP_ENV=development`, `MODEL_PROFILE=production`, `BETA_ENABLED=true`)
- Operator runbook for provisioning via `app.services.beta_cli`
