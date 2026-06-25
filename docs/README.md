# KlassenPilot Docs

This is the mini wiki for the repo. Start here when you need orientation, then
follow the local README closest to the code you are changing.

## Product And Agent Contracts

- `pm_hub.md` - PM source of truth: vision, north star, current product state,
  gaps, roadmap themes, and prioritization.
- `product_vision.md` - current product scope and teacher-facing behavior.
- `agent_contracts.md` - reviewable read/write/tool/output contracts.
- `agent_architecture.md` - agent architecture and retrieval/memory lessons.
- `teacher_agent_security_contract.md` - lightweight runtime safety policy for
  prompt injection, untrusted evidence, hidden writes, and high-stakes decisions.
- `agent_sdk_practices_review.md` - repo-specific OpenAI Agents SDK review and
  upgrade guidance.
- `memory_hierarchy.md` - file-by-file memory scope and update rules.
- `context_management.md` - prompt assembly and context-limit policy.
- `agent_learning_guide.md` - optional learning/reference notes.
- `mem_v2/` - Memory V2 design, backend/frontend maps, tests, traces, and bug
  reports.

Use `../implementation_plans/` for the backlog and concrete implementation
plans only.

## Codebase Map

- `../README.md` - run the full app and understand the product workflow.
- `../AGENTS.md` - repo-level guardrails for AI agents and developers.
- `../backend/README.md` - backend setup, debug CLI, and plan/update-memory
  trace bundles.
- `../backend/app/README.md` - backend package map and request flow.
- `../backend/app/api/README.md` - FastAPI route groups and API boundaries.
- `../backend/app/schemas/README.md` - API schema conventions.
- `../backend/app/services/README.md` - service layer and artifact sessions.
- `../backend/app/teacher_agent/README.md` - agent prompts, tools, models, and runtime state.
- `../backend/app/teacher_agent/wiki/README.md` - wiki facade internals.
- `../backend/tests/README.md` - deterministic test structure and fixtures.
- `../frontend/README.md` - frontend setup and folder map.
- `../frontend/src/README.md` - Next.js app, components, and frontend API flow.
- `../frontend/src/app/README.md` - App Router page map.
- `../frontend/src/content/docs/en/` - teacher-facing beta docs (locale folder; add `de/` later) rendered at
  `/docs` in the app.
- `../frontend/src/components/README.md` - frontend component layers.
- `../frontend/src/lib/README.md` - frontend API/parser/utilities map.
- `../scripts/README.md` - dev, test, Docker, and trace scripts.
- `../implementation_plans/update_memory_free_agent_plan.md` - phase map for
  the free-agent Update Memory rollout and remaining trace/eval hardening.

## Working Rules

- Product behavior changes should update `agent_contracts.md` when contracts
  change.
- Product direction, roadmap, or prioritization changes should update
  `pm_hub.md` and, when engineering sequencing changes,
  `../implementation_plans/product_backlog.md`.
- Memory scope or loading changes should update `memory_hierarchy.md` and/or
  `context_management.md`.
- Memory V2 architecture, backend/frontend integration, or trace changes should
  update `mem_v2/`.
- Agents SDK integration changes should update `agent_sdk_practices_review.md`
  when they change orchestration, session strategy, guardrails, approvals,
  tracing, or eval expectations.
- Implementation plans belong in `../implementation_plans/`, not here.
