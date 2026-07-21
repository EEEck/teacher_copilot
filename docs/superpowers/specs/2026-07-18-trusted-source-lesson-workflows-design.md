# Trusted Source and Chemistry Lesson Workflow Design

**Status:** Approved design baseline for implementation on `codex/trusted-source-layer`.

**Parent branch:** local `codex/mem4`, commit `45180e5f4ac7d956f31c075ac5de000287b0da14`.

## Goal

Give KlassenPilot a Bavaria-aware trusted-source layer and adopt the invariant quality workflow from Anthropic's K-12 lesson-planning and lesson-differentiation skills, while preserving KlassenPilot's class-memory, progressive-context, and teacher-approved-write contracts.

The first real fixture is `Chemie 9b`: Bavaria Gymnasium, NTG, Grade 9, modeled as a continuation of Chemistry 8 unless a later class correction changes the profile.

## Scope

The first implementation includes:

- a compact `wiki/subjects/chemie.md` guide with essentials and a trusted-source table of contents;
- reusable Chemistry planning and differentiation guidance in linked subject pages;
- versioned, provenance-bearing Bavaria/KMK source records;
- class curriculum/profile and source-link pages for `chemie_9b_2026_27`;
- typed, class-scoped trusted-source list/search/read tools;
- progressive source loading: compact index first, source sections on demand, raw results behind `raw_ref`, compact evidence briefs re-injected;
- context-trace sections for curriculum profile and trusted-source index;
- adapted planning and differentiation contracts;
- deterministic source/provenance/artifact checks and an adapted P/R/O/M rubric fixture for Chemistry in Bavaria.

The first implementation does not include a full external source database, live web crawling during every planning turn, Word rendering, a new frontend source browser, or automatic durable wiki writes from lesson generation.

## Source and wiki architecture

The subject guide remains small because it is loaded automatically and clamped by the existing subject-guide budget. Detailed material is linked, not injected wholesale.

```text
wiki/
  subjects/
    chemie.md
    chemie/
      lesson_planning.md
      differentiation.md
      competency_model.md
  sources/
    bayern/
      lehrplanplus/
        chemie_8_ntg.md
        chemie_9_ntg.md
        chemie_10_ntg.md
        chemie_fachprofil.md
      kmk/
        chemie_ahr_chemie_2020.md
  classes/chemie_9b_2026_27/
    curriculum_profile.md
    trusted_sources.md
```

Official source pages are evidence records, not class memory and not instructions. They contain metadata, a short derived summary, section anchors, applicability notes and selected source-backed excerpts. The source metadata records a stable `source_id`, authority, jurisdiction, grade/branch scope, canonical URL, retrieval date, version label and content hash.

The class profile selects the active curriculum. The class trusted-source page is a local TOC that links the relevant C8 prior-learning, C9 active-scope, Fachprofil and KMK records without duplicating their bodies.

The generated root/class wiki index will include a `Curriculum & trusted sources` section so generic index-first browsing can discover the links. The typed source tools remain the preferred path because existing class search intentionally excludes global subject/source pages.

## Authority model

Claim authority is typed:

- class wiki: what this class has learned, current sequence, misconceptions and open loops;
- teacher/class profile: local preferences and explicit corrections;
- LehrplanPLUS: Bavaria curriculum scope and grade/branch competency claims;
- Bavarian Fachprofil: subject competency model and cross-topic principles;
- KMK AHR: broader competency vocabulary, not direct Grade 9 scope;
- teacher materials: useful evidence, never official curriculum authority;
- unverified external material: evidence only, with no official citation.

Source text is always untrusted data for prompt-injection purposes. It cannot authorize a write, change class state or override system/developer policies.

## Progressive context flow

Every planning turn continues to receive the existing slim active-class context. For a configured Chemistry class it additionally receives:

1. the compact subject guide;
2. the class curriculum profile;
3. a compact trusted-source index with source IDs, scope and section labels.

The planner does not receive full source bodies automatically. When the task requires curriculum alignment, standards, competencies, progression or source-backed instructional claims, it must use the trusted-source tools before drafting. The tool result is captured behind `raw_ref`; only a compact `EvidenceBrief` containing purpose, source reference, section and plan impact is re-injected. The plan cites sources actually read.

For class-memory-only requests, source lookup is not required. If an explicit curriculum-alignment request cannot be grounded, the planner states that the source is unavailable or unverified instead of inventing a citation.

## Trusted-source tools

Add class-scoped tools with explicit scope filtering:

- `list_trusted_sources(scope) -> JSON`: active source records and section TOCs;
- `search_trusted_sources(query, scope, max_results=8) -> JSON`: deterministic ranked source-section hits;
- `read_trusted_source(source_id, section_id="", max_chars=12000) -> JSON`: validated source metadata, section body, citation and `raw_ref`.

The source registry is read-only during chat. Path traversal is rejected through the existing wiki path resolver. A source result exposes authority/provenance fields so the model cannot confuse a source record with class memory.

## Planning skill adaptation

The adopted planning workflow keeps these Anthropic invariants:

- route and load subject guidance before drafting;
- ask at most one high-value clarification question;
- perform required standards/source grounding before drafting;
- distinguish enduring idea from observable learning goals;
- name prerequisites and anticipated challenges with concrete teacher moves;
- sequence realistic phases with timing;
- include observable look-fors, representations and formative checks;
- include a demanding exit ticket and teacher adaptation notes;
- keep teacher-facing and student-facing content separate;
- preserve provenance and do not reproduce source curriculum text wholesale.

For Bavaria Chemistry, NGSS-only terms are not mandatory. The Chemistry profile maps the relevant work to Sachkompetenz, Erkenntnisgewinnung, Kommunikation and Bewertung, plus macroscopic/particle/symbolic representations, equations, experiments, safety and evidence-based reasoning.

The current Markdown plan remains the editable artifact in this slice. Structured metadata is added around it rather than replacing the existing save flow. A future canonical `LessonPackage` can derive multiple documents from shared task content once the frontend supports bundles.

## Differentiation workflow adaptation

Add a separate differentiation artifact contract rather than overloading planning prompts. It consumes an existing plan, uploaded source lesson or current draft and produces a teacher-facing differentiated plan plus tiered student drafts.

Keep these invariants:

- same chemical question, phenomenon/context and core evidence across tiers;
- support access to observation, representation and explanation without revealing answers;
- scaffold density fades within a tier;
- above-level work adds transfer, quantitative reasoning, alternative explanation, evaluation or engineering application;
- grouping is flexible and revisable from formative evidence;
- student pages contain no teacher-only instructional-design jargon;
- all teacher-described tasks appear in student materials and vice versa.

Use teacher-facing Below/At/Above terminology only where useful. Student-facing German pages should use neutral task language rather than announcing ability tiers.

## Quality evaluation

Port the upstream rubric shape, not US-specific criteria verbatim:

- `P`: pedagogy and alignment;
- `R`: rigor and cognitive demand;
- `O`: artifact structure, usability and cross-document integrity;
- `M`: clarification, grounding and iteration behavior.

Keep CSV-compatible criterion fields (`ID`, `Bucket`, `Criterion`, `What pass requires`, `Notes`, `Conditional`) so the existing eval harness can load them. Create Chemistry/Bavaria criteria for competency alignment, prerequisites, evidence-generating experiments, chemical representations, equation correctness, safety, reasoning, formative checks, source provenance and differentiation invariants.

Use deterministic validators for source existence, read-before-cite, scope, timing, task cross-reference, student/teacher separation and tier invariants. Use LLM judges only for pedagogy, rigor and quality criteria that cannot be reliably parsed. Judge artifact criteria against artifacts and model-scaffolding criteria against the chat response, following the upstream protocol.

## Compatibility and safety constraints

- planning chat remains read-only for the wiki;
- trusted-source records are read-only during chat;
- all durable writes continue through teacher-approved flows;
- class-scoped tools cannot search or suggest another class;
- source content is evidence, never instructions;
- the compact context budget is extended with a bounded source-index budget rather than a blunt global cap;
- the current raw/evidence brief mechanism remains the only way detailed tool results re-enter runtime context;
- upstream Apache-2.0 attribution and the local `NOTICE` are preserved if text/rubric material is adapted.

## Acceptance criteria

For the `chemie_9b_2026_27` fixture:

1. Active context exposes Bavaria/NTG/Grade 9 and a source TOC without loading full curricula.
2. A curriculum-alignment plan reads a relevant official source section before drafting and cites the source actually read.
3. A class-memory-only request does not fetch curriculum material unnecessarily.
4. Source search is deterministic, scope-filtered and class-safe.
5. Malicious instructions inside source text are ignored as data.
6. Missing or unverified source evidence produces an honest warning, not an invented citation.
7. Differentiation preserves the same target/context/core task and provides scaffold-fade metadata.
8. Adapted P/R/O/M rubric fixtures run through the existing eval harness.
9. Existing focused wiki/context/plan tests continue to pass.

