# Backend API Layer

This folder exposes the HTTP surface for the frontend and local debug scripts.
Routes should be thin adapters over services and wiki facades.

## Files

- `routes.py` - all current `/api` endpoints.
- `deps.py` - FastAPI dependency factories for settings, wiki store, agents,
  ingest service, and plan service.
- `errors.py` - standard error envelope and exception handlers.

## Route Groups

- Health/classes/timeline/wiki reads.
- Ingest sessions: start, optional typed start hint, chat, stream, draft,
  propose, commit.
- Plan sessions: start, chat, stream, draft, save, trace.
- Memory maintenance: compact, refresh, profile propose, apply.

## Conventions

- Validate class/session scope before service calls that mutate or expose
  session data.
- Convert expected `KeyError`/`ValueError` cases into HTTP errors near the
  route boundary.
- Keep public request fields typed when they encode workflow state. For example,
  `IngestSessionStartRequest` uses literal values for `intent`, `target_kind`,
  and `source`; invalid hint values should fail validation instead of being
  normalized later.
- Do not add hidden writes to chat routes. Durable memory writes belong to
  explicit commit/apply endpoints.
- Debug endpoints that expose prompts, raw tool output, or messages should be
  gated by settings.

## Related Docs

- `../services/README.md`
- `../../README.md`
- `../../../docs/agent_contracts.md`
