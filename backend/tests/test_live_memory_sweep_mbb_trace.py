"""Opt-in live Memory Sweep MBB/executive consolidation trace."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


RUN_LIVE_MEMORY_SWEEP_TRACE = os.getenv("RUN_LIVE_MEMORY_SWEEP_TRACE") == "1"


@pytest.mark.skipif(
    not RUN_LIVE_MEMORY_SWEEP_TRACE,
    reason="live Memory Sweep MBB trace is opt-in (set RUN_LIVE_MEMORY_SWEEP_TRACE=1)",
)
@pytest.mark.parametrize(
    ("current_memory", "expected_operation"),
    [
        ("none", "add"),
        ("narrow-mbb", "adjust"),
        ("generalized", "already_covered"),
    ],
)
def test_live_memory_sweep_mbb_trace_variants(
    current_memory: str,
    expected_operation: str,
):
    backend_root = Path(__file__).resolve().parents[1]
    repo_root = backend_root.parent
    script = repo_root / "scripts" / "trace_memory_mbb_executive_consolidation.py"
    run_name = f"pytest-live-mbb-{current_memory.replace('-', '_')}"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--current-memory",
            current_memory,
            "--run-name",
            run_name,
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        timeout=240,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"expected_operation={expected_operation}" in result.stdout
    assert "passed=True" in result.stdout

