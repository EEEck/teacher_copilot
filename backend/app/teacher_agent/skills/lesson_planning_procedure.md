<!--
SPDX-FileCopyrightText: 2026 Anthropic, PBC
SPDX-License-Identifier: Apache-2.0

Close semantic port for KlassenPilot. It preserves the workflow control flow,
quality gates, and shared-content discipline of the Apache-2.0 reference
skill. Material divergences are documented where Bavaria scope, trusted-source
tools, the single canonical Markdown package, or teacher-approved memory
require them.
-->

# Lesson Planning Production Procedure

## Bavaria Chemistry 9 NTG close port

Create one classroom-ready lesson package for the teacher: a teacher lesson
plan, student materials, and an observation/update section. The teacher is the
user you are talking with, never a third party. The package is one canonical
Markdown artifact; its repeated content is written consistently so its sections
do not drift apart on revision.

This procedure is mandatory for a new lesson, a sequence/review lesson, or a
new lesson that includes differentiated student material. Use the separate
differentiation procedure only to adapt an existing lesson.

## Keeping the teacher posted

Once the path is set, say in one or two teacher-facing sentences what you are
about to produce: for example, that you will check the relevant curriculum
section and the class's recent learning, then prepare the lesson, student work,
and observation capture. Do not name tools, Markdown files, schemas, prompts,
or rendering machinery to the teacher.

## Step 0 — Route

Run silently before drafting or asking content questions.

1. **Class and subject.** Determine the active class, subject, grade, branch,
   request type, duration, and whether this is a new lesson, review/sequence,
   assessment, or adaptation. For the current scope the only supported route is
   Bavaria → Gymnasium → Chemistry → Grade 9 → NTG. If the route is ambiguous,
   resolve it in Step 1.
2. **Mandatory reference.** Read the loaded Bavaria Chemistry 9 NTG reference
   now. Loading the subject reference is mandatory before drafting: it carries
   the course-specific pedagogy, section structure, non-negotiables, and
   canonical package mapping. Drafting without it is a critical failure.
3. **Effective class framework.** Treat the compiled teaching-framework profile
   as the teacher-adjusted pedagogical contract. Use it together with the
   compact subject guide and source TOC; do not separately inject or treat the
   inherited base summary as editable class memory.
4. **Source and history route.** Decide what needs exact evidence. Use trusted
   sources for official curriculum claims and class lesson/history tools for
   claims about what this class has learned. Curated framework pages guide
   pedagogy, but are not official curriculum authority.

## Step 1 — Clarify

Read the subject reference first. Use teacher preferences, active class memory,
the current artifact, prior lessons, and supplied materials before asking.

Ask at most **one** high-value question when a missing topic, duration,
available material/safety constraint, or learner evidence prevents a usable
lesson. Apply a reasonable default silently for everything else; name an
important assumption briefly in the plan. Do not re-ask what the active class,
current artifact, or lesson history already establishes.

The draft offer in Step 4 is output logistics, not a content clarification. It
does not consume the one-question limit.

## Step 2 — Ground in trusted sources

Ground before drafting. For every new full lesson package that names an
official competency, progression, requirement, or curriculum expectation, call
`search_trusted_sources` and then `read_trusted_source` for the relevant source
section before building. Record the consulted source reference in the artifact.
A source TOC, a search result, or a remembered curriculum claim is not
grounding.

If no relevant official source has been ingested or the requested claim cannot
be verified, say so plainly in the teacher plan and make no invented official
claim. Continue with class memory and general Chemistry pedagogy only when that
is sufficient for the teacher's request. A revision that does not change scope
may retain its already consulted source reference; re-ground when scope,
competency, or progression changes.

Use subject-guidance search/read only for deeper teaching-method,
representation, or differentiation detail. Use lesson/history tools only when
the compact class context cannot answer the request. Keep raw results behind
their evidence references; do not dump source bodies into the artifact.

## Step 3 — Build the lesson

Follow the loaded Bavaria Chemistry reference for course structure, section
shape, non-negotiables, exit evidence, and the canonical package mapping.

Build original, practical content. A source may inform scope, terminology,
phenomenon selection, misconceptions, task logic, and progression; never copy
student-facing curriculum text, investigation prompts, teacher notes, or task
contexts verbatim. Use official German labels or chemical terms only where
fidelity requires them, with concise English explanation where useful.

For every package:

- start from a meaningful observable phenomenon, data problem, or
  substance-level question when feasible; students generate evidence before
  formal explanation;
- define small, observable knowledge, practice, and meaning/application goals,
  plus prerequisites, success criteria, look-fors, and exit evidence;
- make the link between observable substance behavior, particle models, and
  symbolic Chemistry explicit when appropriate; state why each representation
  helps and require model revision rather than decorative drawing;
- record up to three anticipated ideas as **What / why / teacher move**;
- make timing, materials, safety boundaries, transitions, and contingency
  realistic for this class and period;
- preserve one central Chemistry question and core evidence task across access
  routes. Vary representation, language, grouping, prompts, and scaffolding;
  never silently lower the scientific claim or create permanent ability tracks.

## Step 4 — The draft offer

The full classroom-ready package is the default. Offer a quick outline only
when it would save teacher time or when the teacher asks to inspect direction
before materials are written. The offer is separate from Step 1's one
clarifying question.

- **Go ahead and build it** — the default; proceed directly to Step 5.
- **Quick draft first** — only after Step 2 grounding and Step 3 construction.
  Show the route/topic/source anchor, a short lesson rationale, one line per
  timed phase, the actual student evidence task, prerequisites, and exit
  evidence. Then ask whether to make changes or create the complete package.

Do not use a quick draft to skip grounding, invent unknown constraints, or
write a partial package as if it were classroom-ready.

## Step 5 — Output and completion

When the teacher chooses the full package, or approves a draft, return one
complete canonical `plan_markdown` package in the same turn. It has exactly
three audience headings: `## Teacher Lesson Plan`, `## Student Materials`, and
`## Observation and Update Capture`.

**Shared Markdown package.** Keep repeated identity, goals, core evidence
task, vocabulary, safety, representations, look-fors, exit evidence, and
consulted-source references consistent across the three sections. Student
material contains only student-facing tasks and supports; diagnostic notes,
facilitation moves, safety rationale, and adaptation logic remain teacher-facing.

**Density and integrity.** Write like a colleague's clear working note:

- Use short paragraphs, one action per bullet, and tables for parallel supports
  or phase comparisons. Avoid walls of prose and generic rigor language.
- Every material is used by a named phase; every phase has the materials it
  needs; timings include transitions and sum to the stated duration.
- A task named in the teacher plan matches its wording in student materials and
  produces the stated look-for or exit evidence. Student work fits the time and
  contains adequate answer space or an explicit oral/model response route.
- Student-facing language is accessible without answering the task for the
  learner. Supports sit beside the task they support and fade when evidence
  permits independent reasoning.
- The observation section is ready to capture coverage, participation/evidence,
  misconceptions, what worked, and follow-up. It never exposes teacher-only
  learner diagnosis to students.

**Pre-delivery check.** Before returning, run this explicit integrity
checklist on the Markdown package (not a JSON schema). Curriculum claims still
need read source references, every phase must serve a goal, and practical work
needs safety boundaries. In addition verify:

1. **Materials ↔ phases agree both ways** — every listed material is used by a
   named phase; every phase has the materials it needs.
2. **Shared task wording matches** across teacher and student sections — a task
   named in the teacher plan uses the same wording under Student Materials and
   produces the stated look-for or exit evidence.
3. **Phase minutes include transitions** and sum to the stated duration.
4. **Student section has no teacher diagnostic language** — no look-fors,
   misconception notes, conferring moves, or adaptation rationale on student
   pages.
5. **Exit evidence has sort buckets** with distinguishing criteria (for
   example secure / developing / needs revisit, or Got it / Almost / Needs).
6. **Differentiation integrity** (when access routes are offered) — same
   central question and core evidence task across routes; scaffolds appear as
   task design and stay unlabeled on student pages.

**Revision and close.** When the teacher requests a change, update every
affected occurrence in the canonical Markdown package. Run a **Consistency sweep**
after every context, number, task, vocabulary, safety, or exit-evidence change:
no section may retain stale references. End a completed package with a concise
satisfaction question and three or four specific, topic-relevant revision
options. Never write the wiki from planning chat; durable class adjustments stay
teacher-approved proposals.
