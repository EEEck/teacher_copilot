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
- `runtime_render.py` - shared compact render helpers for workflow session
  state and evidence briefs.
- `workflow_contract.py` - minimal spec-level contract for artifact chat
  workflows.
- `prompt_assembly.py` - shared live-call and diagnostic prompt/context assembly.
- `prompt_trace.py` - compatibility wrapper for plan-session prompt diagnostics.
- `stream_events.py` - internal SSE event models and SDK event translation.
- `wiki/` - markdown wiki implementation modules.
- `wiki_store.py` - compatibility/facade import path for `WikiStore`.

## Agent Workflows

- Ingest chat updates only `diary_markdown`; curated wiki writes happen later
  through teacher-approved commit.
- Plan chat updates only `plan_markdown` plus in-memory planning runtime state;
  wiki/profile writes happen through separate save/apply flows.
- Memory compaction/profile proposal agents propose bounded updates; backend
  code validates scope and persistence.
- Memory Sweep uses two isolated agents: alignment normalizes raw ledger rows
  into durable claim groups, then card generation turns validated groups into
  teacher-reviewable proposals.

## Boundaries

- Tools are read-only during chat.
- Memory Sweep agents never write memory. They return structured alignment/card
  outputs; backend validators own coverage, target consistency, operation
  mapping, and exact replacement checks.
- Planning and Update Memory raw tool outputs are stored behind raw refs and
  summarized into compact evidence briefs.
- Update Memory has one free-agent runtime. Timeline/detail entry points may
  seed it with a typed hint, but unknown dates remain unconfirmed until the
  teacher or agent resolves the target.
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
- `../../../docs/mem_v2/backend.md`
