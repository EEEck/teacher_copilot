# Backend API Layer

This folder exposes the HTTP surface for the frontend and local debug scripts.
Routes should be thin adapters over services and wiki facades.

## Files

- `routes.py` - all current `/api` endpoints.
- `deps.py` - FastAPI dependency factories for settings, wiki store, agents,
  ingest service, plan service, and the memory candidate ledger.
- `errors.py` - standard error envelope and exception handlers.

## Route Groups

- Health/classes/timeline/wiki reads.
- Ingest sessions: start, optional typed start hint, chat, stream, draft,
  propose, commit.
- Plan sessions: start, chat, stream, draft, save, trace.
- Memory maintenance: compact, refresh, profile propose, apply, Memory Sweep
  saved review open/patch/apply/discard, compatibility propose/apply, and
  candidate status updates.

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
- Memory Sweep UI state should go through the saved review endpoints. The
  backend review snapshot is authoritative; frontend caches are visual only.
- Sweep cards expose the second judge's semantic recommendation separately
  from the write operation: `promote`, `merge`, `already_covered`, `downgrade`,
  `reject`, or `needs_review`. Only teacher decisions sent through the saved
  review apply endpoint can change ledger status or wiki files.
- Debug endpoints that expose prompts, raw tool output, or messages should be
  gated by settings.

## Related Docs

- `../services/README.md`
- `../../README.md`
- `../../../docs/agent_contracts.md`
- `../../../docs/mem_v4/README.md`
