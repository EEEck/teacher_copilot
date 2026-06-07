# API Schemas

Pydantic models for the HTTP API live in `api.py`.

## Conventions

- Keep schemas transport-focused. Workflow behavior belongs in services.
- Add fields with safe defaults when possible to preserve frontend compatibility.
- If a response shape changes, update `frontend/src/lib/api.ts` and relevant
  frontend components in the same PR.

## Related Docs

- `../api/README.md`
- `../services/README.md`
