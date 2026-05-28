# KlassenPilot AGENTS.md — Wiki Schema

## Structure

- `raw/classes/{class_id}/` — immutable lesson diaries after teacher approval
- `wiki/classes/{class_id}/lessons/{YYYY-MM-DD}/` — per-date `lesson_results.md` and `lesson_plan.md`
- `wiki/classes/{class_id}/` — roll-ups: course_state, student_notes, misconceptions, open_loops

## Lesson results sections (required)

1. What was covered
2. Student participation
3. What went well
4. What didn't go well
5. Student observations (pseudonyms S-### only)
6. Homework & follow-ups

## Workflows

- **Ingest:** chat → propose diary MD + wiki updates → teacher HITL approve → commit
- **Query:** read index.md first, then class wiki, then plan/generate
- **Never** write wiki without teacher approval
