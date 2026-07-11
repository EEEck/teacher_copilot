# Evaluator Model Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all optional LLM evaluators through GPT-5.4-mini with medium reasoning by default.

**Architecture:** A shared test-only resolver owns model and reasoning-effort
selection. Direct OpenAI and DeepEval judges consume that resolver instead of
maintaining independent fallback literals.

**Tech Stack:** Python, OpenAI Python SDK, DeepEval, pytest.

## Global Constraints

- Production application routing must not change.
- Existing evaluator environment overrides remain supported.
- No live OpenAI calls are required for tests.

---

### Task 1: Shared Evaluator Model Configuration

**Files:**
- Create: `backend/tests/eval/model_config.py`
- Create: `backend/tests/eval/test_model_config.py`

**Interfaces:**
- Produces: `resolve_eval_model(explicit_model=None)` and `build_deepeval_model()`.

- [ ] Write tests for default values, override precedence, and DeepEval generation kwargs.
- [ ] Run the tests and confirm failure because the shared module does not exist.
- [ ] Implement the resolver and DeepEval factory.
- [ ] Run the tests and confirm they pass.

### Task 2: Migrate Evaluator Callers

**Files:**
- Modify: `backend/tests/eval/plan_judge.py`
- Modify: `backend/tests/evals/metrics/chat_metrics.py`
- Modify: `backend/tests/evals/metrics/workflow_metrics.py`
- Modify: `backend/tests/evals/metrics/student_summary_metrics.py`
- Modify: `backend/docs/evals.md`

**Interfaces:**
- Consumes: the shared resolver and DeepEval factory from Task 1.

- [ ] Replace direct fallback literals with the shared helper.
- [ ] Pass medium reasoning to the direct OpenAI judge without temperature.
- [ ] Document the new defaults and override variable.
- [ ] Run focused evaluator tests.
- [ ] Search the repository to confirm no legacy evaluator fallback remains.
