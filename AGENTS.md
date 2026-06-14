# KlassenPilot Agent Guide

Read this first when working on the repo as an AI agent or developer. It is the
short context map for the project. Durable product/agent docs live in `docs/`.
`implementation_plans/` is reserved for the backlog and concrete implementation
plans.

## Project Purpose

KlassenPilot is a private teacher copilot for Gymnasium teachers. The MVP has
two focused workflows:

- **Update memory**: help a teacher turn a lesson conversation into structured
  lesson results, then apply wiki updates only after teacher approval.
- **Create lesson plan**: help a teacher draft a practical next lesson or
  assessment plan grounded in class wiki memory.

The app uses a Karpathy-style markdown wiki as persistent compiled memory. The
wiki is not just retrieval storage; it is the agent-maintained working memory
between raw lesson notes and future planning.

## What To Read First

1. `README.md` - how to run the app and overall architecture.
2. `docs/product_vision.md` - current product vision, scope,
   and teacher-facing copilot behavior.
3. `implementation_plans/product_backlog.md` - versioned feature direction.
4. `docs/agent_architecture.md` - agent architecture,
   memory/retrieval learnings, and implementation map.
5. `docs/agent_contracts.md` - current read/write/tool/output
   contracts for the teacher agents.
6. `docs/memory_hierarchy.md` - file-by-file memory scope,
   loading behavior, and update rules.
7. `docs/context_management.md` - prompt assembly, context
   limits, and why blunt 14k caps were removed.
8. `backend/teacher_wiki/AGENTS.md` - wiki schema and wiki-specific workflow
   rules when touching memory behavior.

Optional learning/reference: `docs/agent_learning_guide.md`.
It is an educational note, not a behavior contract.

## Current Boundaries

- Planning chat is read-only with respect to the wiki. It may update
  `plan_markdown`, but it must not write wiki files directly.
- Memory update chat may update `diary_markdown`, but curated wiki writes happen
  only through the teacher-approved commit flow.
- Prefer compiled wiki memory over raw sources.
- Frontend polish is not the priority unless the user explicitly asks for it.
  The frontend primarily uses `assistant-ui`.
- Keep the MVP simple. Do not add broad agent infrastructure unless it directly
  supports lesson planning or memory update.

## Code Map

- Backend app: `backend/app/`
- Agent prompts: `backend/app/teacher_agent/prompts.py`
- Agent tools: `backend/app/teacher_agent/tools.py`
- Agent definitions: `backend/app/teacher_agent/agent.py`
- Agent runner / OpenAI Agents SDK loop: `backend/app/teacher_agent/agents.py`
- Structured agent outputs: `backend/app/teacher_agent/models.py`
- Context limit policy (central tunables): `backend/app/context_limits.py` +
  `backend/app/config.py`
- Lesson-planning runtime context manager (session/lesson state, evidence
  briefs, memory candidates, renderers): `backend/app/teacher_agent/planning_state.py`
- API schemas: `backend/app/schemas/api.py`
- Wiki store facade: `backend/app/teacher_agent/wiki/store.py`
- Wiki package internals: `backend/app/teacher_agent/wiki/`
- Seed/dev wiki: `backend/teacher_wiki/`
- Memory hierarchy and update rules: `docs/memory_hierarchy.md`
- Backend tests: `backend/tests/`
- Frontend app: `frontend/`

## Agent Contracts

Treat `docs/agent_contracts.md` as the reviewable behavior
contract. If agent behavior changes, update that file in the same change as the
code or explain why it does not apply.

Important current contracts:

- Lesson planning starts from a slim, deduped class slice plus backend-owned
 runtime state (`PlanRuntime`) updated by model-proposed `state_patch`, not a
 replayed transcript or a blunt 14k clip.
- Memory update chat starts from a slim, deduped ingest slice, not stacked
 index/base/query-pack context.
- The planner browses class memory only when the teacher request exceeds that
 base slice; tool outputs are captured behind a `raw_ref` and only compact
 evidence briefs are re-injected (use `get_raw_evidence` for raw on demand).
- Date-range or assessment requests should use range-aware tools.
- Generated plans should cite or name the class memory they use.
- Sparse memory must be reported honestly; ask at most one targeted question.
- Direct wiki writes are explicit actions, never hidden side effects of chat.
 Durable profile/state writes go only through the teacher-approved
 `POST /classes/{id}/memory/apply` (proposals via `/memory/refresh` and
 `/memory/profile/propose`).
- Memory scope is split: global `user.md` (teacher), class `teaching_patterns.md`
 (how the class learns), class `copilot.md` (copilot working agreement); each
 page is size-budgeted.
- New teacher-facing workflows should follow the same context-loading pattern:
  load the profile layer (`teacher_profile.md` + class `copilot_profile.md`)
  when teacher/class preferences matter; build a task-specific compact context
  pack from the memory hierarchy; expose detailed canonical wiki evidence
  through tools; keep runtime/session state separate from durable memory; and
  trace each injected section with source/function/size metadata.
- Update Memory may start from a lesson timeline/detail hint, but that hint is
  resolved by the backend runtime. Known planned/taught lessons can be confirmed
  immediately; unknown hinted dates must stay unconfirmed and require target
  confirmation before the normal teacher-approved commit flow.

## AutoSci Reference

`ref_repos/AutoSci` is a local gitignored reference repo. Use it for
architectural inspiration only.

The useful learning from AutoSci is its discipline:

- clear read/write contracts
- bounded workflows
- evidence packets and citations
- proposal/action separation
- maintenance and lint patterns
- deterministic retrieval and purpose-specific context packs

Do **not** port AutoSci wholesale into this MVP. In particular, avoid adding its
graph engine, worktree fanout, multi-agent review pipeline, research-specific
schemas, or full orchestration machinery unless the product scope changes.

## Testing

Use focused tests for backend agent work:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_wiki_tools.py tests\test_wiki_search.py tests\test_api_plan.py tests\test_prompts.py tests\test_api_stream.py
```

From repo root, the broader deterministic suite is:

```powershell
.\scripts\test.ps1
```

No OpenAI calls should be needed for tests.
