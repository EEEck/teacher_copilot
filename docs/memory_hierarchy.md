# Memory Hierarchy

## Purpose

This document defines KlassenPilot's memory layers, what each file is for, when
it is loaded, and which workflow should update it.

Short rule:

> Canonical wiki records are the source of truth. Compact memory and profiles
> are small derived or preference layers. The LLM may propose updates, but the
> backend validates scope and the teacher approves durable writes.

## Memory Layers

### 1. Global Teacher Profile

Path: `backend/teacher_wiki/wiki/teacher_profile.md`

Alias: `user.md`

Scope: one teacher, across all classes.

Purpose:

- stable teacher preferences
- communication style
- default lesson structure
- cross-class workflow preferences

Examples:

- "Prefers concise 45-minute lesson plans."
- "Feedback and planning language: English for this prototype."
- "Uses pair exercises after board introduction."

Loaded where:

- Real lesson-planning chat calls (`plan_chat`) via
  `build_profiles_assembly`.
- Plan trace exposes it in `prompt_assembly` under `Profiles`.
- Profile proposal skill reads it to avoid duplicate suggestions.

Not loaded where:

- It is not part of `build_plan_context_slim`; it is injected separately as the
  profile slice.

Updated by:

- `POST /api/classes/{class_id}/memory/profile/propose` proposes updates after a
  finished planning session.
- `POST /api/classes/{class_id}/memory/apply` writes approved `user.md` items
  through bounded backend helpers.

Do not put here:

- class-specific learning profile
- one-off lesson constraints
- individual student facts
- raw conversation logs

### 2. Subject Guide

Path: `backend/teacher_wiki/wiki/subjects/{subject}.md`

Example: `backend/teacher_wiki/wiki/subjects/chemie.md`

Scope: subject-wide teaching guidance.

Purpose:

- general lesson patterns for a subject
- common misconceptions for the subject
- reusable question templates
- safety reminders

Loaded where today:

- Current live lesson-planning chat via `build_plan_context_slim`.
- Legacy context builders (`build_base_class_context`, `build_plan_context`)
  include an excerpt.
- Memory compaction source packet may include the subject guide.

Design implication:

- Subject guidance is injected as a small bounded slice. It should stay
  subject-wide and reusable, not class-specific.

Updated by:

- Manual developer/teacher editing for now.
- It should not be updated from class-specific lesson chats.

### 3. Canonical Class Wiki Memory

Path: `backend/teacher_wiki/wiki/classes/{class_id}/`

Scope: one class.

Canonical files include:

- `lessons/{date}/lesson_results.md`
- `lessons/{date}/lesson_plan.md`
- `course_state.md`
- `open_loops.md`
- `misconceptions.md`
- `students.md`
- `students/S-###.md`
- `timeline.md`
- `index.md`

Purpose:

- approved lesson history
- saved plans
- open loops and follow-ups
- misconceptions
- pseudonymous student continuity
- class timeline and index

Loaded where:

- Compact context slices use selected snapshot/rollup data.
- Tools read canonical pages when the model needs evidence:
  `list_lessons`, `read_lesson`, `read_lesson_range`, `search_memory`,
  `read_memory_page`.
- Memory compaction reads canonical wiki memory as source material.

Updated by:

- Memory update flow (`commit_ingest`) after teacher approval.
- Save-plan flow for `lesson_plan.md`.
- Explicit revise/commit actions.

Do not update from:

- normal planning chat
- normal ingest chat before teacher approval
- profile proposal flow

### 4. Compact Class Memory

Path: `backend/teacher_wiki/wiki/classes/{class_id}/memory/`

Scope: one class.

These pages are derived and rebuildable. They make the next prompt small and
high-signal.

#### `taught_so_far.md`

Purpose:

- compact chronological summary of the year's taught content
- major sequence of concepts
- recent lesson sequence

Loaded where today:

- Available through `search_memory`.
- Included in legacy `build_plan_context`.
- Current live planning chat via `build_plan_context_slim`.
- Included in ingest slim context.
- Used by review/query packs.

Good update source:

- memory compaction over approved lesson results and saved plans.

#### `planning_brief.md`

Purpose:

- current planning priorities
- open-loop priorities
- misconception focus
- assessment readiness / next-step summary

Loaded where:

- Current live planning chat via `build_plan_context_slim`.
- Ingest slim context.
- Search and memory page tools.

Good update source:

- memory compaction after lesson results accumulate
- teacher-approved memory refresh

#### `teaching_patterns.md`

Purpose:

- class + subject learning profile
- what has worked or failed for this class
- useful scaffolds, pacing, activity formats

Examples:

- "Students thrive on concrete examples and need visual supports before
  symbolic rules."
- "Peer checking helps reduce equation-balancing errors."

Loaded where:

- Current live planning chat via `build_plan_context_slim`.
- Ingest slim context.
- Search and memory page tools.

Do not put here:

- global teacher preferences
- copilot behavior instructions
- one-off lesson constraints

Good update source:

- compaction from lesson results (`What went well`, `What didn't go well`,
  participation, follow-ups)

#### `copilot_profile.md`

Alias: `copilot.md`

Purpose:

- class-scoped copilot working agreement
- repeated teacher corrections for this class
- planning behavior to apply or avoid
- class-specific interaction preferences

Examples:

- "Use quick diagnostics early."
- "Draft early, then refine the markdown directly."
- "Avoid broad open-ended openings for this class unless scaffolded."

Loaded where:

- Real lesson-planning chat calls (`plan_chat`) via
  `build_profiles_assembly`, separate from the compact class slice.
- Plan trace exposes it in `prompt_assembly` under `Profiles`.

Updated by:

- profile proposal after save, then teacher-approved memory apply
- memory compaction may also rebuild it when explicitly compacting class memory

Do not put here:

- global teacher style (`teacher_profile.md`)
- how the class learns (`teaching_patterns.md`)
- raw session summaries

#### `class_state.md`

Purpose:

- shortest current-state snapshot for this class
- current unit
- last lesson
- likely next move
- active open loops and misconceptions

Loaded where:

- `build_plan_context_slim` will load it if the file exists.
- Ingest slim context will load it if the file exists.

Current observed state:

- In the FCKW trace, `class_state.md` was missing, so it was not included.

Good update source:

- memory refresh/compaction from approved canonical wiki

#### `session_summaries.md`

Purpose:

- optional compact summaries of prior workflow sessions when useful
- should stay sparse; not a transcript store

Loaded where:

- Not part of current live planning base slice.
- Available through search/personal memory style lookup if relevant.

Good update source:

- future session-summary compaction, after teacher approval if durable

### 5. Runtime Session Memory

Location: backend RAM on `ArtifactSession.runtime` (`PlanRuntime`)

Files: none by default.

Purpose:

- short-term working memory for a planning session
- `SessionState`
- `LessonPlanningState`
- `EvidenceBrief`s
- raw tool outputs behind `raw_ref`
- `MemoryCandidate`s
- current artifact version

Loaded where:

- Every plan-chat model call after session start.
- Trace endpoint as `runtime`, `prompt_stack`, `prompt_assembly`, and
  `raw_evidence`.

Updated by:

- model-proposed `state_patch`
- backend validation/merge logic
- tool calls that capture raw evidence

Durability:

- in-memory only for the active session
- useful memory candidates may be proposed after save and written only through
  teacher-approved memory apply

## What Planning Chat Loads Today

There are two model-call stages in a planning session:

- `plan_opening`: lazy greeting before the teacher's first planning request.
  This intentionally loads only the slim class slice, so it can summarize the
  class without injecting teacher/copilot profile memory into a greeting-only
  call.
- `plan_chat`: the real planning/drafting turn after the teacher sends a
  request. This is the stage that loads the full planning prompt stack below.

Current live `plan_chat` loads before the first draft turn:

1. `PLAN_CHAT_SYSTEM`
2. `PLAN_SKILL`
3. `PLAN_MEMORY_POLICY`
4. `build_plan_context_slim(class_id)`:
   - class identity snapshot
   - top misconceptions
   - recent lesson titles
   - bounded subject guide (`wiki/subjects/{subject}.md`)
   - `class_state.md` if present
   - `taught_so_far.md`
   - `planning_brief.md`
   - `teaching_patterns.md`
5. profile slice:
   - `teacher_profile.md`
   - `copilot_profile.md`
6. rendered `SessionState`
7. rendered `LessonPlanningState`
8. current full `lessonplan.md`
9. rendered evidence briefs
10. tool policy
11. recent conversation window

Current live plan chat does **not** directly load:

- `session_summaries.md`
- full `open_loops.md`
- full `students.md`
- last two full lesson notes

Those are fetched through tools when the teacher request needs them.

In a trace bundle, inspect `prompt-02-plan_chat-sections.md` for the first real
planning turn. `prompt-01-plan_opening-sections.md` is intentionally slimmer.

## What Should Be Proposed After A Planning Chat

After a plan is saved, profile/memory proposal can suggest:

- `user.md`: stable global teacher preference
- `copilot.md`: class-specific copilot behavior preference
- `class_state.md`: updated current class state
- `canonical_wiki`: only as a suggestion for teacher-approved wiki action, not
  an automatic write

Examples:

- Teacher says: "I always want plans in English."
  - Target: `user.md`
- Teacher says: "For 9b, avoid starting too open-ended."
  - Target: `copilot.md`
- The final plan establishes the next concrete class direction.
  - Target: `class_state.md`
- A lesson was actually taught and logged.
  - Target: canonical wiki through memory-update commit, not planning chat

## Update Rules

- LLM proposes; backend validates; teacher approves; code writes.
- Global teacher facts go to `teacher_profile.md`.
- Class learning facts go to `teaching_patterns.md`.
- Copilot behavior rules go to `copilot_profile.md`.
- Current state goes to `class_state.md`.
- Year-to-date taught sequence goes to `taught_so_far.md`.
- Detailed lesson history stays canonical in `lessons/{date}/`.
- Individual student facts stay pseudonymous in `students/S-###.md`, not broad
  profiles.

## Debugging

Use the trace bundle script:

```bash
python scripts/run_plan_trace_bundle.py
```

Important generated files:

- `prompt-*-sections.md`: exact model-call context
- `snapshot-*-sections.md`: exact next-turn context at each state
- `08-tool-calls-and-results.md`: tool call inputs/results
- `raw-evidence/`: full raw evidence by `raw_ref`

Do not use old flat files like `context-current.txt` to judge the current live
planning prompt; they can show legacy stacked context that is no longer used.
