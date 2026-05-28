# KlassenPilot AGENTS.md — LLM Wiki Schema

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
  student_notes.md      # index only: ## S-### + link to students/S-###.md
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
3. Teacher approves per file in UI → `commit_ingest` writes raw + approved paths.
4. System updates `timeline.md`, student entity pages, `index.md`, `log.md`.

### Query / plan

1. Read `index.md` → open 2–5 relevant pages (roll-ups, lessons, students).
2. Synthesize with citations to wiki paths.
3. Do not write wiki files unless teacher saves via HITL commit or explicit revise API.

### Lint

1. Read-only scan: orphans, missing `students/S-###` for IDs mentioned in lessons, stale contradictions, broken links.
2. Output a markdown report; optional proposals only — no auto-commit.

## Rules

- **Never** write curated wiki without teacher approval (ingest commit or lesson revise endpoint).
- Student IDs: `S-001` … `S-999` only.
- Do not infer sensitive facts beyond what the teacher said.
