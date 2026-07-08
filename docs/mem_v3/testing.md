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
  `suppressed` unless the new capture has backend-verified `fast_lane=True`.
- **Gate**: singleton inferred held back; 2-occasion cluster eligible;
  backend-verified `fast_lane` eligible; stale singleton expires at +42d
  (clock injected). Unanchored rows use 6-hour buckets as occasions.
- **Capture classification**: "organize this in mbb style" → inferred/low;
  direct quote evidence for "use mbb style for all future briefs" plus
  `speech_act=conduct_request` → `fast_lane=True`; explicit store requests
  can fast-lane content targets; class_state never can.
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
- merge correctness (4 rephrasings → 1 card, occasion_count derived from
  distinct occasion anchors / 6-hour buckets);
- class_state transition → UPDATE of the current-unit bullet;
- verified fast-lane claims land in the pinned section; quote markers alone
  do not.

## Tier 3 — Live traces (opt-in, real model)

Live agent eval fixtures default to the production model profile, independent
of local development/economy settings. Use `LIVE_AGENT_EVAL_MODEL_PROFILE` only
for explicit model-profile comparison runs.

- Migrate `scripts/trace_memory_mbb_executive_consolidation.py` to the
  single-call sweep; keep the pass bar: `full_merge_cards=1`, one
  `teacher_profile.md / Communication` card representing all seeded ids.
- New trace: seed the organic-chemistry fixture ledger into a temp workspace,
  run live sweep, assert ≤5 cards / zero warnings; store bundle under
  `backend/runs/`.
- Live capture drift check: replay the recorded beta transcripts (from
  `beta.sqlite3` messages) through ingest chat; assert candidate counts and
  tags per turn.
- Live speech-act / tool-target check (opt-in): replay direct conduct requests,
  explicit store/remove requests, observations, fabricated quotes, rejected
  near-duplicates, verified-explicit overrides, and class-state non-fast-lane
  cases. Assert component-level tool behavior before the final verdict:
  expected memory targets, forbidden targets, minimum candidate count for
  overlap cases, emitted `speech_act`, and internal `routing_reason`; then
  assert the backend-computed `fast_lane` verdict, not raw model `source`.

## Telemetry as the production feedback loop

`memory_sweep_propose` events already record card_count/queue_counts/
warning_count per run. Success metric for V3 in the next beta round:
median cards per sweep ≤ 6, warning_count 0, and no repeat-approval of the
same preference across batches.
