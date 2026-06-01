# Agent Contracts

This document gathers the teacher copilot agent contracts in one reviewable
place. Code remains the source of truth, but product and agent behavior changes
should be reflected here when they affect the lesson-planning or memory-update
workflow.

## Contract Principles

- Keep workflows bounded and explicit.
- Prefer compiled wiki memory over raw sources.
- Prefer compact class memory and workflow context packages before broader wiki
  browsing.
- Use deterministic, source-bearing retrieval as the pathfinder for large wiki
  browsing; do not default to opaque vector recall.
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

- Base planning context package from `build_context_package(class_id, "plan")`.
- Compact class memory from `wiki/classes/{class_id}/memory/*.md` when present.
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
- Treat `search_memory` as a ranked pathfinder. Use returned `kind`, `title`,
  `score`, `matched_terms`, `source`, and `snippet` to decide whether to drill
  into a lesson, compact memory page, or roll-up.

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

- Base ingest context package from `build_context_package(class_id, "ingest")`.
- Compact class memory from `wiki/classes/{class_id}/memory/*.md` when present.
- Class-scoped memory only for continuity when needed.
- Uploaded teacher materials supplied in the current turn.

Writes:

- Only `diary_markdown` in the structured model output during chat.
- Wiki updates happen only after teacher approval through the commit flow.
- Commit/revise may update student pages, `students.md`, and the other class
  roll-ups for the affected lesson.

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

`search_memory` should return source-bearing ranked results with:

- `path`
- `kind`
- `title`
- `snippet`
- `score`
- `matched_terms`
- `source`

The ranking should prefer compiled class wiki pages over raw sources. Compact
memory, lesson titles, index rows, and roll-up headings are high-signal
pathfinders; full page bodies are secondary evidence.

## Compact Memory Contract

Purpose:

- Maintain small derived class memory pages for fast, personalized workflow
  context.
- Capture stable teaching patterns, current planning priorities, what has been
  taught so far, and Honcho-style teacher/class copilot profile facts.

Reads:

- Approved wiki memory only: lesson results, saved plans, roll-ups, subject
  guide, and existing compact memory.

Writes:

- Only explicit compact actions may write compact memory pages.
- Compact writes are restricted to `wiki/classes/{class_id}/memory/*.md`.
- Compact writes append a `compact` log entry and rebuild the wiki index.
- Planning and ingest chat must not silently compact or write these pages.

Allowed compact pages:

- `taught_so_far.md`
- `planning_brief.md`
- `teaching_patterns.md`
- `copilot_profile.md`
- `session_summaries.md`

Honcho-style profile rules:

- Store stable, reusable teacher/class/copilot facts, not raw session logs.
- Treat teacher corrections and explicit preferences as highest-priority
  profile memory.
- Keep student-specific sensitive details out of broad profile memory; use
  pseudonymous student pages for individual continuity.
- LLM synthesis may propose compact content, but backend code controls allowed
  paths, scope, and persistence.

## Query Pack Contract

Purpose:

- Provide AutoSci-style, read-only orientation packs that help the model browse
  larger class memory without loading the full wiki.

Allowed query packs:

- `planning_query_pack`: recent taught sequence, misconception priorities,
  planning brief, teaching patterns, and open loops.
- `ingest_query_pack`: previous lesson, student roster excerpt, logging
  conventions, compact class memory, and open loops.
- `review_query_pack`: taught-so-far sequence, recurring misconceptions, and
  unresolved issues for review or assessment synthesis.

Rules:

- Query packs are derived at read time and do not write wiki files.
- Query packs can quote compact memory and roll-ups, but canonical lesson
  records remain the source of truth.
- If a query pack is sparse, say so rather than inventing a pattern.

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
- Vector database or embedding index as the default class-memory retrieval path.
- Raw-source fallback as standard planner behavior.
