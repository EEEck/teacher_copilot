# Backend Tests

Backend tests are offline and deterministic by default. They use a temporary
copy of `backend/teacher_wiki/` and a stub agent runner, so normal tests should
not call OpenAI or mutate the repo wiki.

## Fixtures

- `conftest.py` creates:
  - a temp `WikiStore`
  - `StubAgentRunner`
  - `IngestService`
  - `PlanService`
  - FastAPI dependency overrides
- `CLASS_ID` points to the seed chemistry class.

## Test Groups

- `test_api_*.py` - HTTP/session behavior and streaming.
- `test_wiki_*.py` - wiki reads, search, pathing, and context packs.
- `test_plan_context_manager.py` - planning runtime state, evidence refs,
  memory candidates, and trace behavior.
- `test_memory_*.py` - compact memory and profile/apply helpers.
- `test_prompts.py` - prompt contracts and policy text.
- `test_cli_trace.py` - local JSONL/terminal trace formatting.
- `test_live_api_plan_trace.py` - opt-in live API integration test. Skipped
  unless `RUN_LIVE_API_TESTS=1`.

## Run

From repo root:

```powershell
.\scripts\test.ps1
```

Backend only:

```powershell
cd backend
.\.venv\Scripts\python -m pytest
```

Focused agent/memory set:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_stream.py tests\test_plan_context_manager.py tests\test_wiki_context_packs.py tests\test_memory_skills.py
```

## Rules

- Keep default tests network-free and OpenAI-free.
- Use the stub runner for agent behavior expectations.
- Put live/debug scenarios behind explicit environment flags.
