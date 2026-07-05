# Memory V3 Docs

Working design and implementation notes for the Memory V3 effort: fewer,
better memory proposals through source-side throttling, a single-call
high-reasoning sweep, and hard budgets on curated memory. The durable product
contract still lives in `../agent_contracts.md`; Memory V2 background is in
`../mem_v2/`.

## Read Order

1. `design.md` — why V3 exists, what V2 got right and wrong (with beta
   evidence), the V3 architecture, and the borrowed-code table.
2. `implementation_plan.md` — phased build plan with file-level touchpoints.
3. `testing.md` — test-driven approach: offline fixtures from real beta
   ledger data, DeepEval goldens, and live drift traces.

## One-Paragraph Summary

V2 proved the capture → ledger → sweep → HITL apply lifecycle but produced
far too many review cards: blind per-session capture re-emitted the same
claims, exact-hash clustering never merged rephrasings, packet-by-section
fragmentation hid duplicates from the alignment LLM, and over-constrained
lexical validators turned correct merges into unresolvable `needs_decision`
cards. V3 keeps the lifecycle and the strict HITL boundary (teacher-triggered
sweep, every write reviewed) and adds the missing brakes: capture grounded in
teacher words only with visibility into existing memory, deterministic
insert-time folding, an OpenClaw-style promotion gate, one mem0-style
ID-referenced consolidation call on an expensive reasoning model, and
hermes/letta-style character budgets that force compaction.

## Invariants Carried Over From V2 (unchanged)

- Chat workflows capture review-only candidates; no direct durable writes.
- The SQLite ledger is never prompt-facing truth before teacher review.
- `/memory/sweep/apply` stays deterministic: wiki writes first, ledger status
  updates after.
- `teacher_profile.md`, `copilot_profile.md`, class compact memory, and
  subject guides remain curated memory.
- No embeddings, graph memory, or autonomous writes.

## Regression Checks

Deterministic tests plus the MBB/executive merge trace remain the gate for
any sweep/prompt/grouping change (see `../mem_v2/README.md` for commands).
V3 adds ledger-replay goldens built from recorded beta data — see
`testing.md`.
