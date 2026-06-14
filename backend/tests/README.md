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

## Agent behavior eval (recommended tiers)

Do **not** add a heavy eval framework (DeepEval, LangSmith, Promptfoo) for this
prototype. You already have the right primitive: the plan trace endpoint and
run bundle format expose prompt sections, tool calls, runtime phase, and the
final artifact as structured JSON. Build a thin **trace contract scorer** on
top of pytest instead.

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

Focused agent/memory set:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_ingest.py tests\test_api_stream.py tests\eval\test_memory_update_contract.py tests\test_api_plan.py
```

## Rules

- Keep default tests network-free and OpenAI-free.
- Use the stub runner for agent behavior expectations.
- Put live/debug scenarios behind explicit environment flags.
