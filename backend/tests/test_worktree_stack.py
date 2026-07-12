from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_worktree_stack():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "worktree_stack.py"
    spec = importlib.util.spec_from_file_location("worktree_stack", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_generated_stack_config_is_stable_and_worktree_scoped(tmp_path):
    stack = _load_worktree_stack()
    root = tmp_path / "agent-task"
    root.mkdir()

    first = stack.build_stack_config(root, task_name=None, port_available=lambda port: True)
    second = stack.build_stack_config(root, task_name=None, port_available=lambda port: True)
    other = stack.build_stack_config(tmp_path / "other-task", task_name=None, port_available=lambda port: True)

    assert first.compose_project_name == second.compose_project_name
    assert first.backend_port == second.backend_port
    assert first.frontend_port == second.frontend_port
    assert first.compose_project_name.startswith("kp_agent_task_")
    assert first.backend_port != other.backend_port
    assert first.frontend_port != other.frontend_port
    assert 8100 <= first.backend_port <= 8999
    assert 3100 <= first.frontend_port <= 3999


def test_generated_ports_probe_forward_when_preferred_port_is_busy(tmp_path):
    stack = _load_worktree_stack()
    root = tmp_path / "agent-task"
    root.mkdir()
    busy_ports: set[int] = set()
    preferred = stack.derive_port(root, "backend", 8100, 8999)
    busy_ports.add(preferred)

    config = stack.build_stack_config(root, task_name=None, port_available=lambda port: port not in busy_ports)

    assert config.backend_port != preferred
    expected = preferred + 1 if preferred < 8999 else 8100
    assert config.backend_port == expected


def test_prepare_sandbox_wiki_copies_baseline_without_overwriting(tmp_path):
    stack = _load_worktree_stack()
    root = tmp_path / "agent-task"
    baseline = root / "backend" / "teacher_wiki"
    (baseline / "wiki").mkdir(parents=True)
    (baseline / "wiki" / "teacher_profile.md").write_text("baseline", encoding="utf-8")

    sandbox = stack.prepare_wiki(root, mode="sandbox", fresh=False)
    assert sandbox == root / "backend" / "teacher_wiki_sandbox"
    assert (sandbox / "wiki" / "teacher_profile.md").read_text(encoding="utf-8") == "baseline"

    (sandbox / "wiki" / "teacher_profile.md").write_text("mutated", encoding="utf-8")
    reused = stack.prepare_wiki(root, mode="sandbox", fresh=False)
    assert reused == sandbox
    assert (sandbox / "wiki" / "teacher_profile.md").read_text(encoding="utf-8") == "mutated"

    refreshed = stack.prepare_wiki(root, mode="sandbox", fresh=True)
    assert refreshed == sandbox
    assert (sandbox / "wiki" / "teacher_profile.md").read_text(encoding="utf-8") == "baseline"


def test_beta_mode_uses_ignored_worktree_local_beta_data(tmp_path):
    stack = _load_worktree_stack()
    root = tmp_path / "agent-task"
    root.mkdir()

    config = stack.build_stack_config(
        root,
        task_name="agent-task",
        beta_enabled=True,
        port_available=lambda port: True,
    )

    assert config.beta_enabled is True
    assert config.beta_data_host_dir == root / "backend" / "beta_data_sandbox"
    assert config.compose_env()["BETA_ENABLED"] == "true"
    assert config.compose_env()["BETA_DATA_HOST_DIR"] == "./backend/beta_data_sandbox"


def test_model_profile_uses_current_backend_model_profile_env(tmp_path):
    stack = _load_worktree_stack()
    root = tmp_path / "agent-task"
    root.mkdir()

    config = stack.build_stack_config(root, model_profile="production", port_available=lambda port: True)

    env = config.compose_env()
    assert env["MODEL_PROFILE"] == "production"
    assert "OPENAI_CHAT_MODEL" not in env
    assert "OPENAI_FAST_MODEL" not in env
    assert "OPENAI_REASONING_EFFORT" not in env
