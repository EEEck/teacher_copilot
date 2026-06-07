# Backend App Package

FastAPI application code lives here. The backend is intentionally split into
thin HTTP routes, service adapters, agent runtime code, and wiki storage helpers.

## Request Flow

1. `main.py` creates the FastAPI app and installs error handlers.
2. `api/routes.py` receives HTTP requests and handles status-code translation.
3. `services/` owns workflow orchestration and session state.
4. `teacher_agent/` builds and runs OpenAI Agents SDK agents.
5. `teacher_agent/wiki/` reads and writes the markdown wiki through bounded
   helper APIs.

## Folder Map

- `api/` - FastAPI routes, dependency wiring, and error envelopes.
- `schemas/` - Pydantic request/response models for the HTTP API.
- `services/` - application workflow services for ingest, planning, memory
  apply, and generic artifact sessions.
- `teacher_agent/` - prompts, tools, structured outputs, runner, planning
  runtime state, streaming events, and prompt trace helpers.
- `teacher_agent/wiki/` - wiki pathing, parsing, search, context packs,
  compaction, rollups, and store facade internals.
- `cli/` - local debug REPL and JSONL trace tooling.
- `config.py` - environment-backed settings.
- `context_limits.py` - central context-size policy.
- `openai_bootstrap.py` - OpenAI Agents SDK key setup.

## Boundaries

- Routes should stay thin. Put workflow logic in `services/`.
- Services may orchestrate sessions and call agents/wiki helpers, but direct
  wiki writes should remain explicit teacher-approved actions.
- Agent modules should not write durable wiki memory directly from chat turns.
- Wiki internals should stay class-scoped and path-safe.

## Useful Next Reads

- `services/README.md`
- `teacher_agent/README.md`
- `api/README.md`
- `../tests/README.md`
