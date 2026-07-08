# CLAUDE.md

Guidance for Claude Code (and other coding agents) working in this repo.

- Start with [`AGENTS.md`](AGENTS.md) — repo onboarding, behavior contracts,
  wiki schema rules, and developer guardrails.
- Current improvement roadmap and per-milestone progress:
  [`docs/claude_todo.md`](docs/claude_todo.md) — a living document; update
  its "Implementation status" section when a milestone PR lands.
- Product/architecture docs index: [`docs/`](docs/) (see
  [`README.md`](README.md) for the full developer file stack).

## Testing quick reference

- Backend: `cd backend && .venv\Scripts\python -m pytest` (offline,
  deterministic; no OpenAI calls by default).
- Frontend: `cd frontend && npx tsc --noEmit && npx vitest run`.
- Full suite: `.\scripts\test.ps1`.
