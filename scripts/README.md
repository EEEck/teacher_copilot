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
