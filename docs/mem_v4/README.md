# Memory System — Active MemV4 Documentation

MemV4 is the active home for KlassenPilot's durable-memory behavior. The
runtime contract is stable: chat stages review-only candidates, the ledger
folds and gates them, Sweep makes one bounded consolidation judgment, and the
teacher remains the only durable-write authority.

## Read order

1. [`mem_v4_codex.md`](mem_v4_codex.md) — current lifecycle, context,
   admission, priority, Sweep, Apply, and invariants.
2. [`evaluation.md`](evaluation.md) — deterministic contracts, opt-in live
   checks, local trace handling, and golden policy.
3. [`mem_v4_live_eval_ledger.md`](mem_v4_live_eval_ledger.md) — active
   beta-derived regressions, known gaps, and ownership.
4. [`mem_v4_codex_implementation_plan.md`](mem_v4_codex_implementation_plan.md)
   — retained implementation history.
5. [`mem_v4_beta_debug_capture_implementation_plan.md`](mem_v4_beta_debug_capture_implementation_plan.md)
   — temporary local beta-debug capture operations.

## Historical reference

- [`archive/mem_v2_summary.md`](archive/mem_v2_summary.md) and
  [`archive/mem_v3_summary.md`](archive/mem_v3_summary.md) preserve only the
  durable decisions that led here. The full MemV2/MemV3 document trees and the
  V4 discovery notes (brainstorm, empirical inputs) were removed during doc
  consolidation and live in Git history.

Related current contracts: [`../agent_contracts.md`](../agent_contracts.md),
[`../agent_architecture.md`](../agent_architecture.md), and
[`../memory_hierarchy.md`](../memory_hierarchy.md)
(including [§3 Class Teaching Framework Adjustments](../memory_hierarchy.md#3-class-teaching-framework-adjustments)
for class overrides of immutable shared frameworks).
