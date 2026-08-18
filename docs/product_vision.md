# KlassenPilot Product Vision

For the broader PM source of truth, including north star, current product state,
gaps, and roadmap themes, read `pm_hub.md`. This document captures the durable
product vision and scope boundaries that should shape implementation decisions.

## Vision

KlassenPilot gives every teacher a private executive assistant for their
classes. It remembers what happened, prepares what comes next, manages teaching
content and logistics, and turns class context into usable plans, materials, and
follow-ups.

Teachers stay in control. KlassenPilot handles the work around teaching so the
teacher can focus on students, judgment, and classroom presence.

## North Star

Save teachers time by minimizing "work about work," so they can focus on what
matters most: their students.

## Product Thesis

Every approved lesson update makes the copilot more useful for future lessons.

The product should feel like:

> A teacher opens a class, and the copilot already knows what was taught, what
> the class is struggling with, what worked last time, and how this teacher
> likes to plan.

## User Promise

For each class, the teacher should expect the copilot to understand:

- the subject, school year, current unit, and curriculum direction
- the recent lesson sequence and what has been taught so far
- open loops, recurring misconceptions, and assessment readiness
- class-level learning patterns and teaching moves that worked
- the teacher's planning preferences and communication style
- previous corrections the teacher gave the copilot
- relevant uploaded class materials when the teacher has approved them
- trusted external resources only when the task calls for them

The teacher should not have to restate this context in every chat. The copilot
should load the relevant class memory automatically, then browse additional wiki
evidence, uploaded materials, or trusted sources only when the request needs
them.

## Product Shape

The app has five product layers.

1. **Class workspace**
   The class home is the teacher's entry point. It is an executive-assistant
   surface: class briefing, At a glance metrics, Actions into core workflows
   (including Discuss as a docked helper), and a lesson timeline with clear
   Upcoming / Add results / Done status.

2. **Teacher workflows**
   Current core workflows are:
   - update memory from a lesson conversation
   - create a lesson plan from class memory
   - attach PDF class materials in plan chat (citation/source layer; promote on save)

   Near-term workflows include:
   - generate tests/exams
   - year-start materials library / teacher-approved import into durable memory
   - adapt trusted resources
   - draft reports and teaching-admin artifacts

3. **Class copilot memory**
   The wiki is the canonical memory. Compact memory pages and local profile
   pages make the copilot fast, personal, and consistent.

4. **Trusted source layer**
   Uploaded teacher materials and allowlisted external sources can enrich plans
   and resources, but they stay source-labeled and teacher-reviewable. For the
   Chemie 9 NTG beta, planning also uses an adapted open K–12 lesson procedure
   (Anthropic skills, Apache-2.0; not a live plug-in), LehrplanPLUS/KMK as
   provenance-bearing curriculum sources, and immutable shared teaching
   frameworks (class overrides only via `teaching_framework_adjustments.md`).
   Frameworks are curated pedagogy, not legal curriculum text.

5. **Low-friction capture**
   Longer term, voice memo and messaging capture should make it easy to log
   lessons or follow-ups immediately after class. These channels create drafts
   and suggestions, not automatic durable writes.

## Memory Model

KlassenPilot uses a tiered memory model.

- **Canonical wiki memory**
  Approved lesson records, saved plans, roll-ups, misconceptions, open loops,
  student notes, and subject guides. This is the source of truth.

- **Compact class memory**
  Derived pages under `wiki/classes/{class_id}/memory/`:
  `planning_brief.md`, `teaching_patterns.md`, `copilot_profile.md`, and
  `session_summaries.md`. (Current unit / taught sequence is derived from the
  canonical `course_state.md` / `timeline.md` rollups; the retired
  `class_state.md` / `taught_so_far.md` twins.)

- **Inherited subject expert**
  Shared reviewed subject/grade frameworks remain immutable library knowledge.
  Prompt assembly selects the subject, grade, and branch base and combines it
  in memory with `teaching_framework_adjustments.md`. Only the dedicated
  adjustment page is teacher-editable through approval; no generated profile
  file or mutable copy of the Grade 9 summary exists.

- **Workflow context packs**
  Read-only packs for base class chat, lesson planning, memory update, review,
  future assessment generation, and material/resource adaptation.

- **Teacher and copilot profiles**
  Bounded local profiles store stable teacher/class/copilot conclusions:
  preferences, recurring goals, communication style, class learning profile,
  planning patterns that worked, avoid/watch rules, and useful teacher
  corrections.

- **Review-only candidate memory**
  Chat can stage durable-memory candidates through `remember(...)`, but the
  ledger, sweep, review brief, and apply path keep promotion explicit and
  teacher-approved.

- **Source library**
  Uploaded materials and trusted external resources should carry provenance and
  remain distinguishable from approved class memory.

Memory should be class-scoped. Individual student memory should stay
pseudonymous and should not leak into broad teacher/class profile facts.

## Executive Assistant Product Contract

KlassenPilot is an executive assistant for the teacher, not a passive chatbot.
It has two jobs in every interaction:

1. complete the teacher's foreground task efficiently;
2. quietly protect class-state integrity in the background.

Teachers will naturally provide messy, fast, and occasionally inconsistent
input between classes or during short planning windows. This is expected
real-world behavior, not teacher failure. The copilot should compare
consequential details with committed class state, collect supporting evidence,
adapt safe local preferences, and surface only decisions the teacher must make.

The wiki is the committed factual baseline. Teacher input may add new
information or correct stale wiki state, but a conflict must not cause a silent
overwrite, class switch, student reattribution, lesson-history rewrite, or
durable preference change.

> Do the busywork invisibly. Surface only the decisions.

The operating rule is: verify continuously, interrupt selectively. Normal,
aligned input should feel fast. One concise clarification is appropriate when
the answer changes durable memory, active class, student attribution, lesson
history, artifact correctness, or an important instructional assumption.

## Expected Copilot Behavior

The copilot should behave like a careful teaching colleague with access to the
class notebook.

- On class entry, it starts from the base context: global teacher profile,
  active class core, compact subject/grade/branch routing, and workflow state.
- For planning, it adds the active subject expert (compact subject guide,
  immutable grade/branch key summary, class adjustment page, and trusted-source
  TOC), then reads detailed framework/source pages only when needed.
- For memory update, it keeps only subject identity/routing by default so the
  workflow records what happened rather than receiving unnecessary
  lesson-design guidance.
- For memory update, it loads the previous lesson, logging conventions, compact
  memory, student index excerpt, and open loops.
- For broad topic requests, it uses deterministic `search_memory` as a
  pathfinder, then reads the relevant lesson or memory pages.
- For external resources, it uses only trusted/allowlisted sources and labels
  them clearly.
- When it uses memory or sources, it names or cites the source lesson/page/file.
- When memory is sparse, it says so and asks at most one targeted question.
- When it sees a durable pattern, it may propose a profile update for teacher
  review.
- When teacher input conflicts with committed wiki memory, it treats the wiki
  as the baseline and asks how to resolve the discrepancy before writing.

The copilot should not silently rewrite the wiki, invent classroom patterns,
store sensitive student-level conclusions in broad profile memory, or blur the
line between class memory and external sources.

## Current Product Scope

- One teacher, local/private deployment.
- Multiple class ids supported by code, with `chemie_9b_2026_27` as the seed
  fixture.
- Class-scoped markdown wiki memory.
- Update memory with teacher-approved commits.
- Timeline/detail shortcuts for adding or correcting lesson results without
  turning Update Memory into a wizard; class-home timeline status chips
  (Upcoming / Add results / Done) with matching CTAs.
- Create lesson plan with read-only wiki access during chat. PDF class
  materials (Textbook/Personal) OCR into session scratch; promote into
  `materials/` only on plan save.
- Compact memory compaction and profile proposal/apply endpoints.
- MemV4 candidate capture, ledger folding/gating, and teacher-reviewed
  Memory Sweep brief with backend-owned saved review sessions.
- Deterministic source-bearing wiki retrieval.
- Query packs for planning, ingest, and review.
- Backend-owned workflow drafts for Plan / Update Memory (leave and resume).
- Class-home Discuss dock (Gmail-style helper) and Browse class files wiki viewer.

## Near-Term Scope

- Make class home a useful briefing surface.
- Add evidence/source UI.
- Productize test/exam generation.
- Build the class wiki factory and guided setup.
- Year-start materials library / chapterize, and teacher-approved import of
  extracted material into durable wiki memory (OCR never auto-writes MemV4).
- Add trusted search and resource adaptation.
- Make profile updates visible and reviewable.
- Add proactive wiki/input reconciliation, starting with roster/name mismatch
  detection and teacher-confirmed resolution.
- Add sparse-memory and stale-open-loop hygiene.

## Longer-Term Scope

- Proactive suggested tasks.
- Voice memo and messaging capture, such as Telegram-style quick input.
- Subject teaching-practice libraries, starting narrow by subject.
- Broader teaching logistics: follow-ups, report drafts, parent/admin
  communication drafts, and multi-week sequencing.

## Out Of Scope Until Demand Is Proven

- Autonomous wiki writes.
- Always-on external messaging as the default interface.
- Multi-user school admin platform.
- Real student names.
- Grading automation without teacher review.
- Full AutoSci graph or multi-agent orchestration.
- External Honcho dependency as the default memory layer.
- Vector database as the default retrieval path.
- Full textbook corpus access without licensing/source constraints.

## Success Criteria

The product is working when:

- a teacher can open a class and immediately see useful class state
- a teacher can move from class context to a useful next action in minutes
- a lesson plan reflects recent lessons, misconceptions, sources, and teacher
  style
- memory updates improve future planning without hidden writes
- the copilot can explain what memory or source material it used
- compact memory stays small, stable, class-scoped, and rebuildable
- the teacher feels less like they are prompting from scratch each time

## Relationship To Other Docs

- `pm_hub.md` defines PM strategy, north star, current product state, roadmap
  themes, and prioritization.
- `agent_contracts.md` defines behavior contracts and safety boundaries.
- `agent_architecture.md` explains the agent architecture and retrieval lessons.
- `../implementation_plans/product_backlog.md` tracks engineering-facing
  roadmap themes and likely implementation touchpoints.
