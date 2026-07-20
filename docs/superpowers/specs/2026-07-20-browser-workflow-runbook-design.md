# Browser Workflow Runbook Design

## Goal

Allow a future agent to replay the important teacher conversations through the
real KlassenPilot browser UI, against a fresh beta sandbox, and produce a
human-readable pass/fail report with local trace evidence.

## Chosen approach

Use versioned, sanitized browser-runbook manifests rather than introducing a
full Playwright suite now. A future agent drives the existing in-app browser,
replays the manifests, and evaluates browser-visible, trace-visible, and
ledger-visible assertions. The manifest format intentionally leaves room for a
later Playwright adapter.

## Isolation and safety

- Each run starts a fresh worktree stack with `--beta --fresh-beta-data`.
- The runner uses a dedicated beta test account created for that stack.
- It never reuses a teacher's existing beta workspace or browser session.
- Git stores only sanitized inputs and expectations; raw traces, reasoning,
  screenshots, browser state, and beta data remain local and ignored.
- A failed scenario leaves its sandbox and local report intact for inspection;
  cleanup is explicit.

## Scenario manifest

Create one machine-readable manifest per workflow scenario under
`tests/browser_runbooks/`. Each manifest declares:

```yaml
id: discuss_style_scope_boundary
workflow: discussion
class_seed: chemie_9b_2026_27
setup:
  fresh_beta: true
  route: /classes/chemie_9b_2026_27
turns:
  - message: "For this session only, use an MBB-style tone."
    expect:
      reply_contains: ["MBB"]
      ledger_candidates: []
  - message: "In general, use subtle humor and occasional short quotes."
    expect:
      ledger_candidate:
        target: teacher_profile.md
        scope: global
        fast_lane: true
```

The initial scenario set is:

| Workflow | Scenario | Key assertion |
|---|---|---|
| Discuss | session-only MBB then general style preference | no candidate, then one global fast-lane candidate |
| Discuss | Dota detour while planning | concise reply then explicit return to teacher task |
| Plan | first organic lesson | concrete/visual constraints affect plan |
| Plan | Hartree–Fock bait | guard de-escalates university-level content |
| Plan | light orbital preference | permitted lightweight framing and class capture |
| Plan | 5-minute review | class routine without global leakage |
| Update Memory | first organic results | visual/spatial learning evidence is captured |
| Update Memory | alkanes results | phenomenon-first instruction and evidence are separated |
| Update Memory | date mismatch | clarification precedes ready state |
| Update Memory | roster mismatch then correction | block, correction, and recovery are visible |

## Three assertion layers

### Browser-visible

The browser agent verifies route, beta login, streamed reply, draft/status
state, guard/error UI, expected navigation, and that action controls remain
reachable in a constrained viewport.

### Trace-visible

The runner obtains the workflow trace through the existing debug capture or
trace endpoint and verifies tool calls, structured state, candidate metadata,
and expected guard decisions. Raw reasoning is attached only to the local
report.

### Ledger-visible

The runner reads the workspace-scoped candidate ledger and checks target,
scope, admission decision, priority, occasion key, and cluster/folding
outcome. It does not apply or mutate curated memory unless a scenario
explicitly covers teacher approval in a future expansion.

## Runner and report

Add a local-only runner command that:

1. starts the fresh beta stack and registers/logs in the test account;
2. loads one or more manifests;
3. drives each turn through the browser UI;
4. captures three-layer observations after every turn;
5. writes `runs/browser/<run-id>/report.md` plus raw local artifacts;
6. returns nonzero when an assertion fails.

The report has a short scenario table first, followed by per-turn browser
screenshots/observations, trace summary, ledger delta, and links to raw local
artifacts. It must label expected known gaps separately from unexpected
regressions.

## Relationship to existing evals

- Deterministic unit/API and DeepEval tests remain CI gates.
- Browser runbooks are local human/agent acceptance tests and regression
  discovery tools, not CI gating initially.
- A scenario manifest may link to its related `docs/mem_v4` live-eval ledger
  ID and DeepEval golden ID.
- Once UI and routes stabilize, a Playwright adapter may consume the same
  manifests without changing scenario semantics.

## Non-goals

- Adding Playwright, a hosted browser farm, or CI browser execution now.
- Committing beta data, raw reasoning, screenshots, cookies, or credentials.
- Replacing deterministic backend tests or DeepEval judges.
- Automatically applying curated memory changes as part of the initial suite.

## Acceptance criteria

1. A new agent can find the scenario list and run one scenario from its
manifest without reading this chat.
2. Every run uses a fresh beta sandbox and cannot touch existing beta data.
3. A report clearly distinguishes UI, trace, and ledger failures.
4. At least one scenario each for Discuss, Plan, and Update Memory is
implemented before broadening coverage.
