# MemV4 Documentation Consolidation Design

## Goal

Make `docs/mem_v4/` the single active home for memory-system documentation;
delete the obsolete MemV2/MemV3 document trees while retaining two concise
historical summaries that explain the current design.

## Scope

This is a documentation-only change. It does not change runtime memory
behaviour, schemas, API contracts, test fixtures, or beta data.

## Active document set

`docs/mem_v4/` remains the active memory documentation directory.

| File | Responsibility |
|---|---|
| `README.md` | Entry point, current status, and links to canonical design, evaluation, and archive summaries. |
| `mem_v4_codex.md` | Central current design: lifecycle, context package, admission, priority, Sweep, Apply, and invariants. |
| `mem_v4_codex_implementation_plan.md` | Retained implementation record and PR/checklist history. |
| `mem_v4_beta_debug_capture_implementation_plan.md` | Retained operational plan for temporary beta trace capture. |
| `mem_v4_live_eval_ledger.md` | Active regression, ownership, and follow-up ledger. |
| `empirical_inputs.md` | Retained only if its fixtures/evidence are still referenced by active design or tests. |
| `evaluation.md` | Consolidated testing strategy: deterministic contracts, live capture checks, DeepEval judges, local trace handling, and golden policy. |
| `archive/mem_v2_summary.md` | One-page summary of decisions from MemV2 that remain relevant. |
| `archive/mem_v3_summary.md` | One-page summary of decisions from MemV3 that remain relevant. |

## Archive summaries

The summaries are explanatory, not instructions or a second contract. They
retain only the durable reasoning needed to understand MemV4:

- compiled markdown wiki memory rather than transcript replay;
- raw evidence, review ledger, and curated memory as separate layers;
- teacher approval as the only durable-write boundary;
- canonical homes for memory facts and retirement of duplicate rollups;
- explicit durable requests versus inferred evidence;
- distinct-occasion reinforcement and the semantic Sweep second judge.

They exclude PR numbering, completed task lists, stale file paths, raw beta
data, old prompt wording, and unresolved historical TODOs.

## Deletions

Delete from the working tree:

- `docs/mem_v2/` in full;
- `docs/mem_v3/` in full;
- `docs/mem_v4/brainstorm.md`;
- `docs/mem_v4/_ledger_snapshot.json`, `_sweep_cards.json`, and
  `_sweep_snapshot.json`;
- root-level duplicated historical memory notes whose content is incorporated
  into the active MemV4 documentation;
- superseded memory plans only after their durable decision has been folded
  into retained active documentation.

Git history remains the detailed archive.

## Core-document updates

| File | Required update |
|---|---|
| `docs/README.md` | Identify MemV4 as the sole active memory-documentation home; remove MemV3-as-current language. |
| `docs/agent_architecture.md` | Describe the current implementation map and link to MemV4; replace version/PR prose with current behaviour. |
| `docs/agent_learning_guide.md` | Retain durable lessons only; link to archive summaries rather than historical postmortems. |
| `docs/memory_hierarchy.md` | Preserve canonical memory homes, loading rules, and retired-page explanation without links into deleted trees. |
| `docs/agent_contracts.md` | Preserve the executable contract, replacing MemV3 PR references with behavior-based language and active MemV4 links. |
| `backend/docs/evals.md` | Link to `docs/mem_v4/evaluation.md` and the live-eval ledger. |
| `AGENTS.md` | Replace MemV3 PR labels with active MemV4 contract wording where they are still useful. |

## Verification

1. Search the repository for `docs/mem_v2`, `docs/mem_v3`, `mem_v3/`, and
   stale “MemV3 is current” language; update or remove every live-doc link.
2. Confirm remaining version mentions are intentional historical text in the
   two archive summaries or Git-oriented implementation records.
3. Run Markdown-link validation if the repository provides it; otherwise use
   targeted `rg` checks for deleted paths and manually inspect all retained
   navigation pages.
4. Run the focused eval/doc contract tests to ensure the live-eval ledger link
   remains valid.

## Non-goals

- Rewriting the central MemV4 design merely for style.
- Changing runtime code or current golden behaviour.
- Preserving every historical decision as prose in the working tree.
