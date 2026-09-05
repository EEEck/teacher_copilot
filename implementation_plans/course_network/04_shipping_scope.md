# Course knowledge map: first end-to-end release

**Date:** 2026-09-04
**Status:** Shipping scope refined from the product design and the teacher's confirmed direction in the planning conversation. Implementation has not started under this revision.
**Execution baseline:** `codex/class-course-network-design`, inspected at `9e4df80`.

## Outcome

A teacher can prepare one teaching block from curriculum and uploaded course material, inspect its concepts and relationships, and plan a lesson that uses the right concepts, prerequisites, and source sections. Saved plans and approved results remain connected to that course knowledge.

The concept map has two connected uses: a teacher-readable mind map and the agent's structured navigation through class course knowledge. It is central to the upload and planning workflows. A standalone graph-generation chat does not satisfy this release.

## Teacher workflow

1. Open a class and its Course workspace. Review/adopt the existing curriculum seed, or use a bounded generation request to revise the proposed scope before adoption. Clearly label which curriculum sections the map covers.
2. Upload a chapter or worksheet PDF to Course Materials without creating a lesson. Inspect the extracted sections, source pages, and warnings; correct titles, text, page boundaries, or split/merge sections before approving the material.
3. Generate proposed concept mappings. The agent reuses existing concepts and proposes missing concepts or relationships only when supported. Review, correct, accept, or reject the proposed changes, then approve them.
4. Inspect the map. A concept shows its learning goal, prerequisites, related concepts, curriculum evidence, mapped material sections, and linked lesson records.
5. Plan in the existing lesson-planning workflow. The agent automatically retrieves a compact relevant course slice and material content on demand. There is no required node selection or tagging step.
6. Save through the existing plan approval. The saved lesson retains concept and material references. Update Memory continues through its existing approval flow and associates results only when supported by the approved lesson evidence.

## Keep in the first release

- One class-owned network; one node type, `Lernbaustein`; `builds_on` and `related_to` relationships.
- Existing Chemie 8/9 NTG routes and seed support. Prove the first complete scenario on one Chemie 8 teaching block, with a Grade 9 compatibility case.
- Canonical network JSON and compiled overview; existing React Flow viewer, inspector, and narrow-screen outline.
- Backend-owned generation/enrichment procedure, typed proposals, deterministic validation, the existing bounded LLM review pattern, and explicit teacher approval.
- Standalone PDF material import, stable section references, basic extraction corrections, and source/asset inspection.
- Reviewed material mappings and minimal concept/relationship correction through forms and proposals.
- Automatic graph/material retrieval in ordinary planning; saved plan references; evidence-grounded result associations.
- Durable drafts, exact-revision approval, class/workspace isolation, navigation recovery, and explicit restart failure/retry behavior.

## Simplify for this release

- Keep the canvas for inspection and selection. Use shared forms and proposal rows for editing; no edge dragging, freeform canvas editing, persistent layout editor, or undo history.
- Use a flat ordered section list with page ranges and split/merge correction. Preserve detected hierarchy in source evidence if present; do not build a general book-outline editor.
- Start with one chapter-sized PDF per import. Apply the existing upload limits plus a course-import selected-page cap of 30, configured centrally. Larger books can be uploaded as selected chapters.
- Keep the two semantic approvals: approve extracted material, then approve graph mappings/changes. Present them in one resumable import workspace.
- Preserve existing node IDs. Support add, update, retire, add/remove relationship, and replace mappings for the imported material; no node-ID rename or merge migration.
- Keep current subject pedagogy/framework context. Add graph content as a deduplicated source layer; do not make graph adoption remove pedagogical guidance.
- Use existing model routing, OCR provider, draft storage, review UI, and evidence/raw-reference mechanics.

## Defer

Whole-book ingestion/structure management, cross-class reuse, graph databases, embeddings, question banks, automated curriculum crawling, scheduling, progress dashboards, mastery scores, arbitrary graph editing gestures, and broad orchestration infrastructure.

These are excluded from the first release, not missing steps that must be completed before shipping it.

## Knowledge and authority contract

| Record | Owns | Links to |
| --- | --- | --- |
| Course network | Concise concept descriptions/goals, relationships, source references, material mappings | Curriculum sections, material sections |
| Material package | Extracted source text, figures, page provenance, approved section boundaries | Original source pages |
| Lesson records | Saved plan, approved results, concept/material associations | Network node IDs and material IDs |
| Existing class memory | Current unit, teaching history, misconceptions, teaching preferences | Approved lesson evidence |

Do not duplicate full material text in nodes or in both material manifests and section bodies. The material manifest contains metadata and stable pointers into the canonical reviewed text. The overview is a rebuildable projection, not another editable knowledge store.

`source_id builds_on target_id` means the source concept depends on the target concept. Example: `catalysis builds_on activation-energy`. This matches the implementation and corrects the reverse wording in the original product design. `related_to` is semantically symmetric; normalize reversed duplicates.

Curriculum references establish provenance, not proof that the curriculum explicitly mandates every generated prerequisite. Show relationships as curriculum-derived or teacher/material proposals where appropriate; keep concise supporting rationale in the reviewed proposal. Textbooks are teaching resources, not official curriculum authority.

Planned, taught, and revisit are evidence states. Saving a plan never establishes that a concept was taught or mastered. Unconfirmed plan references remain planned when results do not establish coverage.

## Release scenario

Create Chemie 8a, adopt a reactions-block map, import a short catalysis chapter, correct one extracted section, approve the material, review mappings and one justified addition, and inspect the connected source pages. Ask for a lesson on catalysis in the ordinary planner. Verify that it uses activation energy/energy profiles and the mapped pages, saves its references, and respects subsequent approved results when planning the next lesson.

Also prove that an unrelated class cannot read the material, a class without a map still plans normally, stale approval cannot overwrite a newer graph, and leaving/reopening an import preserves the reviewed work.

## Relationship to previous plans

This scope and [05_shipping_implementation.md](05_shipping_implementation.md) govern the next release. Preserve [01_product_design.md](01_product_design.md) as the original vision. Treat [02_delivery_program.md](02_delivery_program.md) and the original B/C/D task lists as reference designs, not the execution order for this release. Existing Epic A work is reused, not rewritten.

Meaningful scope changes from the original: fewer editing controls and document-management features; a flat section manifest instead of a full hierarchy editor; no graph-triggered retirement of the teaching framework; generation/enrichment is explicitly specified; the material-to-planning loop is the release gate.
