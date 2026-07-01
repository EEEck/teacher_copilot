# Bug: Explicit Teacher Preference Is Not Captured As Memory Candidate

Status: partially fixed; architecture plan updated
Date: 2026-06-23
Area: planning chat -> memory candidate ledger
Severity: high for memory learning; no direct wiki corruption

## Summary

When a teacher explicitly states a durable communication preference during
lesson planning, the planner can understand and follow the preference but still
fail to emit a `memory_candidates` item. Because persistence only records
candidates emitted by the agent/runtime, no row is written to the SQLite memory
candidate ledger. The preference is therefore lost after the session unless it
is manually captured elsewhere.

This is not a request for a deterministic keyword fallback. The bug is that the
current capture architecture relies on the main planning model to voluntarily
route durable preference signals into the candidate channel.

## Repro Script

Run with the backend already running:

```powershell
.\backend\.venv\Scripts\python .\scripts\reproduce_memory_candidate_capture_bug.py
```

The script:

1. Starts a new lesson-planning session for `chemie_9b_2026_27`.
2. Runs a three-turn planning scenario.
3. Makes the second teacher turn an explicit durable preference:

```text
Please adjust the plan. From now on, for all lesson-planning summaries, I want you to use MBB-style communication: start with the recommendation, then give 2-3 crisp reasons, then only the essential next steps. This is a general communication preference for me, not just this one class.
```

4. Writes a full raw trace bundle under `backend/runs/`.
5. Queries `backend/teacher_wiki/workflow/memory_candidates.sqlite` for the
   generated `session_id`.
6. Writes `bug-repro-summary.json` into the run directory.

## Expected Behavior

The turn should produce a durable-memory candidate, but not directly update the
wiki. Expected candidate shape:

```json
{
  "target": "user.md",
  "section": "Communication",
  "candidate_update": "Prefers MBB-style communication for lesson-planning summaries: recommendation first, 2-3 crisp reasons, then only essential next steps.",
  "basis": "explicit",
  "source": "chat_observation",
  "confidence": "high",
  "status": "draft"
}
```

The candidate should appear in:

- `PlanRuntime.memory_candidates`
- the final SSE event's `memory_candidates`
- the SQLite memory candidate ledger

No canonical wiki file should be changed without teacher approval.

## Observed Behavior

Fresh repro run created by `scripts/reproduce_memory_candidate_capture_bug.py`:

```text
backend/runs/20260623-memory-candidate-capture-bug-repro
```

Fresh repro summary:

```json
{
  "bug_reproduced": true,
  "session_id": "2dfdf807-ed53-4f68-b7ab-be84c690a893",
  "artifact_mentions_mbb": true,
  "runtime_memory_candidates_count": 0,
  "final_sse_memory_candidates_count": 0,
  "sqlite_ledger_rows_count": 0,
  "prompt_calls": 4,
  "tool_calls": 9,
  "raw_evidence_items": 9
}
```

Existing raw trace bundle:

```text
backend/runs/20260623-memory-pref-plan-trace
```

Session id:

```text
219d6422-823f-492a-b00f-f59e9aeccbbe
```

The model followed the preference in the visible final reply:

```text
Recommendation: this lesson is ready to save.

Why this works: it stays tightly grounded in the recent redox sequence from class memory, keeps the charge-vs-oxidation-number contrast visible, and uses a short, exam-oriented flow that fits the class.

Next step: if you are happy with it, you can click Ready to save plan.
```

The model also put the preference into transient planning state:

```json
"decisions": [
  "Use MBB-style communication for future lesson-planning summaries"
],
"teacher_preferences_for_this_lesson": [
  "Use MBB-style communication for future planning summaries"
]
```

The final plan artifact also contains:

```text
For future planning summaries, use MBB-style communication: recommendation first, then 2-3 crisp reasons, then only the essential next steps.
```

But the final SSE event ended with:

```json
"memory_candidates": []
```

The final runtime trace also shows:

```json
"memory_candidates": []
```

SQLite ledger query for the session returned:

```json
[]
```

```text
count= 0
```

## Raw Trace Artifact Manifest

All raw artifacts for the observed run are in:

```text
backend/runs/20260623-memory-pref-plan-trace
```

A fresh repro bundle with the same failure is in:

```text
backend/runs/20260623-memory-candidate-capture-bug-repro
```

Its machine-readable summary is:

```text
backend/runs/20260623-memory-candidate-capture-bug-repro/bug-repro-summary.json
```

Files:

```text
00-run-meta.json
01-session-start.json
02-trace-before-first-message.json
03-turn1-sse.txt
04-trace-after-turn1.json
05-turn2-sse.txt
06-trace-after-turn2.json
07-turn3-sse.txt
08-trace-after-turn3.json
09-final-lessonplan.md
10-tool-calls-and-results.md
prompt-01-plan_opening-instructions.txt
prompt-01-plan_opening-sections.md
prompt-01-plan_opening-user-input.txt
prompt-01-plan_opening.json
prompt-02-plan_chat-instructions.txt
prompt-02-plan_chat-sections.md
prompt-02-plan_chat-user-input.txt
prompt-02-plan_chat.json
prompt-03-plan_chat-instructions.txt
prompt-03-plan_chat-sections.md
prompt-03-plan_chat-user-input.txt
prompt-03-plan_chat.json
prompt-04-plan_chat-instructions.txt
prompt-04-plan_chat-sections.md
prompt-04-plan_chat-user-input.txt
prompt-04-plan_chat.json
README.md
snapshot-00-before-first-message-instructions.txt
snapshot-00-before-first-message-sections.md
snapshot-00-before-first-message-user-input.txt
snapshot-00-before-first-message.json
snapshot-01-after-turn1-next-prompt-instructions.txt
snapshot-01-after-turn1-next-prompt-sections.md
snapshot-01-after-turn1-next-prompt-user-input.txt
snapshot-01-after-turn1-next-prompt.json
snapshot-02-after-turn2-next-prompt-instructions.txt
snapshot-02-after-turn2-next-prompt-sections.md
snapshot-02-after-turn2-next-prompt-user-input.txt
snapshot-02-after-turn2-next-prompt.json
snapshot-03-after-turn3-next-prompt-instructions.txt
snapshot-03-after-turn3-next-prompt-sections.md
snapshot-03-after-turn3-next-prompt-user-input.txt
snapshot-03-after-turn3-next-prompt.json
raw-evidence/list_lessons_001.txt
raw-evidence/read_lesson_004.txt
raw-evidence/read_lesson_005.txt
raw-evidence/read_lesson_006.txt
raw-evidence/wiki_search_002.txt
raw-evidence/wiki_search_003.txt
raw-evidence/wiki_search_007.txt
```

The most important files are:

- `00-run-meta.json`: session id and exact prompts.
- `07-turn3-sse.txt`: final SSE event; shows the MBB-style reply and
  `memory_candidates: []`.
- `08-trace-after-turn3.json`: final backend trace; shows runtime state and
  `memory_candidates: []`.
- `09-final-lessonplan.md`: final plan artifact; shows the preference was
  understood and written into the transient plan.

## Why This Matters

This is exactly the kind of teacher-behavior signal the memory ledger is meant
to preserve. It is explicit, cross-session, low-risk, and belongs in the
teacher profile after review. Losing it means the weekly preference update has
no evidence to review, because full chats are not stored.

## Likely Cause

Current capture depends on the main planner returning optional
`PlanTurnOutput.memory_candidates`. In this trace, the model routed the
preference into:

- conversational reply,
- `session_state.decisions`,
- `lesson_planning_state.teacher_preferences_for_this_lesson`,
- final lesson artifact,

but did not duplicate it into `memory_candidates`. The deterministic backend
then behaved correctly: it persisted no ledger row because no candidate was
present.

In short, the main planning agent was asked to do two jobs at once:

1. Produce and refine the visible lesson plan.
2. Notice durable memory signals and emit `memory_candidates`.

The teacher's signal was explicit and durable:

```text
From now on... for all lesson-planning summaries... general communication preference...
```

The planner understood the preference, used it in the answer, and stored it in
transient planning state. It did not route the same signal through:

```text
PlanTurnOutput.memory_candidates
-> PlanRuntime.memory_candidates
-> SQLite ledger
```

That is the architectural gap: candidate capture is optional inside the main
task agent, so it can be dropped when the model focuses on the visible artifact.

## Non-Goals For This Bug Report

- Do not add deterministic keyword capture for MBB or similar phrases.
- Do not write directly to `user.md`, `teacher_profile.md`, or class memory.
- Do not change canonical wiki files as part of reproduction.

## Proposed Solution

Do not make a second live observer agent the primary path. Use the same workflow
agent for hot-path candidate emission, then protect that contract with a shared
backend memory-capture layer used by both planning and update-memory.

```text
Teacher turn
-> Planning / Update Memory agent emits artifact + state_patch + optional candidates
-> Shared capture layer validates emitted candidates
-> Shared capture layer repairs missed candidates from typed runtime state, if safe
-> SQLite ledger stores candidates
-> Artifact approval or session end may run bounded consolidation
-> Memory Sweep later reviews/promotes ledger evidence with teacher approval
```

The main agent still owns the semantic judgment in the hot path: if the teacher
states a durable preference, the agent should emit a `memory_candidates` item in
the same structured output. The backend repair is a contract normalizer for the
case seen in this bug: the model already detected the preference in
`state_patch`, but forgot to duplicate it into `memory_candidates`.

This is narrower than raw-message keyword extraction. The backend should not
scan arbitrary chat text for words like "MBB" and invent memories. It may only
promote signals that the model has already put into typed runtime state, with
clear durable scope.

## Shared Capture Contract

The shared layer should cover only candidate mechanics, not the full workflow
runtime. `PlanRuntime` and `MemoryRuntime` keep their workflow-specific fields
and artifacts.

Shared responsibilities:

- validate target, source, basis, confidence, and approval requirement;
- dedupe by target and normalized update;
- cap runtime candidate count;
- attach evidence refs and source metadata;
- convert runtime candidates into ledger rows;
- persist rows after completed turns;
- support lifecycle hooks for artifact-approved, session-end, and
  pre-compaction/session-summary capture.

Workflow-specific responsibilities:

- planning owns `plan_markdown`, `PlanRuntime.session_state`, and
  `lesson_planning_state`;
- update-memory owns `diary_markdown`, target resolution, and
  `lesson_result_state`;
- canonical lesson writes remain in the existing teacher-approved commit flow.

## Lifecycle Consolidation Contract

A bounded LLM consolidation call can still be useful, but it should run as a
memory-manager lifecycle hook, not as a second agent after every turn.

Good trigger points:

- after a plan artifact is saved;
- after an update-memory diary is approved and committed;
- at session end;
- before compaction/session-summary if old messages will be dropped;
- during explicit Weekly Memory Sweep.

Inputs should be bounded and explicit:

- latest teacher message
- latest assistant response
- workflow mode: `plan` or `ingest`
- class id and subject
- current `user.md` / teacher profile excerpt
- current class `copilot_profile.md` excerpt
- current runtime memory candidates for dedupe, if any
- target rules and allowlist

The consolidation job should output structured candidates only:

```json
{
  "candidates": [
    {
      "target": "user.md",
      "section": "Communication",
      "candidate_update": "Prefers MBB-style lesson-planning summaries: recommendation first, 2-3 crisp reasons, then essential next steps.",
      "evidence": "Teacher explicitly stated this is a general communication preference.",
      "evidence_refs": ["plan_session:<id>:turn2"],
      "source": "teacher_explicit",
      "basis": "explicit",
      "confidence": "high"
    }
  ],
  "warnings": []
}
```

The consolidation job cannot write wiki files. It only proposes ledger rows.
All durable wiki writes still require teacher review and `/memory/apply`.

## Promotion Boundary

The ledger still means:

```text
observed candidate != approved memory
```

Even explicit preferences should go to the ledger first. Memory Sweep and
teacher approval decide whether to write `user.md`.

For this example:

```text
target: user.md
channel after backend classification: teacher_behavior
queue: Teacher/Copilot Preferences
status: captured
```

## Why This Design Is Better

The planner can focus on teaching work while still carrying the hot-path memory
contract. The backend shared capture layer prevents already-detected durable
signals from being dropped. Lifecycle consolidation gives us a slower, more
focused memory pass at artifact/session boundaries without paying a second LLM
call after every turn.

This also lets us test memory capture independently:

- explicit global preference -> `user.md`
- class-specific copilot rule -> `copilot.md` / `copilot_profile.md`
- class learning pattern -> `teaching_patterns.md`
- subject concept -> `wiki/subjects/chemie.md`
- one-off instruction such as "use MBB just for this answer" -> no durable
  candidate, or a low-confidence session-only signal
- prompt-injection attempt -> no write, optionally a warning

Tests should assert behavior, not exact prose:

- `target == "user.md"`
- `basis == "explicit"`
- `confidence == "high"`
- candidate mentions MBB / recommendation / reasons / next steps
- ledger row exists
- wiki file is unchanged

## Implementation Plan

1. Move candidate validation, dedupe, caps, and rendering into a shared
   workflow memory-capture module.
2. Keep `PlanRuntime` and `MemoryRuntime` separate, but have both delegate
   candidate merge/persistence to the shared module.
3. Strengthen `PlanTurnOutput` and `IngestTurnOutput` field descriptions and
   prompts so explicit durable preferences must be emitted as candidates.
4. Add typed-state repair for durable preferences already captured in
   `state_patch` but missing from top-level `memory_candidates`.
5. Persist through the existing ledger path, after backend validation and
   dedupe.
6. Surface candidates in trace/SSE/API as today.
7. Add `AgentRunner.extract_memory_candidates(...)` only as a lifecycle
   consolidation hook for artifact-approved/session-end/weekly sweep, not as a
   required second call after every chat turn.
8. Add golden tests for the MBB case, negative one-off cases, existing-candidate
   dedupe, class-learning pattern routing, and subject-guide routing.

Key point: no broad deterministic keyword fallback. Deterministic code handles
validation, target allowlisting, dedupe, typed-state contract repair, status
lifecycle, and approved writes. The actual "is this a memory-worthy signal?"
decision should come from the workflow model in the hot path or from a bounded
lifecycle consolidation LLM at explicit capture boundaries.
