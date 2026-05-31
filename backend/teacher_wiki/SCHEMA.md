# Teacher wiki schema (prototype)

Karpathy-style layers under `teacher_wiki/`:

| Layer | Path pattern | Notes |
|-------|----------------|-------|
| Index | `index.md` | Catalog; rebuilt on commit. Read first when searching. |
| Log | `log.md` | Append-only commit audit trail. |
| Class wiki | `wiki/classes/{class_id}/` | Approved lesson results, roll-ups, students, timeline. |
| Raw | `raw/classes/{class_id}/` | Immutable diary snapshot at commit time. |

## Lesson diary sections

Each ingest diary uses these `##` headings (see `DIARY_SECTION_HEADINGS` in code):

- What was covered
- Student participation
- What went well
- What didn't go well
- Student observations (`S-###` student ids)
- Homework & follow-ups

## Commit rules

### Ingest (`commit_ingest`)

- `compile_from_diary` proposes every path that may change: `lesson_results.md`, roll-ups, `students/S-###.md`, `student_notes.md`, `timeline.md`, and `raw/classes/...`.
- The teacher approves per file in the UI; only rows with `approved: true` are written.
- `lesson_results.md` must be approved or commit returns 400.
- Unapproved paths are never written (no hidden finalize step).

### Lesson revise (`revise_lesson` API)

- Separate from ingest HITL: the teacher edits an existing lesson diary and calls the revise endpoint.
- Deterministically re-applies lesson results, roll-ups, student entities, student index, and timeline in one shot (no per-file checkboxes).
- Use ingest when logging a new lesson; use revise when correcting an already-committed lesson.

## Agent query flow

1. Use context pack + index excerpt in the prompt when possible.
2. `find_in_memory` — match index lesson table, then body scan.
3. `read_memory_page` — one full page when snippets are insufficient.
