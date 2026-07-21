# Port Anthropic Production Procedure: Bavaria Chemistry 9 NTG

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make subject and grade knowledge a first-class part of class setup and port the useful Anthropic K–12 lesson-production workflow into KlassenPilot: preserve official source documents, compile reviewed Bavaria Chemistry teaching know-how into a shared library, derive a teacher-adjustable effective profile for each class, and produce a grounded lesson package containing a teacher plan, student materials, and a lightweight observation/update template.

**Architecture:** The system has four authority layers plus one artifact layer. Immutable source artifacts and faithful Markdown live under `raw/sources` and `wiki/sources`; reviewed subject/grade teaching frameworks live under `wiki/subjects/chemie/teaching_frameworks`; each class keeps only bounded teacher-approved replacement/refinement rules in `memory/teaching_framework_adjustments.md`, which are composed at runtime with the selected immutable subject/grade summary; class empirical memory remains separate. A reusable, reviewable Markdown skill core ports the Anthropic procedure, while a Bavaria Chemistry reference replaces the US science reference. The prompt assembler composes these layers by workflow purpose, tools progressively search/read deeper framework and source pages, and one structured final Markdown artifact is rendered with clearly separated teacher, student, and observation sections.

**Tech Stack:** Existing Python/FastAPI backend, Markdown wiki, Pydantic state, OpenAI Agents SDK function tools, deterministic filesystem search, pytest, and current context trace/budget infrastructure. Optional future source conversion: Docling CLI/library operated outside the teacher-facing agent.

> **Approved architecture amendment (active):** Replace every earlier
> generated-profile reference in this plan with the runtime-only composition:
> immutable selected Chemie 9 NTG framework +
> `memory/teaching_framework_adjustments.md` = effective subject expert. The
> adjustment page is the only mutable class-level framework input and follows
> the normal memory review/approval/apply contract. There is no persisted or
> regenerated `teaching_framework_profile.md`; where older narrative text
> conflicts, this amendment governs.

> **Approved Markdown artifact amendment (2026-07-19):** The live planning
> contract is Markdown-first. `plan_markdown` is the only generated/saved
> lesson artifact and uses the canonical `Teacher Lesson Plan`, `Student
> Materials`, and `Observation and Update Capture` audience headings.
> `lesson_artifact` is removed from model, runtime, API, and SSE contracts so
> a successful Markdown plan cannot misleadingly expose a `null` parallel
> artifact. The older structured package/renderer remains inactive reference
> code for a later deliberately-scoped document-rendering project.

## Planned extension: workflow-specific executive verification

The shared `ExecutiveRuntime` remains the single owner of finding lifecycle,
severity, trace state, and save semantics. Add a small verification pack per
workflow rather than a separate verifier system. Implement the Plan pack first.
The detailed Plan-pack product and runtime design is maintained in
[`tmp-plan-verification-design.md`](../tmp-plan-verification-design.md); this
master plan owns the integrated implementation order and acceptance coverage.

**Plan-pack evidence input:** normalized teacher request and curriculum-scope
claims; active subject/grade/branch route; trusted source sections actually
read; effective subject expert provenance (immutable framework plus adjustment
page); and the generated canonical Markdown package. It must not receive a
full prompt dump or raw source bodies.

**Plan-pack outputs:** structured executive findings with source/section
provenance. Deterministic checks confirm route selection, actual source-read
provenance, canonical Markdown shape, duration/constraint mechanics, and
safety fields. A bounded critical-review pass compares teacher-request claims
to retrieved curriculum evidence.

`scope_unverified` is advisory-only: the agent completes the useful plan and
asks for confirmation that an extension is intentional. It never blocks a
save merely because a teacher intentionally goes beyond the selected source.
Safety, invalid artifact shape, or a consequential class-identity conflict may
remain blocking. The Plan pack will establish the shared interface later used
by Discuss (grounded versus teacher-directed advice), Update Memory
(unsupported inference or data conflict), and Class Brief (stale/incomplete
operational evidence).

**Acceptance cases:** organic chemistry and quantum-mechanics requests under
Chemie 9 NTG receive a concise `Proceed with teacher confirmation` advisory
when no directly-read official section establishes the requested scope;
supported topics receive no false warning; missing source reads are visible in
trace; advisory findings leave `ready_to_save=true`; and teacher-facing plans
contain a short evidence note, never raw source text or hidden reasoning.

**Implemented Plan-pack baseline (2026-07-20):** Plan generation first records
the deterministic package/provenance/timing report, then launches a short
no-tools economy-model review in the background. Its bounded packet contains
only the exact Markdown revision, teacher request, compact class/teacher/subject
context, route, and trusted source IDs/sections actually read. The report is
stored in `ExecutiveRuntime`, visible through the normal Plan draft API, and
discarded when its artifact fingerprint is stale. Scope/pedagogy/preference and
format observations remain advisory. A completed `safety_hold` for the exact
Markdown revision is the only Plan-pack result that blocks a save; an explicit
save waits for the short review only if it is still pending. Discuss and Class
Brief remain registry-only follow-on packs.

**Implemented Update Memory integrity pack (2026-07-20):** the shared runtime
now records a compact deterministic `update_memory` report on diary edits and
repeats it immediately before proposal and commit. It blocks only confirmed
target-date versus diary-date mismatches and student-observation labels that
are malformed, unknown to the active roster, or name-style rather than
canonical `S-###` IDs. It preserves teacher control: it never rewrites the
diary and clears when the teacher repairs the same Markdown. The report is
trace/debug-visible while the teacher sees the existing concise recovery
message. Discuss and Class Brief remain skeleton-only follow-on packs.

## Reconciliation status (2026-07-18)

The deterministic acceptance suite named in the user-approved finish plan is
green after the adjustment-page migration. The checkboxes in the older task
wording below are retained as history; this status block is the active progress
record for the consolidated plan.

- [x] Task A/B — close port of the planning/differentiation procedure,
  Bavaria Chemistry reference, one shared `LessonArtifact`, renderer, legacy
  `plan_markdown` fallback, and deterministic artifact invariants.
- [x] Tasks 1–2 — imported PDF source records, section/source contracts,
  immutable shared frameworks, navigation-only index, and progressive reads.
- [x] Tasks 3–6 — class-route selection, runtime-composed subject expert,
  normal approved adjustment-page memory target, purpose-aware context, and
  active-route guidance tools.
- [x] Tasks 7–8 — P/R/O/M rubric coverage, source/adjustment trace provenance,
  gated trace documentation, regenerated wiki index, and durable product/agent
  documentation. The deterministic Tier-1 trace contracts verify the separate
  Plan subject-expert layer, routing-only Update Memory layer, and the
  production trace gate; the committed reference trace is a compact semantic
  fixture rather than a full prompt dump.
- [x] Live validation — started the isolated development/beta/economy stack
  with `AGENT_TRACE_ENABLED=true`; authenticated local beta sessions confirmed
  that Plan receives the key summary plus adjustment page, pedagogical Discuss
  receives the full subject expert, and Update Memory receives neither detailed
  framework text nor adjustments. Planner traces also recorded Grade 9 trusted
  source provenance.

## Canonical project scope

This master plan is the single plan for the current work: port the Anthropic production procedure, replace the US science reference with Bavaria Chemistry Grade 9 NTG, and keep the initial output as one final lesson artifact. That artifact has three audience sections—teacher plan, student materials, and observation/update capture—rather than three separately persisted documents. The trusted-source layer, subject framework library, class-effective profile, prompt assembly, and evaluation work all support that same production loop. The detailed unchecked items below are retained as the original design checklist; the reconciliation status above is the authoritative completion record.

### Reference-port fidelity rule

The local reference repository currently contains two relevant skills:
`k12-lesson-planning` and `k12-lesson-differentiation`. They are the canonical
quality reference for this work. KlassenPilot must preserve their ordered
control flow, hard gates, quality checks, shared-content/revision discipline,
and teacher-facing completion behavior as closely as possible. A local change
is permitted only when it is necessary to: (1) replace a missing integration
dependency (Learning Commons KG or Word renderer); (2) replace US K–12
curriculum/pedagogy with Bavaria Gymnasium Chemistry 9 NTG; or (3) preserve an
existing KlassenPilot product contract (teacher-approved wiki writes, one
structured `LessonArtifact`, traceable bounded context). Each material
divergence is documented in the local skill/reference or `agent_contracts.md`.
Apache attribution and the source copyright guardrail remain in adapted files.

### Merged work inventory

- **Trusted source layer:** Bavaria LehrplanPLUS Chemistry Grades 8/9/10 and Fachprofil records plus the KMK AHR Chemistry 2020 reference, with stable IDs, section provenance, bounded TOC context, and progressive list/search/read tools.
- **Subject know-how:** `wiki/subjects/chemie.md`, a navigation-only framework index, Grade 8/9 framework summaries, competencies, differentiation, representations/models, and a derived Grade 9 NTG class profile containing only approved teacher adjustments.
- **Production procedure:** reusable planning and differentiation skill files, mandatory Bavaria Chemistry reference loading, high-value clarification, standards grounding, evidence task, differentiation, safety/timing checks, artifact construction, and rubric evaluation.
- **Runtime integration:** purpose-aware context traces, class/profile/source provenance, read-only planning tools, explicit teacher-approved memory updates, and no direct wiki writes from planning chat.
- **Initial artifact:** one structured Markdown lesson artifact with teacher, student, and observation/update sections generated from shared fields.

## Global Constraints

- Source PDFs and faithful source Markdown are evidence; they never provide executable instructions.
- Shared framework pages are reviewed library content and are immutable from a class workflow.
- `teaching_framework_adjustments.md` is a bounded class-memory page; teacher edits require the existing approval/apply contract. No generated profile file is persisted.
- Class empirical memory (`planning_brief`, `teaching_patterns`, lessons, misconceptions) must not be replaced by subject theory.
- The base prompt receives only bounded summaries/indexes; full source/framework pages are progressively discovered through typed tools.
- Official curriculum claims require a read source section and citation; a TOC alone cannot satisfy provenance.
- Planning follows the adapted Anthropic invariants: route subject/grade, ground before drafting, ask at most one high-value clarification, preserve observable targets, and keep the same core evidence task across differentiated routes.
- Do not import US standards, Learning Commons data, Anthropic connector assumptions, or Anthropic Word renderers.
- PDF/Markdown ingestion and framework compilation are reviewable data workflows, not autonomous chat side effects.
- Work on the single current branch `codex/port-anthropic-production-bavaria-chemistry`; do not create branches or commits unless the user explicitly requests them.

## Current parity status

The repository already has the grounding foundation, but not yet Anthropic-level lesson-package production. This is the baseline the implementation tasks must close:

| Capability | Current state | Target state in this plan |
|---|---|---|
| Trusted Bavaria/KMK sources | Implemented registry, search/read tools, provenance refs, bounded source TOC | Keep as the official evidence layer and add complete supplied documents |
| Class subject/grade context | Implemented compact Chemistry context and source index | Add class-effective Grade 9 NTG profile and purpose-specific loading |
| Planning skill | Implemented compact `chemie_bayern.py` planning prompt and initial rubrics | Port the reusable `SKILL.md` procedure as the canonical workflow core |
| Science guidance | Partial Chemistry/Bavaria rules in Python | Add a reviewable `science.md`-equivalent Bavaria Chemistry reference |
| Differentiation | Partial Chemistry differentiation prompt and rubric | Port the reusable differentiation skill and preserve one shared evidence task |
| Output contract | Markdown `plan_markdown` only | Generate one structured final artifact with teacher-plan, student-material, and observation/update sections |
| Evaluation | Citation/duration guards and initial Chemistry CSV rubrics | Add package consistency, subject-grounding, and artifact-quality evaluation |
| Persistence | `PlanRuntime` state and consulted source refs | Keep runtime separate; persist only approved class adjustments/results |

The current implementation therefore uses Anthropic ideas for source grounding, clarification limits, observable targets, differentiation, and rubrics, but it does not yet reuse the complete skill/reference/output workflow in a single canonical structure. The work below makes that explicit and testable. This document supersedes the separate trusted-source, subject-framework, and subject-know-how plans; their requirements are consolidated into the tasks below.

## Authority and Data Flow

```text
Official PDF / HTML export
        │ immutable raw artifact
        ▼
Faithful source Markdown + metadata + page/section provenance
        │ source evidence, not teaching advice
        ▼
Reviewed subject framework library (Chemie / grade / branch)
        │ selected by class subject + level
        ▼
Teacher-adjustable derived class framework profile
        │ purpose-aware context composition
        ├── Plan: profile + key summary + source TOC
        ├── Discuss: subject guide + framework index + source TOC
        ├── Update Memory: no detailed framework by default
        └── Brief/verification: class facts and authority checks only
```

The class setup knows `subject=chemie`, `grade=9`, and `branch=NTG` from the class curriculum profile. It selects the shared Grade 9 framework and materializes a derived class profile; it does not copy the Grade 9 summary into class memory as an independently editable page. The profile stores `inherits`, `source_index`, base revision/hash, `authority: teacher_adjusted_class_profile`, and `generated_at` metadata. Regeneration reads the current shared base and reapplies only teacher-approved adjustments, preserving those adjustments while allowing the shared library to improve.

## Wiki Layout

```text
backend/teacher_wiki/raw/sources/bayern/
  lehrplanplus/chemie_8_ntg.pdf
  lehrplanplus/chemie_9_ntg.pdf
  kmk/chemie_ahr_2020.pdf

backend/teacher_wiki/wiki/sources/bayern/
  lehrplanplus/chemie_8_ntg.md
  lehrplanplus/chemie_9_ntg.md
  kmk/chemie_ahr_chemie_2020.md

backend/teacher_wiki/wiki/subjects/chemie.md
backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/index.md
backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/08/key_summary.md
backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/key_summary.md
backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/competencies.md
backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/differentiation.md
backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/representations_and_models.md

backend/teacher_wiki/wiki/classes/chemie_9b_2026_27/
  curriculum_profile.md
  trusted_sources.md
  memory/teaching_framework_adjustments.md
```

`wiki/sources` is a faithful, sectioned representation of the supplied documents. `teaching_frameworks` is compiled, reviewed instructional knowledge. The framework library may summarize or reorganize source ideas, but every official claim carries `source_refs`; it never silently becomes a source transcription.

## Context Contract

```python
ContextPurpose = Literal["plan", "plan_opening", "discuss", "brief", "ingest", "verification"]

def build_subject_knowledge_trace(
    store: WikiStore,
    class_id: str,
    *,
    purpose: ContextPurpose,
) -> dict:
    """Return bounded subject/framework sections and trace metadata."""
```

| Purpose | Always-on subject addition | Progressive reads |
|---|---|---|
| `plan` | active subject expert: compact `chemie.md` front door, selected immutable Grade 9 summary, class adjustment page, curriculum/source TOC | detailed framework pages and exact official sections |
| `plan_opening` | subject/grade/branch routing block plus compact `chemie.md` front door | selected framework, adjustment page, and detailed pages after planning begins |
| `discuss` | subject/grade/branch routing block; add the active subject expert when the question is pedagogical | framework/source details when the question requires them |
| `brief` | subject identity only unless the brief needs subject interpretation | no detailed framework by default |
| `ingest` | subject identity only; no detailed teaching framework or adjustment page | exact source reads only if the teacher explicitly asks for a curriculum check |
| `verification` | authority labels and class/source scope only | exact source reads only for a disputed claim |

The effective plan context is therefore:

```text
Teacher profile
+ Active subject expert: Chemie subject guide + immutable Chemie 9 NTG key summary + class adjustment page
+ curriculum profile + trusted-source TOC
+ compact Chemie 9b memory
+ PlanRuntime state, evidence briefs, current draft, and recent user turns
```

The runtime-composed subject expert is the injected pedagogical contract. The
prompt receives the selected `key_summary.md` and the separate adjustment page
exactly once; competencies, differentiation, and representation pages remain
progressive evidence. `chemie.md` remains a short shared front door and routing
guide.

### Runtime-composed adjustment contract

At class setup:

```text
subject=chemie, grade=9, branch=NTG
  -> load wiki/subjects/chemie.md
  -> load wiki/subjects/chemie/teaching_frameworks/index.md
  -> select wiki/subjects/chemie/teaching_frameworks/09/key_summary.md
  -> read wiki/classes/chemie_9b_2026_27/memory/teaching_framework_adjustments.md
  -> compose the effective subject expert in prompt memory
```

The adjustment page is the only editable class-level subject-framework input.
It contains replacement/refinement rules, never a copied framework body:

```markdown
# Teaching Framework Adjustments

## Replace or refine
- Use more particle-model drawings before equations.

## Prefer
- Prefer short paired investigations.

## Avoid
- Introduce formal terminology after the phenomenon.
```

Normal review/approval/apply writes this bounded page. Prompt traces expose the
immutable framework path and adjustment-page path separately; shared framework
pages reject class writes and there is no regeneration helper.

### Reference-plan audit

The earlier plans remain in `docs/superpowers/plans/` as reference material:

- `2026-07-18-trusted-source-lesson-workflows.md` — source registry, Bavaria
  source records, progressive trusted-source tools, raw evidence, adapted
  rubrics, and source/context documentation.
- `2026-07-18-subject-framework-class-profile.md` — shared Chemistry framework
  library, grade/branch selection, inherited class profile, purpose-specific
  context, teacher-approved adjustments, and framework search tools.
- `2026-07-18-subject-knowhow-class-core.md` — the immediate predecessor that
  combined subject know-how with the Anthropic lesson-production work.

This master plan retains all of those requirements in Tasks 1-8 and adds the
missing production-quality output contract. No reference plan is a competing
implementation plan; changes should be made here first.

### Conversation decision audit

The current scope and decisions carried forward from the project discussion are:

- Bavaria only; Gymnasium Chemistry; first fixture `chemie_9b`; branch NTG;
  verify the current Bavarian grade mapping from official sources before
  expanding beyond the fixture.
- Keep supplied PDFs as immutable raw sources and faithful Markdown under the
  trusted-source wiki layer; use LehrplanPLUS and KMK AHR material as authority.
- Keep the Karpathy-style Markdown wiki as the persistent compiled memory for
  this slice; do not introduce a separate curriculum database or live web
  crawler. A Docling-based ingestion CLI remains a later source-conversion
  track, outside the teacher-facing runtime.
- Use compact source metadata and TOCs in prompts; discover full source and
  framework sections progressively through typed search/read tools.
- Make subject know-how a class-setup capability with inherited shared base
  knowledge and a teacher-adjustable derived class profile.
- Port Anthropic's production procedure, differentiation workflow, subject
  reference structure, shared-content discipline, and evaluation approach;
  replace US curriculum/science guidance with Bavaria Chemistry 9 NTG.
- Keep memory updates teacher-approved and separate from planning; planning is
  read-only with respect to the wiki.
- Initial output is one final lesson artifact with teacher, student, and
  observation/update sections, not three separately persisted documents.
- Keep implementation prompts/evals, developer-facing documentation, and the
  generated lesson artifact in English during this build for one-language model
  development. Some source data remains German by necessity: official Bavaria
  curriculum labels, German chemical terms, and supplied German teaching
  materials retain their original wording with an English explanation where
  useful. Do not hardcode a universal `Use English` sentence; use explicit
  `artifact_language="en"` plus source-language metadata.
- Work remains on the single current branch; no new branches or commits unless
  explicitly requested.

### Two-dimensional base context

Every class-scoped workflow receives one labeled base context with two orthogonal dimensions:

1. **Teacher and class dimension:** global teacher profile, active class identity/course state, class signals, compact class memory, and workflow runtime state.
2. **Subject-expert dimension:** compact subject/grade/branch routing for every workflow; the full active subject expert (subject front door + selected immutable framework + class adjustment page + source TOC) for planning and other pedagogical workflows.

The global teacher profile is deliberately a separate `Teacher Layer`, not duplicated inside `Active Class Core`. It is still included in every main prompt through the base assembly, so the assistant remains personalized without making global teacher preferences look like class facts or copying them into class memory.

### Context recommendation

The inherited subject memory pack should be the class's **Active Subject Expert**:

- `chemie.md` is the compact shared subject front door and routing guide.
- `teaching_frameworks/index.md` is navigation only; it is not injected as a
  second copy of the framework body.
- The selected `key_summary.md` is immutable shared library knowledge. It is
  composed at runtime with `teaching_framework_adjustments.md`, which contains
  only approved class-level replacement/refinement rules.
- `search_subject_guidance` and `read_subject_guidance` search/read only the
  active subject framework root. The skill tells the model when to use the
  index, subject tools, or trusted-source tools.

The lesson-planning workflow then adds a new Anthropic-derived planning skill,
the active subject expert, and a bounded planning context. The planning context
should contain the recent taught sequence, misconception priorities, open loops,
and planning brief before deeper lesson reads. The current code already puts the
last three lesson summaries in Active Class Core and exposes `list_lessons`,
`read_lesson`, and `read_lesson_range`; `build_planning_query_pack` also exists
with a six-lesson sequence, but it is a legacy/derived builder and is not part
of the current live Plan prompt. Task 4 must decide whether to add its compact
orientation fields to Plan or rely on the existing core plus tools, without
stacking duplicate packs.

Update Memory keeps its existing task-specific context: previous lesson,
roster/course/open-loop continuity, `MemoryRuntime`, diary draft, evidence, and
teacher layer. It should not receive detailed subject pedagogy by default.

## Implementation Tasks

### Task A: Port the reusable Anthropic skill workflow and Bavaria Chemistry reference

**Files:**
- Create: `backend/app/teacher_agent/skills/lesson_planning_procedure.md`
- Create: `backend/app/teacher_agent/skills/lesson_differentiation_procedure.md`
- Create: `backend/app/teacher_agent/skills/chemie_bayern_reference.md`
- Create: `backend/app/teacher_agent/skills/loader.py`
- Modify: `backend/app/teacher_agent/skills/chemie_bayern.py`
- Modify: `backend/app/teacher_agent/prompt_assembly.py`
- Test: `backend/tests/test_skill_loader.py`, `backend/tests/test_prompts.py`

**Interfaces:**

```python
load_skill(name: Literal["lesson_planning", "differentiation"]) -> str
load_subject_reference(subject: str, grade: int, branch: str | None) -> str
compose_active_skill(subject: str, grade: int, branch: str | None, task: str) -> str
```

- [x] Reimplemented the planning procedure with Anthropic's six visible steps:
  **Step 0 Route**, **Step 1 Clarify**, **Step 2 Ground in trusted sources**,
  **Step 3 Build**, **Step 4 Draft offer**, and **Step 5 Output and
  completion**. Preserve their control flow and imperatives closely; translate
  only Learning Commons KG → trusted-source tools, Word documents → one
  `LessonArtifact`, and US K–12 science → Bavaria Chemistry 9 NTG.
- [x] Ported the structure of `k12-lesson-differentiation/SKILL.md`, including
  routed source-lesson identification, trusted-source grounding, the eight
  differentiation rules, a shared core question/evidence task, access and
  representation changes, language/grouping supports, fading scaffolds, and an
  accessibility check. The deliberate MVP divergence is one structured
  artifact rather than a teacher plan plus three separately rendered worksheets.
- [x] Replace US standards and Learning Commons assumptions with `curriculum_profile.md`, Bavaria trusted-source tools, the class-effective profile, and progressive wiki reads. Keep the source policy, copyright guardrails, and teacher-review boundaries.
- [x] Created `chemie_bayern_reference.md` as the direct functional equivalent
  of the science reference, limited to Bavaria Gymnasium Chemistry Grade 9 NTG:
  C8 prerequisite bridge, C9 course branches, investigation before explanation,
  model revision, observable goals, anticipated misconceptions with
  what/why/teacher move, representation rationale, safety, timing, look-fors,
  exit checks, and `LessonArtifact` mapping.
- [x] Keep Markdown files as the reviewable canonical skill/reference content; the loader supplies bounded text to prompt assembly and records source/function/size trace metadata. Do not duplicate the same long guidance in Python constants.
- [x] Add tests for required sections, subject/grade routing, absence of US-only assumptions, bounded loading, and prompt trace provenance.
- [x] Replace the provisional `PLAN_CHAT_SYSTEM` checklist rather than extending
  it incrementally. The Anthropic skill core becomes the authoritative
  procedure for routing, clarification, source grounding, pedagogy,
  differentiation, artifact construction, and evaluation.
- [x] Remove the rigid six-section output contract (`learning goals`, `lesson
  flow`, `warmup`, `practice tasks`, `homework`, `teacher notes`) from the
  production contract. Those are only possible sections inside the richer
  artifact, not the definition of lesson quality.
- [x] Remove the unconditional `Use English` behavior. Internal skill files,
  traces, tests, developer documentation, and the initial artifact use English;
  official Bavaria labels, German chemical terms, and supplied German source
  excerpts retain their source language through explicit metadata.
- [x] Run `cd backend; .venv\\Scripts\\python -m pytest tests/test_skill_loader.py tests/test_prompts.py -q`; keep the changes on the current branch.

### Task B: Add one structured final lesson artifact

**Files:**
- Create: `backend/app/teacher_agent/lesson_package.py`
- Create: `backend/app/teacher_agent/package_renderer.py`
- Modify: `backend/app/teacher_agent/models.py`
- Modify: `backend/app/teacher_agent/planning_state.py`
- Modify: `backend/app/services/plan_service.py`
- Create: `backend/tests/test_lesson_package.py`
- Create: `backend/tests/test_package_renderer.py`

**Interfaces:**

```python
class LessonArtifact(BaseModel):
    shared: LessonShared
    sections: list[ArtifactSection]
    consulted_sources: list[SourceRef]

class LearningGoal(BaseModel):
    statement: str
    knowledge: str | None
    practice: str | None
    meaning: str | None

class AnticipatedStudentIdea(BaseModel):
    idea: str
    why_it_may_appear: str
    teacher_move: str

class RepresentationChoice(BaseModel):
    representation: str
    purpose: str
    transition_to_or_from: str | None

class LessonShared(BaseModel):
    subject: str
    grade: int
    branch: str | None
    artifact_language: str
    duration_minutes: int
    phenomenon_or_context: str
    central_question: str
    big_idea: str
    learning_goals: list[LearningGoal]
    prerequisites: list[str]
    core_evidence_task: str
    anticipated_student_ideas: list[AnticipatedStudentIdea]
    representations: list[RepresentationChoice]
    differentiation_invariants: list[str]
    success_criteria: list[str]
    look_fors: list[str]
    vocabulary: list[str]
    safety_notes: list[str]
    exit_ticket: list[str]

class ArtifactSection(BaseModel):
    audience: Literal["teacher", "student", "observation"]
    title: str
    sections: list[DocumentSection]

render_markdown_artifact(artifact: LessonArtifact) -> str
```

`artifact_language` defaults to `en` for the current build. Source records
carry their own language metadata; German curriculum headings, chemical terms,
and quoted source labels may remain German inside an otherwise English artifact.

- [x] Make the agent produce one `LessonArtifact` as the source of truth; repeated learning goals, vocabulary, safety, and exit criteria must come from `shared` rather than independently generated sections.
- [x] Preserve the existing `PlanTurnOutput` and `plan_markdown` compatibility while adding artifact serialization to runtime state/API responses without storing full source bodies.
- [x] Render one Markdown artifact with exactly three top-level audience sections: teacher lesson plan, student materials, and observation/update capture. The observation section must map to existing memory-update fields (what was covered, participation/evidence, misconceptions, what worked, follow-up) and remain lightweight.
- [x] Enforce cross-section consistency: shared goals and the core evidence task appear identically where needed; student materials contain no teacher-only notes; safety statements are present for practical work; observation fields are actionable.
- [x] Require the quality dimensions currently absent from the provisional prompt: phenomenon/context before explanation, model revision, knowledge/practice/meaning goals, anticipated student ideas with why and teacher move, representation rationale, common evidence task across differentiation, formative look-fors, realistic timing, safety, and exit evidence.
- [x] Added deterministic validation for required audiences, duration, safety,
  source references, Chemie 9 NTG representation/differentiation fields, and
  student/teacher audience boundaries within the single artifact. Curriculum
  provenance is constrained to linked trusted sources at plan finalization.
- [x] Run `cd backend; .venv\\Scripts\\python -m pytest tests/test_lesson_package.py tests/test_package_renderer.py tests/test_api_plan.py -q`; keep the changes on the current branch.

### Task 1: Register and validate the source/document layer

**Files:**
- Modify: `backend/teacher_wiki/wiki/sources/bayern/lehrplanplus/chemie_8_ntg.md`
- Modify: `backend/teacher_wiki/wiki/sources/bayern/lehrplanplus/chemie_9_ntg.md`
- Modify: `backend/teacher_wiki/wiki/sources/bayern/kmk/chemie_ahr_chemie_2020.md`
- Create: `backend/teacher_wiki/raw/sources/bayern/` document manifest when PDFs arrive
- Modify: `backend/app/teacher_agent/wiki/trusted_sources.py`
- Test: `backend/tests/test_trusted_sources.py`

- [x] Add source metadata fields `source_format`, `ingestion_method`, `review_status`, and `artifact_path` while retaining canonical URL, retrieval date, and content hash.
- [x] Require stable section headings `## Section: <id> — <official heading>` in faithful Markdown; preserve page markers where available.
- [x] Add tests that source records parse, source IDs are stable, unlinked sources are rejected, and source bodies remain outside compact context.
- [x] Keep initial PDF conversion/manual Markdown acceptance outside runtime; a future Docling CLI may produce the same format.
- [x] Run `cd backend; .venv\Scripts\python -m pytest tests/test_trusted_sources.py -q`; keep the changes on the current branch.

### Task 2: Build the shared Chemistry framework library

**Files:**
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/index.md`
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/08/key_summary.md`
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/key_summary.md`
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/competencies.md`
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/differentiation.md`
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/representations_and_models.md`
- Modify: `backend/teacher_wiki/wiki/subjects/chemie.md`
- Test: `backend/tests/test_subject_frameworks.py`

- [x] Define frontmatter `framework_id`, `subject`, `grade`, `branch`, `authority`, `source_refs`, `status`, and `version`.
- [x] Make `index.md` navigation-only: grade slots, purposes, links, source IDs, and update status.
- [x] Compile Grade 8/9 summaries from the faithful source Markdown with original instructional wording, observable teacher-useful principles, prerequisites, difficulties, safety, and representation guidance.
- [x] Keep detailed competencies/differentiation/model pages on demand; do not copy student-facing curriculum passages.
- [x] Test that every framework source reference points to an existing source section and that `index.md` never embeds full page bodies.
- [x] Run focused tests and keep the changes on the current branch.

### Task 3: Implement grade selection and runtime effective-subject composition

**Files:**
- Create: `backend/app/teacher_agent/wiki/subject_frameworks.py`
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/teacher_agent/wiki/memory.py`
- Create: `backend/teacher_wiki/wiki/classes/chemie_9b_2026_27/memory/teaching_framework_adjustments.md`
- Test: `backend/tests/test_subject_frameworks.py`

**Interfaces:**

```python
load_framework_index(store, subject) -> FrameworkIndex
select_framework(store, subject, grade, branch) -> FrameworkSummary
framework_for_class(store, class_id) -> FrameworkSummary
build_active_subject_expert_context_trace(store, class_id, purpose) -> dict
```

- [x] Select Grade 9 NTG from `curriculum_profile.md`; treat C8 as prior learning and KMK as broader reference.
- [x] Reject path traversal and frameworks for another subject/branch unless explicitly allowed by the class route.
- [x] Keep the shared framework immutable and compose it at runtime with the bounded class adjustment page; no profile is generated or stored.
- [x] Inject the key summary and adjustment page exactly once as the active subject expert, with separate trace source labels.
- [x] Test missing/mismatched route handling, provenance, source references, no invented class facts, and class-core de-duplication.

### Task 4: Compose purpose-aware workflow contexts

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/context_limits.py`
- Modify: `backend/app/teacher_agent/wiki/context_packs.py`
- Modify: `backend/app/teacher_agent/prompt_assembly.py`
- Modify: `backend/app/services/plan_service.py`
- Modify: `backend/app/services/discussion_service.py`
- Modify: `backend/app/services/ingest_service.py`
- Modify: `backend/app/teacher_agent/agents.py`
- Test: `backend/tests/test_wiki_context_packs.py`, `backend/tests/test_prompts.py`

- [x] Add separate budgets for subject guide, framework index, grade summary, and class profile.
- [x] Add `build_subject_knowledge_trace(..., purpose=...)` and trace authorities `curated_guidance`, `teacher_adjusted_class_profile`, and `official_source_index`.
- [x] Add `build_active_subject_expert_context_trace(store, class_id, purpose)` and `build_base_assistant_context_trace(store, class_id, purpose)`; the base trace always includes the Teacher Layer, Active Class Core, and compact subject routing, while the full subject expert is purpose-selected.
- [x] Make Plan and differentiation receive `chemie.md` plus the compiled effective profile and source TOC; do not inject the Grade 9 summary separately. Make Update Memory omit detailed teaching framework bodies and include only subject/profile identity when needed; keep Discuss progressive and source-aware.
- [x] Give Plan a bounded planning-only orientation for recent taught sequence, misconception priorities, open loops, and planning brief. Reuse the existing recent-lesson snapshot and planning query-pack fields without stacking duplicate class packs; retain `list_lessons`/`read_lesson`/`read_lesson_range` for deeper evidence.
- [x] Test that oversized framework content is clamped per section and cannot displace class memory or user input.
- [x] Run context/prompt tests and keep the changes on the current branch.

### Task 5: Add progressive subject-guidance retrieval

**Files:**
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/teacher_agent/tools.py`
- Modify: `backend/app/teacher_agent/prompts.py`
- Test: `backend/tests/test_wiki_tools.py`, `backend/tests/test_prompts.py`

**Interfaces:**

```python
WikiStore.search_subject_guidance(class_id, query, max_results=8) -> list[dict]
WikiStore.read_subject_guidance(class_id, path) -> dict
search_subject_guidance(query, max_results=8)
read_subject_guidance(path)
```

- [x] Search only the active subject framework root and return path, grade, page, section, source refs, matched terms, and a bounded snippet.
- [x] Read only allowlisted active-subject framework paths and capture raw evidence behind `raw_ref`.
- [x] Update planning policy: summary/profile for orientation, subject tools for deeper pedagogy, trusted-source tools for exact official claims.
- [x] Test active-subject isolation, source provenance, bounded outputs, and path rejection.
- [x] Verify subject-guidance search tests and keep the changes on the current branch.

### Task 6: Add teacher-adjustable class know-how through HITL

**Files:**
- Modify: `backend/app/teacher_agent/memory_capture.py`
- Modify: `backend/app/services/memory_skills.py`
- Modify: `backend/app/teacher_agent/wiki/memory.py`
- Modify: `backend/app/teacher_agent/prompts.py`
- Modify: `backend/teacher_wiki/AGENTS.md`
- Modify: `docs/agent_contracts.md`
- Modify: `docs/memory_hierarchy.md`
- Test: `backend/tests/test_memory_capture.py`, `backend/tests/test_memory_apply.py`

- [x] Add `teaching_framework_adjustments.md` as a bounded, normal class-memory target.
- [x] Let `remember`/proposal stage teacher adjustments only when the teacher explicitly states a durable class teaching preference.
- [x] Require teacher approval before the dedicated adjustment page changes; direct writes to shared `teaching_frameworks` remain invalid.
- [x] Preserve the existing quote/evidence and review-only candidate contract; source/framework inheritance remains visible in prompt trace rather than duplicated in mutable memory.
- [x] Test normal planning has no hidden writes, rejected proposals cannot modify the page, and approved changes use the normal memory-apply path.

### Task 7: Validate the Anthropic-derived planning/differentiation contracts

**Files:**
- Modify: `backend/app/teacher_agent/skills/chemie_bayern.py`
- Modify: `backend/app/teacher_agent/planning_state.py`
- Modify: `backend/tests/evals/rubrics/chemie_bayern_planning.csv`
- Modify: `backend/tests/evals/rubrics/chemie_bayern_differentiation.csv`
- Create: `backend/tests/evals/rubrics/chemie_bayern_framework_context.csv`
- Test: `backend/tests/test_prompts.py`, `backend/tests/test_plan_context_manager.py`

- [x] Ensure the active profile is treated as teacher-adjusted guidance, not official curriculum authority.
- [x] Require prerequisites, observable targets, `what/why/teacher move` difficulties, evidence-generating tasks, exit checks, and safe realistic timing in planning.
- [x] Preserve one Chemistry question/context/core evidence task across differentiation routes; vary access, representation, language, grouping, and fading scaffolds.
- [x] Add P/R/O/M criteria for grade selection, profile provenance, source-read behavior, workflow isolation, and no source-body dumping.
- [x] Test prompt traces and state patches without storing full framework bodies in runtime state.
- [x] Treat Tasks A and B as the implementation of the reusable skill/output contract; this task adds the runtime integration and regression coverage rather than another parallel prompt implementation.
- [x] Run the evaluation tests and keep the changes on the current branch.

### Task 8: Index, document, and validate the complete system

**Files:**
- Modify: `backend/app/teacher_agent/wiki/indexing.py`
- Modify: `backend/teacher_wiki/index.md`
- Modify: `docs/agent_architecture.md`
- Modify: `docs/agent_contracts.md`
- Modify: `docs/memory_hierarchy.md`
- Modify: `implementation_plans/product_backlog.md`
- Test: `backend/tests/test_wiki_indexing.py` and the focused suite

- [x] Add root-index links for shared subject frameworks and each class adjustment page without embedding detailed bodies.
- [x] Document the four authority layers and the class-setup composition contract.
- [x] Document the structured lesson artifact as the single source for its three audience sections and explain which fields feed Update Memory.
- [x] Document that Update Memory excludes detailed teaching guidance by default.
- [x] Regenerate `backend/teacher_wiki/index.md` using `WikiStore.rebuild_index()`.
- [x] Run:
  `cd backend; .venv\Scripts\python -m pytest tests/test_skill_loader.py tests/test_lesson_package.py tests/test_package_renderer.py tests/test_trusted_sources.py tests/test_subject_frameworks.py tests/test_wiki_context_packs.py tests/test_wiki_tools.py tests/test_prompts.py tests/test_memory_capture.py tests/test_memory_apply.py tests/test_wiki_indexing.py -q`
- [x] Run focused Ruff checks and `git diff --check`.
- [x] Run the documentation/index checks and keep the changes on the current branch.

## Later Source Ingestion Track

After the three PDFs and faithful Markdown are available:

- Keep the PDFs under `raw/sources/bayern/` unchanged.
- Validate Markdown headings, page markers, section IDs, canonical URLs, and hashes.
- Replace compact seed source records with faithful source Markdown while preserving stable source IDs.
- Regenerate reviewed `teaching_frameworks` pages from the source records and teacher review.
- Add a future Docling-based CLI that produces the same Markdown/metadata contract; it must not be a teacher-facing runtime tool.

## Self-Review

- [x] The plan treats subject know-how as a class-setup capability, not merely a prompt addition.
- [x] Shared source/framework library, class-derived profile, and empirical class memory have separate authorities.
- [x] The class profile is teacher-adjustable but does not mutate shared library files.
- [x] Workflow-specific context prevents Update Memory from receiving unnecessary lesson-design guidance.
- [x] Anthropic workflow invariants are adapted without importing US curriculum or connector dependencies.
- [x] The plan explicitly distinguishes current partial Anthropic reuse from the missing full skill/reference/output port.
- [x] The initial output scope is bounded to one final artifact with teacher-plan, student-material, and lightweight observation/update sections.
- [x] The lesson artifact has one shared content model to prevent drift across sections.
- [x] Shared Grade 9 knowledge is inherited through a derived class profile; the base summary is never treated as independently editable class memory.
- [x] The context design separates the Teacher Layer, class-only Active Class Core, and purpose-selected Active Subject Expert while preserving personalized assistant behavior.
- [x] The plan distinguishes existing recent-lesson support (snapshot summaries plus lesson tools) from the missing live planning orientation and avoids reintroducing stacked query packs.
- [x] Manual PDF/Markdown ingestion is supported now and automated Docling ingestion is explicitly staged later.
