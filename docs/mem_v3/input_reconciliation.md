# Input ↔ Wiki reconciliation (design note + eval scaffold)

Status: **design + eval scaffold, not yet implemented.** Surfaced by beta
testing (2026-07-07). Owner principle captured below; deterministic detector +
clarify wiring are a tracked follow-up. The live LLM judge now documents the
desired behavior; the non-roster clarify case is an intentional xfail until the
detector/model-clarify path is wired. Real-user validation deliberately
deferred (see "Test with real users").

## The principle

**The committed wiki is the baseline; teacher input that conflicts with it is a
*proposed* change, not a silent overwrite.** The agent should trust the wiki
first and **clarify** a discrepancy, only accepting the deviation on explicit
teacher confirmation ("a new student joined", "yes, this changed"). This matches
2026 memory-agent practice (write-time conflict resolution; HITL for contested
writes) and KlassenPilot's existing rule that HITL applies to *writes*.

Concrete trigger from beta: the teacher's notes referenced student IDs that
weren't on the roster (typos). The agent handled it well **once asked**, but the
teacher wants it **proactive**: flag non-roster IDs at draft time, don't silently
record a non-existent student, don't fabricate one.

## Why a prompt alone is too brittle (the lesson we keep relearning)

Telling the model "check every ID against the roster and ask if it collides"
relies on the model *remembering to run a check every turn* — the same
emission-gap failure mode as capture (mem_v3 PR4), and worse on the economy
profile (`gpt-5.4-mini`), where these checks matter most for cost. Roster
membership is a **deterministic fact**, not a judgment; leaving a yes/no factual
check to the model's attention is the anti-pattern the whole capture-discipline
design pushes against.

## The pattern: deterministic detect → model clarify → HITL confirm

| Step | Owner | What |
|---|---|---|
| **Detect** | deterministic code | Validate student-target observations against the roster (a pure function — see `non_roster_ids()`). Same shape as the `remember()` tool's quote-provenance check: ground in truth, don't guess. |
| **Clarify** | the model | On a flagged mismatch, surface it in natural language: *"S-099 isn't in this class — a typo, or did a new student join?"* The model owns the phrasing, not the detection. |
| **Confirm** | the teacher (HITL) | The wiki wins until the teacher explicitly authorizes the change: "new student → add to roster" (explicit write) vs "typo → drop/correct". No silent write, no silent drop. |

Split rule: **deterministic code for anything factual/safety-critical** (roster
membership, contradicting a committed value); **prompt + model for the
fuzzy/semantic** (a light "the committed wiki is the baseline; surface conflicts,
don't overwrite" line is a fine *complement*, never the sole mechanism).

## Related gap — removal on revise (tombstone)

Revising a lesson is idempotent per `lesson_date` for entities the new diary
*mentions* (each rollup replaces its `## {date}` section — see
`test_ingest_idempotency.py`). But an entity that *disappears* between versions
(e.g. a typo'd student committed, then removed in a later revision) leaves an
orphaned date section — a classic deletion/tombstone gap. Narrow today (the beta
flow removes typos from the draft *before* the first save), but real. Fix: at
commit, diff prior-committed vs new entities for the date and strip the
difference.

## Eval scaffold (in place)

- Goldens: `backend/tests/evals/goldens/wiki_input_reconciliation.py` — three
  paths: non-roster observation → **flag/clarify**; valid observation →
  **accept**; explicit "new student joined, add them" → **accept (confirmed
  change)**.
- Eval: `backend/tests/evals/test_klassenpilot_wiki_reconciliation.py`
  - Deterministic (always-on): verifies each golden's `non_roster_ids` against
    the real roster — proving detection is pure code, and guarding the goldens.
  - Live judge (opt-in, `RUN_LIVE_AGENT_EVALS=1`): runs each scenario through a
    real ingest turn; clarify cases **xfail** (documented target, not a red
    regression) until the detector + clarify are wired; "don't spuriously flag /
    don't mislabel an explicit new student" hard-fail (real regressions).

## Implementation follow-up (when greenlit)

1. Deterministic roster-membership validator on student observations at
   draft/commit; surface flagged IDs to the model/UI.
2. Wire the clarifying question + the confirm path (new roster entry only on
   explicit teacher confirmation).
3. The removal-on-revise tombstone fix.
4. Flip the live clarify xfails to expected passes; measure on the production
   profile (`gpt-5.5`).

## Decisions (2026-07-07)

- **Beta = names-first, IDs stay the internal key.** The agent should chat, reply,
  and display in student **names**; wiki entity files remain `students/S-###.md`
  (names are the display label, IDs the key). Keeps the pseudonymity layer intact
  and reversible for real (non-fake) students post-beta. This is a *display /
  render* change, not a re-keying: input names already map to IDs
  (`_pseudonymize_known_students`); the work is (a) stop showing raw `S-###` on
  teacher-facing surfaces and (b) resolve names→IDs at commit so observations
  still file under the right entity.
- **The roster check works on names + IDs.** Once built, flag both a mistyped
  `S-###` and a **name that doesn't match any enrolled student** (normalized /
  fuzzy compare against the roster name column) — not only exact-ID membership.
  The current `non_roster_ids()` detector is the ID half; a `non_roster_names()`
  half (fuzzy) is added when the detector is wired.

## Test with real users (deferred, on purpose)

The judge eval documents the *target*, but the real signal is behavioral with
teachers: does proactive flagging feel helpful or naggy? How often are
non-roster IDs typos vs genuine new students? Does "trust the wiki, confirm
changes" match teacher mental models, or do they expect the agent to just accept
their notes? Validate with real testers before hardening thresholds — captured
in the backlog, not to be settled from goldens alone.
