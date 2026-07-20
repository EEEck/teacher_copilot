# Agent evals (DeepEval + trace contracts)

MemV4 is the active memory-evaluation home. Read
[`../../docs/mem_v4/evaluation.md`](../../docs/mem_v4/evaluation.md) for the
layered policy and
[`../../docs/mem_v4/mem_v4_live_eval_ledger.md`](../../docs/mem_v4/mem_v4_live_eval_ledger.md)
for beta-derived known gaps. This runbook contains the executable commands.

How to run KlassenPilot agent evals, where they should execute, and how they
relate to the running dev container vs a separate test environment.

## Recommendation: where evals run

**Use a separate host/CI Python venv — not inside the running app container.**

| Approach | Use for | Why |
|----------|---------|-----|
| **Host/CI venv + pytest** (recommended) | Default CI, build loop, live agent evals | Tests use FastAPI `TestClient` with dependency injection — **no running uvicorn required**. Temp wiki copy; seed wiki is never mutated. |
| **Running backend HTTP** (`localhost:8010`) | Human debug bundles, optional `RUN_LIVE_API_TESTS` | Trace bundle scripts and `test_live_api_plan_trace.py` hit the live API. Good for “what is docker serving right now?” — not the primary CI gate. |
| **Inside `docker compose` backend service** | **Not recommended** | Dev image installs runtime deps only (`pip install -e .`), not `deepeval`/pytest. Couples test tooling to the serving process and slows hot-reload dev. |

```mermaid
flowchart LR
  subgraph recommended [Recommended CI / build loop]
    Venv[Host or CI venv]
    Pytest[pytest tests/evals]
    TC[TestClient in-process]
    App[app.main FastAPI]
    Venv --> Pytest --> TC --> App
  end
  subgraph optional [Optional debug]
    Docker[docker compose backend :8010]
    Bundle[trace bundle scripts]
    Bundle --> Docker
  end
```

**Summary:** The eval suite is a **test harness that imports the app**, not a
client of the production/dev server. Keep `docker compose up` for manual UI/API
work; run `pytest` from `backend/.venv` (or CI) for gates.

Exception: if you explicitly want to validate the **exact** long-running
process (e.g. after env wiring changes in Compose), use trace bundles or
`RUN_LIVE_API_TESTS=1` against `http://localhost:8010` — treat that as a
secondary smoke path, not the default loop.

## One-time setup

From repo root or `backend/`:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
```

`[dev]` adds `pytest`, `ruff`, and `deepeval`. Copy `backend/.env` with
`OPENAI_API_KEY` only when running **live** evals (see below).

## Eval tiers

| Tier | Tests | OpenAI | Server needed |
|------|-------|--------|---------------|
| **0 — Unit / API stub** | `tests/test_*.py`, `tests/eval/*` | No | No |
| **1 — DeepEval context** | `tests/evals/test_klassenpilot_layers.py`, `test_klassenpilot_context.py` | No | No |
| **2 — DeepEval chat stub** | `tests/evals/test_klassenpilot_chat_stub.py` | No | No |
| **3 — DeepEval chat live** | `tests/evals/test_klassenpilot_chat_live.py` | Yes | No |
| **4 — Live API HTTP** | `tests/test_live_api_plan_trace.py` | Yes | Yes (`:8010`) |
| **5 — Trace bundles** | `scripts/run_*_trace_bundle.py` | Yes | Yes (`:8010`) |

Tiers 0–2 are **CI-safe** (no API key, no running backend).

## Commands

### Full backend suite (includes evals)

From repo root:

```powershell
.\scripts\test.ps1
```

Backend only:

```powershell
cd backend
.\.venv\Scripts\python -m pytest
```

### DeepEval goldens only (deterministic — recommended every PR)

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_layers.py tests/evals/test_klassenpilot_context.py tests/evals/test_klassenpilot_chat_stub.py -v
```

Expanded deterministic eval set:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_layers.py tests/evals/test_klassenpilot_context.py tests/evals/test_klassenpilot_chat_stub.py tests/evals/test_klassenpilot_wiki_search.py tests/evals/test_klassenpilot_workflows_stub.py -v
```

Student Summary judge golden:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_student_summary_judge.py -v
```

### Live agent chat + LLM judge (opt-in)

Uses real `AgentRunner` (OpenAI Agents SDK) still **in-process** via
`TestClient` — docker does not need to be running.

Live agent evals are production-profile goldens by default: the fixture forces
`MODEL_PROFILE=production` and ignores local chat/important/utility reasoning
effort overrides. It still reads normal API key and model-id settings, so
`OPENAI_STRONG_MODEL` is the production model under test.

```powershell
cd backend
$env:RUN_LIVE_AGENT_EVALS="1"
$env:RUN_LLM_CHAT_JUDGE="1"          # GEval grounding judge (default on for live)
$env:OPENAI_API_KEY="sk-..."         # or backend/.env loaded by pydantic-settings
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_chat_live.py -v
```

Explicit model-profile comparison:

```powershell
$env:LIVE_AGENT_EVAL_MODEL_PROFILE="economy"
```

Optional eval-specific reasoning-effort overrides:

```powershell
$env:LIVE_AGENT_EVAL_CHAT_REASONING_EFFORT="medium"
$env:LIVE_AGENT_EVAL_IMPORTANT_REASONING_EFFORT="high"
$env:LIVE_AGENT_EVAL_UTILITY_REASONING_EFFORT="minimal"
```

Optional judge model override:

```powershell
$env:DEEPEVAL_MODEL="gpt-5.4-mini"
$env:DEEPEVAL_REASONING_EFFORT="medium"
```

Optional LLM judges default to `gpt-5.4-mini` with medium reasoning.
`OPENAI_FAST_MODEL` remains a legacy fallback when `DEEPEVAL_MODEL` is unset.

Disable LLM judge but keep live agent:

```powershell
$env:RUN_LLM_CHAT_JUDGE="0"
```

Memory-capture live goldens use component-level tool-call expectations inspired
by DeepEval tool-correctness evals: a golden can require multiple expected
memory targets, forbid leakage into other targets, and set a minimum candidate
count before checking the backend `fast_lane` verdict. This keeps overlap cases
such as "durable class learning pattern + immediate planning priority" from
collapsing into a single-target pass.

### MemV4 live-derived goldens

Sanitized beta observations and their owning follow-up branches are tracked in
[`docs/mem_v4/mem_v4_live_eval_ledger.md`](../../docs/mem_v4/mem_v4_live_eval_ledger.md).
The ledger deliberately keeps raw reasoning and beta trace payloads out of Git.

Run deterministic contracts without an API key:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_memory_capture_golden_contract.py tests/evals/test_klassenpilot_memory_capture_stub.py tests/evals/test_discussion_golden_contract.py -q
```

Run live memory-capture checks and the Discuss task-anchor `GEval` only with an API key:

```powershell
$env:RUN_LIVE_AGENT_EVALS="1"
$env:RUN_LLM_CHAT_JUDGE="1"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_memory_capture_live.py tests/evals/test_klassenpilot_discussion_live.py -v
```

Wiki-vs-input reconciliation has both deterministic and optional live/LLM judge
coverage:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_wiki_reconciliation.py -v

$env:RUN_LIVE_AGENT_EVALS="1"
$env:RUN_LLM_WIKI_RECONCILIATION_JUDGE="1"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_wiki_reconciliation.py -rx -v
```

Known urgent xfail: `non_roster_observation_is_flagged` currently fails the LLM
judge because the ingest agent silently accepts `S-099` even though the eval
wiki roster says that student is not enrolled in Chemie 9b. This is a product
behavior gap, not a flaky test: the next implementation pass should add
deterministic roster-conflict detection and a teacher clarification path before
student observations are recorded.

### Executive-verification evals

The executive-verification golden suite exercises the shared `ExecutiveRuntime`
against a focused Chemie 9b eval wiki. It covers three interaction outcomes:

- a date plus student-ID mismatch blocks readiness, then proceeds after the
  teacher resolves both facts;
- an unrelated English/Macbeth paste blocks a Chemie 9b artifact; and
- a valid but naturally messy organic-chemistry lesson result proceeds without
  unnecessary clarification.

The always-on deterministic layer validates the golden fixture and its wiki
preconditions. The live contract layer asserts backend-owned `ready` and
`executive_state.status`; it is the authoritative check for whether a durable
action is permitted. The optional LLM judge evaluates teacher-facing behavior,
not write readiness.

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_executive_verification.py -q

$env:RUN_LIVE_AGENT_EVALS="1"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_executive_verification.py::test_executive_verification_live_contract -q -rA

$env:RUN_LLM_EXECUTIVE_VERIFICATION_JUDGE="1"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_executive_verification.py::test_executive_verification_llm_judge_live -q -rA
```

**Known finding (2026-07-09, deferred):** the live contract passed the
mismatch/resolution and wrong-context cases, but the valid organic-chemistry
input produced a correct draft with `ready=false`. The system is safe but
over-blocks this low-risk case. The LLM judge passed all three scenarios because
it assesses the reply/artifact quality and does not receive the backend
readiness state. Keep this as a red live-contract regression until a later
prompt/runtime calibration pass; do not weaken the write gate or change the
golden expectation to make it pass.

Milestone C adds deterministic API coverage for the write boundary: a manual
draft edit that introduces an unknown student must return HTTP 409 with
`write_verification_blocked` and must not write the plan, create an ingest
review, or commit wiki files. These checks use the stub verifier and remain
network-free; an opt-in live manual-edit recovery golden follows once the
verifier behavior is calibrated.

Enable the optional LLM judge for the Student Summary golden:

```powershell
$env:RUN_LLM_STUDENT_SUMMARY_JUDGE="1"
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_student_summary_judge.py -v
```

### Live API against running backend (secondary)

Start backend first (`docker compose up`, `restart-dev.ps1`, or manual uvicorn).

```powershell
$env:RUN_LIVE_API_TESTS="1"
$env:LIVE_API_BASE_URL="http://localhost:8010"
cd backend
.\.venv\Scripts\python -m pytest tests/test_live_api_plan_trace.py -v
```

### Human trace bundles (debug, not CI gates)

Requires backend on `:8010`. See [backend/README.md](../README.md) plan/memory
trace bundle sections.

## Golden matrix

| Family | IDs | What it checks |
|--------|-----|----------------|
| Layer isolation — 9b | `9b_global`, `9b_global_class`, `9b_global_class_subject` | Teacher → class memory → `chemie.md` |
| Layer isolation — 10c mock | `10c_global`, `10c_global_class`, `10c_global_class_subject` | Same + `ESL.md`, no chemie leakage |
| Workflow startup — 9b | `9b_plan_startup`, `9b_ingest_startup` | Session-open `prompt_assembly` |
| Chat stub/live — 9b | `9b_plan_fckw_turn1`, `9b_plan_redox_lesson_lookup`, `9b_plan_fckw_turn2_review`, `9b_ingest_turn2_collect` | Message → tools → trace → (live) GEval judge |

Fixture wiki overlay: `tests/fixtures/eval_wiki/` (`engl_10c_2026_27`, `ESL.md`).

Additional deterministic goldens:

| Family | IDs | What it checks |
|--------|-----|----------------|
| Wiki search - 9b/10c | `9b_misconception_charge_vs_oxidation`, `9b_redox_date_range_pathfinder`, `10c_subject_bound_search` | Source-bounded wiki pathfinding and class isolation |
| Workflow E2E stub - 9b | `9b_plan_fckw_3turn_e2e`, `9b_memory_update_3turn_e2e` | Complete multi-turn workflow state, evidence, and final artifact |
| Security chat - 9b | `security_plan_direct_prompt_injection`, `security_plan_upload_prompt_injection`, `security_plan_tool_output_injection`, `security_ingest_write_memory_now`, `security_plan_raw_trace_request`, `security_plan_high_stakes_student_decision` | Lightweight teacher-agent security contract: no hidden prompt/trace/raw-ref leakage, no hidden durable-write claims, and redirect for high-stakes student decisions |
| Student Summary - 9b | `s045_balanced_learning_and_support_trajectory` | S-045 durable-summary trajectory: improving written notation/test performance plus recent disruption as a neutral support pattern, without high-stakes or fixed-trait language |

Live GEval is intentionally limited to four chat goldens by default: two
planning quality checks and two memory-update quality checks. The redox lesson
lookup remains a deterministic live/tool-routing check without an LLM judge.

## Security evals

Security goldens are part of the deterministic chat stub suite. They are not a
full red-team harness; they pin the current lightweight contract while keeping
the normal build loop offline and debuggable.

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/evals/test_klassenpilot_chat_stub.py -v
.\.venv\Scripts\python -m pytest tests/test_prompts.py -v
```

The `SecurityContractMetric` checks teacher-visible output only. It fails on
obvious prompt/trace/raw-ref leakage, API-key-looking strings, hidden durable
write claims, and high-stakes student decisions. Broader DeepTeam OWASP ASI
automation is deferred to a later hardening pass; useful findings should be
converted into deterministic DeepEval goldens.

## How failures look

DeepEval metrics return **score 0–1** and a **reason** string. Example:

```
AssertionError: Metrics: ToolInvocation[9b_plan_fckw_turn1] (
  score: 0.0, reason: - missing required tool 'search_memory' ...
) failed.
```

Build-loop rules:

1. Read `reason` bullets.
2. Fix app code (`context_packs.py`, `prompt_assembly.py`, tools, prompts).
3. Do **not** lower thresholds or delete goldens to greenwash.
4. Re-run the tier that failed.

Note: `deepeval test run` CLI may fail in some installs; **pytest is the
supported runner** (`deepeval` pytest plugin).

## File map

| Path | Role |
|------|------|
| `tests/evals/goldens/` | Golden definitions (layer, startup, chat, search, workflow) |
| `tests/evals/contracts/layer_contract.py` | Layer isolation scorer |
| `tests/evals/metrics/` | DeepEval `BaseMetric` + `GEval` wrappers |
| `tests/evals/harness.py` | Trace fetch, chat turns, retrieval context for judge |
| `tests/evals/conftest.py` | Eval wiki fixture, `DeepEvalTracingProcessor`, live client |
| `tests/eval/plan_trace_scorer.py` | Shared trace contract scorer |
| `tests/eval/ingest_trace_scorer.py` | Ingest startup scorer |
| `tests/README.md` | Shorter test-group index |

## CI sketch (future)

```yaml
# Example job — not wired in repo yet
- pip install -e ".[dev]"
- pytest tests/evals/test_klassenpilot_layers.py tests/evals/test_klassenpilot_context.py tests/evals/test_klassenpilot_chat_stub.py
# Nightly only:
# RUN_LIVE_AGENT_EVALS=1 pytest tests/evals/test_klassenpilot_chat_live.py
```

Do **not** add pytest/deepeval to the runtime `Dockerfile.dev` CMD image unless
you introduce a separate `Dockerfile.test` used only in CI.
