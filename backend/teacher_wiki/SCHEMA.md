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

- `lesson_results.md` must be approved for `commit_ingest`.
- Unapproved proposal paths are not written.
- Student entities, student index, and timeline are updated only from approved lesson commit flows.

## Agent query flow

1. Use context pack + index excerpt in the prompt when possible.
2. `find_in_memory` — match index lesson table, then body scan.
3. `read_memory_page` — one full page when snippets are insufficient.
