# Teacher Agent Package

This package owns the model-facing behavior for KlassenPilot. It builds prompts,
tools, structured outputs, streaming translations, planning runtime state, and
prompt trace diagnostics.

## Files

- `agent.py` - OpenAI Agents SDK agent definitions.
- `agents.py` - `AgentRunner`: async run/stream loops, model settings,
  turn-limit handling, shared turn preparation/finalization helpers, and
  high-level agent methods used by services.
- `prompts.py` - system prompts and policy blocks.
- `models.py` - structured output models returned by agents.
- `tools.py` - class-scoped wiki read tools for agent use.
- `planning_state.py` - backend-owned planning runtime state, state patches,
  evidence briefs, raw evidence refs, and memory candidates.
- `memory_update_state.py` - backend-owned Update Memory runtime state:
  target/date, intent, phase, lesson-result category progress, evidence briefs,
  raw refs, and merge validation.
- `class_discussion_state.py` - backend-owned runtime state for the read-only
  class Discuss chat.
- `executive_verification.py` - shared `ExecutiveRuntime`: findings, severity,
  fingerprints, readiness, and the deterministic write gate.
- `roster_resolve.py` - resolve observation subjects (roster keys, aliases, and
  rapidfuzz fuzzy matches) to `S-###` ids at the write boundary; advisory
  warnings for unmappable subjects (never hard-blocks).
- `memory_capture.py` - shared durable-memory candidate capture helpers.
- `memory_targets.py` - shared target policy for durable memory candidates and
  apply routes.
- `citation_presentation.py` - deterministic presentation/validation for
  reviewed trusted-source summaries.
- `lesson_package.py` / `package_renderer.py` - structured single-source
  lesson-package contract and its deterministic Markdown renderer.
- `quality.py` - deterministic guards and rubric loaders for trusted lesson
  workflows.
- `runtime_render.py` - shared compact render helpers for workflow session
  state and evidence briefs.
- `workflow_contract.py` - minimal spec-level contract for artifact chat
  workflows.
- `prompt_assembly.py` - shared live-call and diagnostic prompt/context assembly.
- `prompt_trace.py` - compatibility wrapper for plan-session prompt diagnostics.
- `stream_events.py` - internal SSE event models and SDK event translation.
- `plan_verification.py` - revision-bound Plan verification packet/report:
  immediate deterministic provenance/timing checks plus a bounded background
  review.
- `memory_verification.py` - deterministic diary target/roster
  integrity checks used at edit, proposal, and commit boundaries.
- `wiki/` - markdown wiki implementation modules.
- `wiki_store.py` - compatibility/facade import path for `WikiStore`.

## Agent Workflows

- Ingest chat updates only `diary_markdown`; curated wiki writes happen later
  through teacher-approved commit.
- Plan chat updates only `plan_markdown` plus in-memory planning runtime state;
  wiki/profile writes happen through separate save/apply flows.
- Memory compaction/profile proposal agents propose bounded updates; backend
  code validates scope and persistence.
- Memory Sweep uses the V3/V4 path: candidate capture flows through
  `remember(...)`, ledger folding and the promotion gate provide priority
  metadata, and one high-reasoning consolidation call reviews both reinforced
  claims and held singleton evidence before returning teacher-reviewable
  operations. The model's `sweep_action` is a semantic recommendation; the
  backend keeps target ownership, write mechanics, and teacher approval
  deterministic.

## Boundaries

- Wiki tools are read-only during chat. The `remember(...)` tool only stages a
  review-only runtime candidate; it does not write a ledger row or wiki file
  directly.
- Memory Sweep never writes memory during proposal. It returns structured
  operations; backend validators own claim coverage, target consistency,
  operation mapping, and exact replacement checks.
- Planning and Update Memory raw tool outputs are stored behind raw refs and
  summarized into compact evidence briefs.
- Update Memory has one free-agent runtime. Timeline/detail entry points may
  seed it with a typed hint, but unknown dates remain unconfirmed until the
  teacher or agent resolves the target.
- `ExecutiveRuntime` is shared workflow state, separate from `PlanRuntime` and
  `MemoryRuntime`. It owns findings, severity, fingerprints, and readiness;
  workflow packs add evidence without replacing the shared lifecycle.
- Plan verification is advisory by default and never rewrites Markdown. Its
  only save blocker is a completed severe-safety hold for the exact draft.
  Update Memory integrity blocks only target-date or roster-label conflicts and
  likewise never rewrites teacher text.
- Prompt trace output is diagnostic and may contain sensitive local session
  data; keep it gated at the API boundary.
- Artifact workflows should build prompt/context through shared assembly helpers
  first, then use the same assembly for local debug bundles and live model
  calls. Future one-shot helper agents should adopt the same pattern when the
  v1.2 debug generalization is implemented.
- New teacher-facing workflows should define their memory layers up front:
  global teacher context via `build_teacher_context_trace`, active-class memory
  via `build_active_class_core_context_trace`, task-specific runtime context,
  detailed canonical evidence through tools, and trace metadata for every
  rendered section.
- If agent behavior changes, update `../../../docs/agent_contracts.md`.

## Related Docs

- `wiki/README.md`
- `../../../docs/agent_architecture.md`
- `../../../docs/memory_hierarchy.md`
- `../../../docs/context_management.md`
- `../../../docs/mem_v4/README.md`
- `../../../docs/mem_v4/evaluation.md`
