# Backend Services

Services contain product workflow orchestration between HTTP routes, agents, and
wiki storage.

## Files

- `artifact_session_service.py` - generic artifact-session lifecycle:
  in-memory sessions, messages, current markdown artifact, readiness/status,
  streaming finalization, and optional mode-specific runtime hooks.
- `artifact_spec.py` - per-mode policy for artifact sessions. Ingest and plan
  define their templates, readiness checks, turn runners, optional openings,
  mode-specific runtime/trace hooks, streaming adapters, final-event adapters,
  and workflow trace contracts here.
- `stream_safety.py` - production stream display policy for teacher-visible
  SSE events. Development mode keeps raw diagnostics; production strips raw
  reasoning text, tool arguments, and tool outputs before emission.
- `ingest_service.py` - memory-update adapter around the artifact session core,
  start-hint resolution for timeline/detail entry points, and propose/commit
  behavior for lesson diaries.
- `memory_candidate_ledger.py` - SQLite-backed durable memory candidate ledger
  for cross-session Memory Sweep evidence, grouping, and status transitions.
- `memory_gate.py` - promotion gate and silent decay for ledger candidates.
- `memory_sweep.py` - V3 single-call Memory Sweep consolidation: builds the
  gate-passing claim packet, validates ID-referenced operations structurally,
  and assembles teacher-reviewable cards.
- `memory_skills.py` - typed memory write/read service contract for curated
  memory apply paths.
- `plan_service.py` - lesson-planning adapter around the artifact session core,
  plus plan save and trace response assembly.
- `memory_apply.py` - teacher-approved durable memory apply dispatcher,
  including exact `adjust` replacement support for Memory Sweep cards.

## Mental Model

- `ArtifactSessionService` is the lifecycle core.
- `ArtifactSpec` is the mode policy.
- Streaming dispatch and final-event normalization go through `ArtifactSpec`;
  the shared session service should not branch on concrete modes such as
  `plan` or `ingest`.
- `IngestService` and `PlanService` are API-facing adapters.
- Durable wiki mutations are explicit service methods, not side effects of chat.
- Memory Sweep treats the candidate ledger as raw evidence. Folding and the
  promotion gate decide what reaches review; one high-reasoning consolidation
  call proposes operations; only teacher-approved decisions write durable wiki
  memory.
- Update Memory start hints are resolved before the agent turn. Known planned
  or taught lessons can be confirmed and moved to `collect_results`; unknown
  hinted dates must stay in `identify_target` with `needs_confirmation=true`.
- Services should call public `WikiStore` facade methods. If service code needs
  parsing helpers, expose them on the facade instead of reaching into private
  `_extract_*` methods.

## Maintenance Notes

- If a future artifact type is added, prefer a new `ArtifactSpec` and a thin
  service adapter before forking the session lifecycle.
- Keep workflow-specific runtime concepts behind spec/service hooks so the
  artifact core stays reusable.
- Prefer small helper functions or strategy objects over inheritance when
  reducing plan/ingest duplication. The current abstraction is `ArtifactSpec`
  plus thin service adapters.
- Keep tests offline with the stub agent in `backend/tests/conftest.py`.

## Related Docs

- `../teacher_agent/README.md`
- `../../tests/README.md`
- `../../../docs/agent_architecture.md`
- `../../../docs/mem_v3/README.md`
