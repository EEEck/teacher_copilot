# Agents SDK Practices Review

This is a repo-specific review of KlassenPilot against current OpenAI Agents
SDK guidance. It is intentionally practical: preserve what is working for the
teacher MVP, and add SDK features only when they solve a concrete product or
debugging problem.

Official references used for this review:

- OpenAI Agents SDK guide:
  https://developers.openai.com/api/docs/guides/agents
- Agent definitions:
  https://developers.openai.com/api/docs/guides/agents/define-agents
- Running agents:
  https://developers.openai.com/api/docs/guides/agents/running-agents
- Tools in the Agents SDK:
  https://developers.openai.com/api/docs/guides/tools#usage-in-the-agents-sdk
- Guardrails and human review:
  https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- Integrations and observability:
  https://developers.openai.com/api/docs/guides/agents/integrations-observability
- Agent workflow evals:
  https://developers.openai.com/api/docs/guides/agent-evals

## Overall Assessment

The current KlassenPilot design is well aligned with the Agents SDK for this
MVP. The product needs one visible teacher copilot, a small set of class-scoped
tools, structured outputs, backend-owned state, and explicit approval before
durable writes. The repo mostly implements that shape already.

The strongest choices are:

- one focused planning chat agent instead of a broad multi-agent graph
- `Agent` + `Runner.run` / `Runner.run_streamed` as the model/tool loop
- `@function_tool` wrappers for deterministic wiki reads
- Pydantic `output_type` models for ingest, planning, compaction, and profile
  proposal
- backend-owned `PlanRuntime` and `MemoryRuntime` with model-proposed
  `state_patch`
- explicit separation between chat turns and durable wiki writes
- compact evidence briefs plus raw evidence refs
- local prompt/tool trace bundles for debugging

The main gaps are not urgent blockers. They are future upgrade points:

- SDK tracing should be correlated with local `class_id` / `session_id` when
  live debugging becomes frequent.
- SDK `session` / `SQLiteSession` should be considered only if in-memory
  sessions become a deployment limitation.
- SDK guardrails or tool-level approvals should be added only if side-effecting
  actions move inside the agent loop.
- Tool closures work today, but SDK run context may become cleaner if the tool
  surface grows or tools need shared authenticated dependencies.
- Live behavior should eventually graduate from ad-hoc trace inspection to a
  small repeatable eval set.

## How The Repo Maps To SDK Concepts

| SDK concept | KlassenPilot implementation | Review |
|-------------|-----------------------------|--------|
| Agent definition | `backend/app/teacher_agent/agent.py` | Good: agents are named, scoped, and typed. |
| Agent loop | `backend/app/teacher_agent/agents.py` | Good: async `Runner.run` and streamed runs are used; sync blocking is avoided. |
| Function tools | `backend/app/teacher_agent/tools.py` | Good: chat tools are read-only, class-scoped, and documented. |
| Structured outputs | `backend/app/teacher_agent/models.py` | Good: downstream code receives typed outputs instead of parsing prose. |
| App-owned state | `PlanRuntime` in `planning_state.py`; `MemoryRuntime` in `memory_update_state.py` | Good: state is validated and compactly re-injected. |
| Conversation strategy | `ArtifactSessionService` + trimmed message window | Valid: the app owns sessions and artifacts. Do not also add SDK sessions unless replacing this strategy deliberately. |
| Human approval | memory refresh/propose/apply APIs | Good: durable writes are outside chat and teacher-approved. |
| Observability | plan trace endpoint + stream event trace | Good locally; add SDK trace correlation later. |
| Evals | deterministic tests + optional live plan trace test | Good start; add focused workflow eval cases as behavior stabilizes. |

## Preserve These Design Choices

### Start With One Focused Agent

OpenAI guidance says to start with the smallest specialist that owns a clear
task, and split only when ownership, tools, approval policy, or output style
materially differ. KlassenPilot should keep one visible teacher copilot for
lesson planning and memory update. Specialist agents for compaction/profile
proposal are acceptable because they are backend workflow steps with different
outputs and write boundaries.

Do not introduce handoffs or a manager graph just because the SDK supports
them. Add another agent only when it reduces a specific prompt/tool conflict or
creates a genuinely different approval boundary.

### Keep State Ownership In The Backend

Planning and Update Memory use app-owned session state:

- `PlanRuntime` stores workflow state, lesson state, evidence briefs, raw refs,
  memory candidates, and artifact version.
- `MemoryRuntime` stores update target state, workflow-session state,
  lesson-result category progress, evidence briefs, raw refs, and diary version.
- The model proposes `state_patch`.
- Backend code validates and merges the patch.
- The prompt injects compact rendered state sections instead of replaying the
  full transcript.

This matches the SDK distinction between model-visible conversation/context and
runtime-only application state. Continue keeping teacher/class IDs, wiki root,
allowed paths, persistence, and merge rules in backend code.

### Keep Tool Schemas Product-Quality

Tool names, docstrings, parameters, and output shape are model-facing product
surface. The current planning tools pass the right test: a human could usually
choose between `list_lessons`, `read_lesson_range`, `search_memory`, and
`read_memory_page` from their descriptions alone.

When tool selection fails, first improve the tool interface or add a higher
level task-shaped tool. Avoid growing brittle prompt keyword lists.

### Keep Approval Outside Chat For Now

The SDK supports human review for sensitive tool calls, but KlassenPilot's chat
tools are read-only. Durable writes already happen through explicit API flows
after teacher review. That is simpler and safer for the MVP.

Only use SDK `needs_approval` / interruption-resume patterns if a future agent
tool itself performs a side effect inside the run, such as writing a wiki page,
sending a message, deleting data, or calling an external school system.

## Recommended Near-Term Improvements

### 1. Trace Correlation

The local trace endpoint is useful and should remain the primary developer
debug surface. For live SDK traces, add correlation once needed:

- include `class_id`, `session_id`, workflow mode, and artifact version in the
  trace/workflow name or metadata where the SDK supports it
- keep sensitive trace payload settings conservative for teacher data
- retain the local trace bundle because it shows repo-specific prompt assembly
  and raw evidence refs better than a generic trace alone

### 2. Session Persistence Decision

The SDK docs recommend choosing one conversation strategy. KlassenPilot has
chosen application-owned sessions. Keep that until there is a real deployment
need for multi-worker or restart-resilient chat history.

If the prototype outgrows RAM sessions, evaluate:

- persisting `ArtifactSession` + `PlanRuntime` in SQLite or another app store
- using SDK `SQLiteSession` only if the SDK-managed conversation history should
  replace local replay for that workflow
- avoiding a mixed strategy that sends both local replay and SDK-managed history
  for the same conversation

### 3. Workflow Spec Discipline

Artifact workflows should register their runtime factory, prompt trace hook,
streaming adapter, final-event adapter, and trace contract on `ArtifactSpec`.
The shared session service may dispatch through the registered spec; it should
not grow workflow-name branches for streaming or finalization.

### 4. Guardrail Placement

Current safety relies on scoped tools, Pydantic outputs, backend validation, and
teacher approval. That is appropriate for read-only chat tools.

Add SDK guardrails when the risk changes:

- input guardrails for requests that should be blocked before the main model
  runs
- output guardrails for redaction or safety validation before returning to the
  UI
- tool guardrails next to any tool that touches files, external systems, or
  sensitive student data

### 5. Eval Ladder

Keep deterministic tests for contracts and local behavior. Add live/eval layers
in this order:

1. deterministic tests for prompt assembly, tool schemas, merge behavior, and
   wiki path safety
2. opt-in live trace scenario tests for high-value planning regressions
3. a small JSONL case set covering tool choice, sparse memory, date ranges,
   no-write boundaries, and final plan quality
4. trace grading once SDK traces are correlated and representative

## Do Not Do Yet

- Do not add `SandboxAgent`; the teacher workflows do not need model-controlled
  shell/file execution.
- Do not add handoffs for normal lesson planning; one visible copilot is easier
  to audit and matches product scope.
- Do not add vector retrieval before deterministic wiki retrieval shows
  measurable failures.
- Do not put durable writes inside normal chat turns.
- Do not mix SDK sessions, previous response IDs, and local replay in the same
  conversation without a migration plan.

