# KlassenPilot Agent Guide

Read this first when working on the repo as an AI agent or developer. It is the
short context map for the project; detailed behavior contracts live in
`implementation_plans/`.

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

1. `README.md` — how to run the app and overall architecture.
2. `implementation_plans/agent_contracts.md` — current read/write/tool/output
   contracts for the teacher agents.
3. `implementation_plans/agent_design_plan.md` — MVP design rationale and
   AutoSci/Karpathy learnings.
4. `implementation_plans/product_backlog.md` — versioned product backlog (v1.1-v1.3);
   v1.3 memo covers proactive briefing / suggested tasks on landing.
5. `backend/teacher_wiki/AGENTS.md` — wiki schema and wiki-specific workflow
   rules when touching memory behavior.

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
- API schemas: `backend/app/schemas/api.py`
- Wiki store facade: `backend/app/teacher_agent/wiki/store.py`
- Wiki package internals: `backend/app/teacher_agent/wiki/`
- Seed/dev wiki: `backend/teacher_wiki/`
- Backend tests: `backend/tests/`
- Frontend app: `frontend/`

## Agent Contracts

Treat `implementation_plans/agent_contracts.md` as the reviewable behavior
contract. If agent behavior changes, update that file in the same change as the
code or explain why it does not apply.

Important current contracts:

- Lesson planning starts from the base context pack.
- The planner browses class memory only when the teacher request exceeds that
  base pack.
- Date-range or assessment requests should use range-aware tools.
- Generated plans should cite or name the class memory they use.
- Sparse memory must be reported honestly; ask at most one targeted question.
- Direct wiki writes are explicit actions, never hidden side effects of chat.

## AutoSci Reference

`ref_repos/AutoSci` is a local gitignored reference repo. Use it for
architectural inspiration only.

The useful learning from AutoSci is its discipline:

- clear read/write contracts
- bounded workflows
- evidence packets and citations
- proposal/action separation
- maintenance and lint patterns

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
