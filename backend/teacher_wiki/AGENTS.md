# KlassenPilot AGENTS.md - LLM Wiki Schema

This file is the wiki-specific schema and workflow contract for
`backend/teacher_wiki/`. For full repo onboarding and agent development context,
read [`../../AGENTS.md`](../../AGENTS.md) first. For current behavior contracts,
read [`../../docs/agent_contracts.md`](../../docs/agent_contracts.md).

This file is for coding agents and developers. It is not injected into the
teacher-facing KlassenPilot agent as class memory.

## Three layers

1. **Raw** - `raw/classes/{class_id}/{YYYY-MM-DD}-{slug}.md` - immutable approved diaries. Never edit after commit.
2. **Curated wiki** - `wiki/classes/{class_id}/` - structured pages maintained by the agent with teacher HITL on ingest.
3. **Navigation** - `index.md` is the catalog the teacher-facing agent may use
   to orient wiki reads; `log.md` is the append-only audit/change log and
   should not be treated as class memory.

## Memory pages and scope

Compact, size-budgeted derived pages back the copilot's working memory. Keep
each scope clean, dedupe, and replace stale facts.

- `wiki/teacher_profile.md` (**user.md**, GLOBAL, one per teacher) - communication
  style, stable preferences, default lesson structure. Agent-maintained, bounded.
- `wiki/subjects/{subject}.md` (subject guide) - subject-wide teaching guidance,
  common misconceptions, safety reminders, and reusable question patterns. Do
  not store class-specific observations here.
- `memory/teaching_patterns.md` (class + subject) - how THIS class learns and
  which teaching approaches work or fail. This holds the class learning profile.
- `memory/copilot_profile.md` (**copilot.md**, class) - copilot working agreement
  only: planning patterns, avoid-rules, repeated corrections, and agent behavior.
- `memory/planning_brief.md` and `memory/session_summaries.md`.
- Current unit / taught-so-far sequence is NOT a memory page: it is derived
  from the canonical `course_state.md` and `timeline.md` rollups.

Durable writes to these pages are teacher-approved only through the memory
refresh/propose/apply endpoints. Planning and ingest chat never write them.

### Memory update routing

During chat, collect possible durable updates as candidates only. The LLM may
propose, but backend code validates scope and writes only after teacher approval.

- Global teacher preference -> `wiki/teacher_profile.md`.
- Subject-wide chemistry guidance -> `wiki/subjects/chemie.md` through a
  manual/update workflow only; do not infer it from one class.
- Class learning pattern -> `memory/teaching_patterns.md`.
- Copilot behavior rule for this class -> `memory/copilot_profile.md`.
- Current class state / taught sequence -> NOT memory; read the canonical
  `course_state.md` / `timeline.md` rollups (deterministic from lessons).
- Lesson facts -> `lessons/{YYYY-MM-DD}/lesson_results.md` through ingest HITL.
- Student-specific facts -> `students/S-###.md`, pseudonymous only. Each student
  page starts with `## Student Summary` and then keeps dated observation
  sections below it.

Overlap rule: if one teacher statement is both a durable class learning pattern
and an immediate planning priority, propose separate candidates for
`memory/teaching_patterns.md` and `memory/planning_brief.md`. Keep temporal
scope in the teaching-pattern text when the teacher names an upcoming block.

## Directory layout

```text
wiki/classes/{class_id}/
  class_config.md
  course_state.md
  misconceptions.md
  open_loops.md
  memory/
    planning_brief.md
    teaching_patterns.md   # class+subject teaching style (how this class learns)
    copilot_profile.md     # class copilot working agreement (copilot.md)
    session_summaries.md
  students.md           # class student index / roster
  timeline.md           # chronological narrative with links to lessons
  students/S-###.md     # entity pages (durable summary + dated observations)
  lessons/{YYYY-MM-DD}/
    lesson_results.md
    lesson_plan.md
    materials.json      # lesson → promoted material_ids (plan save)
  materials/
    textbooks|personal/{material_id}/  # OCR citation layer, not MemV4
```

## Lesson results sections (required)

1. What was covered
2. Student participation
3. What went well
4. What didn't go well
5. Student observations (pseudonyms `S-###` only - never real names)
6. Homework & follow-ups

## Linking

- Link lessons: `[title](lessons/2026-09-21/lesson_results.md)`
- Link students: `[S-014](students/S-014.md)`
- Link raw: relative path from lesson header `> Raw: [...]`

## Workflows

### Ingest

1. Read `index.md` first, then relevant class pages via tools.
2. Chat -> update diary draft -> `compile_from_diary` proposes wiki diffs.
3. Teacher approves per file in UI -> `commit_ingest` writes **only** approved paths plus log/index rebuild.
4. Unchecked files, such as a student entity page, are not written. There is no bypass after commit.
5. Ingest appends dated student observations only. It does not rewrite
   `## Student Summary`; Weekly Memory Sweep proposes those durable summary
   updates from approved dated evidence.

### Lesson revise (not ingest HITL)

1. Teacher submits an updated diary for an existing lesson date via the revise API.
2. The system re-writes lesson results, roll-ups, students index, students, timeline, and raw in one deterministic pass with no per-file approval UI.
3. Prefer ingest + checkboxes for new lessons; use revise only to fix an already-committed lesson.

### Query / plan

1. Read `index.md` -> open 2-5 relevant pages such as roll-ups, compact memory, lessons, or students.
2. Synthesize with citations to wiki paths.
3. Do not write wiki files unless the teacher saves via HITL commit, plan save
   (which may promote OCR packages into `materials/`), or explicit revise API.
   Class materials are a citation/source layer; OCR never writes course_state,
   diary, or compact memory pages.

### Lint

1. Read-only scan: orphans, missing `students/S-###` for IDs mentioned in lessons, stale contradictions, and broken links.
2. Output a markdown report; optional proposals only - no auto-commit.

## Rules

- **Never** write curated wiki on ingest without teacher approval (`commit_ingest` per-file checkboxes). Lesson revise is an explicit teacher action that re-applies all derived files for that date.
- Student IDs: `S-001` ... `S-999` only.
- Do not infer sensitive facts beyond what the teacher said.
- Student summaries must be neutral, evidence-grounded learning-trajectory
  notes. Avoid diagnosis, grading, placement, discipline, or fixed-trait
  labels.
