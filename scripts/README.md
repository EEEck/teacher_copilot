# Scripts

Utility scripts for local development, testing, Docker, and trace bundles.

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

This script seeds temporary Memory Sweep candidates for the examples in
`docs/mem_v2/design.md` section 4.4, calls the local public API endpoints, writes
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
