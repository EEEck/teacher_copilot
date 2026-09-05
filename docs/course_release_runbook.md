# Course-map closed-beta release runbook

This supplements [Railway deployment](../deploy/railway/README.md). It describes
the repository's single-process configuration; it does not certify the hosted
environment. Do not move this release to multiple workers/replicas: generation
reservations and approval locks coordinate one backend process, while SQLite and
wiki files persist on its volume.

## Before updating the beta

1. Finish the local acceptance record in
   [course plan 09](../implementation_plans/course_network/09_teacher_owned_release_acceptance.md),
   run backend tests, frontend tests/typecheck and production build, and review
   the final diff. Resolve or explicitly document failures before release.
2. Confirm frontend/backend use the same reviewed commit. Verify the deployed
   branch in Railway before pushing; the existing runbook describes a separate
   beta deploy branch. This feature does not authorize a deployment by itself.
3. Confirm the persistent volume contains `BETA_DATA_ROOT` (normally
   `/data/beta_data`): `beta.sqlite3` plus each workspace's entire `teacher_wiki`.
   Include workspace `workflow/`, material scratch/import files, approved PDFs,
   assets, manifests, graph and lesson files. Backing up only markdown loses
   recoverable drafts and source evidence.
4. Pause writes/stop the backend before a consistent filesystem backup. Copy
   the whole volume tree, including SQLite sidecars. Keep the previous application
   image/commit and restore into a separate test volume first. Do not copy a live
   SQLite main file alone or overwrite a teacher workspace to test restoration.
5. Verify a restored test copy opens classes, graphs, PDF sections and pending
   requests. Record the backup location, commit and restore result in the release
   log; keep secrets out of that log.

## Provisioning and scope

`python -m app.services.beta_cli provision` retains the demo by default. Its
optional `--workspace-mode empty` creates a clean teacher workspace from the
allowlisted shared chemistry assets. Required arguments remain `--tester-id`,
`--workspace-id`, and `--invite-code`; pass a unique invitation through the normal
operator secret workflow. Provisioning preserves an existing workspace.

The homepage lets either mode create a new Chemie 8/9 NTG class. Test with two
invitations and the same class ID: each must see only its own classes, materials,
drafts and lesson records. Demo exploration remains available where provisioned.

## Material processing and operator access

The upload surfaces name the existing processors: Mistral OCR extracts PDF text
and figures; OpenAI uses extracted text for review and planning. Course review
currently sends only `original_ocr` and `proposed_extraction`; independent
original-PDF text is not added. Source inspection remains part of teacher review.

The persistent workspace includes original PDFs, extracted assets, approved text,
lesson artifacts and workflow records. Archive keeps those files for historical
citations; it does not erase them. This release adds no automatic retention/purge
schedule. Before onboarding real teachers, document the beta operator's retention
and deletion process, including backups, and limit access to the hosted volume
and backup copies accordingly.

Follow the existing Railway trace settings: HTTP agent-trace endpoints are off
by default in production and on in development, unless explicitly overridden.
Confirm the actual hosted override and who can inspect telemetry, exports and
traces. Do not put extracted material, session contents or credentials in public
issue reports; use the existing private beta reporting route.

## Interrupted work

- **Chapter extraction:** reopen Course → Materials, resume its import and use
  Retry extraction. Original PDF bytes are saved before the background job.
  Inspect corrections and rerun review before approval.
- **Map generation:** the request, map revision/hash and material snapshot are
  saved before the model call. Leaving the page does not cancel it. After a
  process restart, reopen Materials and explicitly retry the saved request.
  Retry does not silently accept a changed map/material. Discard a stale request
  and start a new one. Never edit SQLite rows to force approval.
- **Review failure:** invalid model output/timeouts produce a retryable error.
  The current adopted graph stays unchanged. Corrected content always needs a
  fresh review at its exact revision/hash.
- **Archived chapter:** Restore material re-enables automatic course retrieval.
  Historical PDF and section references remain readable while archived.

## Hosted smoke test after an approved deployment

Use synthetic content: login → demo → create own class → adopt seed → upload a
short selected-page PDF → edit/review/approve → enrich/review/approve → plan using
that chapter without reupload → save → approved lesson results → next plan.
Check source links, sign-out/account isolation and pending-work recovery after a
backend restart. Run one restored-volume read check. External teacher feedback
and this hosted check remain distinct from local Docker evidence.
