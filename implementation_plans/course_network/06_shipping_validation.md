# Course network implementation and validation

Implementation checkout: `C:/Users/matth/.codex/worktrees/849f/teacher_agent_v2`.
Branch: `codex/class-course-network-design`, based on `9e4df80` for this change.

## Teacher workflow implemented

1. Open **Course** from class home. Review the curriculum seed; if review requests
   changes, revise it with the backend procedure, review again, and adopt it.
2. Open **Materials** and upload a PDF chapter (40 MB / 30 selected pages maximum).
   Extraction continues after navigation. Reopen the import to correct text,
   titles and section boundaries, split/merge sections, or exclude sections.
3. Review the exact extraction and approve the chapter. It becomes available in
   the class library and ordinary lesson planning, independently of any plan upload.
4. Choose **Connect to course map**. Inspect new/changed concepts and proposed
   section connections. Correct concept titles, target concepts, relations or
   notes; reject changes. Existing connections that would disappear are listed.
   Save corrections, review the exact proposal, then approve map changes.
5. Inspect a concept, read its linked chapter section and open the source PDF.
   Create a lesson through the normal planning workflow. Relevant map and material
   context is included automatically, alongside the existing subject guidance.
6. Save the lesson. Valid explicit concept/material citations are recorded with
   the saved plan hash. Use normal Update Memory for actual lesson results.
   Later planning can use those approved results without treating planned content
   as taught or mastered.

## Deliberate MVP implementation choices

- Keep the canvas as an inspection view. No freehand graph editor, scheduling,
  mastery score, full-book hierarchy, cross-class reuse or graph database.
- One stable section body in approved Markdown; manifests and graph mappings store
  references/metadata. Original PDF/assets and workflow review artifacts retain evidence.
- Model generation/review uses bounded calls and persists completed proposals/reviews.
  OCR has a durable extraction state, Running entry and explicit restart retry.
  A separate model-job orchestration layer is not part of this first cut.
- Result connections are computed from canonical approved result text and valid
  plan references, with explicit-mention versus planned-lesson-context labels.
  No second results store or inferred progress write is introduced.
- Plan sidecars are idempotent and content-hash guarded. They are ignored if stale;
  a failed save can be repeated. The existing plan-save workflow remains the owner.
- Graph publication uses a receipt and an atomic reservation of the accepted
  review. Chapter publication uses the same reservation before publishing its
  exact manifest/body. Concurrent review/discard cannot supersede that reservation.

## Deterministic evidence

- Final full backend regression run: 753 passed, 45 skipped, two known baseline failures
  explicitly deselected. Both failures were reproduced before implementation:
  `test_memory_sweep_review_api_explains_new_candidates_that_make_a_draft_stale`
  and `test_proposal_sends_singletons_to_the_second_judge[asyncio]`.
- Subsequent targeted verification: 28 approval/recovery/race/API tests passed;
  ten citation/results/context/import tests passed.
- Final full frontend suite: 225 passed across 50 files; TypeScript passed.
  The course tests include the empty-replacement removal notice and exact-review
  approval gates. Mapping state is refreshed from the published map and before
  subsequent generated proposals.
- Independent read-only code review identified a superseded-review publication
  race and invisible mapping removals. Both were fixed and covered by regressions.
- Tracked OpenAPI contract includes the 20 new course paths and their referenced
  request/error schemas. No credentials were added to tracked files.

## Live local API evidence

Docker Compose project `kp_course_e2e_849f` was built and started from the feature
worktree, with an isolated wiki under `.worktree-stack/course-e2e/wiki`.
The main checkout's `backend/.env` was supplied as an ignored Compose env-file
override. Keys were not displayed or copied into source files.

- Backend health confirmed OpenAI configuration; OCR key presence was checked
  without printing its value.
- A self-authored one-page chemistry chapter passed real Mistral extraction,
  document review and explicit approval.
- The real seed reviewer requested wording changes. The new revise path generated
  a corrected seed, which passed a fresh review and was adopted.
- Live material enrichment and review produced an adopted revision-2 map with
  11 concepts and three chapter mappings, reusing existing concepts where appropriate.
- The ordinary live planner produced a complete 45-minute lesson using the chapter
  and Course references. Normal plan save succeeded. The saved sidecar records
  three valid concept IDs and the approved material ID at network revision 2.
- The normal live Update Memory chat produced complete results for the same test
  lesson, generated reviewable wiki proposals, and committed those approved results
  through the ordinary commit endpoint. The record includes the unresolved
  ion-charge/electron-count confusion for the next lesson.
- The next-lesson context builder was exercised against those actual saved files:
  it included the approved results and unresolved ion-charge confusion, kept three
  valid saved concept references, and left the graph at revision 2.

The live harness and raw responses are ignored under `.worktree-stack/course-e2e/`.
They are test evidence, not production fixtures or new agent infrastructure.

## Browser follow-up

The initial browser attempt was blocked by automatic approval review because the
account's usage limit was reached. Access succeeded in the user-requested
follow-up session. [07 — browser acceptance](07_browser_acceptance.md) records the
realistic salts/conductivity workflow, actual UI approvals and saves, and the
concept-reference bug found and fixed during that test. A further 19 focused
provenance, context and plan API tests passed after that correction.

Stack left available at `http://localhost:3313`; API at `http://localhost:8588`.
Baseline `backend/teacher_wiki/` was not changed by live tests. Only the isolated
test wiki received material, graph, plan and lesson-result workflow changes.
