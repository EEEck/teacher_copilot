# Class Course Network Design

## Status

Approved product design for technical planning. This document defines the MVP
product boundary and durable behavior. Endpoint shapes, exact file
serialization, component boundaries, migrations, epics, and PR sequencing
belong in the follow-up implementation plan.

## Summary

KlassenPilot will add a class-owned course network to the class wiki. The
network is a durable map of teachable content for one class, initially Chemie 8
NTG and then Chemie 9 NTG. It connects a reviewed curriculum seed, textbook and
teacher-material sections, lesson planning, and lesson results without turning
lesson planning into a graph-maintenance workflow.

Teachers build and enrich the network at the start of the year and later by
quarter or teaching block. The lesson-planning agent uses it automatically on a
weekly cadence. All durable network changes remain teacher-reviewed. Planning
stays read-only with respect to the wiki.

The MVP deliberately keeps the model small:

- the network lives inside one class wiki;
- it has one node type, **Lernbaustein**;
- materials and lessons link to stable Lernbaustein IDs;
- there is no question bank, reusable cross-class network, graph database,
  competency-node hierarchy, or Kanban workflow.

## Why This Is Needed

The current Chemie 8/9 NTG mechanism combines:

- immutable LehrplanPLUS source extracts;
- a short shared grade/branch teaching-framework summary;
- a bounded class-specific `teaching_framework_adjustments.md` memo;
- lesson-linked PDF materials promoted only when a lesson plan is saved.

This grounds lesson planning, but it cannot represent the structure visible in
the teacher's Miro knowledge map: teachable chemistry topics, dependencies,
textbook coverage, and the relationship between the planned and taught
curriculum. A short override memo is also a poor fit for structural edits.

The target is not a general knowledge-graph platform. It is a practical class
course map that makes the existing lesson workflow better.

## Product Principles

1. **Class-owned for the MVP.** Each class has its own canonical network. A
   future export/import workflow may reuse it elsewhere, but inheritance and
   shared ownership are out of scope.
2. **Start from the class, not a blank canvas.** Chemie 8 NTG is seeded from the
   reviewed curriculum route during class setup.
3. **One canonical home per artifact.** Nodes live in the network, source
   content lives in materials, and plans/results live in lesson records.
4. **Automatic use, explicit maintenance.** The planning agent discovers the
   relevant network context. The teacher does not need to select nodes before
   planning. Editing the network is a separate workflow.
5. **Proposal before durable action.** Curriculum adoption, material mappings,
   and later graph edits pass deterministic validation, LLM review, and teacher
   approval before commit.
6. **Provenance survives transformation.** Curriculum claims and material
   mappings retain inspectable links to their sources.
7. **Keep the graph replaceable.** The wiki data model is canonical. The graph
   canvas is a frontend projection, not the persistence model.

## MVP Information Architecture

Conceptually, each class wiki gains two course-content arms alongside its
existing lesson and memory records:

```text
wiki/classes/{class_id}/
  course_network/
    Lernbausteine
    relationships
    review/version metadata
  materials/
    textbooks/
    personal-or-teacher-materials/
  lessons/
    {date}/
      lesson_plan.md
      lesson_results.md
      material references
      Lernbaustein references
  existing class configuration, rollups, and compact memory
```

The exact files and serialization are deferred to the technical plan. The
contract is that they remain class-scoped, inspectable through the wiki, safe
to validate deterministically, and independent of React Flow's node format.

## Canonical Domain Model

### Lernbaustein

The network has one teacher-facing node type: **Lernbaustein**. A Lernbaustein
may represent a concept, topic, method, or coherent teachable block such as
Massenerhaltung, Aktivierungsenergie, Stoffmenge, or Stöchiometrie.

Its canonical content stays small:

```yaml
id: chem8-aktivierungsenergie
title: Aktivierungsenergie
description: Energie, die zum Start einer chemischen Reaktion benötigt wird.
learning_goal: >
  Schülerinnen und Schüler erklären die Aktivierungsenergie anhand eines
  Energiediagramms.
curriculum_refs:
  - source: lehrplanplus-chemie-8-ntg
    section: lb3
origin: curriculum
status: adopted
```

Required semantics:

- `id` is stable within the class and is used by mappings and lessons;
- `title` and `description` are teacher-readable;
- `learning_goal` is optional and captures the competency dimension without a
  second competency-node type;
- `curriculum_refs` retain provenance;
- `origin` distinguishes seeded, teacher-created, and material-proposed nodes;
- `status` distinguishes draft/proposed content from adopted content.

Layout coordinates, selection state, open panels, and other canvas concerns are
not part of the pedagogical node contract.

### Relationships

Relationships are separate records rather than embedded prose. The MVP uses a
small controlled set, initially:

- `builds_on`: the source depends on or meaningfully builds on the target;
- `related_to`: the two Lernbausteine have a useful non-prerequisite relation.

The technical plan may choose directed storage for both while rendering
`related_to` symmetrically. Visual placement is not a relationship type.

### Material mappings

Textbooks and teacher materials remain canonical material packages. A mapping
links a material section or page range to one or more Lernbausteine and retains
source provenance. The material itself is never copied into the node.

Mappings support the planner's retrieval but do not grant materials authority
over the curriculum. The source type remains explicit so the agent can
distinguish official curriculum evidence, textbook exposition, and teacher
material.

### Lesson references

Lesson plans and results retain their existing canonical homes. They gain
stable references to the Lernbausteine used by that lesson.

The planning agent automatically proposes or records:

- primary Lernbausteine;
- supporting or prerequisite Lernbausteine;
- material sections used.

These references are saved as part of normal teacher plan approval. They may be
visible and editable, but they do not create a mandatory tagging step.

The Update Memory experience remains unchanged. Under the hood, approved lesson
results may reuse the plan's Lernbaustein references and derive taught/revisit
associations through the existing teacher-approved commit boundary. They do not
silently mutate the network.

## Questions and Exercises

There is no structured question bank in this MVP.

Questions and exercises remain inside their source material. When graph-aware
retrieval includes a relevant textbook chapter, worksheet, or exam, the lesson
planner may reuse or adapt questions present in that retrieved content or
derive new questions for the plan. Resulting questions remain part of the
lesson plan; they are not extracted, deduplicated, tagged, or stored as atomic
reusable records.

Future requirement: when structured question ingestion or generation is
implemented, every approved question must be coupled to a fixed, versioned
rubric. Editing the question must create or require review of a matching rubric
revision. The future rubric should support expected evidence, scoring criteria,
maximum points, acceptable variants, and common errors so the same item can be
used for assessments and rubric-grounded answer evaluation. This requirement
does not affect MVP storage or workflows.

## Two Operating Cadences

### Build and maintain: yearly or quarterly

This is a dedicated, resumable class-course workflow:

1. The teacher creates or initializes a class with the Chemie 8 NTG route.
2. KlassenPilot proposes a course network seeded from reviewed curriculum data.
3. The teacher reviews and adopts the proposed Lernbausteine and relationships.
4. The teacher uploads a textbook, selected chapters, or teacher materials.
5. The teacher reviews document identity, OCR quality, hierarchy, chapter or
   section boundaries, and page ranges.
6. The agent proposes mappings between approved material sections and existing
   Lernbausteine, plus any genuinely missing nodes or relationships.
7. The teacher accepts, edits, or rejects the proposed operations.
8. Approved changes are committed atomically to the class wiki.
9. The teacher can reopen the dedicated network workspace later for manual or
   agent-assisted maintenance.

Network editing does not need to be embedded in lesson planning.

### Use: weekly

The existing lesson workflow is enhanced, not replaced:

1. The teacher asks for the next lesson in the normal planning workflow.
2. The agent infers the relevant scope from the request, current course state,
   timeline, recent lesson results, and network structure.
3. The backend retrieves a bounded neighbourhood of relevant Lernbausteine,
   prerequisites, mapped materials, and class history.
4. The agent drafts or revises the lesson using that evidence.
5. The plan automatically carries the relevant Lernbaustein and material
   references.
6. The teacher reviews and saves the plan through the current save flow.
7. After teaching, the teacher uses the current Update Memory flow. No new graph
   step is introduced.

## Human-in-the-Loop Contract

### Gate 1: document extraction review

Before a course material becomes canonical, the teacher reviews:

- document title and edition when available;
- detected table of contents and section hierarchy;
- chapter/section labels and page ranges;
- OCR warnings and uncertain boundaries;
- included diagrams or page assets where relevant.

The teacher can split, merge, rename, reorder, or exclude detected sections.
Only the approved extraction package is promoted to the class material library.

### Gate 2: network mapping review

After extraction, the agent proposes typed network operations:

- map a material section to a Lernbaustein;
- add or update a Lernbaustein;
- add or remove a relationship;
- remove or replace a stale mapping.

The teacher can accept, edit, or reject individual operations before a single
atomic commit.

### Permanent graph maintenance

The graph workspace supports the same proposal-and-review contract outside
material ingestion. Manual edits and agent-assisted edits become one durable
network draft rather than bypassing validation.

### Validation and LLM checking

All commit paths share one review pipeline.

Deterministic checks cover:

- valid and unique IDs;
- no dangling or cross-class references;
- controlled relationship types;
- invalid dependency cycles;
- duplicate material mappings;
- referenced material sections that no longer exist;
- delete impact;
- stale network revisions and concurrent edits.

An independent LLM review checks matters code cannot reliably judge:

- chemistry and curriculum plausibility;
- accidental confusion of textbook claims with official curriculum authority;
- implausible prerequisites or collapsed concepts;
- misleading learning goals;
- unsafe experiment guidance introduced into network content;
- unsupported changes or missing provenance.

Serious findings block commit until resolved; advisories remain visible. The
reviewer never silently rewrites the teacher's draft. This should reuse the
product's existing proposal/review/commit discipline and shared review UI
patterns rather than create a separate trust model.

## Agent Retrieval Contract

Lesson planning remains wiki read-only until the teacher saves the plan. The
teacher does not have to choose graph nodes before planning.

The backend assembles a compact purpose-specific context pack containing:

- inferred primary Lernbausteine;
- a bounded neighbourhood of `builds_on` and relevant `related_to` nodes;
- mapped material summaries and section references;
- current class course state and timeline evidence;
- recent lesson results, misconceptions, or open loops relevant to those nodes.

The planner receives summaries and references first, with raw material content
available on demand through tools. This follows the existing evidence-brief and
`raw_ref` pattern rather than injecting the complete graph and complete books
into every prompt.

Sparse or ambiguous evidence must be reported honestly. The agent may ask one
targeted clarification, consistent with the current planning contract.

## Frontend Product Surfaces

The MVP needs these teacher-facing surfaces:

1. **Class setup integration**: show the selected curriculum route and the
   network-seeding/adoption state.
2. **Course network workspace**: inspect, search, select, and propose edits to
   Lernbausteine and relationships; open node details and mapped materials;
   review pending changes before commit.
3. **Class materials library**: upload and inspect durable textbooks and teacher
   materials independently of a lesson.
4. **Document extraction review**: review and correct document structure before
   promotion.
5. **Network mapping review**: approve the agent's proposed mappings and graph
   operations.
6. **Existing lesson planner**: no required new entry step; graph retrieval and
   automatic references are integrated behind the current workflow.
7. **Existing Update Memory flow**: no required new teacher interaction.

The detailed page/routes, shared components, responsive behavior, and review
layout belong in the implementation plan.

## Graph Canvas Direction

Use [React Flow](https://reactflow.dev/) (`@xyflow/react`) as the preferred
frontend graph-canvas library, subject to a small implementation spike in the
technical plan. Its current official documentation provides custom React nodes
and edges, TypeScript support, pan/zoom/selection, keyboard accessibility,
validation hooks, save/restore examples, layout integrations, and testing
guidance. The project is MIT-licensed and maintained in the
[xyflow repository](https://github.com/xyflow/xyflow).

React Flow owns canvas interaction only. KlassenPilot owns:

- canonical node, relationship, mapping, and revision schemas;
- authorization and class isolation;
- drafts and review operations;
- validation and commit behavior;
- semantic design-system components rendered inside custom nodes and panels;
- conversion between API records and React Flow's view model.

The backend must never persist React Flow's complete JSON object as the domain
source of truth. Optional positions may be stored as presentation metadata, but
pedagogical relationships and provenance remain independent.

## Error and Recovery Behavior

- OCR and mapping jobs are resumable; navigation does not discard accepted
  background work.
- Failed OCR or mapping leaves the last approved wiki state unchanged.
- A stale network revision blocks commit and reloads a clear comparison instead
  of overwriting newer work.
- A partially accepted review commits atomically or not at all.
- Removing a node shows affected mappings and lesson references before approval.
- Missing material sections degrade retrieval honestly and surface repair
  actions; they do not produce invented content.
- Existing workflow error components and the Running box should be reused where
  their contracts fit.

## Core User Stories

1. **Initialize the course network.** As a teacher, I can initialize Chemie 8
   NTG from a reviewed curriculum seed rather than draw the course from scratch.
2. **Review and adopt the seed.** As a teacher, I approve the initial network
   before it becomes canonical class wiki data.
3. **Upload course materials.** As a teacher, I can upload a textbook or several
   chapters for the coming teaching block without creating a lesson first.
4. **Correct extraction.** As a teacher, I can fix document structure and OCR
   uncertainty before promotion.
5. **Review mappings.** As a teacher, I can accept, edit, or reject proposed
   mappings and graph changes.
6. **Maintain the graph.** As a teacher, I can inspect and update the network
   later through a dedicated reviewed workflow.
7. **Plan without manual graph setup.** As a teacher, I ask for a lesson as I do
   today; the agent discovers the relevant graph, materials, and prior class
   evidence automatically.
8. **Save automatic references.** As a teacher, my approved plan records the
   Lernbausteine and materials it used without requiring another tagging step.
9. **Capture results as today.** As a teacher, I use the existing Update Memory
   experience while the system preserves the lesson-to-network association.

## MVP Scope

Included:

- class-owned networks for Chemie 8 NTG, followed by Chemie 9 NTG;
- curriculum-seeded Lernbausteine and simple relationships;
- initial adoption, dedicated inspection, and reviewed editing;
- standalone textbook/chapter and teacher-material ingestion;
- extraction review and network-mapping review;
- material-to-Lernbaustein mappings with provenance;
- graph-aware planning retrieval;
- automatic lesson-to-Lernbaustein references;
- current lesson-result workflow with no additional teacher step;
- React Flow as the preferred canvas direction.

Explicitly excluded:

- question or exercise extraction;
- a structured question bank;
- question tagging, operator/AFB indexing, or question deduplication;
- reusable cross-class graph ownership, inheritance, export, or import;
- separate competency nodes;
- a graph database or general ontology;
- vector search as the default retrieval path;
- Kanban and weekly organization;
- assessment generation or autonomous grading;
- lesson portability between classes;
- cross-teacher sharing or collaboration.

## Relationship to Current Product Documentation

Implementation of this design must update the durable product and engineering
contracts in the same change set:

- `docs/pm_hub.md`: promote the year-start library and class course network from
  gap/roadmap language into current product state as slices ship;
- `docs/product_vision.md`: add the two-cadence course-network behavior and
  preserve teacher-control boundaries;
- `implementation_plans/product_backlog.md`: replace or refine the existing
  class factory, year-start library/chapterize, and inherited-framework backlog
  items with the chosen epics and PR sequence;
- `docs/agent_architecture.md`: document network retrieval, evidence packets,
  and the shared LLM-review boundary;
- `docs/agent_contracts.md`: add the network read/write/tool contracts and remove
  graph/wiki-editor items from deferred scope only as they ship;
- `docs/memory_hierarchy.md` and `backend/teacher_wiki/AGENTS.md`: define the
  class-network and mapping canonical homes, loading rules, and migration from
  `teaching_framework_adjustments.md`;
- `frontend/ARCHITECTURE.md` and `frontend/DESIGN.md`: document the graph
  workspace, shared review components, and React Flow design-system adapter.

Documentation changes should ship with the PR that changes the corresponding
behavior, not as a disconnected final cleanup.

## Delivery Decomposition

The technical plan should decompose the work into independently shippable
epics rather than one broad graph PR:

1. class-network schema, storage, validation, and curriculum seed;
2. class setup and initial network adoption;
3. read-only graph workspace and React Flow foundation;
4. reviewed graph editing and shared LLM checking;
5. standalone class materials library and extraction review;
6. material-to-network mapping and review;
7. graph-aware lesson retrieval and automatic plan references;
8. lesson-result association, migrations, evals, and product-doc completion.

The implementation plan must inspect current class-provisioning work and reuse
or integrate it instead of duplicating class creation. It must also identify
where the existing material OCR packaging, workflow drafts, review/commit UI,
running-job infrastructure, evidence briefs, and wiki validation can be reused
or require focused refactoring.

## Acceptance Criteria

The MVP is complete when:

1. A newly initialized Chemie 8 NTG class receives a teacher-reviewed proposed
   network grounded in the approved curriculum route.
2. No network becomes canonical without explicit teacher adoption.
3. A teacher can upload and approve course material independently of a lesson.
4. A teacher can correct extraction structure before material promotion.
5. Material mappings and graph edits require deterministic validation, LLM
   review, and teacher approval.
6. A teacher can inspect and maintain the graph through a dedicated workspace.
7. Normal lesson planning automatically retrieves relevant graph and material
   context without requiring node selection.
8. Saving a plan persists its network/material references through the existing
   approval boundary.
9. Update Memory retains its current teacher-facing flow.
10. Planning chat never mutates the canonical network or material library.
11. Failed or stale drafts cannot partially overwrite approved wiki state.
12. Product, agent, wiki, and frontend documentation matches each shipped
    behavior.
