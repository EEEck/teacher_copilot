from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

BACKEND_PORT_START = 8100
BACKEND_PORT_END = 8999
FRONTEND_PORT_START = 3100
FRONTEND_PORT_END = 3999

MODEL_PROFILES: dict[str, dict[str, str]] = {
    "economy": {"MODEL_PROFILE": "economy"},
    "production": {"MODEL_PROFILE": "production"},
}


class StackConfig:
    def __init__(
        self,
        *,
        repo_root: Path,
        task_name: str,
        compose_project_name: str,
        backend_port: int,
        frontend_port: int,
        wiki_host_dir: Path,
        beta_enabled: bool,
        beta_data_host_dir: Path,
        app_env: str,
        model_profile: str,
    ) -> None:
        self.repo_root = repo_root
        self.task_name = task_name
        self.compose_project_name = compose_project_name
        self.backend_port = backend_port
        self.frontend_port = frontend_port
        self.wiki_host_dir = wiki_host_dir
        self.beta_enabled = beta_enabled
        self.beta_data_host_dir = beta_data_host_dir
        self.app_env = app_env
        self.model_profile = model_profile

    def compose_env(self) -> dict[str, str]:
        env = {
            "COMPOSE_PROJECT_NAME": self.compose_project_name,
            "BACKEND_PORT": str(self.backend_port),
            "FRONTEND_PORT": str(self.frontend_port),
            "WIKI_HOST_DIR": _relative_for_compose(self.repo_root, self.wiki_host_dir),
            "BETA_ENABLED": "true" if self.beta_enabled else "false",
            "BETA_DATA_HOST_DIR": _relative_for_compose(self.repo_root, self.beta_data_host_dir),
            "APP_ENV": self.app_env,
        }
        if self.model_profile != "from-env":
            env.update(MODEL_PROFILES[self.model_profile])
        return env


def sanitize_name(value: str) -> str:
    chars = []
    previous_dash = False
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    sanitized = "".join(chars).strip("-")
    return sanitized or "worktree"


def short_hash(value: str, length: int = 6) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def derive_port(repo_root: Path, salt: str, start: int, end: int) -> int:
    span = end - start + 1
    digest = hashlib.sha256(f"{repo_root.resolve()}:{salt}".encode("utf-8")).hexdigest()
    return start + (int(digest[:8], 16) % span)


def default_port_available(port: int) -> bool:
    for host in ("127.0.0.1",):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                return False
    return True


def choose_available_port(
    preferred: int,
    start: int,
    end: int,
    port_available=default_port_available,
) -> int:
    span = end - start + 1
    for offset in range(span):
        port = start + ((preferred - start + offset) % span)
        if port_available(port):
            return port
    raise RuntimeError(f"No available port found in range {start}-{end}.")


def build_stack_config(
    repo_root: Path,
    *,
    task_name: str | None = None,
    backend_port: int | None = None,
    frontend_port: int | None = None,
    wiki_host_dir: Path | None = None,
    beta_enabled: bool = False,
    beta_data_host_dir: Path | None = None,
    app_env: str = "development",
    model_profile: str = "from-env",
    port_available=default_port_available,
) -> StackConfig:
    repo_root = repo_root.resolve()
    resolved_task = sanitize_name(task_name or repo_root.name)
    project_hash = short_hash(str(repo_root))
    compose_project_name = f"kp_{resolved_task.replace('-', '_')}_{project_hash}"
    backend = _resolve_port(
        backend_port,
        derive_port(repo_root, "backend", BACKEND_PORT_START, BACKEND_PORT_END),
        BACKEND_PORT_START,
        BACKEND_PORT_END,
        port_available,
        "backend",
    )
    frontend = _resolve_port(
        frontend_port,
        derive_port(repo_root, "frontend", FRONTEND_PORT_START, FRONTEND_PORT_END),
        FRONTEND_PORT_START,
        FRONTEND_PORT_END,
        port_available,
        "frontend",
    )
    if backend == frontend:
        raise RuntimeError(f"Backend and frontend cannot share host port {backend}.")
    return StackConfig(
        repo_root=repo_root,
        task_name=resolved_task,
        compose_project_name=compose_project_name,
        backend_port=backend,
        frontend_port=frontend,
        wiki_host_dir=(wiki_host_dir or repo_root / "backend" / "teacher_wiki_sandbox").resolve(),
        beta_enabled=beta_enabled,
        beta_data_host_dir=(beta_data_host_dir or repo_root / "backend" / "beta_data_sandbox").resolve(),
        app_env=app_env,
        model_profile=model_profile,
    )


def _resolve_port(
    explicit: int | None,
    preferred: int,
    start: int,
    end: int,
    port_available,
    label: str,
) -> int:
    if explicit is not None:
        if not port_available(explicit):
            raise RuntimeError(f"Requested {label} port {explicit} is already in use.")
        return explicit
    return choose_available_port(preferred, start, end, port_available)


def prepare_wiki(repo_root: Path, *, mode: str, fresh: bool) -> Path:
    repo_root = repo_root.resolve()
    baseline = repo_root / "backend" / "teacher_wiki"
    sandbox = repo_root / "backend" / "teacher_wiki_sandbox"
    if mode == "baseline":
        return baseline
    if not baseline.exists():
        raise FileNotFoundError(f"Baseline wiki not found: {baseline}")
    if sandbox.exists() and fresh:
        shutil.rmtree(sandbox)
    if not sandbox.exists():
        shutil.copytree(baseline, sandbox)
    return sandbox


def prepare_beta_data(path: Path, *, fresh: bool) -> None:
    if path.exists() and fresh:
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_override_file(config: StackConfig) -> Path | None:
    if config.model_profile == "from-env":
        return None
    env = MODEL_PROFILES[config.model_profile]
    override_dir = config.repo_root / ".worktree-stack"
    override_dir.mkdir(exist_ok=True)
    override_file = override_dir / "compose.override.yaml"
    lines = [
        "services:",
        "  backend:",
        "    environment:",
    ]
    for key, value in env.items():
        lines.append(f"      {key}: {value}")
    override_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return override_file


def compose_command(config: StackConfig, command: str, extra_args: list[str]) -> list[str]:
    files = ["-f", str(config.repo_root / "compose.yaml")]
    override = write_override_file(config)
    if override is not None:
        files.extend(["-f", str(override)])
    base = ["docker", "compose", *files]
    if command == "up":
        return [*base, "up", "--build", "-d", *extra_args]
    if command == "up-fg":
        return [*base, "up", "--build", *extra_args]
    if command == "down":
        return [*base, "down", *extra_args]
    if command == "logs":
        return [*base, "logs", "-f", *extra_args]
    if command == "ps":
        return [*base, "ps", *extra_args]
    raise ValueError(f"Unknown command: {command}")


def run_compose(config: StackConfig, command: str, extra_args: list[str]) -> int:
    env = os.environ.copy()
    env.update(config.compose_env())
    cmd = compose_command(config, command, extra_args)
    return subprocess.call(cmd, cwd=config.repo_root, env=env)


def _relative_for_compose(repo_root: Path, path: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
        return "./" + rel.as_posix()
    except ValueError:
        return path.resolve().as_posix()


def print_config(config: StackConfig) -> None:
    for key, value in config.compose_env().items():
        print(f"{key}={value}")
    print(f"FRONTEND_URL=http://localhost:{config.frontend_port}")
    print(f"API_HEALTH_URL=http://localhost:{config.backend_port}/api/health")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an isolated Docker Compose stack for this Git worktree.")
    parser.add_argument("command", choices=["config", "up", "up-fg", "down", "logs", "ps"], nargs="?", default="config")
    parser.add_argument("--task-name", help="Stable task name for the Compose project. Defaults to the worktree folder name.")
    parser.add_argument("--backend-port", type=int, help="Explicit backend host port. Defaults to a stable generated free port.")
    parser.add_argument("--frontend-port", type=int, help="Explicit frontend host port. Defaults to a stable generated free port.")
    parser.add_argument("--wiki", choices=["sandbox", "baseline"], default="sandbox", help="Use an ignored sandbox wiki or the tracked baseline wiki.")
    parser.add_argument("--fresh-wiki", action="store_true", help="Recreate backend/teacher_wiki_sandbox from backend/teacher_wiki before running.")
    parser.add_argument("--beta", action="store_true", help="Enable beta tester mode and use backend/beta_data_sandbox.")
    parser.add_argument("--fresh-beta-data", action="store_true", help="Recreate backend/beta_data_sandbox before running.")
    parser.add_argument("--app-env", choices=["development", "production"], default="development")
    parser.add_argument("--model-profile", choices=["from-env", *MODEL_PROFILES.keys()], default="from-env")
    args, compose_args = parser.parse_known_args(argv)
    args.compose_args = compose_args[1:] if compose_args[:1] == ["--"] else compose_args
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = Path.cwd()
    wiki_dir = prepare_wiki(repo_root, mode=args.wiki, fresh=args.fresh_wiki)
    config = build_stack_config(
        repo_root,
        task_name=args.task_name,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        wiki_host_dir=wiki_dir,
        beta_enabled=args.beta,
        app_env=args.app_env,
        model_profile=args.model_profile,
    )
    if args.beta:
        prepare_beta_data(config.beta_data_host_dir, fresh=args.fresh_beta_data)
    print_config(config)
    if args.command == "config":
        return 0
    return run_compose(config, args.command, args.compose_args)


if __name__ == "__main__":
    raise SystemExit(main())
