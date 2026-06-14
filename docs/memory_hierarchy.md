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

- Real lesson-planning chat calls (`plan_chat`) and update-memory chat calls via
  `build_teacher_context_trace`.
- Plan and ingest traces expose it as the `Teacher layer`.
- Profile proposal skill reads it to avoid duplicate suggestions.

Not loaded where:

- It is not part of active class memory. It is injected separately as the global
  teacher layer so class switching can rebuild class context without duplicating
  teacher preferences.

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

- Current live class-scoped chats through
  `build_active_class_core_context_trace(class_id)`.
- Legacy context builders (`build_base_class_context`, `build_plan_context`)
  include an excerpt.
- Memory compaction source packet may include the subject guide.

Design implication:

- Subject guidance is injected as a small bounded slice. It should stay
  subject-wide and reusable, not class-specific.
- The selected subject comes from `wiki.get_class(class_id).subject`. The
  prompt builder must not scan or load every subject guide.

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

- Included in the active class core context.
- Available through `search_memory`.
- Included in legacy `build_plan_context`.
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

- Included in the active class core context.
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

- Included in the active class core context.
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

- Included in the active class core context as
  `Class memory: copilot_profile.md`.
- Plan and ingest traces expose it under `Active class core`.

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

- Included in the active class core context if the file exists.

Current observed state:

- In the FCKW trace, `class_state.md` was missing, so it was not included.

Good update source:

- memory refresh/compaction from approved canonical wiki

#### `session_summaries.md`

Purpose:

- optional compact summaries of prior workflow sessions when useful
- should stay sparse; not a transcript store

Loaded where:

- Included in the active class core context if the file exists, with the same
  compact memory page budget discipline as other `memory/*.md` files.
- Available through search/personal memory style lookup if relevant.

Good update source:

- future session-summary compaction, after teacher approval if durable

### 5. Runtime Session Memory

Location: backend RAM on `ArtifactSession.runtime` (`PlanRuntime` or
`MemoryRuntime`)

Files: none by default.

Purpose:

- short-term working memory for an active artifact session
- Planning: `SessionState`, `LessonPlanningState`, `EvidenceBrief`s, raw tool
  outputs behind `raw_ref`, `MemoryCandidate`s, and current plan version.
- Update Memory: `MemoryTargetState`, `MemorySessionState`,
  `LessonResultState`, `MemoryEvidenceBrief`s, raw tool outputs behind
  `raw_ref`, and current diary version.

Loaded where:

- Every plan-chat and update-memory chat model call after session start.
- Planning trace endpoint as `runtime`, `prompt_stack`, `prompt_assembly`, and
  `raw_evidence`.
- Update-memory session/chat/draft/propose responses as `memory_state`.

Updated by:

- model-proposed `state_patch`
- backend validation/merge logic
- tool calls that capture raw evidence

Durability:

- in-memory only for the active session
- useful planning memory candidates may be proposed after save and written only
  through teacher-approved memory apply
- update-memory runtime state is discarded with the session after the normal
  teacher-approved commit/revise path writes canonical lesson memory

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
4. `build_teacher_context_trace()`:
   - `wiki/teacher_profile.md`
5. `build_active_class_core_context_trace(class_id)`:
   - class identity snapshot
   - top misconceptions
   - recent lesson titles
   - bounded subject guide selected from `wiki.get_class(class_id).subject`
   - all existing compact class memory files under
     `wiki/classes/{class_id}/memory/*.md`
6. rendered `SessionState`
7. rendered `LessonPlanningState`
8. current full `lessonplan.md`
9. rendered evidence briefs
10. tool policy
11. recent conversation window

Current live update-memory chat loads the same Teacher Layer and Active Class
Core exactly once, then adds an Update Memory task context containing bounded
continuity hints such as the previous lesson excerpt, student roster excerpt,
and most recent saved plan.

Current live plan chat does **not** directly load:

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
