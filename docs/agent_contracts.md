# Agent Contracts

This document gathers the teacher copilot agent contracts in one reviewable
place. Code remains the source of truth, but product and agent behavior changes
should be reflected here when they affect the lesson-planning or memory-update
workflow.

For file-by-file memory scope and update rules, see `memory_hierarchy.md`.

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

## Agents SDK Integration Contract

KlassenPilot uses the OpenAI Agents SDK as a code-first orchestration layer, but
the product contract stays backend-owned and teacher-reviewable.

- One SDK run is one application-level chat turn. The backend prepares the
  prompt, calls `Runner.run` or `Runner.run_streamed`, then validates the
  structured output before mutating session state.
- Agent definitions should stay focused: a workflow gets another agent only when
  it needs a materially different tool surface, output schema, model, or
  approval policy.
- `output_type` Pydantic models are contractual. Route behavior through typed
  fields and backend merge rules rather than parsing assistant prose.
- Use application-owned runtime/session state for lesson planning unless the
  session strategy is deliberately migrated. Do not mix local transcript replay
  with SDK sessions or previous-response continuation in the same conversation
  without a migration plan.
- Chat tools must remain read-only unless a new contract explicitly adds SDK
  human-review interruptions for side effects.
- If side-effecting tools are added inside an agent run, they need tool-local
  validation and human approval before execution.
- Local trace bundles remain the primary developer diagnostic surface. SDK
  traces should be correlated with `class_id`, `session_id`, workflow mode, and
  artifact version before they become a primary review tool.

## Lesson Planning Contract

Purpose:

- Help the teacher create or revise a lesson plan.
- Use class wiki memory to ground the plan in recent lessons, open loops,
  misconceptions, and prior plans.
- Support assessment or quiz drafting inside the plan markdown when requested.

Reads:

- Slim planning context slice from `build_plan_context_slim(class_id)`.
- Compact class memory from `wiki/classes/{class_id}/memory/*.md` when present.
- Class-scoped lesson memory through planning tools.
- Uploaded teacher materials supplied in the current turn.

Writes:

- Only `plan_markdown` and the runtime state objects in the structured model
  output (see Runtime Context Manager below).
- No direct wiki writes.
- Saving a plan is a separate explicit API action.

Runtime context manager:

- The chat is driven by backend-owned structured state, persisted on the
  session (`PlanRuntime`) and re-injected compactly each turn, not by replaying
  the whole transcript. The model returns `state_patch`, `last_change_summary`,
  `new_evidence_briefs`, and `memory_candidates` as part of `PlanTurnOutput`.
  The backend validates and applies the patch; missing fields mean "no change".
  Full `session_state` / `lesson_planning_state` fields are compatibility
  fallback only, not the preferred contract.
- The per-turn prompt is a slim, deduped class slice (`build_plan_context_slim`)
  + bounded `user.md`/`copilot.md` slice + rendered state + the current full
  `lessonplan.md` + compact evidence briefs. There is no blunt 14k-char clip;
  per-section budgets (`MEMORY_PAGE_BUDGETS`) bound construction size. All
  tunables are centralized in `app/context_limits.py` / `config.py` — see
  `context_management.md`.
- The verbatim conversation window is configurable (`plan_history_turns`,
  default 8). Trimming is safe because durable context lives in injected state.
  Emergency backstops default to **0** (disabled) for modern large-context models.
- Progressive exposure: tool outputs are captured behind a `raw_ref`; only
  compact briefs are injected on later turns. The model calls
  `get_raw_evidence(raw_ref)` for exact wording, provenance, or contradiction
  checks.
- State patch validation: the backend accepts only known fields, ignores invalid
  phases, appends/dedupes list updates, and never lets an empty model field wipe
  accumulated runtime state.
- `phase` is conversation/workflow state, not the save-button state. Keep the
  phase in `lesson_refinement` while the teacher is still revising, even if the
  artifact is structurally complete enough to save. Use `finalize` only when
  the teacher's intent clearly indicates the plan is accepted/finished after any
  requested final tweak. The model should infer that intent from the whole
  message and conversation, not from a keyword trigger list.
- `memory_candidates` are proposed only during chat and surfaced at save; they
  are never written from a planning turn (durable writes are a separate
  teacher-approved action — see Memory Review/Apply Contract).
- After a successful plan save, the UI should call the profile proposal flow
  with the final `lessonplan.md`, `session_state`, `lesson_planning_state`, and
  accumulated `memory_candidates`. The returned `user.md` / `copilot.md`
  proposals are reviewable suggestions only.

Allowed tools:

- `list_lessons(start_date?, end_date?, topic?, max_results?)`
- `read_lesson(lesson_date)`
- `read_lesson_range(start_date, end_date, topic?, max_lessons?)`
- `search_memory(query, max_results?)`
- `read_memory_page(path)`
- `get_raw_evidence(raw_ref)`

Browsing policy:

- Use the compact planning pack first for orientation. It gives current unit,
  recent lesson titles, misconception priorities, planning brief, and teaching
  patterns.
- Browse when the teacher request depends on class evidence that is not already
  explicit in the compact slice: multi-lesson history, older topics, date
  ranges, review/assessment coverage, exact prior lesson details, or
  source-backed claims about what students found confusing.
- Choose tools by information need, not keyword matching:
  - sequence map before detail -> `list_lessons`
  - multi-lesson evidence -> `read_lesson_range`
  - one known date -> `read_lesson`
  - broad topic/pathfinding -> `search_memory`
  - exact compact/roll-up wording -> `read_memory_page`
  - exact captured tool output -> `get_raw_evidence`
- Treat `search_memory` as a ranked pathfinder. Use returned `kind`, `title`,
  `score`, `matched_terms`, `source`, and `snippet` to decide whether to drill
  into a lesson, compact memory page, or roll-up.
- Do not add brittle prompt trigger lists for every phrasing a teacher might
  use. If a tool-selection failure recurs, first improve tool names,
  descriptions, parameters, output shape, or add a higher-level tool that
  matches the teacher task.

Output contract:

- Return a conversational `reply`.
- Return updated `plan_markdown`.
- Preserve manual edits from the current draft when possible.
- `ready_to_save` is deterministic backend saveability, currently based on the
  markdown artifact passing structural checks. It is not inferred from assistant
  wording and does not mean the teacher is done.
- A saveable draft may be `ready_to_save` while the session remains in
  `lesson_refinement`. The UI save action is separate from the model's workflow
  phase.
- Use lightweight inline citations or source mentions, such as "based on the
  2026-05-29 lesson notes."
- Do not include debug-only evidence sections such as `## Evidence briefs` in
  teacher-facing `plan_markdown`. Evidence briefs belong in runtime state and
  trace diagnostics; the artifact should cite sources naturally.
- If memory is sparse, state what was found and ask one targeted question rather
  than fabricating coverage.

Tool-interface contract:

- Tool descriptions are part of the model-facing interface. They should explain
  what the tool does, when to use it, what inputs mean, and what the output
  represents.
- Tool output should be structured enough that the model can cite and summarize
  without guessing: source paths, dates/ranges, warnings, summaries, and raw
  refs where applicable.
- Prefer a higher-level tool when a natural teacher request repeatedly requires
  the same low-level call sequence. Candidate: `retrieve_lesson_history(topic,
  count, purpose)` returning lesson sequence, recurring confusions, compact
  citations, and raw refs.

## Memory Update Contract

Purpose:

- Help the teacher turn a free-form update-memory conversation into structured
  lesson results.
- Support three MVP intents in one agent: log a new lesson, add missing results
  for a planned/older lesson, and correct existing lesson observations.
- Preserve the teacher's intent and avoid inventing events that were not stated.

Reads:

- Slim ingest context slice from `build_ingest_context_slim(class_id)`.
- Compact class memory from `wiki/classes/{class_id}/memory/*.md` when present.
- Class-scoped lesson/memory evidence through update-memory tools.
- Uploaded teacher materials supplied in the current turn.

Writes:

- Only `diary_markdown` and backend-owned `MemoryRuntime` state during chat.
- Wiki updates happen only after teacher approval through the commit flow.
- Commit/revise may update student pages, `students.md`, and the other class
  roll-ups for the affected lesson.

Runtime context manager:

- The chat is driven by backend-owned `MemoryRuntime` persisted on
  `ArtifactSession.runtime`.
- The model returns `state_patch`, `new_evidence_briefs`,
  `last_change_summary`, and optional `unsupported_intent_reason` as part of
  `IngestTurnOutput`. The backend validates and merges the patch; missing fields
  mean "no change".
- Runtime state tracks target/date identification (`target`), conversation
  phase (`identify_target`, `collect_results`, `review_draft`, `unsupported`),
  lesson-result categories, compact evidence briefs, raw evidence refs, and a
  diary version counter.
- Runtime state is returned to clients as `memory_state` on ingest session/chat,
  draft/propose responses, and streamed final events. It is diagnostic/workflow
  state, not durable memory.

Allowed behavior:

- Ask at most one clarifying question when important diary sections are missing.
- The general **Update memory** entry point starts free-agent target discovery.
  A future timeline/detail button may start the same agent with a date hint, but
  the backend still validates the target through the same runtime state.
- The agent may draft from strong evidence before final confirmation, but it
  should keep target confidence explicit in `state_patch` and conversationally
  confirm ambiguous dates/lessons with the teacher.
- Use pseudonymous student IDs only.
- Do not infer sensitive facts beyond what the teacher said.
- Never write wiki files directly from the chat turn.
- The live ingest prompt must include each high-signal source at most once
  (previous lesson, roster excerpt, course state, open loops, misconceptions,
  compact memory, logging conventions). Do not stack index + base context +
  ingest query pack into the chat prompt.
- If the teacher asks for a future memory task outside lesson-results
  logging/correction, set `unsupported_intent_reason` and explain the supported
  scope briefly.

Allowed tools:

- `list_memory_targets(start_date?, end_date?, topic?, status?, max_results?)`
- `read_memory_target(lesson_date)`
- `search_memory(query, max_results?)`
- `read_memory_page(path)`
- `get_raw_evidence(raw_ref)`

Browsing policy:

- Use the compact ingest pack first for normal same-day logging.
- Use `list_memory_targets` when the target is vague ("today", "last class",
  "the planned lesson", "that acids lesson") or when the teacher wants to fill
  older missing results.
- Use `read_memory_target` before correcting an existing lesson or filling
  results for a planned lesson.
- Capture and summarize useful tool results into `new_evidence_briefs`; fetch
  raw refs only for exact wording, provenance, or contradiction checks.

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

Allowed compact pages (each has a hard size budget in `MEMORY_PAGE_BUDGETS`,
enforced at write AND inject time via `clamp_memory_page`):

- `taught_so_far.md`
- `planning_brief.md`
- `teaching_patterns.md` — class + subject TEACHING STYLE: how this class learns
  and which approaches work/fail (holds the class learning profile).
- `copilot_profile.md` (`copilot.md`) — class-scoped COPILOT WORKING AGREEMENT
  only: planning patterns, avoid-rules, repeated corrections, agent behavior.
- `class_state.md` — derived current-state snapshot for the class.
- `session_summaries.md`

Plus one global, cross-class page:

- `wiki/teacher_profile.md` (`user.md`) — agent-maintained global teacher
  profile: communication style, stable preferences, default lesson structure.
  Bounded by `add_user_profile_conclusion`.

Scope discipline (no cross-contamination):

- Global teacher preferences → `user.md`. Class learning profile →
  `teaching_patterns.md`. Copilot working agreement → `copilot.md`.
- Dedupe and REPLACE stale facts rather than appending; report stale/conflicting
  facts in the compaction `stale_report`.

Honcho-style profile rules:

- Store stable, reusable teacher/class/copilot facts, not raw session logs.
- Treat teacher corrections and explicit preferences as highest-priority
  profile memory.
- Keep student-specific sensitive details out of broad profile memory; use
  pseudonymous student pages for individual continuity.
- LLM synthesis may propose compact content, but backend code controls allowed
  paths, scope, and persistence.

## Memory Review / Apply Contract

Purpose:

- Promote durable memory only with explicit teacher approval (HITL); planning
  chat and ingest chat never write profile/state pages.

Proposal (read-only, no writes):

- `POST /classes/{id}/memory/refresh` proposes refreshed derived pages
  (`taught_so_far`, `planning_brief`, `teaching_patterns`, `copilot_profile`,
  `class_state`) plus a `stale_report`. It does not write.
- `POST /classes/{id}/memory/profile/propose` proposes `user.md` / `copilot.md`
  updates from a finished session, labeling each candidate `explicit` vs
  `inferred` with a confidence. It does not write.
- Plan save returns the compact planning-state snapshot needed to call
  `/memory/profile/propose`; profile learning is best-effort after the lesson
  plan has already been saved.

Apply (the only durable-write path for these pages):

- `POST /classes/{id}/memory/apply` writes only the teacher-approved items via
  the bounded helpers (`add_user_profile_conclusion`, `add_profile_conclusion`,
  `commit_memory_compaction` for `class_state`). Unsupported targets (e.g.
  `canonical_wiki`) are skipped, not written.
- `POST /classes/{id}/memory/compact` remains the full derived-page rebuild and
  now also writes `class_state`, each page clamped to budget.

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

## Debug Trace Contract

Purpose:

- Make agent behavior reviewable during development without guessing what was
  loaded or remembered.

Plan trace endpoint:

- `GET /classes/{id}/plan/sessions/{session_id}/trace` returns a read-only
  debug bundle for the in-memory planning session.
- The bundle includes prompt stack sections, current `lessonplan.md`, compact
  runtime state, recent messages, captured streamed events, evidence briefs, and
  raw evidence refs.
- The bundle also includes `prompt_assembly`: a source -> function -> rendered
  text breakdown of what was fed into the model, plus per-turn
  `prompt_assembly` events in `event_trace`.
- The event trace is high-signal: tool calls/results, final metadata, and errors.
  It intentionally excludes per-token reasoning deltas so tool behavior remains
  inspectable.
- The trace is diagnostic only. It must not write wiki memory, profile pages, or
  session summaries.
- Trace output may contain teacher/session content and raw tool evidence; treat
  it as local developer data, not durable product memory.

## Deferred Contracts

These are intentionally not part of the MVP contract:

- Dedicated evidence metadata in the API.
- Source panel in the frontend.
- AutoSci-style graph or edge schema.
- Multi-agent review pass.
- Full wiki health-check/lint workflow.
- Vector database or embedding index as the default class-memory retrieval path.
- Raw-source fallback as standard planner behavior.
