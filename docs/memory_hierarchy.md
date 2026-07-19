# Memory Hierarchy

## Purpose

This document defines KlassenPilot's memory layers, what each file is for, when
it is loaded, and which workflow should update it.

Short rule:

> Canonical wiki records are the source of truth. Compact memory and profiles
> are small derived or preference layers. The LLM may propose updates, but the
> backend validates scope and the teacher approves durable writes.

## Routing Summary

A memory target is chosen by the fact's durable purpose, not by surface wording
like "next", "remember", or "for this lesson".

- `teacher_profile.md` / `user.md`: stable global teacher preferences across
  classes: communication style, default lesson structure, workflow preferences,
  and reusable teacher-facing conventions.
- `wiki/subjects/{subject}.md`: subject-wide reusable guidance that should
  apply beyond one class, such as common misconceptions, safety reminders,
  lesson patterns, and question templates.
- `wiki/subjects/{subject}/teaching_frameworks/...`: reviewed, immutable
  subject/grade/branch teaching library. These pages are shared base knowledge,
  not class memory and not directly editable from a class workflow.
- `wiki/sources/{jurisdiction}/...`: compact, provenance-bearing extracts of
  approved external curriculum sources. They are read progressively through
  typed source tools, never treated as class memory or prompt instructions.
- `classes/{class_id}/curriculum_profile.md` and `trusted_sources.md`: the
  class's source scope and compact source table of contents; both are small
  configuration/navigation pages, not a copied curriculum.
- `course_state.md`: canonical current class state derived from approved
  lessons: current unit, last lesson, next planned focus, and overall status.
- `timeline.md`: canonical chronological lesson sequence with dated links,
  covered content, and concise highlights.
- `memory/planning_brief.md`: compact near-term planning brief for this class:
  current priorities, open loops, misconception focus, assessment readiness,
  and immediate next-step pressure.
- `memory/teaching_patterns.md`: durable class learning profile: how this class
  learns, what scaffolds/materials/pacing/activity formats work or fail, and
  recurring class-specific pedagogy.
- `memory/copilot_profile.md` / `copilot.md`: class-scoped copilot working
  agreement: how the agent should plan or behave for this class, including
  repeated teacher corrections and avoid-rules.
- `memory/teaching_framework_adjustments.md`: bounded teacher-approved class
  replacement/refinement rules. Prompt assembly combines it with the immutable
  shared Grade 9 framework; it never copies the Grade 9 summary.
- `memory/session_summaries.md`: sparse compact summaries of prior workflow
  sessions when they help continuity; not a transcript store.
- `lessons/{date}/lesson_results.md`: canonical approved record of what
  happened in one taught lesson.
- `lessons/{date}/lesson_plan.md`: saved plan artifact for one lesson; useful
  evidence, but not itself durable profile memory.
- `students/S-###.md`: pseudonymous individual student learning trajectory with
  dated evidence and a reviewed summary.
- `open_loops.md`: canonical unresolved class follow-ups, questions, and
  pending teaching tasks derived from lessons.
- `misconceptions.md`: canonical class misconception rollup grounded in
  approved lesson evidence.
- `index.md`: navigation catalog for finding relevant wiki pages; it orients
  reads but is not the behavioral source of truth.

Overlap rules:

- If a fact is both a durable class learning pattern and an immediate planning
  priority, capture both with separate concise contents for
  `teaching_patterns.md` and `planning_brief.md`.
- If a teacher gives an agent-behavior instruction and explains why it works
  for the class, capture the behavior in `copilot_profile.md` and the learning
  pattern in `teaching_patterns.md`.
- If the teacher says the rule applies across the subject, route to
  `wiki/subjects/{subject}.md`; if it applies to this class, route to
  `teaching_patterns.md`; if it applies to the teacher's general style, route
  to `teacher_profile.md`.

Conflict rule:

- Committed wiki memory is the baseline. If teacher input conflicts with known
  wiki state, such as a student ID/name that is not on the roster or a class
  status that contradicts `course_state.md`, treat it as a proposed change and
  clarify before writing. Deterministic code should detect factual conflicts;
  the model should phrase the clarification and the teacher confirms the
  resolution.

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
- teacher-confirmed professional context only when it materially improves
  future assistance

Examples:

- "Prefers concise 45-minute lesson plans."
- "Feedback and planning language: English for this prototype."
- "Uses pair exercises after board introduction."
- "Also teaches part time at university." (only after an explicit request to
  remember it; it does not change active-class scope.)

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
- `POST /api/classes/{class_id}/memory/apply` writes approved `teacher_profile.md`
  items
  through bounded backend helpers.
- **Recommended extension:** an explicit `remember(...)` request may stage a
  review-only `teacher_profile.md` candidate in the application-owned ledger.
  Use the section `Professional context` only for concise, teacher-confirmed
  context with a foreseeable product use; it still requires teacher approval
  before profile application. Until that capture policy is implemented,
  professional disclosures remain session context.

Do not put here:

- class-specific learning profile
- one-off lesson constraints
- individual student facts
- raw conversation logs
- casual personal or employment disclosures that the teacher did not ask the
  copilot to remember
- facts that would imply another active class, course, or tool capability

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

Target loading keeps this page as the compact subject front door. Planning and
differentiation compose the active subject expert from the shared Grade 9 base
and `teaching_framework_adjustments.md`; the adjustment page is not duplicated
in Active Class Core.

Design implication:

- Subject guidance is injected as a small bounded slice. It should stay
  subject-wide and reusable, not class-specific.
- The selected subject comes from `wiki.get_class(class_id).subject`. The
  prompt builder must not scan or load every subject guide.

Updated by:

- Manual developer/teacher editing.
- Weekly Memory Sweep / review flows may promote approved `subject_concept`
  candidates through `POST /api/classes/{class_id}/memory/apply`.
- `/memory/apply` only accepts the active class subject path, for example
  `wiki/subjects/chemie.md` for a chemistry class. Other subject paths are
  skipped.

Do not update from:

- normal class-specific lesson chats without teacher approval.
- compact class-memory refresh (`/memory/refresh` or `class_memory_proposal`).

### 3. Class Teaching Framework Adjustments

Path: `backend/teacher_wiki/wiki/classes/{class_id}/memory/teaching_framework_adjustments.md`

Scope: one class's effective subject/grade/branch teaching contract.

This ordinary bounded class-memory page contains only approved adjustments and
cautions, not a copied framework.

At prompt assembly, the system selects the shared framework from the class
curriculum profile and combines it with this page in memory. Planning chat
cannot write either page; changes use the existing proposal and approval flow.

Loaded where:

- the active subject expert is needed for planning, differentiation, or a
  pedagogical discussion;
- detailed framework pages are not needed in Update Memory, class briefs, or
  verification by default.

### 4. Canonical Class Wiki Memory

Path: `backend/teacher_wiki/wiki/classes/{class_id}/`

Scope: one class.

Canonical files include:

- `lessons/{date}/lesson_results.md`
- `lessons/{date}/lesson_plan.md`
- `course_state.md`
- `open_loops.md`
- `misconceptions.md`
- `students.md`
- `students/S-###.md` with `## Student Summary` first, then dated
  observation sections
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

### 5. Compact Class Memory

Path: `backend/teacher_wiki/wiki/classes/{class_id}/memory/`

Scope: one class.

These pages are derived and rebuildable. They make the next prompt small and
high-signal.

Update paths:

- `POST /api/classes/{class_id}/memory/refresh` proposes refreshed compact
  pages without writing.
- `POST /api/classes/{class_id}/ingest/commit` may return
  `class_memory_proposal` after the approved lesson wiki commit. This is the
  immediate class-evolution proposal for the saved lesson.
- `POST /api/classes/{class_id}/memory/compact/apply` writes the reviewed
  compact pages exactly as approved.
- `POST /api/classes/{class_id}/memory/apply` appends bounded approved
  conclusions to selected compact pages; it is not the full-page replacement
  path.

#### `taught_so_far.md` — RETIRED (mem_v3 PR2)

The taught sequence is a deterministic projection of the canonical lesson
record, so it now lives in `timeline.md` (and the current unit in
`course_state.md`) — not in a curated compact twin. Context builders derive the
sequence from the timeline; the sweep reads the rollups rather than maintaining
this page. See [`docs/mem_v3/next_implementation.md`](mem_v3/next_implementation.md)
(the two-axis memory map) and Learning 10 in
[`docs/mem_v3/learnings.md`](mem_v3/learnings.md).

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
- reviewed `class_memory_proposal` after an approved lesson-memory commit

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
- reviewed `class_memory_proposal` after an approved lesson-memory commit when
  the evidence is class-learning behavior, not teacher preference

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

#### `class_state.md` — RETIRED (mem_v3 PR2)

The "current unit / last lesson / next move / open loops" snapshot duplicated
the canonical `course_state.md` rollup (diary-derived) — one fact, two homes,
out of sync by design. It was retired so every such fact has exactly one home in
the canonical rollups; the sweep and context builders read `course_state.md` /
`timeline.md` directly. See the two-axis memory map in
[`docs/mem_v3/next_implementation.md`](mem_v3/next_implementation.md) and
Learning 10 in [`docs/mem_v3/learnings.md`](mem_v3/learnings.md).

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
  `raw_ref`, `MemoryCandidate`s, and current diary version.

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
- candidate observations are not canonical memory. They are session-scoped
  suggestions surfaced for teacher review after save/commit. A future durable
  ledger should live outside `wiki/` (for example SQLite session storage or a
  gitignored workflow file), not in a teacher-visible or model-loaded wiki page.

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

- `teacher_profile.md` (`user.md` alias): stable global teacher preference
- `copilot.md`: class-specific copilot behavior preference
- `teaching_patterns.md`: stable class learning patterns seen across approved
  lesson evidence
- `planning_brief.md`: compact current planning-priority updates when the signal
  is stable enough for teacher review
- `canonical_wiki`: only as a suggestion for teacher-approved wiki action, not
  an automatic write

(Current unit / taught sequence is not a proposal target — it is derived from
the canonical `course_state.md` / `timeline.md` rollups; mem_v3 PR2 retired the
`class_state.md` / `taught_so_far.md` twins.)

Examples:

- Teacher says: "I always want plans in English."
  - Target: `teacher_profile.md` (the model calls `remember(...)` with this quote)
- Teacher says: "For 9b, avoid starting too open-ended."
  - Target: `copilot.md`
- The final plan establishes the next concrete class direction.
  - Not memory: it is captured in the saved plan and the canonical rollups.
- A lesson was actually taught and logged.
  - Target: canonical wiki through memory-update commit, not planning chat

## Update Rules

- LLM proposes; backend validates; teacher approves; code writes.
- Global teacher facts go to `teacher_profile.md`.
- Class learning facts go to `teaching_patterns.md`.
- Copilot behavior rules go to `copilot_profile.md`.
- Current unit / taught sequence is NOT curated memory: it is derived from the
  canonical `course_state.md` / `timeline.md` rollups (mem_v3 PR2).
- `remember(...)` capture carries an internal `routing_reason` for traces and
  eval diagnostics; it helps explain target choice but does not change the
  allowed target or fast-lane verdict.
- Review-only lesson facts go to `canonical_wiki` candidates until an ingest
  commit/revise action writes the canonical lesson files.
- Detailed lesson history stays canonical in `lessons/{date}/`.
- Individual student facts stay pseudonymous in `students/S-###.md`, not broad
  profiles. Lesson updates capture dated evidence; Weekly Memory Sweep promotes
  approved trajectory summaries into each page's `## Student Summary`.

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
