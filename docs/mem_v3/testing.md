# Memory V3 Testing

Test-driven: fixtures and failing goldens land in Phase 1, before behavior
changes. Three tiers, consistent with `backend/docs/evals.md`.

## Tier 1 — Offline deterministic pytest (default, CI)

Real recorded beta data as fixtures (extracted once, anonymized):

- `organic_chemistry_ledger.json` — 12 rows / 4 claims across 4 sessions
  (the over-capture case).
- `mbb_repetition_ledger.json` — the preference applied 6× in V2.

Assertions per layer:

- **Ledger/folding**: 12 rows insert into ≤5 open clusters; exact dup →
  `duplicate`; rephrasing adopts matched cluster_key; sections normalized to
  vocabulary; applied-match → `already_covered`; rejected-match →
  `suppressed` unless explicit_ask.
- **Gate**: singleton inferred held back; 2-session cluster eligible;
  explicit_ask always eligible; stale singleton expires at +42d (clock
  injected).
- **Capture classification**: "organize this in mbb style" → inferred/low;
  "use mbb style for all future briefs" → explicit_ask; repaired state
  candidates get the same classification.
- **Sweep contract** (LLM stubbed): operations validate structurally —
  unknown memory_id rejected with retry; UPDATE quoting enforced; full claim
  coverage enforced; second failure → exactly one notice, zero cards, no raw
  reason in payload.
- **Budgets**: over-budget apply fails with actionable message; near-budget
  usage is included in sweep propose input.

## Tier 2 — DeepEval goldens (CI-safe, agent stubbed / recorded)

Extend `backend/tests/evals/` pattern: ledger-replay scenarios scored on
structure, not prose —

- card count ceilings per fixture ("this ledger must never produce >N
  cards");
- merge correctness (4 rephrasings → 1 card, signal_count 4);
- class_state transition → UPDATE of the current-unit bullet;
- explicit_ask claims land in the pinned section.

## Tier 3 — Live traces (opt-in, real model)

- Migrate `scripts/trace_memory_mbb_executive_consolidation.py` to the
  single-call sweep; keep the pass bar: `full_merge_cards=1`, one
  `teacher_profile.md / Communication` card representing all seeded ids.
- New trace: seed the organic-chemistry fixture ledger into a temp workspace,
  run live sweep, assert ≤5 cards / zero warnings; store bundle under
  `backend/runs/`.
- Live capture drift check: replay the recorded beta transcripts (from
  `beta.sqlite3` messages) through ingest chat; assert candidate counts and
  tags per turn.

## Telemetry as the production feedback loop

`memory_sweep_propose` events already record card_count/queue_counts/
warning_count per run. Success metric for V3 in the next beta round:
median cards per sweep ≤ 6, warning_count 0, and no repeat-approval of the
same preference across batches.
