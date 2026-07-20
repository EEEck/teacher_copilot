# MemV4 Evaluation Policy

MemV4 treats deterministic contracts as the release gate and live/LLM checks
as calibrated regression discovery. A green judge does not authorize a write;
the backend's typed write boundary and teacher approval do.

## Evaluation layers

| Layer | Purpose | Where it runs |
|---|---|---|
| Deterministic unit/API contracts | Candidate scope, target routing, ledger folding, write boundaries, and fixture integrity | CI/host venv; no API key |
| Stub workflow goldens | Prompt assembly, tool routing, runtime state, and teacher-visible contracts | CI/host venv; no API key |
| Live agent checks | Capture/tool behavior against a real model and production-profile routing | Opt-in host venv with API key |
| LLM judges | Quality/calibration over selected live artifacts; never the authorization gate | Opt-in host venv with API key |
| Browser runbooks | Fresh-sandbox, browser/trace/ledger acceptance testing | Local human/agent run; not CI initially |

## Source of truth and retention

- [`mem_v4_live_eval_ledger.md`](mem_v4_live_eval_ledger.md) records each
  beta-derived scenario, expected behavior, related golden, and known gap.
- [`../../backend/docs/evals.md`](../../backend/docs/evals.md) contains exact
  commands and environment variables.
- Raw reasoning, browser state, screenshots, cookies, trace payloads, and beta
  workspaces remain local/ignored. Git contains only sanitized assertions and
  fixtures.
- Do not lower a golden threshold or delete a failing case to make a run green.
  Record the gap, preserve the deterministic contract, and fix the behavior in
  a focused slice.

## Browser acceptance

Use the sanitized manifest design in
[`../superpowers/specs/2026-07-20-browser-workflow-runbook-design.md`](../superpowers/specs/2026-07-20-browser-workflow-runbook-design.md).
Every run starts from a fresh beta sandbox and records browser-visible,
trace-visible, and ledger-visible observations separately.

## Current focus

The live ledger's known capture gaps and the product backlog's P0
input-to-wiki reconciliation/date-awareness tasks are the next behavior work.
The offline Plan-quality P/R/O/M calibration is intentionally a shadow process:
it informs prompt and deterministic-guard improvements without adding live
teacher latency or hidden rewriting.
