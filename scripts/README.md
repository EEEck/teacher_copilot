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
and write a run bundle. If another workflow needs this, create a shared
scenario-driven runner instead of copying either script again.
