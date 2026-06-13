# Update Memory Free-Agent Rollout

Goal: make Update Memory feel like one free-agent copilot that can identify the
lesson target, load the right context, and help the teacher produce reviewed
lesson results, while keeping all durable wiki writes teacher-approved.

## Phase 1 - Runtime Contract (done)

- Add backend-owned `MemoryRuntime` on `ArtifactSession.runtime`.
- Extend `IngestTurnOutput` with `state_patch`, `new_evidence_briefs`,
  `last_change_summary`, and `unsupported_intent_reason`.
- Return `memory_state` through ingest session/chat/draft/propose responses and
  streamed final events.
- Keep commit semantics unchanged: chat updates only `diary_markdown`; wiki
  writes still happen only through approve/commit.

## Phase 2 - Target Discovery Tools (done)

- Give the update-memory agent a purpose-specific read-only tool surface:
  `list_memory_targets`, `read_memory_target`, `search_memory`,
  `read_memory_page`, and `get_raw_evidence`.
- Use compact ingest context first; browse only for ambiguous target dates,
  planned/older lessons, corrections, or missing evidence.
- Capture tool outputs behind raw refs and summarize useful evidence into
  runtime briefs.

## Phase 3 - Hinted Entry Points (done)

- Keep the top **Update memory** action as free-agent discovery.
- Add timeline/detail entry points that start the same agent with a date/intent
  hint, then skip most target discovery when confidence is high.
- Recommended first hint: planned-only timeline lesson -> `update_missing_results`
  with `lesson_date`, saved plan loaded, target still visible to the teacher.
- Implemented via optional `POST /classes/{id}/ingest/sessions` start hints.
  Timeline/detail links pass `lesson_date`, `lesson_title`, `intent`,
  `target_kind`, and `source=timeline_hint`.

## Phase 4 - Review/Correction UX (done)

- For existing taught lessons, support correction/revise flow with existing
  results loaded before editing.
- Surface target/date confidence and the latest change summary in the UI without
  turning the experience into a wizard.
- Keep unsupported future memory tasks conversational: explain current scope and
  set `unsupported_intent_reason`.
- Implemented by loading existing lesson results for taught-lesson correction
  hints, rendering the memory target/status strip, and keeping the existing
  review/approve commit path unchanged.

## Phase 5 - Trace/Eval Hardening

- Add an update-memory trace bundle parallel to plan trace if debugging needs it.
- Add eval/test cases for vague target, timeline hint, planned lesson results,
  correction of older observations, and unsupported future memory intents.
- Only then consider broader memory features such as memo generation or profile
  learning from update-memory sessions.
