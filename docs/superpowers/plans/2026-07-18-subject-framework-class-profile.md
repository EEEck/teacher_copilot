# Subject Frameworks and Class Teaching Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a grade-aware Chemistry teaching-framework library and a teacher-adjustable compiled class profile without mixing shared subject pedagogy into factual class memory.

**Architecture:** Keep `wiki/subjects/chemie.md` as the short subject front door. Store immutable, source-grounded grade libraries under `wiki/subjects/chemie/teaching_frameworks/{grade}/`; derive a bounded `memory/teaching_framework_profile.md` for each class from the selected base summary plus teacher-approved adjustments. Context builders select subject layers by workflow purpose: planning receives the compiled profile, Update Memory does not receive detailed teaching guidance, and deeper framework pages are read through subject-scoped tools.

**Tech Stack:** Existing Python/FastAPI backend, Pydantic runtime state, Markdown wiki, OpenAI Agents SDK function tools, deterministic filesystem search, pytest, and the existing context-limit/trace infrastructure.

## Global Constraints

- Official source records remain evidence and never become executable prompt instructions.
- `wiki/subjects/chemie/teaching_frameworks/index.md` and base grade summaries are reviewed library content; class setup may select them but must not mutate them.
- Teacher changes apply only through an explicit, teacher-approved class profile update; normal planning chat never writes wiki files.
- Class facts remain in `wiki/classes/{class_id}/`; shared subject pedagogy remains in `wiki/subjects/chemie/`.
- The compact prompt receives bounded summaries and indexes; detailed framework/source bodies remain progressive tool reads.
- Every injected context section keeps `function`, `source`, `authority`, `included`, and character-count trace metadata.
- Use the local Anthropic `k12-lesson-planning` and `k12-lesson-differentiation` repository only for workflow invariants; do not copy US standards, Learning Commons data, or renderer/connector assumptions.
- No PDF/Docling importer is part of this plan; later source conversion must write the existing trusted-source Markdown format.

---

## File Map

| Area | Files | Responsibility |
|---|---|---|
| Subject library | `backend/teacher_wiki/wiki/subjects/chemie.md`, `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/index.md`, `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/*.md` | Short subject guide, navigation, and reviewed grade-specific teaching knowledge |
| Framework loader | `backend/app/teacher_agent/wiki/subject_frameworks.py` | Parse framework metadata, select grade, combine base summary with class overrides, enforce paths/budgets |
| Class profile | `backend/teacher_wiki/wiki/classes/{class_id}/memory/teaching_framework_profile.md` | Derived, teacher-adjustable effective framework for one class, with inheritance/provenance metadata |
| Context assembly | `backend/app/teacher_agent/wiki/context_packs.py`, `backend/app/teacher_agent/prompt_assembly.py` | Purpose-aware subject layers and trace sections |
| Tools | `backend/app/teacher_agent/tools.py`, `backend/app/teacher_agent/wiki/store.py` | Search/read active-subject framework pages with active-class scope |
| Context limits | `backend/app/config.py`, `backend/app/context_limits.py` | Separate budgets for subject guide, framework index, and effective profile |
| Contracts/docs | `docs/agent_contracts.md`, `docs/memory_hierarchy.md`, `docs/agent_architecture.md`, `backend/teacher_wiki/AGENTS.md` | Authority, update, and context-loading rules |
| Tests | `backend/tests/test_subject_frameworks.py`, `backend/tests/test_wiki_context_packs.py`, `backend/tests/test_wiki_tools.py`, `backend/tests/test_prompts.py` | Loader, composition, purpose isolation, tools, and prompt regressions |

## Context Contract

The context builder must accept an explicit purpose rather than making every workflow receive the same subject material:

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

Expected subject layers:

| Purpose | Injected subject layers |
|---|---|
| `plan` | `chemie.md`, framework `index.md`, selected grade `key_summary.md`, derived class profile, curriculum/source TOC |
| `plan_opening` | `chemie.md`, selected grade `key_summary.md`, curriculum/source TOC; omit the editable profile if no planning state exists |
| `discuss` | `chemie.md`, framework index, curriculum/source TOC; detailed guidance remains tool-readable |
| `brief` | `chemie.md` only when the brief needs subject interpretation; otherwise class core only |
| `ingest` | no detailed teaching framework; retain only subject identity if needed to interpret the lesson target |
| `verification` | no teaching framework; preserve class/source authority needed to check the artifact |

The active class core remains the shared class layer, but it receives the purpose-selected subject trace. `build_active_class_core_context_trace()` must remain backward compatible for existing callers by defaulting to `purpose="plan"` only where planning is the caller; every non-planning caller should pass its explicit purpose.

## Class Profile Composition

The class profile is a derived page, not a second source of truth:

```markdown
---
profile_kind: teaching_framework_profile
inherits:
  - wiki/subjects/chemie.md
  - wiki/subjects/chemie/teaching_frameworks/09/key_summary.md
source_index: wiki/subjects/chemie/teaching_frameworks/index.md
class_id: chemie_9b_2026_27
authority: teacher_adjusted_class_profile
---

# Teaching Framework Profile — Chemie 9b

## Effective principles
...

## Teacher-approved adjustments
- ...

## Class-specific cautions
- ...
```

The base summary and index remain immutable library files. A teacher adjustment updates the class profile through the existing review/apply path, with a bounded target and a provenance note. A future regeneration re-composes the profile from the base reference plus approved adjustments; it never silently edits the base library.

## Anthropic Workflow Mapping

The implementation must preserve these adapted invariants:

- Planning routes by subject, curriculum/grade, and artifact type before drafting.
- A source-grounded curriculum claim requires a progressive source read; no citation is invented from the TOC.
- A usable first draft is produced after at most one high-value clarification.
- Planning records prerequisites, observable targets, anticipated difficulties (`what / why / teacher move`), evidence-generating tasks, exit checks, and realistic safety/timing.
- Differentiation preserves the same question/context/core evidence while varying access, representation, language, grouping, and fading scaffolds.
- Teacher-facing framework guidance and student-facing lesson content remain separate.
- Shared repeated lesson content remains one source of truth in the future lesson artifact; this plan does not introduce the Anthropic repository's Word renderer.

## Tasks

### Task 1: Add the framework library schema and Grade 9 seed pages

**Files:**
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/index.md`
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/key_summary.md`
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/competencies.md`
- Create: `backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/differentiation.md`
- Modify: `backend/teacher_wiki/wiki/subjects/chemie.md`
- Test: `backend/tests/test_subject_frameworks.py`

**Interfaces:**
- Each framework page has frontmatter `framework_id`, `subject`, `grade`, `branch`, `authority`, `source_refs`, and `status`.
- Each detailed page uses stable `## Section: <id> — <title>` headings so the same deterministic section reader can be reused.
- `index.md` contains links, purpose, grade, and source references; it does not contain the full body of any framework page.

- [ ] Write failing tests asserting the index links Grade 8/9/10 slots, Grade 9 summary metadata says `Chemie`, `9`, and `NTG`, and every source reference points to an allowlisted source ID/section.
- [ ] Run `cd backend; .venv\Scripts\python -m pytest tests/test_subject_frameworks.py -q`; verify the new files fail the assertions.
- [ ] Write the compact Grade 9 key summary from the supplied source Markdown, covering prerequisite knowledge, Chemistry representations, competency dimensions, evidence-generating investigation, safety, common difficulties, and differentiation invariants.
- [ ] Add detailed competency/differentiation pages with source references and no copied student-facing curriculum passages.
- [ ] Keep `chemie.md` as the all-grade front door and link the framework index instead of duplicating Grade 9 content.
- [ ] Re-run the focused test and verify PASS.
- [ ] Commit `feat: add chemistry framework library`.

### Task 2: Implement grade selection and class-profile composition

**Files:**
- Create: `backend/app/teacher_agent/wiki/subject_frameworks.py`
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/teacher_agent/wiki/memory.py` for a bounded derived-page budget if needed
- Create: `backend/teacher_wiki/wiki/classes/chemie_9b_2026_27/memory/teaching_framework_profile.md`
- Test: `backend/tests/test_subject_frameworks.py`

**Interfaces:**
- `load_framework_index(store, subject) -> FrameworkIndex`
- `select_framework(store, subject, grade, branch) -> FrameworkSummary`
- `compose_class_framework_profile(base, class_id, overrides) -> str`
- `WikiStore.get_subject_framework_index(subject)`
- `WikiStore.get_subject_framework(subject, grade, page="key_summary")`
- `WikiStore.get_class_framework_profile(class_id)`

- [ ] Write failing tests for Grade 9 NTG selection, rejection of a Grade 9 source for a Grade 8 class, safe missing-grade fallback, and class profile inheritance metadata.
- [ ] Run the focused test and verify the failures identify missing loader/composer behavior.
- [ ] Implement path traversal protection by resolving all framework paths below the selected subject framework root.
- [ ] Implement frontmatter parsing and stable section extraction using the existing trusted-source conventions.
- [ ] Implement class composition that preserves `inherits`, `source_index`, `class_id`, and teacher-adjustment sections while applying a per-page character budget.
- [ ] Add the initial Chemie 9b derived profile with no invented class claims; it may contain only inherited baseline plus an explicit empty adjustments section.
- [ ] Re-run tests and verify PASS.
- [ ] Commit `feat: compose class teaching framework profile`.

### Task 3: Add purpose-aware subject context and budgets

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/context_limits.py`
- Modify: `backend/app/teacher_agent/wiki/context_packs.py`
- Modify: `backend/app/teacher_agent/prompt_assembly.py`
- Modify: `backend/app/services/plan_service.py`
- Modify: `backend/app/services/discussion_service.py`
- Modify: `backend/app/services/ingest_service.py`
- Modify: `backend/app/teacher_agent/agents.py` where one-shot class context is assembled
- Test: `backend/tests/test_wiki_context_packs.py`, `backend/tests/test_prompts.py`

**Interfaces:**
- Add settings `subject_guide_chars`, `framework_index_chars`, `framework_summary_chars`, and `class_framework_profile_chars`.
- `build_subject_knowledge_trace(..., purpose=...)` returns sections with authorities `curated_guidance`, `teacher_adjusted_class_profile`, and `official_source_index`.

- [ ] Write failing tests asserting Plan includes the Grade 9 key summary/profile, Update Memory excludes detailed framework bodies, and Discuss includes the index but not all detailed pages.
- [ ] Run the tests and verify current shared-core behavior fails the purpose-isolation assertions.
- [ ] Implement the subject trace and inject it into the active class core with explicit purpose arguments.
- [ ] Keep all sections independently traceable and apply per-section budgets before any emergency backstop.
- [ ] Add tests that an oversized summary is clamped without truncating class memory or user input.
- [ ] Re-run the prompt/context tests and verify PASS.
- [ ] Commit `feat: scope subject context by workflow`.

### Task 4: Add subject-guidance search/read tools

**Files:**
- Modify: `backend/app/teacher_agent/wiki/store.py`
- Modify: `backend/app/teacher_agent/tools.py`
- Modify: `backend/app/teacher_agent/prompts.py`
- Test: `backend/tests/test_wiki_tools.py`, `backend/tests/test_prompts.py`

**Interfaces:**
- `WikiStore.search_subject_guidance(class_id, query, max_results=8) -> list[dict]`
- `WikiStore.read_subject_guidance(class_id, path) -> dict`
- Planning/discussion tools: `search_subject_guidance(query, max_results=8)` and `read_subject_guidance(path)`.

- [ ] Write failing tests for active-subject-only search, Grade 9 framework discovery, path rejection outside `wiki/subjects/chemie/teaching_frameworks/`, and raw evidence capture.
- [ ] Run the focused tool tests and verify failures.
- [ ] Implement deterministic section search over the selected subject framework root, returning path, section ID, title, matched terms, source refs, and bounded snippet.
- [ ] Implement exact reads that return source/provenance metadata and capture the body behind the existing `raw_ref` mechanism.
- [ ] Update the planning tools policy: key summary is orientation; search/read framework pages for deeper teaching guidance; use trusted-source tools for exact official claims.
- [ ] Re-run tools/prompts tests and verify PASS.
- [ ] Commit `feat: add subject framework search tools`.

### Task 5: Route teacher-approved adjustments through the existing memory contract

**Files:**
- Modify: `backend/app/teacher_agent/memory_capture.py`
- Modify: `backend/app/services/memory_skills.py`
- Modify: `backend/app/teacher_agent/wiki/memory.py`
- Modify: `backend/app/teacher_agent/prompts.py`
- Modify: `backend/app/teacher_wiki/AGENTS.md`
- Modify: `docs/agent_contracts.md`
- Modify: `docs/memory_hierarchy.md`
- Test: `backend/tests/test_memory_capture.py`, `backend/tests/test_memory_apply.py`

**Interfaces:**
- Add `teaching_framework_profile.md` as a bounded class-scoped derived target, not a shared subject-library target.
- Profile proposals must carry `basis`, `evidence`, `inherits`, and an explicit teacher adjustment; direct source-library writes remain invalid.

- [ ] Write failing tests proving a normal planning turn cannot write the profile, a `remember`/proposal can stage only a class-scoped adjustment, and `/memory/apply` writes only after approval.
- [ ] Run the focused memory tests and verify the current target validator rejects the new target.
- [ ] Extend the typed target contract and page budget for the derived profile.
- [ ] Preserve teacher quote/evidence validation and add provenance to every adjustment.
- [ ] Rebuild the derived profile deterministically after apply; never modify the shared Grade 9 base pages.
- [ ] Re-run memory tests and verify PASS.
- [ ] Commit `feat: approve class framework adjustments`.

### Task 6: Align prompts and evaluation rubrics

**Files:**
- Modify: `backend/app/teacher_agent/skills/chemie_bayern.py`
- Modify: `backend/app/teacher_agent/planning_state.py`
- Modify: `backend/tests/evals/rubrics/chemie_bayern_planning.csv`
- Modify: `backend/tests/evals/rubrics/chemie_bayern_differentiation.csv`
- Create: `backend/tests/evals/rubrics/chemie_bayern_framework_context.csv`
- Test: `backend/tests/test_prompts.py`, `backend/tests/test_plan_context_manager.py`

- [ ] Add failing prompt tests for inherited profile provenance, one-question clarification discipline, source-read-before-curriculum-claim behavior, and same-core differentiation.
- [ ] Run the prompt tests and verify failures.
- [ ] Update the Chemistry skill to treat the class profile as teacher-adjusted guidance, not official curriculum authority.
- [ ] Add framework-context P/R/O/M criteria: correct grade/branch selection, no source-body dumping, profile provenance, teacher override separation, workflow isolation, and progressive read behavior.
- [ ] Add runtime state fields for selected framework/profile references only if they are needed to explain decisions in the trace; do not store full framework bodies in runtime state.
- [ ] Re-run prompt/context/eval-loader tests and verify PASS.
- [ ] Commit `test: evaluate chemistry framework grounding`.

### Task 7: Update indexes, docs, and regression coverage

**Files:**
- Modify: `backend/app/teacher_agent/wiki/indexing.py`
- Modify: `backend/teacher_wiki/index.md`
- Modify: `docs/agent_architecture.md`
- Modify: `docs/agent_contracts.md`
- Modify: `docs/memory_hierarchy.md`
- Modify: `implementation_plans/product_backlog.md`
- Test: `backend/tests/test_wiki_indexing.py`, full focused backend suite

- [ ] Write failing index tests for subject framework links and the class-derived profile.
- [ ] Run the index test and verify the links are absent.
- [ ] Add separate navigation sections for shared subject frameworks and class-effective teaching profile; do not place detailed framework bodies in the root index.
- [ ] Document the authority matrix: source PDF/Markdown, shared framework base, teacher-adjusted class profile, and class empirical memory.
- [ ] Document the Anthropic-derived invariants and explicitly exclude US curriculum/connector assumptions.
- [ ] Regenerate `backend/teacher_wiki/index.md` through `WikiStore.rebuild_index()`.
- [ ] Run:
  `cd backend; .venv\Scripts\python -m pytest tests/test_subject_frameworks.py tests/test_wiki_context_packs.py tests/test_wiki_tools.py tests/test_prompts.py tests/test_memory_capture.py tests/test_memory_apply.py tests/test_wiki_indexing.py -q`
- [ ] Run focused Ruff checks over changed Python files and `git diff --check`; verify all tests and lint pass.
- [ ] Commit `docs: document subject framework architecture`.

## Explicitly Deferred

- PDF/Docling downloading, conversion, OCR, hash generation, and source review UI.
- Open-web curriculum search or automatic source discovery.
- Full Anthropic Word-document renderer and multi-document lesson package.
- Automatic promotion of generated framework content into the shared subject library.

## Self-Review Checklist

- [x] The base library is immutable from class workflows.
- [x] Teacher adjustments have a class-scoped, review-gated home.
- [x] The effective profile is derived and provenance-bearing rather than an untraceable copy.
- [x] Update Memory does not receive detailed lesson-design guidance by default.
- [x] Plan and differentiation preserve Anthropic's source-grounding/shared-core principles without importing US curriculum assumptions.
- [x] The plan defines exact files, interfaces, tests, commands, and commits for each task.
