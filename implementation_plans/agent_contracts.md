# Agent Contracts

This document gathers the teacher copilot agent contracts in one reviewable
place. Code remains the source of truth, but product and agent behavior changes
should be reflected here when they affect the lesson-planning or memory-update
workflow.

## Contract Principles

- Keep workflows bounded and explicit.
- Prefer compiled wiki memory over raw sources.
- Separate read-only reasoning from write/update actions.
- Browse only when the base context is insufficient.
- Cite or name the memory used when it affects a plan.
- Report sparse or missing memory honestly.
- Ask at most one targeted question when blocked.
- Never silently mutate wiki files from a planning turn.

## Lesson Planning Contract

Purpose:

- Help the teacher create or revise a lesson plan.
- Use class wiki memory to ground the plan in recent lessons, open loops,
  misconceptions, and prior plans.
- Support assessment or quiz drafting inside the plan markdown when requested.

Reads:

- Base planning context pack from `load_index_context + build_plan_context`.
- Class-scoped lesson memory through planning tools.
- Uploaded teacher materials supplied in the current turn.

Writes:

- Only `plan_markdown` in the structured model output.
- No direct wiki writes.
- Saving a plan is a separate explicit API action.

Allowed tools:

- `list_lessons(start_date?, end_date?, topic?, max_results?)`
- `read_lesson(lesson_date)`
- `read_lesson_range(start_date, end_date, topic?, max_lessons?)`
- `search_memory(query, max_results?)`
- `read_memory_page(path)`

Browsing policy:

- Do not browse when the base planning pack fully covers a normal next-lesson
  request.
- Browse when the teacher asks for older lessons, a date range, a topic outside
  the visible pack, or a test/quiz spanning prior weeks.
- For range requests, prefer `list_lessons` first and `read_lesson_range` when
  details are needed.
- For a single known date, use `read_lesson`.
- For topic lookup, use `search_memory`, then `read_memory_page` only when the
  snippet is not enough.

Output contract:

- Return a conversational `reply`.
- Return updated `plan_markdown`.
- Preserve manual edits from the current draft when possible.
- Use lightweight inline citations or source mentions, such as "based on the
  2026-05-29 lesson notes."
- If memory is sparse, state what was found and ask one targeted question rather
  than fabricating coverage.

## Memory Update Contract

Purpose:

- Help the teacher turn a lesson conversation into structured lesson results.
- Preserve the teacher's intent and avoid inventing events that were not stated.

Reads:

- Base ingest context pack from `load_index_context + build_ingest_context`.
- Class-scoped memory only for continuity when needed.
- Uploaded teacher materials supplied in the current turn.

Writes:

- Only `diary_markdown` in the structured model output during chat.
- Wiki updates happen only after teacher approval through the commit flow.

Allowed behavior:

- Ask at most one clarifying question when important diary sections are missing.
- Use pseudonymous student IDs only.
- Do not infer sensitive facts beyond what the teacher said.
- Never write wiki files directly from the chat turn.

## Tool Result Contract

Planning tool results should be compact, class-scoped, and easy for the model to
use. They should prefer structured JSON with:

- `date` or `range`
- `title`
- `summary` or compact excerpt
- `source_paths`
- `warnings` when memory is missing, sparse, truncated, or invalid

Tool outputs should not expose files outside `wiki/classes/{class_id}/` through
planning reads.

## Backend Safety Contract

- Plan stream final results must be request-local, not stored on shared runner
  state.
- Plan save must validate `lesson_date` as an ISO date before using it in paths.
- `WikiStore` facade defaults should match underlying wiki helper defaults.
- Broader ingest hardening is deferred unless the ingest flow is being changed.

## Deferred Contracts

These are intentionally not part of the MVP contract:

- Dedicated evidence metadata in the API.
- Source panel in the frontend.
- AutoSci-style graph or edge schema.
- Multi-agent review pass.
- Full wiki health-check/lint workflow.
- Raw-source fallback as standard planner behavior.
