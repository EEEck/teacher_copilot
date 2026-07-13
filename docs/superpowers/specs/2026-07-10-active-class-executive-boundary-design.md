# Active-Class Executive Boundary Design

## Goal

Keep every planning and update-memory chat strictly within its URL-selected
class while preserving proactive verification and durable-write protection.

## Product contract

Each workflow session is strictly limited to its active class; the copilot may
verify that a reference does not belong to that class, but must never search,
suggest, or offer to move work to another class.

The assistant may say that an ID, lesson, or concept is not supported by the
active class record. It must leave the mismatched fact out of the artifact and
ask only for an active-class correction, removal, or an explicit correction to
the active class's own history. A question about what the class covered is an
evidence request, not a new lesson fact.

## Scope

- Add the contract and the history-question rule to the shared executive prompt.
- Extend the prompt regression test to pin both phrases.
- Add ingest goldens for unknown student IDs and unsupported Hartree--Fock
  content/history, including no cross-class teacher-facing wording.
- Update the LLM judge criteria to enforce the same boundary.

## Non-goals

- No class-switching UI, workflow, or API.
- No new cross-class read path or roster-specific tool.
- No change to the existing known valid-input live-eval calibration finding.

## Verification

Run deterministic eval-definition/prompt tests first. Then run the opt-in live
executive-verification evals and LLM judge. A prompt-calibration failure is
reported rather than hidden; unrelated known valid-input over-blocking remains
documented separately.
