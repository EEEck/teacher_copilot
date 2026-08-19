# Scripts

Utility scripts for local development, testing, Docker, and trace bundles.

## Railway beta invites

- `railway-beta-provision.sh` — **prefer this in Git Bash**
- `railway-beta-provision.ps1` — same flow for PowerShell

Generate a secure `{prefix}_{random}` invite, SSH into the linked Railway
**backend**, run `beta_cli provision`, then `chmod`/`chown` the beta volume so
the API (`app`, uid 1000) can write `workflow/` even when SSH ran as root.
Prints a paste-ready invite message and appends
`deploy/railway/invites.local.md` (gitignored).

```bash
# Git Bash
cd /c/Users/matth/teacher_agent_v2
./scripts/railway-beta-provision.sh maria
./scripts/railway-beta-provision.sh lb "LB (Chemie 9b)"
```

```powershell
# PowerShell (optional)
.\scripts\railway-beta-provision.ps1 -Prefix maria
```

Requires: Railway CLI logged in + linked project, SSH key registered
(`railway ssh keys add -k ~/.ssh/railway_ed25519.pub -n railway-klassenpilot-beta`),
and the backend service healthy with `/data` volume.

On the backend container, manage testers with:

```bash
railway ssh -s backend -- python -m app.services.beta_cli list
railway ssh -s backend -- python -m app.services.beta_cli disable --tester-id t_maria
railway ssh -s backend -- python -m app.services.beta_cli enable --tester-id t_maria
railway ssh -s backend -- python -m app.services.beta_cli report-all
```

## Development

- `restart-dev.ps1` / `restart-dev.sh` / `restart-dev.cmd` - restart backend
  and frontend dev servers.
- `stop-dev.ps1` - stop local dev processes.
- `docker-dev.sh` - Docker Compose helper.

## Testing

- `test.ps1` - backend pytest, frontend typecheck, and frontend Vitest.

Run from repo root:

```powershell
.\scripts\test.ps1
```

## A1 live class provisioning acceptance

After starting this worktree's sandbox with `worktree-stack.cmd up`, paste the
printed backend URL (do not reuse a port from another worktree):

```powershell
$backendUrl = Read-Host "Paste the backend URL printed by worktree-stack.cmd up"
.\backend\.venv\Scripts\python .\scripts\run_a1_class_provisioning_e2e.py `
  --api-base $backendUrl `
  --wiki-root .\backend\teacher_wiki_sandbox `
  --report .\.worktree-stack\a1-api-report.json
```

## Plan materials browser HITL

- [`plan_materials_mo_e2e_prompts.md`](plan_materials_mo_e2e_prompts.md) —
  textbook attach → MO / dissociation chat; images in `plan_markdown`.
  Helper: `python scripts/run_plan_materials_mo_e2e.py`.
- [`plan_context_materials_hitl.md`](plan_context_materials_hitl.md) —
  Context tab groups, two PDFs as a set, Remove, class-memory toggles,
  live ESL-on-Chemie 422. Helper:
  `python scripts/run_plan_context_materials_e2e.py`.

If Node is installed but not on PATH in the current PowerShell session:

```powershell
$env:Path = "${env:ProgramFiles}\nodejs;$env:Path"
.\scripts\test.ps1
```

## Plan Trace Bundle

- `run_plan_trace_bundle.py`
- `run_plan_trace_bundle.ps1`

These call the local API, run the default three-turn FCKW/CFC planning debug
scenario, and write a trace bundle under `backend/runs/`.

Use the generated `prompt-*-sections.md` files to verify the default prompt
context. Planning should show `Teacher layer`, `Active class core`, `Session
state`, `Lesson planning state`, `Current lesson artifact`, and `Evidence
briefs`; long lesson history and raw evidence should appear through tool calls
and `raw-evidence/`.

The API trace endpoints are enabled by default in development and disabled by
default in production. Set `AGENT_TRACE_ENABLED=true` for local production-mode
debug runs. `PLAN_TRACE_ENABLED=true` remains supported as a backward-compatible
alias.

Generated outputs under `runs/` and `backend/runs/` are ignored by Git.

## Update Memory Trace Bundle

- `run_memory_update_trace_bundle.py`
- `run_memory_update_trace_bundle.ps1`

These call the local API, run the default three-turn lesson-results update
debug scenario for `2026-05-29`, and write a trace bundle under `backend/runs/`.
The bundle includes prompt assembly, streamed tool calls/results, memory runtime
state, raw evidence refs, and the final diary markdown.

Update Memory should show `Teacher layer`, `Active class core`, `Update Memory
task context`, `Memory target state`, `Memory session state`, `Lesson result
state`, and `Memory evidence briefs`. It should not include
`teacher_wiki/AGENTS.md`, full roll-ups, full student files, or full lesson
files in the default prompt context.

## Trace Script Maintenance

The plan and memory trace scripts intentionally have the same developer shape:
start an artifact session, stream fixed teacher turns, fetch the trace endpoint,
and write a run bundle. In local development, each turn also writes raw
reasoning events extracted from the SSE response as `*-reasoning.txt` and
`*-reasoning.json`. If another workflow needs this, create a shared
scenario-driven runner instead of copying either script again.

## Memory Candidate Scenario Traces

- `trace_memory_pref_mbb.py` - live planning-chat reproduction for the MBB
  preference capture path.
- `trace_memory_group_learning_pattern.py` - live update-memory reproduction
  for a class learning pattern candidate.
- `trace_memory_repeated_signal_promotion.py` - seeded ledger scenario for
  repeated weak class-learning signals and sweep promotion.
- `trace_memory_mbb_executive_consolidation.py` - seeded ledger scenario with
  two MBB-style communication signals plus one executive-style signal; records
  whether Memory Sweep suggests one consolidated
  `teacher_profile.md / Communication` review card. By default it temporarily
  hides unrelated open ledger rows during the proposal call and restores them
  immediately afterward; use `--no-isolate` to inspect the full live sweep
  inbox. Use `--current-memory none`, `--current-memory narrow-mbb`, and
  `--current-memory generalized` to verify `add`, `adjust`, and
  `already_covered`.

Example:

```powershell
cd .
.\backend\.venv\Scripts\python .\scripts\trace_memory_mbb_executive_consolidation.py `
  --run-name manual-mbb-executive-merge
```

Passing shape: `passed=true`, `full_merge_cards=1`, and one card representing
all three seeded candidate IDs. This is the core live drift check for backend
memory merging; deterministic tests still live under `backend/tests/`.

## Memory Sweep 4.4 Trace Bundle

- `run_memory_sweep_44_trace_bundle.py`

This script seeds temporary Memory Sweep candidates for the Memory Sweep
examples (see `docs/mem_v4/`), calls the local public API endpoints, writes
before/after wiki snapshots, records apply/status responses, and stores a
review bundle under `backend/runs/`.

Default two-example run:

```powershell
cd .
.\backend\.venv\Scripts\python .\scripts\run_memory_sweep_44_trace_bundle.py
```

All four section 4.4 examples:

```powershell
cd .
.\backend\.venv\Scripts\python .\scripts\run_memory_sweep_44_trace_bundle.py --scenario all
```

By default the script removes its temporary smoke bullets from wiki files after
verification while leaving applied ledger rows as audit history. Use
`--keep-writes` to inspect the durable wiki changes in place.

## Memory V4 Golden Trace Bundle

- `run_memory_v4_golden_trace.py`

This diagnostic reuses the memory-capture goldens and writes a bundle organized
around the four V4 control stages: Admission, Priority, Sweep, and Apply. The
default deterministic mode does not call the API:

```powershell
.\backend\.venv\Scripts\python .\scripts\run_memory_v4_golden_trace.py
```

To capture the full live workflow trace, prompt assembly, SSE stream, runtime
candidates, and optional Sweep response:

```powershell
.\backend\.venv\Scripts\python .\scripts\run_memory_v4_golden_trace.py `
  --mode live --scenario two --run-sweep
```

The diagnostic never applies or writes curated Markdown. Generated bundles are
written under `backend/runs/`.
