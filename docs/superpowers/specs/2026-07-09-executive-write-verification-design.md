# Executive Write Verification — Milestone C Design

## Goal

Protect durable plan and memory writes using the exact teacher-submitted draft,
while giving the teacher a clear way to correct or discuss a blocked edit.

## Product behavior

KlassenPilot keeps the foreground artifact intact and does not silently alter
or discard a teacher's manual edit. At every relevant durable-write boundary it
checks the exact submitted text against committed class state and the current
executive-verification state.

If the check passes, the requested save/proposal/commit proceeds. If it finds a
consequential unresolved mismatch, the action is blocked and the teacher sees a
concise assistant-style explanation, for example:

> I didn't save this yet: S-099 is not in Chemie 9b's roster, and this edit
> would create a durable student note. You can correct the draft, tell me which
> student you meant, or confirm that this is a new student.

The teacher can edit manually and retry, or continue the existing chat to ask
the copilot to correct the draft. A new student, changed class, or disputed
lesson history remains a teacher-approved change; the verifier never writes it
silently.

## Scope

Apply this behavior at three boundaries:

| Boundary | Exact input verified | On success | On block |
|---|---|---|---|
| Plan save | `SavePlanRequest.plan_markdown` | Save the plan | Do not write the plan |
| Ingest propose | Current diary submitted for proposal | Build review proposals | Do not create proposals |
| Ingest commit | `CommitIngestRequest.diary_markdown` and approved updates | Commit wiki updates | Do not write wiki files |

The existing shared executive chat loop remains unchanged. Profile proposals,
memory sweep application, and other non-artifact flows are out of scope for
this milestone.

## Architecture

### Exact-draft verifier

Add a focused, read-only verifier run. It receives only the exact submitted
artifact, compact authority-labelled class context, and current executive
state. It may use the existing class-scoped read/search/reference-resolution
tools when needed. It returns a structured verification patch and a digest of
the submitted text; it has no write tools and cannot change the artifact.

The backend computes the SHA-256 digest itself after newline normalization and
uses it as the source of truth. A result is usable only for the same digest.

### Gate

The write gate permits the side effect only when:

1. the verifier result fingerprint equals the exact submitted artifact;
2. the verifier/runtime has no open blocking findings; and
3. the workflow's existing structural readiness rules still pass.

This is intentionally a fresh verification at every boundary. Reusing the last
chat result would allow a stale artifact or a manually introduced error to
bypass the irreversible-action check.

### Blocked-action contract

A blocked write returns HTTP `409` with a typed payload containing:

- `code: "write_verification_blocked"`;
- the requested action (`plan_save`, `ingest_propose`, or `ingest_commit`);
- the artifact fingerprint;
- the current `executive_state`, including open findings and evidence refs;
- a teacher-visible, concise `message`.

The frontend preserves the draft and renders this as a system-generated
assistant-style message in the existing artifact workspace. It does not
auto-send a repair message or mutate the draft. On the next teacher chat turn,
the pending verification finding is already in shared executive runtime, so the
copilot can explain or fix it when asked.

## Data and state rules

- `ExecutiveRuntime` records the latest write-verification fingerprint and
  result separately from workflow-specific state.
- A fresh verifier replaces or resolves only findings relevant to the exact
  submitted artifact. It must not preserve an old blocking finding that the
  teacher removed from the draft.
- The backend, not the verifier, hashes input and decides whether the side
  effect may execute.
- A verifier may identify a discrepancy; it may not accept a contested fact as
  canonical or mutate wiki state.

## Failure handling

- Verifier transport/model failure fails closed for durable actions, returning a
  typed retryable error without writing anything.
- A stale/mismatched digest fails closed as `artifact_changed_since_verification`.
- Existing `ValueError` validation errors remain `400`/`422`; write-verification
  blocks are specifically `409` so the UI can preserve the recovery context.

## Tests

Deterministic unit/API coverage must prove:

1. a structurally ready plan/diary with a matching, clear verifier result writes;
2. an unresolved existing blocking finding prevents each relevant action;
3. a manual edit is reverified rather than relying on the last chat artifact;
4. a manual edit that introduces an unknown student blocks with `409` and
   writes nothing;
5. a manual edit that removes the issue can pass after fresh verification;
6. verifier failure performs no durable write; and
7. the `409` payload has enough data for the existing chat UI to render a
   teacher-facing recovery message.

Live evals are not required to land the boundary contract. Once stable, add
one opt-in golden that demonstrates a manual edit blocking and recovery.

## Non-goals

- No broad skill/subagent framework.
- No autonomous roster/class/history writes.
- No new wizard or separate validation mode.
- No change to the known valid-input over-blocking live-eval finding; that is a
  later prompt/runtime calibration task.
