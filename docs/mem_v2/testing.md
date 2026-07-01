# Memory V2 Testing And Traces

Memory V2 tests should keep the hot path deterministic and use live-model trace
scripts only as drift signals.

## Deterministic Backend Tests

- `backend/tests/test_memory_capture.py` - shared capture validation, repair,
  dedupe, and runtime integration behavior.
- `backend/tests/test_memory_sweep_backend.py` - ledger grouping, packet
  building, sanitizer behavior, sweep proposal/apply routes, overlapping
  evidence, and MBB/executive-style regression cases.
- `backend/tests/test_memory_targets.py` - target allowlist and channel routing.
- `backend/tests/evals/test_klassenpilot_memory_sweep_stub.py` - stubbed Memory
  Sweep golden scenarios.

Run the focused Memory Sweep suite from `backend/`:

```powershell
.\.venv\Scripts\python -m pytest tests\test_memory_sweep_backend.py tests\test_memory_capture.py -q
```

## Trace Scripts

- `scripts/reproduce_memory_candidate_capture_bug.py` - original live planning
  reproduction for the missing MBB candidate.
- `scripts/trace_memory_pref_mbb.py` - live planning-chat trace for MBB capture.
- `scripts/trace_memory_group_learning_pattern.py` - live Update Memory trace
  for a class learning pattern.
- `scripts/trace_memory_repeated_signal_promotion.py` - seeded ledger scenario
  for repeated class-learning signals and sweep promotion/apply.
- `scripts/trace_memory_mbb_executive_consolidation.py` - seeded ledger
  scenario with two MBB signals plus one executive-style signal. It records
  whether the sweep proposer emits one consolidated
  `teacher_profile.md / Communication` card. Use `--current-memory none`,
  `--current-memory narrow-mbb`, and
  `--current-memory generalized` to check `add`, `adjust`, and
  `already_covered`.
- `scripts/run_memory_sweep_44_trace_bundle.py` - section 4.4 scenario bundle
  for Memory Sweep examples.

Trace outputs under `backend/runs/` are diagnostic artifacts and should not be
treated as source-of-truth docs.

## Expected Regression Shape

For the MBB/executive scenario, the desired sweep proposal is one teacher
review card like:

```json
{
  "target": "teacher_profile.md",
  "section": "Communication",
  "operation": "add",
  "status_recommendation": "promote",
  "content": "Teacher prefers concise executive-style communication, including MBB/McKinsey-style framing when useful.",
  "candidate_ids": ["row_mbb_1", "row_mbb_2", "row_executive_1"],
  "signal_count": 3
}
```

If current memory has narrower MBB wording, the expected operation is `adjust`
with `replaces_content` copied exactly from the current memory excerpt. If
current memory already covers the generalized preference, the expected
operation is `already_covered` with the same represented evidence, not another
duplicate wiki write.

This scenario is a regression test, not a production prompt example. Prompt
tests should assert that active Memory Sweep system prompts do not mention MBB,
McKinsey, consulting-style, or executive-style communication. The production
prompt should instead use domain-neutral classroom examples that teach the same
operation: surface labels become observable alignment fields, shared attributes
become one durable claim, and real distinguishing attributes become scope or
conflict.
