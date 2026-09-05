# Browser acceptance: salts and conductivity

## Scenario

A Chemie 9b teacher prepares a 45-minute lesson for 2026-10-08 on why salt
solution conducts electricity. The previous approved lesson recorded confusion
between ion charge and electron count. The teacher uploads a self-authored
two-page chapter with particle-model explanations, observations, partner tasks
and an exit question. No real student data or external textbook is uploaded.

Use the existing sandbox class `chemie_9b_2026_27` at `http://localhost:3313`.
This stack serves worktree `849f`, branch `codex/class-course-network-design`.
The PDF fixture and its rendered page checks are retained under the ignored
`.worktree-stack/course-e2e/` directory.

## Acceptance record

- Browser access succeeded in the follow-up session.
- Class home opens the adopted revision-2 map with 11 concepts. The narrow
  viewport exposes a searchable outline and concept inspector.
- Uploaded `salze-leitfaehigkeit.pdf`, selected pages 1-2, and started extraction.
  Left the page and returned; the completed extraction could be resumed.
- Both extracted sections match the authored chapter. Read the returned text.
- Reviewed extraction; approval enabled. Changed the second section title to
  `Leitfähigkeit: Partneraufgaben und Diagnose`; approval and review disabled
  while dirty. Saved corrections; approval stayed disabled until fresh review.
- Approved the chapter through the UI. Material `mat_e1dfd9996b27` appeared in
  the library, including the corrected section title and readable page-2 body.

- Generated enrichment through `Connect to course map`: one conductivity node,
  two prerequisite edges to existing ion-formation/hydration concepts, and two
  material mappings (`explains` and `practices`). Added a teacher note to the
  practice mapping, saved, reviewed and approved through the UI.
- Map revision 3 contains 12 concepts. Search found the conductivity concept;
  its inspector resolved the approved page-2 body. The source link opened the
  actual two-page PDF at page 2, visually verified in the browser PDF viewer.
- Exercised the desktop canvas at 1440 x 1000 (needed to reveal the canvas).
  Selecting the ion-formation node updated the inspector. Following its `Used by`
  connection selected conductivity and showed the reciprocal `Builds on` link.
- Reloaded the map: revision 3 and the new conductivity concept persisted.

- Requested an ordinary 45-minute lesson for 2026-10-08 without uploading the
  chapter again. The generated plan cited the approved material, used its four
  observation cases, connected to prior ion-charge/electron-count confusion,
  and included diagnosis, partner diagrams, consolidation and exit-ticket phases
  totalling 45 minutes (6 + 13 + 11 + 10 + 5). The plan passed its normal review.
- Saved through the date confirmation and opened the lesson detail for 2026-10-08.
  Native date-input keyboard interaction was used to commit the chosen date;
  merely filling the date with the browser tool did not update React state.

## Bug found during acceptance

The generated plan named the three exact concept IDs as bold Markdown tokens,
without a `Course:` prefix. Initial save preserved the material reference but
left `course_refs.json.node_ids` empty. Added regression cases for bold and inline
code canonical IDs; both failed on the original parser, then passed after the
bounded parser correction. Unknown IDs, retired IDs, partial IDs and titles stay
excluded. The agent contract was updated in the same change.

Focused verification: 19 provenance, planning-context and plan API tests passed.
The original generated Markdown was re-entered through the browser editor and
resubmitted through the normal save confirmation to verify the correction.

- Browser resave preserved the exact original plan hash
  `8de14e5b9ee5fe6f048a5b38cf3cb855a98cbe16852ce73bff0b238efe8657c2`.
  The sidecar now records conductivity, ion formation and salt hydration, plus
  `mat_e1dfd9996b27`, at network revision 3. No results file existed during chat.
- Opened `Add lesson results` from the saved lesson. The target date was already
  confirmed. Entered simulated outcomes: 18/24 explained ion mobility correctly;
  six retained a free-electron misconception; the sugar comparison was not taught.
- Inspected the structured diary and wiki proposals. Used the review editor to
  remove the missed sugar task from the misconception rollup, retaining it in
  canonical results and follow-ups. The existing compiler had copied that timing
  issue from "What didn't go well" into misconceptions; this remains a refinement
  opportunity for that existing workflow, with teacher review handling this case.
- Committed reviewed changes through `Save all`. Browser showed `Memory saved`;
  actual saved files retain the counts, misconception, unfinished work and next
  five-minute focus. The teacher correction survived publication.

- Class home showed the 2026-10-08 lesson as `Done`. Started a new ordinary
  planning session and requested only the first ten minutes for 2026-10-12,
  asking it to inspect the saved results without restating the misconception or
  unfinished task.
- The new planner recovered ion movement versus electron flow as the targeted
  repeat, explicitly kept the sugar comparison unfinished, and cited the 08.10
  results plus the approved material's exercise section. Its 10-minute draft
  has retrieval, comparison, correction and a bridge to that open task. It is
  left as a reviewable draft, not saved as a complete lesson.
- Restored the default browser viewport after desktop canvas verification.

## Outcome and limits

The realistic core workflow passed through actual browser controls, with live
OCR/model calls: upload, resume, correct, review, approve, map, inspect source,
plan, save, record results, approve memory and plan from those results. The
provenance regression was fixed and its browser save replay passed with identical
plan text. Baseline wiki fixtures remain unchanged; all teaching data belongs to
the isolated sandbox stack. Changes remain uncommitted in the feature worktree.

This is one representative happy path plus review-invalidation, navigation and
provenance checks. It does not replace the deterministic concurrency/restart and
class-isolation tests, or establish browser coverage of every error path. The
existing memory compiler still benefits from teacher correction of rollup
classification, demonstrated above. The initial planner language is English by
the current product contract, even when the teacher and source material use German.

## Chemistry self-review follow-up — 2026-09-05

Applied the teacher-approved chemistry corrections through the existing proposal,
exact review and browser approval flow. The sandbox map is now revision 4 with
13 concepts, 17 connections and 7 material mappings. Existing node IDs and all five
previous mappings, including the teacher's practice note, were preserved.

- Changed lattice → ion formation and conductivity → ion formation/hydration from
  prerequisites to associations. Conductivity now builds on the lattice, with its
  goal explicitly comparing fixed ions in solid NaCl with mobile ions in solution.
- Added one bond/molecular polarity concept, depending on bonding and geometry;
  water builds on polarity, and hydration also builds on water. Interactions remain
  related to polarity because not every interaction requires a permanent dipole.
- Clarified the lattice and particle-interactions wording. Added page-1 explanations
  to ion formation and lattice, with notes identifying partial concept coverage.
- Verified revision 4 after navigation, followed conductivity → lattice and its
  reverse Used by connection, selected polarity on the desktop canvas, and followed
  its water connection. Restored the default viewport. Material evidence remains
  accessible in the inspector. The teacher guide is `docs/course_graph_guide.md`.

Live quality checks exposed two limitations. One generation response was invalid
JSON (HTTP 500, no draft/write); a single retry succeeded. That response claimed
section mappings were included but omitted their typed operations. The prepared
teacher correction replaced the incomplete proposal through its revision/hash
update API before review. Generation error presentation and summary/operation
agreement prompted the release fixes recorded below; this is not evidence of
reliable fully automatic correction generation.

The reviewer found a real hydration/polarity gap but also repeatedly claimed
existing links were absent. Added a deterministic prerequisite index to its packet,
plus instructions to check all prerequisites and the full learning goal. The new
regression test failed before the index existed and passed afterward. Fresh live
review accepted artifact revision 2 with no findings; browser Approve map changes
committed draft `55348c19-1ebf-446d-80b9-20b7a18b1970`. The final graph was verified
both on disk and in the browser. This improves evidence presentation but does not
guarantee future model judgments.

Focused verification: 40 generation, review, edit and operation tests passed;
`git diff --check` passed. Reused Docker project `kp_course_e2e_849f` on ports
3313/8588. No baseline `backend/teacher_wiki` changes; only the isolated sandbox's
graph and its normal derived/audit files were published. Work remains uncommitted
on `codex/class-course-network-design` in worktree `849f`.

## Pre-commit verification — 2026-09-05

Re-ran the full deterministic backend suite with the two previously reproduced
baseline failures listed in 06 excluded; exit status 0. The frontend suite passed
225 tests across 50 files, TypeScript passed, and the staged diff passed whitespace
checks. The commit contains feature source, tests, OpenAPI and documentation only;
environment files, temporary test directories and the live sandbox wiki are excluded.

## Release fixes after the first push — 2026-09-05

Feature checkpoint `d3e5638` was pushed to `codex/class-course-network-design`.
The follow-up handles invalid model JSON, invalid output schemas and timeouts with
a safe retryable 502 response. Offline API tests exercise both adopted-map proposals
and seed revision: failure publishes nothing, preserves the existing graph/draft
snapshot, omits provider details from the response, and permits a successful retry.
The runtime and checked-in OpenAPI error contracts agree.

The review screen now derives concept/connection counts from its editable proposal
and current graph. Chapter links distinguish additions, edits and removals; unchanged
links are not counted as additions. Retirement includes implicit removals without
double-counting explicit ones. Model summary/coverage claims and stale per-mapping
rationales are no longer presented as the actual change inventory. This does not
verify that every teacher request was fulfilled or replace chemistry review.

Browser verification used a disposable proposal through the normal draft service
with an intentionally false model summary. The live UI correctly showed one concept
edit and zero chapter-link additions. Rejecting the edit immediately updated the
count to zero and disabled review/approval until saving. The proposal was discarded
through the browser; canonical revision 4 and its 13 concepts remained unchanged.
The browser was returned to the course map. No additional model calls were needed.

Validation: course API/generation/review/edit/operation regressions passed; all
231 frontend tests across 51 files passed, TypeScript passed, and diff checks passed.
Reused the existing isolated Docker stack and worktree `849f`. Baseline wiki fixtures
and canonical sandbox wiki files were unchanged during this follow-up; only the
disposable workflow draft was created and discarded.
