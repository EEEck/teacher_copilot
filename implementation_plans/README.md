# Implementation Plans

This folder is intentionally narrow:

- `product_backlog.md` - versioned roadmap and parking lot.
- `update_memory_free_agent_plan.md` - completed phase map for Update Memory
  runtime, target discovery tools, hinted entry points, and review/correction
  UX; phase 5 tracks trace/eval hardening and future consolidation.
- `ingest_context_hermes_alignment_plan.md` - proposal to align Update Memory
  context loading with the Hermes 3-layer model (core / task / on-demand); remove
  `teacher_wiki/AGENTS.md` from ingest prompts; add missing profiles; slim roll-ups.
  **Implement this first.**
- `ingest_session_state_parity_plan.md` - follow-on proposal for Update Memory
  structured session state in prompts, evidence brief inject, and last-8-turns
  history trim (parity with lesson planning). **Depends on alignment plan (A–C).**
- Concrete implementation plans for upcoming or active changes.

PM strategy, north star, current product state, and roadmap themes live in
`../docs/pm_hub.md`. Durable product docs, agent contracts, architecture notes,
memory hierarchy, and learning/reference notes live in `../docs/`.
