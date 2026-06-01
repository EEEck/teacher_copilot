# KlassenPilot AGENTS.md — LLM Wiki Schema

This file is the wiki-specific schema and workflow contract for
`backend/teacher_wiki/`. For full repo onboarding and agent development context,
read [`../../AGENTS.md`](../../AGENTS.md) first. For current behavior contracts,
read [`../../implementation_plans/agent_contracts.md`](../../implementation_plans/agent_contracts.md).

## Three layers

1. **Raw** — `raw/classes/{class_id}/{YYYY-MM-DD}-{slug}.md` — immutable approved diaries. Never edit after commit.
2. **Curated wiki** — `wiki/classes/{class_id}/` — structured pages maintained by the agent (with teacher HITL on ingest).
3. **Navigation** — `index.md` (catalog), `log.md` (append-only changelog).

## Directory layout

```text
wiki/classes/{class_id}/
  class_config.md
  course_state.md
  misconceptions.md
  open_loops.md
  students.md           # class student index / roster
  timeline.md           # chronological narrative with links to lessons
  students/S-###.md     # entity pages (compounding observations)
  lessons/{YYYY-MM-DD}/
    lesson_results.md
    lesson_plan.md
```

## Lesson results sections (required)

1. What was covered
2. Student participation
3. What went well
4. What didn't go well
5. Student observations (pseudonyms `S-###` only — never real names)
6. Homework & follow-ups

## Linking

- Link lessons: `[title](lessons/2026-09-21/lesson_results.md)`
- Link students: `[S-014](students/S-014.md)`
- Link raw: relative path from lesson header `> Raw: [...]`

## Workflows

### Ingest

1. Read `index.md` first, then relevant class pages via tools.
2. Chat → update diary draft → `compile_from_diary` proposes wiki diffs.
3. Teacher approves per file in UI → `commit_ingest` writes **only** approved paths (plus log/index rebuild).
4. Unchecked files (e.g. a student entity page) are not written — there is no bypass after commit.

### Lesson revise (not ingest HITL)

1. Teacher submits an updated diary for an existing lesson date via the revise API.
2. The system re-writes lesson results, roll-ups, students index, students, timeline, and raw in one deterministic pass (no per-file approval UI).
3. Prefer ingest + checkboxes for new lessons; use revise only to fix an already-committed lesson.

### Query / plan

1. Read `index.md` → open 2–5 relevant pages (roll-ups, lessons, students).
2. Synthesize with citations to wiki paths.
3. Do not write wiki files unless teacher saves via HITL commit or explicit revise API.

### Lint

1. Read-only scan: orphans, missing `students/S-###` for IDs mentioned in lessons, stale contradictions, broken links.
2. Output a markdown report; optional proposals only — no auto-commit.

## Rules

- **Never** write curated wiki on ingest without teacher approval (`commit_ingest` per-file checkboxes). Lesson revise is an explicit teacher action that re-applies all derived files for that date.
- Student IDs: `S-001` … `S-999` only.
- Do not infer sensitive facts beyond what the teacher said.
