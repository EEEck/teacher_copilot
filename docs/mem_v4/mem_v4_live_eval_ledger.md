# MemV4 live-eval ledger

This is the review and handoff ledger for sanitized beta observations. It records behaviour, expected coverage, and ownership; it does **not** contain private beta trace payloads, lesson text, student data, or raw reasoning.

Use trace bundles only locally when reproducing an item. The stable contract is the golden ID and intended behaviour below.

| ID | Observed beta case | Golden / tier | Intended behaviour | Status and follow-up |
|---|---|---|---|---|
| M4-LIVE-01 | Session-only MBB tone followed by a general Legion Commander/subtle-humor preference | `mbb_session_then_general_style_boundary`; deterministic fixture + opt-in live capture | Session-only tone creates no durable candidate; a clearly general preference stages one global `teacher_profile.md` fast-lane candidate. | Coverage added. |
| M4-LIVE-02 | Light, intuitive orbital perspective was missed by capture | `light_orbital_preference_class_fast_lane`; deterministic fixture + opt-in live capture | Stage one class `copilot_profile.md` fast-lane candidate; never leak it globally. | Known live gap. Branch: `codex/mem4-capture-orbital-scope`. |
| M4-LIVE-03 | Phenomenon-first instruction and observed engagement were collapsed | `phenomenon_first_instruction_and_evidence`; deterministic fixture + opt-in live capture | Class working agreement in `copilot_profile.md` fast lane **and** regular `teaching_patterns.md` evidence signal. | Known live gap. Branch: `codex/mem4-evidence-decomposition`. |
| M4-LIVE-04 | Five-minute review produced unrelated global preferences | `five_minute_review_no_global_leakage`; deterministic fixture + opt-in live capture | Permit one class working agreement; optionally near-term planning. Never unrelated `teacher_profile.md` claims. | Known live gap. Branch: `codex/mem4-admission-leakage`. |
| M4-LIVE-05 | `unknown` speech act/scope can leave ledger noise | `unknown_scope_no_durable_capture`; deterministic fixture + opt-in live capture | Current-artifact or uncertain request does not stage durable memory. | Known live gap. Branch: `codex/mem4-unknown-admission`. |
| M4-LIVE-06 | Discuss answered a Dota detour but did not reliably return to the teacher task | `discussion_dota_detour_task_anchor`; deterministic route/criteria contract + opt-in DeepEval `GEval` | Brief natural response, no invented game details, then explicit return to the organic-chemistry task. | Coverage added. Branch on live failure: `codex/discuss-task-anchor`. |
| M4-LIVE-07 | Model reasoned about omitting the Discuss structured state schema | Documented contract issue; no behavioural golden yet | Required output envelope; `state_patch: null` means no state change; malformed envelope gets one validation retry. | Design follow-up. Branch: `codex/discuss-required-envelope`. |

## Memory-home rule

```text
teacher working agreement → copilot_profile.md
observed class learning evidence → teaching_patterns.md
class overrides of shared subject/grade pedagogy → teaching_framework_adjustments.md
immediate next-step pressure → planning_brief.md
global cross-class preference → teacher_profile.md
```

Shared `wiki/subjects/.../teaching_frameworks/` pages are not capture targets.

The ledger does not authorize durable writes. Every candidate remains subject to admission, Sweep review, and teacher Apply.

## Running the coverage

From `backend/`, deterministic contracts run without OpenAI:

```powershell
<python> -m pytest tests/evals/test_memory_capture_golden_contract.py tests/evals/test_klassenpilot_memory_capture_stub.py tests/evals/test_discussion_golden_contract.py -q
```

Live capture and the DeepEval Discuss judge are opt-in:

```powershell
$env:RUN_LIVE_AGENT_EVALS="1"
$env:RUN_LLM_CHAT_JUDGE="1"
<python> -m pytest tests/evals/test_klassenpilot_memory_capture_live.py tests/evals/test_klassenpilot_discussion_live.py -v
```

Known live gaps should remain visible. Do not lower thresholds, delete the golden, or copy raw beta traces into this repository to make a run green.
