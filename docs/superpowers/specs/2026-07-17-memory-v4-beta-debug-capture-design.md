# Memory V4 Beta Debug Capture Design

## Purpose

Provide a temporary, local-only flight recorder for manual Memory V4 testing
in the real app. A developer can perform a small number of intentional chat
turns, inspect the complete memory path, and promote useful examples into
deterministic goldens and tests.

The recorder is a development diagnostic. It is not teacher-facing product
telemetry and is not a durable production observability system.

## Scope and configuration

The recorder runs only when all of the following are true:

- the app uses beta storage (`BETA_ENABLED=true`);
- the app is not production (`APP_ENV=development` for this test run); and
- `MEMORY_V4_DEBUG_CAPTURE=true` is explicitly set.

The worktree runtime uses `MODEL_PROFILE=economy`. That routes normal chat to
the cheap model at medium reasoning and keeps Memory Sweep on the strong model
at high reasoning, because Sweep is the second semantic judge for durable
memory. Existing development trace endpoints remain enabled outside production.

`backend/.env` is a local, untracked copy of the main repository's runtime
configuration. Credentials and this debug flag are never committed.

## Architecture

Use beta storage for a small searchable index and a beta-data trace directory
for the full payload. The same `trace_id` joins the two.

```text
real beta app turn
  -> existing workflow trace / stream / memory services
  -> MemoryV4DebugRecorder (no-op unless explicitly enabled)
       -> beta SQLite index: identity, workflow, session, turn, outcome, path
       -> beta data JSON: complete append-only diagnostic bundle
  -> normal teacher-visible stream (unchanged and sanitized)
```

This deliberately does not overload the existing generic beta `event` rows
with multi-megabyte prompts and tool output. It preserves their operational
reporting role while making full traces readable from disk.

One trace bundle is created for each memory-relevant chat turn. Later Sweep
and Apply operations append lifecycle records to the relevant bundle or create
their own linked operation bundle when no chat turn is available.

## Captured data

Each JSON bundle is append-only and records timestamped lifecycle events.
It includes only data already present in the local workflow/runtime.

1. Identity and routing: beta workspace, class, app session, workflow/session,
   turn number, model profile/model/effort, and code version where available.
2. Context and prompt: teacher message, bounded workflow history, runtime state,
   memory/context-pack sections, prompt assembly metadata and assembled text.
3. Model execution: API/SDK reasoning events that are actually exposed, model
   responses, tool calls, arguments, outputs, and errors. It does not claim to
   expose a hidden private chain of thought not emitted by the API.
4. Admission and priority: raw `remember` proposals, verified quote/provenance,
   speech act and scope, deterministic allow/reject/hold reasons, batch cap,
   ledger inserts, folds, reinforcement, and fast-lane verdicts.
5. Sweep: selected ledger evidence, target excerpts/context, consolidation
   output, backend validation/retries, operation decisions, review fingerprint,
   and persisted review cards.
6. Apply: explicit teacher decision, affected candidates, result/warnings,
   ledger closure, changed paths, and local wiki diff.

Raw content is allowed only because this is an explicit local beta debugging
run. It must never be added to standard beta reports, normal event payloads, or
teacher-visible server-sent events.

## Integration boundaries

Introduce one narrow `MemoryV4DebugRecorder` service with explicit recording
methods and a no-op implementation when disabled. It owns file layout, JSON
serialization, redaction boundary, and index writes. Existing domain services
remain authoritative for their decisions.

Record at these boundaries:

- prompt/context assembly and raw local stream event capture in the three chat
  workflows (Discuss, Plan, Update Memory);
- durable candidate discipline and ledger persistence;
- Memory Sweep proposal/consolidation and review persistence; and
- teacher-approved Memory Apply and wiki diff recording.

The recorder observes already-built values. It must not influence candidate
admission, model prompts, sweep behavior, or apply behavior. Capture failures
are logged and do not fail a teacher workflow.

## Manual test and golden workflow

1. Start the worktree beta stack with the copied local environment, development
   app environment, economy profile, and explicit recorder flag.
2. Exercise a small intentional scenario set: direct standing preference,
   "always" observation that must not fast-lane, uncertain scope/speech act,
   multi-claim batching, repeated evidence/folding, Sweep merge/downgrade, and
   teacher approval/apply.
3. Use a local inspection script to list bundles and render a concise timeline
   plus links/files for raw context and events.
4. Review selected bundles with the teacher/developer. Convert stable expected
   behavior into existing deterministic memory-capture, batch, ledger, and
   sweep goldens. Keep live bundles out of CI.

## Failure handling and cleanup

- Recorder writes are best-effort: a serialization or filesystem failure cannot
  block chat, Sweep, or Apply.
- Each bundle records recorder errors in its index when possible.
- The feature is controlled by one explicit flag and beta-only guard. Turning
  the flag off returns the app to current behavior.
- When the diagnostic cycle is complete, remove the recorder and its tests or
  retain only the general-purpose trace improvements that prove useful. Delete
  the local beta data directory separately; it is untracked test data.

## Acceptance criteria

- A beta development turn in each workflow produces an inspectable bundle when
  the flag is on and produces no bundle when it is off.
- A bundle explains the full Admission -> Priority -> Sweep -> Apply path for
  a candidate, including reason codes and the underlying context/prompt.
- Existing teacher stream safety remains unchanged: raw reasoning and tool
  payloads are not exposed in ordinary UI events.
- Existing beta telemetry/reporting and normal tests continue to work.
- A developer can select a real bundle and create a deterministic golden from
  it without rerunning a live model call.
