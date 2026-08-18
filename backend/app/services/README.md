# Backend Services

Services contain product workflow orchestration between HTTP routes, agents, and
wiki storage.

## Files

- `artifact_session_service.py` - generic artifact-session lifecycle:
  messages, current markdown artifact, readiness/status, streaming
  finalization, optional mode-specific runtime hooks, and open-or-resume against
  the durable workflow-draft store.
- `workflow_drafts.py` - SQLite-backed `WorkflowDraft` store under wiki
  `workflow/`: chat messages, artifact markdown, runtime JSON, revision/hash,
  and pending-turn resume metadata for Plan / Update Memory.
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
- `memory_gate.py` - occasion/reinforcement priority metadata and silent decay
  for ledger candidates. It does not hide held singleton evidence from Sweep.
- `memory_sweep.py` - V4 second-judge Memory Sweep consolidation: builds a
  bounded claim packet containing reinforced and held singleton evidence,
  validates ID-referenced operations plus target ownership structurally, and
  assembles teacher-reviewable cards.
- `memory_sweep_reviews.py` - backend-owned saved Memory Sweep review sessions
  (generate/resume, fingerprint/stale detection, edits/decisions, apply,
  discard, refresh).
- `memory_skills.py` - typed memory write/read service contract for curated
  memory apply paths.
- `plan_service.py` - lesson-planning adapter around the artifact session core,
  plus plan save, in-plan PDF material upload (OCR → scratch), and promote-on-save.
- `materials_ocr.py` / `materials_ocr_prompts.py` / `materials_ocr_packaging.py`
  - Mistral OCR 4 runtime, wiki-assembled STEM/generic annotation prompts, and
  artifact-trio packaging. `run_openai_vision_ocr_fallback` / `engine="openai_vision"`
  is a skeleton only (`NotImplementedError`); not an automatic backup.
- `materials_scratch.py` - plan-session OCR packages outside the wiki index;
  promote copies into `materials/{textbooks|personal}/` (skips debug JSON).
- `discussion_service.py` - class Discuss adapter, a thin wrapper over
  `ArtifactSessionService`.
- `class_brief_service.py` - on-demand read-only class-home executive briefing
  (recent lessons, open loops, sparse areas), cached in process with refresh.
- `output_safety.py` - deterministic safety checks for teacher-visible agent
  output (complements `stream_safety.py`).
- `sqlite_util.py` - shared SQLite connection helper (sets `busy_timeout`) used
  by every app-owned SQLite store.
- `beta.py` - invite-code beta identity, workspace provisioning, and telemetry
  storage.
- `beta_cli.py` - operator CLI for provisioning and managing invite-code beta
  testers.
- `beta_report.py` - Markdown reports over beta tester telemetry and wiki diffs.
- `memory_v4_debug_capture.py` - best-effort local beta trace bundles for MemV4
  development (gated to beta + development + explicit flag).
- `artifact_session_service.py` also coordinates the shared persisted
  `ExecutiveRuntime` lifecycle and invokes the bounded Plan/Update Memory
  verification adapters from `teacher_agent/`.
- `memory_apply.py` - teacher-approved durable memory apply dispatcher,
  including exact `adjust` replacement support for Memory Sweep cards.

## Mental Model

- `ArtifactSessionService` is the lifecycle core; `workflow_drafts` is the
  durable source of truth for active Plan/Update Memory drafts.
- `ArtifactSpec` is the mode policy.
- `ExecutiveRuntime` is the shared verification lifecycle; Plan and Update
  Memory attach small packs through `ArtifactSessionService` rather than
  creating separate verifier systems.
- `memory_sweep_reviews` owns saved sweep review state the same way drafts own
  chat artifacts; the frontend never authorizes apply from a local-only cache.
- Streaming dispatch and final-event normalization go through `ArtifactSpec`;
  the shared session service should not branch on concrete modes such as
  `plan` or `ingest`.
- `IngestService` and `PlanService` are API-facing adapters.
- Durable wiki mutations are explicit service methods, not side effects of chat.
- Plan's report is revision-bound and advisory except for a completed exact-draft
  severe-safety hold. Update Memory integrity is deterministic and blocks only
  date/roster write conflicts; neither pack edits teacher Markdown.
- Memory Sweep treats the candidate ledger as raw evidence. Folding and the
  promotion gate attach priority metadata; one high-reasoning second judge
  proposes `sweep_action` plus write mechanics; only teacher-approved decisions
  write durable wiki memory.
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
- `../../../docs/mem_v4/README.md`
