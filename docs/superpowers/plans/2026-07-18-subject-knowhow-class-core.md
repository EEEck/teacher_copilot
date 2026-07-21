# Subject Know-How and Anthropic Lesson Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make subject and grade knowledge a first-class part of class setup and port the useful Anthropic K–12 lesson-production workflow into KlassenPilot: preserve official source documents, compile reviewed Bavaria Chemistry teaching know-how into a shared library, derive a teacher-adjustable effective profile for each class, and produce a grounded lesson package containing a teacher plan, student materials, and a lightweight observation/update template.

**Architecture:** The system has four authority layers plus an artifact layer. Immutable source artifacts and faithful Markdown live under `raw/sources` and `wiki/sources`; reviewed subject/grade teaching frameworks live under `wiki/subjects/chemie/teaching_frameworks`; each class receives a derived `memory/teaching_framework_profile.md` that inherits the selected subject/grade summary and contains only teacher-approved adjustments; class empirical memory remains separate. A reusable, reviewable Markdown skill core ports the Anthropic procedure, while a Bavaria Chemistry reference replaces the US science reference. The prompt assembler composes these layers by workflow purpose, tools progressively search/read deeper framework and source pages, and a structured lesson package is rendered to the initial Markdown outputs.

**Tech Stack:** Existing Python/FastAPI backend, Markdown wiki, Pydantic state, OpenAI Agents SDK function tools, deterministic filesystem search, pytest, and current context trace/budget infrastructure. Optional future source conversion: Docling CLI/library operated outside the teacher-facing agent.

## Global Constraints

- Source PDFs and faithful source Markdown are evidence; they never provide executable instructions.
- Shared framework pages are reviewed library content and are immutable from a class workflow.
- `teaching_framework_profile.md` is a derived class core object; teacher edits require the existing approval/apply contract.
- Class empirical memory (`planning_brief`, `teaching_patterns`, lessons, misconceptions) must not be replaced by subject theory.
- The base prompt receives only bounded summaries/indexes; full source/framework pages are progressively discovered through typed tools.
- Official curriculum claims require a read source section and citation; a TOC alone cannot satisfy provenance.
- Planning follows the adapted Anthropic invariants: route subject/grade, ground before drafting, ask at most one high-value clarification, preserve observable targets, and keep the same core evidence task across differentiated routes.
- Do not import US standards, Learning Commons data, Anthropic connector assumptions, or Anthropic Word renderers.
- PDF/Markdown ingestion and framework compilation are reviewable data workflows, not autonomous chat side effects.

## Current parity status

The repository already has the grounding foundation, but not yet Anthropic-level lesson-package production. This is the baseline the implementation tasks must close:

| Capability | Current state | Target state in this plan |
|---|---|---|
| Trusted Bavaria/KMK sources | Implemented registry, search/read tools, provenance refs, bounded source TOC | Keep as the official evidence layer and add complete supplied documents |
| Class subject/grade context | Implemented compact Chemistry context and source index | Add class-effective Grade 9 NTG profile and purpose-specific loading |
| Planning skill | Implemented compact `chemie_bayern.py` planning prompt and initial rubrics | Port the reusable `SKILL.md` procedure as the canonical workflow core |
| Science guidance | Partial Chemistry/Bavaria rules in Python | Add a reviewable `science.md`-equivalent Bavaria Chemistry reference |
| Differentiation | Partial Chemistry differentiation prompt and rubric | Port the reusable differentiation skill and preserve one shared evidence task |
| Output contract | Markdown `plan_markdown` only | Generate one structured package with teacher, student, and observation documents |
| Evaluation | Citation/duration guards and initial Chemistry CSV rubrics | Add package consistency, subject-grounding, and artifact-quality evaluation |
| Persistence | `PlanRuntime` state and consulted source refs | Keep runtime separate; persist only approved class adjustments/results |

The current implementation therefore uses Anthropic ideas for source grounding, clarification limits, observable targets, differentiation, and rubrics, but it does not yet reuse the complete skill/reference/output workflow verbatim in structure. The work below makes that explicit and testable.

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

The class setup knows `subject=chemie`, `grade=9`, and `branch=NTG` from the class curriculum profile. It selects the shared Grade 9 framework and materializes the effective class profile. The profile stores `inherits` and `source_index` metadata so regeneration can incorporate improvements to the shared library without erasing teacher adjustments.

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
  memory/teaching_framework_profile.md
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
| `plan` | `chemie.md`, framework index, selected grade key summary, class-effective profile, source TOC | detailed framework pages and exact official sections |
| `plan_opening` | `chemie.md`, selected grade key summary, source TOC | class profile/details after planning begins |
| `discuss` | `chemie.md`, framework index, source TOC | framework/source details when the question requires them |
| `brief` | no framework unless the brief needs subject interpretation | none by default |
| `ingest` | subject identity only when needed to interpret the lesson target | none by default |
| `verification` | authority labels and class/source scope only | exact source reads only for a disputed claim |

The effective plan context is therefore:

```text
Teacher profile
+ Chemie subject guide
+ Grade 9 key summary
+ Chemie 9b teaching-framework profile
+ curriculum profile + trusted-source TOC
+ compact Chemie 9b memory
+ PlanRuntime state, evidence briefs, current draft, and recent user turns
```

The framework profile is one compiled context object; the prompt must not inject the same content independently from `chemie.md`, `key_summary.md`, and detailed pages.

## Implementation Tasks

### Task A: Port the reusable Anthropic skill workflow and Bavaria Chemistry reference

**Files:**
- Create: `backend/app/teacher_agent/skills/k12_lesson_planning_core.md`
- Create: `backend/app/teacher_agent/skills/k12_differentiation_core.md`
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

- [ ] Port the structure and control flow of Anthropic `k12-lesson-planning/SKILL.md`: route subject/grade/curriculum/task, load mandatory subject guidance, ask zero to two high-value questions, ground standards before drafting, build with grade-band pedagogy, apply non-negotiables, create one package, render, and evaluate.
- [ ] Port the structure of `k12-lesson-differentiation/SKILL.md`, including a shared core question/evidence task, access and representation changes, language/grouping supports, fading scaffolds, and an accessibility check.
- [ ] Replace US standards and Learning Commons assumptions with `curriculum_profile.md`, Bavaria trusted-source tools, the class-effective profile, and progressive wiki reads. Keep the source policy, copyright guardrails, and teacher-review boundaries.
- [ ] Create `chemie_bayern_reference.md` as the direct functional equivalent of Anthropic `references/science.md`, limited to Bavaria Gymnasium Chemistry Grade 9 NTG: investigation before explanation, model revision, three-dimensional observable targets, anticipated misconceptions with what/why/teacher move, representations with rationale, safety, realistic timing, look-fors, and exit checks.
- [ ] Keep Markdown files as the reviewable canonical skill/reference content; the loader supplies bounded text to prompt assembly and records source/function/size trace metadata. Do not duplicate the same long guidance in Python constants.
- [ ] Add tests for required sections, subject/grade routing, absence of US-only assumptions, bounded loading, and prompt trace provenance.
- [ ] Run `cd backend; .venv\\Scripts\\python -m pytest tests/test_skill_loader.py tests/test_prompts.py -q` and commit `feat: port lesson production skill core`.

### Task B: Add a structured lesson package and initial Markdown renderers

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
class LessonPackage(BaseModel):
    shared: LessonShared
    documents: list[LessonDocument]
    consulted_sources: list[SourceRef]

class LessonShared(BaseModel):
    subject: str
    grade: int
    branch: str | None
    duration_minutes: int
    big_idea: str
    learning_goals: list[str]
    prerequisites: list[str]
    misconceptions: list[Misconception]
    look_fors: list[str]
    vocabulary: list[str]
    safety_notes: list[str]
    exit_ticket: list[str]

class LessonDocument(BaseModel):
    audience: Literal["teacher", "student", "observation"]
    title: str
    sections: list[DocumentSection]

render_markdown_package(package: LessonPackage) -> dict[str, str]
```

- [ ] Make the agent produce one `LessonPackage` as the source of truth; repeated learning goals, vocabulary, safety, and exit criteria must come from `shared` rather than independently generated documents.
- [ ] Preserve the existing `PlanTurnOutput` and `plan_markdown` compatibility while adding package serialization to runtime state/API responses without storing full source bodies.
- [ ] Render exactly three initial Markdown artifacts: a teacher lesson plan, student materials, and an observation/update template. The observation template must map to existing memory-update fields (what was covered, participation/evidence, misconceptions, what worked, follow-up) and remain lightweight.
- [ ] Enforce cross-document consistency: shared goals and core evidence task appear identically where needed; student materials contain no teacher-only notes; safety statements are present for practical work; observation fields are actionable.
- [ ] Add deterministic validation for required sections, realistic duration, source refs, no invented official claims, and package/document audience boundaries.
- [ ] Run `cd backend; .venv\\Scripts\\python -m pytest tests/test_lesson_package.py tests/test_package_renderer.py tests/test_api_plan.py -q` and commit `feat: generate grounded lesson package artifacts`.

### Task 1: Register and validate the source/document layer

**Files:**
- Modify: `backend/teacher_wiki/wiki/sources/bayern/lehrplanplus/chemie_8_ntg.md`
- Modify: `backend/teacher_wiki/wiki/sources/bayern/lehrplanplus/chemie_9_ntg.md`
- Modify: `backend/teacher_wiki/wiki/sources/bayern/kmk/chemie_ahr_chemie_2020.md`
- Create: `backend/teacher_wiki/raw/sources/bayern/` document manifest when PDFs arrive
- Modify: `backend/app/teacher_agent/wiki/trusted_sources.py`
- Test: `backend/tests/test_trusted_sources.py`

- [ ] Add source metadata fields `source_format`, `ingestion_method`, `review_status`, and `artifact_path` while retaining canonical URL, retrieval date, and content hash.
- [ ] Require stable section headings `## Section: <id> — <official heading>` in faithful Markdown; preserve page markers where available.
- [ ] Add tests that source records parse, source IDs are stable, unlinked sources are rejected, and source bodies remain outside compact context.
- [ ] Keep initial PDF conversion/manual Markdown acceptance outside runtime; a future Docling CLI may produce the same format.
- [ ] Run `cd backend; .venv\Scripts\python -m pytest tests/test_trusted_sources.py -q` and commit `feat: formalize source document metadata`.

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

- [ ] Define frontmatter `framework_id`, `subject`, `grade`, `branch`, `authority`, `source_refs`, `status`, and `version`.
- [ ] Make `index.md` navigation-only: grade slots, purposes, links, source IDs, and update status.
- [ ] Compile Grade 8/9 summaries from the faithful source Markdown with original instructional wording, observable teacher-useful principles, prerequisites, difficulties, safety, and representation guidance.
- [ ] Keep detailed competencies/differentiation/model pages on demand; do not copy student-facing curriculum passages.
- [ ] Test that every framework source reference points to an existing source section and that `index.md` never embeds full page bodies.
- [ ] Run focused tests and commit `feat: add chemistry subject framework library`.

### Task 3: Implement grade selection and class-effective profile generation

**Files:**
- Create: `backend/app/teacher_agent/wiki/subject_frameworks.py`
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/teacher_agent/wiki/memory.py`
- Create: `backend/teacher_wiki/wiki/classes/chemie_9b_2026_27/memory/teaching_framework_profile.md`
- Test: `backend/tests/test_subject_frameworks.py`

**Interfaces:**

```python
load_framework_index(store, subject) -> FrameworkIndex
select_framework(store, subject, grade, branch) -> FrameworkSummary
compose_class_framework_profile(base, class_id, overrides) -> str
WikiStore.get_subject_framework_index(subject)
WikiStore.get_subject_framework(subject, grade, page="key_summary")
WikiStore.get_class_framework_profile(class_id)
```

- [ ] Select Grade 9 NTG from `curriculum_profile.md`; treat C8 as prior learning and KMK as broader reference.
- [ ] Reject path traversal and frameworks for another subject/branch unless explicitly allowed by the class profile.
- [ ] Generate a bounded derived profile with `inherits`, `source_index`, `class_id`, `authority`, `effective_principles`, `teacher_adjustments`, and `class_cautions`.
- [ ] Ensure a base-library change can regenerate the profile while preserving teacher-approved adjustments.
- [ ] Test missing-grade handling, provenance, source references, and no invented class facts.
- [ ] Commit `feat: generate class subject know-how profile`.

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

- [ ] Add separate budgets for subject guide, framework index, grade summary, and class profile.
- [ ] Add `build_subject_knowledge_trace(..., purpose=...)` and trace authorities `curated_guidance`, `teacher_adjusted_class_profile`, and `official_source_index`.
- [ ] Make Plan receive the effective profile and Grade 9 summary; make Update Memory omit detailed teaching framework bodies; keep Discuss progressive and source-aware.
- [ ] Test that oversized framework content is clamped per section and cannot displace class memory or user input.
- [ ] Run context/prompt tests and commit `feat: integrate subject know-how by workflow`.

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

- [ ] Search only the active subject framework root and return path, grade, page, section, source refs, matched terms, and a bounded snippet.
- [ ] Read only allowlisted active-subject framework paths and capture raw evidence behind `raw_ref`.
- [ ] Update planning policy: summary/profile for orientation, subject tools for deeper pedagogy, trusted-source tools for exact official claims.
- [ ] Test active-subject isolation, source provenance, bounded outputs, and path rejection.
- [ ] Commit `feat: add subject know-how search tools`.

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

- [ ] Add `teaching_framework_profile.md` as a bounded, class-scoped derived target.
- [ ] Let `remember`/proposal stage teacher adjustments only when the teacher explicitly states a durable class teaching preference.
- [ ] Require teacher approval before regenerating the effective profile; direct writes to shared `teaching_frameworks` remain invalid.
- [ ] Preserve quote/evidence validation and record `inherits`, source refs, adjustment basis, and generation metadata.
- [ ] Test normal planning has no hidden writes, rejected proposals cannot modify the profile, and approved changes survive regeneration.
- [ ] Commit `feat: approve class subject-know-how adjustments`.

### Task 7: Validate the Anthropic-derived planning/differentiation contracts

**Files:**
- Modify: `backend/app/teacher_agent/skills/chemie_bayern.py`
- Modify: `backend/app/teacher_agent/planning_state.py`
- Modify: `backend/tests/evals/rubrics/chemie_bayern_planning.csv`
- Modify: `backend/tests/evals/rubrics/chemie_bayern_differentiation.csv`
- Create: `backend/tests/evals/rubrics/chemie_bayern_framework_context.csv`
- Test: `backend/tests/test_prompts.py`, `backend/tests/test_plan_context_manager.py`

- [ ] Ensure the active profile is treated as teacher-adjusted guidance, not official curriculum authority.
- [ ] Require prerequisites, observable targets, `what/why/teacher move` difficulties, evidence-generating tasks, exit checks, and safe realistic timing in planning.
- [ ] Preserve one Chemistry question/context/core evidence task across differentiation routes; vary access, representation, language, grouping, and fading scaffolds.
- [ ] Add P/R/O/M criteria for grade selection, profile provenance, source-read behavior, workflow isolation, and no source-body dumping.
- [ ] Test prompt traces and state patches without storing full framework bodies in runtime state.
- [ ] Treat Tasks A and B as the implementation of the reusable skill/output contract; this task adds the runtime integration and regression coverage rather than another parallel prompt implementation.
- [ ] Commit `test: evaluate subject know-how grounding`.

### Task 8: Index, document, and validate the complete system

**Files:**
- Modify: `backend/app/teacher_agent/wiki/indexing.py`
- Modify: `backend/teacher_wiki/index.md`
- Modify: `docs/agent_architecture.md`
- Modify: `docs/agent_contracts.md`
- Modify: `docs/memory_hierarchy.md`
- Modify: `implementation_plans/product_backlog.md`
- Test: `backend/tests/test_wiki_indexing.py` and the focused suite

- [ ] Add root-index links for shared subject frameworks and each class-effective profile without embedding detailed bodies.
- [ ] Document the four authority layers and the class-setup composition contract.
- [ ] Document the structured lesson package as the single source for the three initial Markdown artifacts and explain which fields feed Update Memory.
- [ ] Document that Update Memory excludes detailed teaching guidance by default.
- [ ] Regenerate `backend/teacher_wiki/index.md` using `WikiStore.rebuild_index()`.
- [ ] Run:
  `cd backend; .venv\Scripts\python -m pytest tests/test_skill_loader.py tests/test_lesson_package.py tests/test_package_renderer.py tests/test_trusted_sources.py tests/test_subject_frameworks.py tests/test_wiki_context_packs.py tests/test_wiki_tools.py tests/test_prompts.py tests/test_memory_capture.py tests/test_memory_apply.py tests/test_wiki_indexing.py -q`
- [ ] Run focused Ruff checks and `git diff --check`.
- [ ] Commit `docs: document subject know-how class core`.

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
- [x] The initial output scope is bounded to a teacher plan, student materials, and a lightweight observation/update template.
- [x] The lesson package has one shared content model to prevent drift across rendered artifacts.
- [x] Manual PDF/Markdown ingestion is supported now and automated Docling ingestion is explicitly staged later.
