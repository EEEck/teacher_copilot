# CLAUDE.md

Guidance for Claude Code (and other coding agents) working in this repo.

- Start with [`AGENTS.md`](AGENTS.md) — repo onboarding, behavior contracts,
  wiki schema rules, and developer guardrails.
- Product strategy and current state: [`docs/pm_hub.md`](docs/pm_hub.md).
  Engineering roadmap, open work, tech-debt, and incidents:
  [`implementation_plans/product_backlog.md`](implementation_plans/product_backlog.md).
- Product/architecture docs index: [`docs/`](docs/) (see
  [`README.md`](README.md) for the full developer file stack).

## Testing quick reference

- Backend: `cd backend && .venv\Scripts\python -m pytest` (offline,
  deterministic; no OpenAI calls by default). Materials OCR packaging/prompts
  are in that suite; live Mistral needs `RUN_LIVE_MISTRAL_OCR=1`.
- Frontend: `cd frontend && npx tsc --noEmit && npx vitest run`.
- Full suite: `.\scripts\test.ps1`.
