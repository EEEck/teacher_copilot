from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import deps
from app.config import Settings
from app.main import app
from app.services.beta import BetaAuthService, BetaTelemetry, RequestIdentity

SEED_WIKI = Path(__file__).resolve().parent.parent / "teacher_wiki"
CLASS_ID = "chemie_9b_2026_27"


def _service(tmp_path: Path) -> BetaAuthService:
    service = BetaAuthService(
        db_path=tmp_path / "beta.sqlite3",
        data_root=tmp_path / "beta_data",
        seed_wiki_root=SEED_WIKI,
        cookie_name="kp_beta_session",
        session_days=30,
        cookie_secure=False,
    )
    service.initialize()
    return service


def _enable_beta(monkeypatch, tmp_path: Path, service: BetaAuthService) -> None:
    settings = Settings(
        beta_enabled=True,
        beta_data_root=tmp_path / "beta_data",
        beta_cookie_name="kp_beta_session",
        beta_cookie_secure=False,
    )
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    app.dependency_overrides[deps.get_beta_auth_service] = lambda: service


def test_invite_login_creates_persistent_opaque_session(tmp_path: Path):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
        display_label="Anna",
        seed_label="seed-chem9b",
    )

    login = service.login("anna-invite")

    assert login.tester_id == "t_anna"
    assert login.workspace_id == "w_anna_chem9b"
    assert login.role == "tester"
    assert "t_anna" not in login.session_token
    assert "w_anna" not in login.session_token

    identity = service.resolve_session_token(login.session_token)
    assert identity == RequestIdentity(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        role="tester",
        wiki_root=tmp_path
        / "beta_data"
        / "workspaces"
        / "w_anna_chem9b"
        / "teacher_wiki",
    )
    assert (identity.wiki_root / "wiki" / "classes" / "chemie_9b_2026_27").exists()


def test_invalid_invite_code_is_rejected(tmp_path: Path):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )

    assert service.login("wrong-code") is None


def test_telemetry_records_visible_messages_artifacts_and_wiki_diff(tmp_path: Path):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )
    identity = service.resolve_session_token(service.login("anna-invite").session_token)
    telemetry = BetaTelemetry(tmp_path / "beta.sqlite3")
    telemetry.initialize()

    telemetry.record_app_session(
        identity,
        app_session_id="sess-1",
        class_id="chemie_9b_2026_27",
        mode="ingest",
        status="chatting",
    )
    telemetry.record_message(
        identity,
        app_session_id="sess-1",
        class_id="chemie_9b_2026_27",
        mode="ingest",
        role="user",
        content="We reviewed oxidation numbers.",
    )
    telemetry.record_artifact_snapshot(
        identity,
        app_session_id="sess-1",
        class_id="chemie_9b_2026_27",
        mode="ingest",
        artifact_kind="diary",
        markdown="# Lesson Results\n",
    )
    commit_id = telemetry.record_wiki_commit(
        identity,
        app_session_id="sess-1",
        class_id="chemie_9b_2026_27",
        mode="ingest",
        action="memory_committed",
        changed_files=[
            (
                "wiki/classes/chemie_9b_2026_27/lessons/2026-10-01/lesson_results.md",
                "old line\n",
                "new line\n",
            )
        ],
        metadata={"approved_count": 1},
    )

    with sqlite3.connect(tmp_path / "beta.sqlite3") as conn:
        messages = conn.execute("select role, content from message").fetchall()
        snapshots = conn.execute(
            "select artifact_kind, markdown from artifact_snapshot"
        ).fetchall()
        diff_row = conn.execute(
            "select wiki_path, before_hash, after_hash, diff_text from wiki_file_diff where commit_id = ?",
            (commit_id,),
        ).fetchone()

    assert messages == [("user", "We reviewed oxidation numbers.")]
    assert snapshots == [("diary", "# Lesson Results\n")]
    assert diff_row[0].endswith("lesson_results.md")
    assert diff_row[1] != diff_row[2]
    assert "-old line" in diff_row[3]
    assert "+new line" in diff_row[3]


def test_beta_login_endpoint_sets_cookie_and_me_resolves_identity(tmp_path: Path):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )

    app.dependency_overrides[deps.get_beta_auth_service] = lambda: service
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            login = client.post("/api/beta/login", json={"invite_code": "anna-invite"})
            assert login.status_code == 200
            assert "kp_beta_session=" in login.headers["set-cookie"]
            assert "HttpOnly" in login.headers["set-cookie"]

            me = client.get("/api/beta/me")
            assert me.status_code == 200
            assert me.json() == {
                "tester_id": "t_anna",
                "workspace_id": "w_anna_chem9b",
                "role": "tester",
            }
    finally:
        app.dependency_overrides.clear()


def test_beta_cookie_scopes_api_writes_to_workspace(
    tmp_path: Path, monkeypatch
):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )
    service.provision_tester(
        tester_id="t_ben",
        workspace_id="w_ben_chem9b",
        invite_code="ben-invite",
    )
    _enable_beta(monkeypatch, tmp_path, service)

    try:
        with TestClient(app, raise_server_exceptions=False) as anna:
            assert anna.post(
                "/api/beta/login", json={"invite_code": "anna-invite"}
            ).status_code == 200
            res = anna.post(
                f"/api/classes/{CLASS_ID}/memory/apply",
                json={
                    "items": [
                        {
                            "target": "teaching_patterns.md",
                            "section": "What Worked",
                            "content": "Anna-specific review warmup worked.",
                        }
                    ]
                },
            )
            assert res.status_code == 200

        anna_file = (
            tmp_path
            / "beta_data"
            / "workspaces"
            / "w_anna_chem9b"
            / "teacher_wiki"
            / "wiki"
            / "classes"
            / CLASS_ID
            / "memory"
            / "teaching_patterns.md"
        )
        ben_file = (
            tmp_path
            / "beta_data"
            / "workspaces"
            / "w_ben_chem9b"
            / "teacher_wiki"
            / "wiki"
            / "classes"
            / CLASS_ID
            / "memory"
            / "teaching_patterns.md"
        )
        assert "Anna-specific review warmup worked." in anna_file.read_text(
            encoding="utf-8"
        )
        assert "Anna-specific review warmup worked." not in ben_file.read_text(
            encoding="utf-8"
        )
    finally:
        app.dependency_overrides.clear()


def test_memory_apply_records_workspace_wiki_diff(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )
    _enable_beta(monkeypatch, tmp_path, service)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.post(
                "/api/beta/login", json={"invite_code": "anna-invite"}
            ).status_code == 200
            res = client.post(
                f"/api/classes/{CLASS_ID}/memory/apply",
                json={
                    "items": [
                        {
                            "target": "teaching_patterns.md",
                            "section": "What Worked",
                            "content": "Diff telemetry captures this approved memory.",
                        }
                    ]
                },
            )
            assert res.status_code == 200

        with sqlite3.connect(tmp_path / "beta.sqlite3") as conn:
            event_type = conn.execute(
                "select type from event where type = 'memory_apply'"
            ).fetchone()
            diff_text = conn.execute(
                "select diff_text from wiki_file_diff"
            ).fetchone()[0]

        assert event_type == ("memory_apply",)
        assert "+- Diff telemetry captures this approved memory." in diff_text
    finally:
        app.dependency_overrides.clear()


def test_ingest_session_and_draft_are_recorded_as_telemetry(
    tmp_path: Path, monkeypatch
):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )
    _enable_beta(monkeypatch, tmp_path, service)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.post(
                "/api/beta/login", json={"invite_code": "anna-invite"}
            ).status_code == 200
            start = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions")
            assert start.status_code == 200
            session_id = start.json()["session_id"]
            draft_markdown = "# Lesson Results\n\n## What was covered\n- Redox recap\n"
            draft = client.patch(
                f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/draft",
                json={"diary_markdown": draft_markdown},
            )
            assert draft.status_code == 200

        with sqlite3.connect(tmp_path / "beta.sqlite3") as conn:
            app_session = conn.execute(
                "select tester_id, workspace_id, class_id, mode, status from app_session"
            ).fetchone()
            event_types = [
                row[0] for row in conn.execute("select type from event order by event_id")
            ]
            snapshot = conn.execute(
                "select artifact_kind, markdown from artifact_snapshot"
            ).fetchone()

        assert app_session == (
            "t_anna",
            "w_anna_chem9b",
            CLASS_ID,
            "ingest",
            "chatting",
        )
        assert "session_started" in event_types
        assert "draft_updated" in event_types
        assert snapshot == ("diary", draft_markdown)
    finally:
        app.dependency_overrides.clear()
