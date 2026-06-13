# Backend Services

Services contain product workflow orchestration between HTTP routes, agents, and
wiki storage.

## Files

- `artifact_session_service.py` - generic artifact-session lifecycle:
  in-memory sessions, messages, current markdown artifact, readiness/status,
  streaming finalization, and optional mode-specific runtime hooks.
- `artifact_spec.py` - per-mode policy for artifact sessions. Ingest and plan
  define their templates, readiness checks, turn runners, optional openings,
  and mode-specific runtime/trace hooks here.
- `ingest_service.py` - memory-update adapter around the artifact session core,
  plus propose/commit behavior for lesson diaries.
- `plan_service.py` - lesson-planning adapter around the artifact session core,
  plus plan save and trace response assembly.
- `memory_apply.py` - teacher-approved durable memory apply dispatcher.

## Mental Model

- `ArtifactSessionService` is the lifecycle core.
- `ArtifactSpec` is the mode policy.
- `IngestService` and `PlanService` are API-facing adapters.
- Durable wiki mutations are explicit service methods, not side effects of chat.

## Maintenance Notes

- If a future artifact type is added, prefer a new `ArtifactSpec` and a thin
  service adapter before forking the session lifecycle.
- Keep plan-specific runtime concepts behind spec/service hooks so the artifact
  core stays reusable.
- Keep tests offline with the stub agent in `backend/tests/conftest.py`.

## Related Docs

- `../teacher_agent/README.md`
- `../../tests/README.md`
- `../../../docs/agent_architecture.md`
