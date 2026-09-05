# Teacher-owned course release acceptance

Status: local implementation and validation complete; hosted release not signed off.

Implementation branch: `codex/class-course-network-design`, worktree `849f`.
Local Docker project: `kp_course_release_849f`, frontend `http://localhost:3314`,
backend `http://localhost:8589`. Isolated beta data lives in ignored
`.worktree-stack/course-e2e/release-restored` after the successful restore rehearsal;
`release-beta` is the preserved recovery checkpoint. The old port 3313 stack remains untouched.
Tracked baseline wiki is unchanged.

## Realistic browser scenario

A synthetic chemistry teacher keeps the demo class and creates Chemie 8a for
2026/27, with an editable label, no roster, and a short prior-learning note.
The teacher imports a self-authored three-page reactions/energy PDF (pages 1 and
3 only, including an energy diagram and table). They correct an OCR typo and
review its relationship to activation energy and catalysis. A separate filtration
PDF enters through ordinary lesson planning, then becomes reusable course material.
No student records, real teacher profile or private school material is used.

## Local acceptance evidence

| Step | Observed result |
| --- | --- |
| Demo invite and homepage | Demo retained; own-class action visible |
| Own class creation | `chemie_8a_2026_27`, custom label, blank roster, prior learning saved |
| Curriculum seed | Live review/adoption, revision 1, 12 concepts and 12 connections |
| Empty lesson history | No lessons logged; adopting the graph no longer invents a last-taught date |
| Original PDF upload | Pages 1 and 3 extracted; energy diagram and table assets retained |
| Teacher correction | OCR `erhofft` corrected to source `erhoeht`; title edited; approval disabled until new review |
| Reviewer gap resolved | Guidance now permits organizational labels and plausible OCR corrections; live review accepted with a manual-PDF-check advisory. Payload remains OCR + proposed extraction. Richer PDF-text transmission was rejected by automatic approval review and remains optional/pending authorization. |
| Ordinary planning | Live 20-minute filtration plan grounded in attached self-authored PDF; no experiment |
| Plan save | Saved through confirmation for 2026-09-14; timeline shows planned lesson, zero taught lessons |
| Saved-PDF bridge | Library discovers same material ID and opens existing extraction without upload/OCR |
| Chapter approval and enrichment | Both PDFs approved through UI; energy mappings corrected and reviewed; map revision 4 has 13 concepts, 13 connections and 6 material links |
| Teacher chemistry review | Refined filtration goal; clarified that filtrate can contain dissolved salt; removed a broad exo/endo mapping from a chapter teaching only the exothermic example; changed catalysis mapping from extends to explains |
| Archive/restore | Unsaved learning-goal correction survived both actions |
| Invalid inputs | Malformed PDF returned 422 before OCR; duplicate saved PDF returned 409 with existing material guidance |
| Next lesson without upload | Filtration follow-up saved for 2026-09-16 from approved material and recorded learning difficulty |
| Energy lesson without upload | A 25-minute activation-energy/catalysis lesson saved for 2026-09-18 using the approved energy chapter, its rendered diagram and table, and prior approved learning observations. The teacher corrected one source-task wording mismatch in the normal plan editor before review/save; the saved lesson retains the correction. No new upload or developer data repair. |
| Approved results | Synthetic 2026-09-14 results reviewed and saved; a terminology-only correction used the normal diary edit/review/save controls |
| Map → lesson | Desktop inspector showed planned 2026-09-16 and approved-results 2026-09-14 links separately; results link opened ordinary lesson detail |
| Second account | Empty workspace had no classes; UI-created the same class ID with a different label, empty materials and fresh plan; original account's classes/draft returned on login |
| Demo compatibility | Grade 9 demo retained real seeded history (last taught 2026-05-29) and its 10-concept / 7-connection seed proposal |
| Controlled generation failure | Temporary local one-second timeout produced 502 plus immediate Retry/Discard controls; adopted map unchanged |
| Restore and retry | Stopped backend; 197 copied files byte-identical; all 7 SQLite integrity checks passed. Restored map, two PDFs, lessons, both accounts and failed request. Normal 240-second timeout restored; browser Retry created a proposal from the saved request |
| Proposal controls | Reversed prerequisite in review, rejected optional new concept, observed dependent connection disappear and factual counts return to zero, then discarded proposal; adopted map stayed revision 4 |
| Source display | Approved filtration PDF and original energy PDF opened in browser; original energy diagram visually checked. The in-app PDF viewer opened page 1 despite a correct `#page=3` URL; page-selection mapping is separately verified by deterministic tests. |
| Onboarding and processing guidance | First-session documentation renders demo and own-class paths. Both the standalone upload form and ordinary planning attachment dialog display the shared Mistral OCR / OpenAI processing note. |

## Remaining acceptance

- Integrate and deploy the locally verified branch; the commit containing this
  acceptance record is the local implementation checkpoint, not a deployed build.
- Browser limitations: the fast requests completed before two attempted
  interruptions; the controlled timeout plus stopped-backend restore/retry
  provides the actual failure/recovery evidence. Source-PDF page fragments do not
  automatically select the requested page in the in-app viewer. Exhaustive race,
  upload-limit and cross-account source-access cases are deterministic test
  evidence, not claimed as successful browser interactions.
- Hosted deployment, restored hosted-volume check and an external teacher pilot
  require separate evidence; local completion does not imply those occurred.

## Test evidence

Full deterministic backend suite: **838 passed, 45 opt-in live cases skipped**, no
test exclusions. The two previous failures were expired fixed-date test fixtures
and an async readiness assumption; test-only fixes preserve expiry behavior.
Frontend: **252 tests in 55 files passed**; TypeScript and production build passed.
Build retains existing nonfatal Tailwind ambiguity warnings and backend tests
retain a deprecated eval-model warning. OpenAPI includes all 26 course routes and
the `uses_linked_material` relation.

Focused deterministic suites cover workspace provisioning, class creation,
source/section compatibility, archive lifecycle, generation durability/races,
correction editing, request-grounded planning, lesson links and two-cookie beta
isolation. Independent final review found two P2s (stale OCR summaries and
nonascending source-page mapping); both were fixed and independently rechecked.
The additional material-use lesson association and OCR-only review guidance were
also independently reviewed with no new P1/P2 findings.
Operator steps are in [the release runbook](../../docs/course_release_runbook.md).
