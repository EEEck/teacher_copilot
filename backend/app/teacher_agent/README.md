# Teacher Agent Package

This package owns the model-facing behavior for KlassenPilot. It builds prompts,
tools, structured outputs, streaming translations, planning runtime state, and
prompt trace diagnostics.

## Files

- `agent.py` - OpenAI Agents SDK agent definitions and prompt assembly.
- `agents.py` - `AgentRunner`: async run/stream loops, model settings,
  turn-limit handling, and high-level agent methods used by services.
- `prompts.py` - system prompts and policy blocks.
- `models.py` - structured output models returned by agents.
- `tools.py` - class-scoped wiki read tools for agent use.
- `planning_state.py` - backend-owned planning runtime state, state patches,
  evidence briefs, raw evidence refs, and memory candidates.
- `prompt_trace.py` - diagnostic prompt assembly snapshots for plan sessions.
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

## Boundaries

- Tools are read-only during chat.
- Planning raw tool outputs are stored behind raw refs and summarized into
  compact evidence briefs.
- Prompt trace output is diagnostic and may contain sensitive local session
  data; keep it gated at the API boundary.
- Artifact workflows should build prompt/context through shared assembly helpers
  first, then use the same assembly for local debug bundles and live model
  calls. Future one-shot helper agents should adopt the same pattern when the
  v1.2 debug generalization is implemented.
- If agent behavior changes, update `../../../docs/agent_contracts.md`.

## Related Docs

- `wiki/README.md`
- `../../../docs/agent_architecture.md`
- `../../../docs/memory_hierarchy.md`
- `../../../docs/context_management.md`
