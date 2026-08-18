# Backend Tests

Backend tests are offline and deterministic by default. They use a temporary
copy of `backend/teacher_wiki/` and a stub agent runner, so normal tests should
not call OpenAI or mutate the repo wiki.

## Fixtures

- `conftest.py` creates:
  - a temp `WikiStore`
  - `StubAgentRunner`
  - `IngestService`
  - `PlanService`
  - FastAPI dependency overrides
- `CLASS_ID` points to the seed chemistry class.

## Test Groups

- `test_api_*.py` - HTTP/session behavior and streaming.
- `test_wiki_*.py` - wiki reads, search, pathing, and context packs.
- `test_plan_context_manager.py` - planning runtime state, evidence refs,
  memory candidates, and trace behavior.
- `test_memory_*.py` - compact memory and profile/apply helpers.
- `test_prompts.py` - prompt contracts and policy text.
- `test_cli_trace.py` - local JSONL/terminal trace formatting.
- `test_materials_ocr_packaging.py` / `test_materials_ocr_prompts.py` /
  `test_materials_plan_api.py` - OCR packaging, wiki-assembled STEM/generic
  prompts, upload → scratch, promote-skip-debug.
- `test_materials_ocr_live.py` - opt-in live Mistral OCR (packaging + ESL
  upload 422 on Chemie). Skipped unless `RUN_LIVE_MISTRAL_OCR=1`.
  Browser playbook: `scripts/plan_context_materials_hitl.md`.
- `test_live_api_plan_trace.py` - opt-in live API integration test for the
  three-turn FCKW scenario. Skipped unless `RUN_LIVE_API_TESTS=1`.
- `eval/test_fckw_plan_contract.py` - offline FCKW trace contract scorer
  (startup context, per-turn tools, phase, artifact patterns).
- `eval/test_memory_update_contract.py` - offline Update Memory trace contract
  for target selection, tool calls, runtime state, pseudonymized diary output,
  and trace hygiene.
- `test_api_ingest.py` - ingest API, commit safety, and typed start-hint
  behavior for taught/planned/unknown lesson targets.
- `eval/plan_trace_scorer.py` - shared scorer used by contract + live tests.
- `eval/fckw_contract.py` - declarative expectations aligned with
  `docs/memory_hierarchy.md`.
- `fixtures/fckw_plan/trace_before_turn1.json` - committed startup trace fixture.
- `fixtures/eval_wiki/` - eval-only `engl_10c_2026_27` mock class + `ESL.md` subject guide.
- `eval/ingest_trace_scorer.py` - shared ingest startup trace scorer.
- `evals/` - DeepEval build-loop goldens (layer isolation, workflow startup, chat, wiki search, workflow E2E).

## DeepEval build loop (`tests/evals/`)

**Where to run:** host/CI `backend/.venv` with `pip install -e ".[dev]"` — **not**
inside the running docker/uvicorn container. Tests use in-process `TestClient`;
no server on `:8010` required for tiers 0–2.

Canonical guide: [`docs/evals.md`](../docs/evals.md) (architecture, tiers, env
vars, CI notes).

Deterministic DeepEval goldens wrap the existing trace contract scorers. No OpenAI
credits required for the committed suite.

**Golden matrix (19 deterministic total):**

| Family | Goldens | What it checks |
|--------|---------|----------------|
| Layer isolation — Chemie 9b | `9b_global`, `9b_global_class`, `9b_global_class_subject` | Global teacher layer → + class memory → + `chemie.md` subject |
| Layer isolation — Englisch 10c mock | `10c_global`, `10c_global_class`, `10c_global_class_subject` | Same progression with `engl_10c_2026_27` + `ESL.md` (no chemie leakage) |
| Workflow startup — Chemie 9b | `9b_plan_startup`, `9b_ingest_startup` | Full plan/ingest session trace before first teacher message |
| **Chat turns (stub, CI)** | `9b_plan_fckw_turn1`, `9b_plan_redox_lesson_lookup`, `9b_plan_fckw_turn2_review`, `9b_ingest_turn2_collect` | Message → tool calls → trace evidence (deterministic) |
| **Chat turns (live, opt-in)** | same chat goldens + `9b_plan_materials_embed_mo_asset` | Above + selected DeepEval `GEval` LLM judge; materials golden is live-only (seeded OCR fixture) |

Additional deterministic goldens:

| Family | Goldens | What it checks |
|--------|---------|----------------|
| **Wiki search (stub, CI)** | `9b_misconception_charge_vs_oxidation`, `9b_redox_date_range_pathfinder`, `10c_subject_bound_search` | Source-bounded wiki pathfinding and class isolation |
| **Workflow E2E (stub, CI)** | `9b_plan_fckw_3turn_e2e`, `9b_memory_update_3turn_e2e` | Complete multi-turn workflow state, evidence, and final artifact |
| **Memory Sweep (stub, CI)** | `9b_memory_sweep_routes_channels`, `9b_memory_sweep_subject_vs_class_boundary`, `9b_memory_sweep_rejected_stays_rejected` | Candidate queue routing, class-vs-subject write boundaries, rejected-candidate suppression |
| **Memory capture routing (stub/live)** | memory-capture goldens in `goldens/memory_capture.py` | `remember(...)` target routing, dual routing for class pattern + planning priority, forbidden leakage, and non-durable traps |
| **Wiki input reconciliation** | `wiki_input_reconciliation.py` | Deterministic roster mismatch detection plus optional LLM judge for clarify/accept behavior |
| **Student Summary judge (stub, CI)** | `s045_balanced_learning_and_support_trajectory` | S-045 summary preserves improving written trajectory and recent disruption as a neutral support pattern |

The chat-turn family also includes `9b_ingest_turn3_ready`, which checks final
Update Memory readiness, review phase, and pseudonymized diary output.

**Run deterministic suite (CI-safe):**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_layers.py tests/evals/test_klassenpilot_context.py tests/evals/test_klassenpilot_chat_stub.py -v
```

Expanded deterministic set:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_layers.py tests/evals/test_klassenpilot_context.py tests/evals/test_klassenpilot_chat_stub.py tests/evals/test_klassenpilot_wiki_search.py tests/evals/test_klassenpilot_workflows_stub.py -v
```

Memory sweep deterministic evals:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_memory_sweep_stub.py -v
```

Memory V3 capture and wiki-reconciliation deterministic checks:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_memory_capture_golden_contract.py tests/evals/test_memory_capture_live_diagnostics.py tests/evals/test_klassenpilot_memory_capture_stub.py tests/evals/test_klassenpilot_wiki_reconciliation.py -v
```

Student Summary judge golden:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_student_summary_judge.py -v
```

Optional LLM judge for that golden:

```powershell
$env:RUN_LLM_STUDENT_SUMMARY_JUDGE="1"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_student_summary_judge.py -v
```

Focused Memory Sweep backend contract:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_memory_targets.py tests\test_memory_sweep_backend.py tests\test_prompts.py -q
```

Memory V4 second-judge contracts:

```powershell
.\.venv\Scripts\python -m pytest tests\test_memory_v4_sweep.py -q
```

These tests cover held-singleton visibility, priority metadata, semantic Sweep
actions, target ownership, and the teacher-review-only apply boundary.

Core live drift check for memory merging:

```powershell
cd ..
.\backend\.venv\Scripts\python .\scripts\trace_memory_mbb_executive_consolidation.py --run-name manual-mbb-executive-merge
```

Run all current-memory variants through pytest when intentionally checking live
model drift:

```powershell
cd backend
$env:RUN_LIVE_MEMORY_SWEEP_TRACE="1"
.\.venv\Scripts\python -m pytest tests\test_live_memory_sweep_mbb_trace.py -q
```

The three variants should pass with one consolidated `teacher_profile.md /
Communication` card: no current memory -> `add`, narrow current memory ->
`adjust`, generalized current memory -> `already_covered`. It is intentionally a
live-model drift check; normal pytest skips it, and deterministic prompt tests
assert the production system prompts do not hardcode those labels.

**Run live chat evals (real OpenAI Agents SDK + LLM judge):**

```powershell
cd backend
$env:RUN_LIVE_AGENT_EVALS="1"
$env:RUN_LLM_CHAT_JUDGE="1"   # GEval grounding judge (default on for live)
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_chat_live.py -v
```

Live agent evals force the production model profile by default, ignoring local
`MODEL_PROFILE` and local reasoning-effort overrides. Set
`LIVE_AGENT_EVAL_MODEL_PROFILE=economy` only when the point of the run is an
explicit model-profile comparison.

Focused live capture:

```powershell
cd backend
$env:RUN_LIVE_AGENT_EVALS="1"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_memory_capture_live.py -rx
```

Optional wiki-reconciliation LLM judge:

```powershell
cd backend
$env:RUN_LIVE_AGENT_EVALS="1"
$env:RUN_LLM_WIKI_RECONCILIATION_JUDGE="1"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_wiki_reconciliation.py -rx
```

The non-roster-student clarify scenario is currently documented as an xfail:
the desired behavior is to flag/clarify before writing, while the current agent
still silently accepts the non-roster ID. This is an urgent product trust gap,
not a reason to weaken the golden.

Each chat golden scores three metrics:

1. **ToolInvocation** — required/any-of tool names from SSE `tool_call` events
2. **TraceEvidence** — post-turn trace phase, `raw_evidence`, artifact patterns
3. **GroundedChat** (live only) — `GEval` judges `input` + `retrieval_context` + `actual_output`

Retrieval context for the judge is built from startup class core, tool results, and `raw_evidence` refs in the trace.

**Build-loop rules:**

1. Read metric `reason` strings on failure.
2. Fix context loading in `app/teacher_agent/wiki/context_packs.py` or `prompt_assembly.py` — do not weaken thresholds or delete goldens.
3. Re-run the eval suite above plus tier-1 tests in `tests/eval/`.

OpenAI Agents SDK tracing (`DeepEvalTracingProcessor`) is registered in
`tests/evals/conftest.py` for future live goldens.

## Agent behavior eval (recommended tiers)

| Tier | When | Cost | What it catches |
|------|------|------|-----------------|
| 0 — Deterministic | Every PR (`pytest`) | Free | Prompt assembly, context pack sections, state-patch merge, stub tool routing |
| 1 — Trace contracts | Every PR or nightly | Free | Structural invariants on trace JSON (sections present, phase per turn, tool names) |
| 2 — Live behavioral | Opt-in / model swap | OpenAI credits | Full 3-turn FCKW run against real model + contract scorer |

**Tier 0** stays on `StubAgentRunner` in `conftest.py` — fast, no drift signal for
real models, but guards prompt/context regressions.

**Tier 1** is implemented in `tests/eval/plan_trace_scorer.py` +
`tests/eval/fckw_contract.py`. Assert **structure**, not verbatim LLM prose:

- **Before turn 1:** class slice sections include `Class identity snapshot`,
  `Top misconceptions`, `Recent lessons`, `Planning brief`, `Teaching patterns`;
  artifact empty; no evidence briefs yet.
- **After turn 1:** `search_memory` called; at least one of `read_lesson` /
  `read_lesson_range`; `phase == lesson_refinement`; artifact mentions 45 min,
  FCKW/CFC, Montreal Protocol, oxidation number vs charge.
- **After turn 2:** range/history tools used for last-lecture review; artifact
  reflects review/recap of prior confusion.
- **After turn 3:** `phase == finalize`; artifact includes 2-minute active recall.

Store a **reference trace** under `tests/fixtures/fckw_plan/` (sanitized JSON
snippets) for section-name and tool-sequence baselines. Compare with tolerant
matching (regex / `any_of` tool lists), not full snapshot diff — models will
word plans differently.

**Tier 2** is `test_live_api_plan_trace.py`: run the three prompts, fetch trace
after each turn, pass through the same scorer. Enable with `RUN_LIVE_API_TESTS=1`.

Optional **soft scoring**: `tests/eval/plan_judge.py` with `RUN_LLM_PLAN_JUDGE=1`
(one cheap rubric JSON call via existing `openai` client).

Golden run bundles under `backend/runs/` are for human debug only (gitignored).
Commit only the **contract spec** and small **fixture trace excerpts**.

## Run

From repo root:

```powershell
.\scripts\test.ps1
```

Backend only:

```powershell
cd backend
.\.venv\Scripts\python -m pytest
```

Focused agent/memory + DeepEval set:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/ tests/eval/test_fckw_plan_contract.py tests/eval/test_memory_update_contract.py
```

## Rules

- Keep default tests network-free and OpenAI-free.
- Use the stub runner for agent behavior expectations.
- Put live/debug scenarios behind explicit environment flags.
