from pathlib import Path

import pytest

from app.services import workspace_template as template
from app.services import beta_cli
from app.config import Settings
from app.teacher_agent.wiki_store import WikiStore

SEED_WIKI = Path(__file__).resolve().parent.parent / "teacher_wiki"


def test_initializer_defaults_to_empty_and_existing_destination_is_untouched(tmp_path):
    destination = tmp_path / "wiki"
    template.initialize_teacher_workspace(SEED_WIKI, destination)
    assert WikiStore(root=destination).list_classes() == []
    before = {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
    # Even a missing seed must not affect a workspace that already exists.
    template.initialize_teacher_workspace(tmp_path / "missing", destination, mode="demo")
    assert {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*") if p.is_file()} == before


def test_copy_failure_never_publishes_a_partial_workspace_and_retry_succeeds(tmp_path, monkeypatch):
    destination = tmp_path / "wiki"
    original_copy = template.shutil.copy2
    copied = 0

    def fail_after_first_file(*args, **kwargs):
        nonlocal copied
        copied += 1
        if copied == 2:
            raise OSError("injected copy failure")
        return original_copy(*args, **kwargs)

    monkeypatch.setattr(template.shutil, "copy2", fail_after_first_file)
    with pytest.raises(OSError, match="injected copy failure"):
        template.initialize_teacher_workspace(SEED_WIKI, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".workspace-*"))
    monkeypatch.setattr(template.shutil, "copy2", original_copy)
    template.initialize_teacher_workspace(SEED_WIKI, destination)
    assert WikiStore(root=destination).list_classes() == []


@pytest.mark.parametrize("workspace_mode", [None, "empty", "demo"])
def test_beta_cli_defaults_to_demo_and_supports_explicit_empty(tmp_path, monkeypatch, workspace_mode):
    monkeypatch.setattr(beta_cli, "get_settings", lambda: Settings(beta_data_root=tmp_path))
    monkeypatch.setattr(beta_cli, "_seed_wiki_root", lambda: SEED_WIKI)
    args = ["provision", "--tester-id", "teacher", "--workspace-id", "teacher", "--invite-code", "test-code"]
    if workspace_mode:
        args.extend(["--workspace-mode", workspace_mode])
    assert beta_cli.main(args) == 0
    wiki = WikiStore(root=tmp_path / "workspaces/teacher/teacher_wiki")
    assert bool(wiki.list_classes()) == (workspace_mode != "empty")
