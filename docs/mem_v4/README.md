# Memory V4 Docs

Brainstorm and decision notes for the next memory write-admission tightening
after Memory V3.

**Read order:**

1. [`empirical_inputs.md`](empirical_inputs.md) — sandbox ledger + Sweep cards +
   teacher prompts + current capture policy (the concrete failure case).
2. [`brainstorm.md`](brainstorm.md) — background, root cause, `ref_repos`
   functions/prompts/multi-model notes (§4.8–4.9), recommended changes.

3. [`mem_v4_codex.md`](mem_v4_codex.md) — approved central design and
   end-to-end contracts.
4. [`mem_v4_codex_implementation_plan.md`](mem_v4_codex_implementation_plan.md)
   — execution checklist and remaining integration gaps.

Supporting dumps: `_ledger_snapshot.json`, `_sweep_cards.json`.

Related:

- V3 design and learnings: [`../mem_v3/`](../mem_v3/)
- Codex hardening design: [`mem_v4_codex.md`](mem_v4_codex.md)
- Behavior contract: [`../agent_contracts.md`](../agent_contracts.md)
- Architecture: [`../agent_architecture.md`](../agent_architecture.md)

Status: V4 implementation in progress on the shared `codex/mem4` branch.
