from __future__ import annotations

import sqlite3
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import deps
from app.config import Settings
from app.main import app
from app.services.beta import BetaAuthService, BetaTelemetry, RequestIdentity
from app.services.memory_candidate_ledger import MemoryCandidateLedger, MemoryCandidateRow

SEED_WIKI = Path(__file__).resolve().parent.parent / "teacher_wiki"
CLASS_ID = "chemie_9b_2026_27"


def _service(tmp_path: Path, *, seed_wiki_root: Path = SEED_WIKI) -> BetaAuthService:
    service = BetaAuthService(
        db_path=tmp_path / "beta.sqlite3",
        data_root=tmp_path / "beta_data",
        seed_wiki_root=seed_wiki_root,
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
    monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)
    app.dependency_overrides[deps.get_beta_auth_service] = lambda: service


def _disable_beta(monkeypatch, tmp_path: Path, service: BetaAuthService) -> None:
    settings = Settings(
        beta_enabled=False,
        beta_data_root=tmp_path / "beta_data",
        beta_cookie_name="kp_beta_session",
        beta_cookie_secure=False,
    )
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)
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


def test_provisioned_workspace_does_not_inherit_seed_workflow_runtime_data(
    tmp_path: Path,
):
    seeded_copy = tmp_path / "seed_wiki"
    shutil.copytree(SEED_WIKI, seeded_copy)
    workflow = seeded_copy / "workflow"
    workflow.mkdir()
    (workflow / "memory_candidates.sqlite").write_bytes(b"sqlite-fixture")
    service = _service(tmp_path, seed_wiki_root=seeded_copy)

    identity = service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )

    assert (seeded_copy / "workflow" / "memory_candidates.sqlite").exists()
    assert not (identity.wiki_root / "workflow").exists()


def test_provisioned_workspace_is_group_writable_for_api_process(tmp_path: Path):
    """Provision must leave the wiki tree writable (Discuss creates workflow/)."""
    service = _service(tmp_path)
    identity = service.provision_tester(
        tester_id="t_cutes",
        workspace_id="w_cutes",
        invite_code="cuteS_invite",
    )

    mode = identity.wiki_root.stat().st_mode & 0o777
    assert mode & 0o222, f"wiki_root not writable: {oct(mode)}"
    # App must be able to create the runtime workflow dir after seed copy.
    workflow = identity.wiki_root / "workflow"
    workflow.mkdir()
    (workflow / "probe.txt").write_text("ok", encoding="utf-8")
    assert (workflow / "probe.txt").read_text(encoding="utf-8") == "ok"


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


def test_beta_login_endpoint_sets_cookie_and_me_resolves_identity(
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
            login = client.post("/api/beta/login", json={"invite_code": "anna-invite"})
            assert login.status_code == 200
            assert "kp_beta_session=" in login.headers["set-cookie"]
            assert "HttpOnly" in login.headers["set-cookie"]

            me = client.get("/api/beta/me")
            assert me.status_code == 200
            payload = me.json()
            assert payload["tester_id"] == "t_anna"
            assert payload["workspace_id"] == "w_anna_chem9b"
            assert payload["role"] == "tester"
            assert payload["profile_complete"] is False
            assert payload["display_name"] == ""
            assert payload["stats"]["feedback_notes"] == 0
    finally:
        app.dependency_overrides.clear()


def test_beta_me_not_found_when_beta_disabled(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    _disable_beta(monkeypatch, tmp_path, service)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            me = client.get("/api/beta/me")
            assert me.status_code == 404
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


def test_memory_sweep_propose_records_beta_telemetry_with_warnings(
    tmp_path: Path, monkeypatch
):
    class FailingSweepAgent:
        async def consolidate_memory_sweep(self, *args, **kwargs):
            raise RuntimeError("offline consolidation")

    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )
    _enable_beta(monkeypatch, tmp_path, service)
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add(
        MemoryCandidateRow(
            id="cand_sweep_warning",
            created_at="2026-07-03T09:00:00Z",
            updated_at="2026-07-03T09:00:00Z",
            class_id=CLASS_ID,
            subject="chemie",
            workflow="ingest",
            session_id="sess-1",
            turn_index=1,
            channel="class_learning_pattern",
            target="teaching_patterns.md",
            section="What Worked Well",
            candidate_update="Use group roles before symbolic redox tasks.",
            evidence_summary="Teacher repeated that group roles helped.",
            evidence_refs=["trace:sess-1:turn1"],
            source="teacher_explicit",
            basis="explicit",
            confidence="high",
            cluster_key="class.group_roles",
        )
    )
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_agents] = lambda: FailingSweepAgent()

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.post(
                "/api/beta/login", json={"invite_code": "anna-invite"}
            ).status_code == 200
            res = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/propose")
            assert res.status_code == 200, res.text
            assert res.json()["warnings"]

        with sqlite3.connect(tmp_path / "beta.sqlite3") as conn:
            event = conn.execute(
                """
                select type, payload_json
                from event
                where type = 'memory_sweep_propose'
                """
            ).fetchone()

        assert event is not None
        assert event[0] == "memory_sweep_propose"
        assert '"warning_count": 1' in event[1]
        # Mem V3: teachers (and telemetry payloads) get the plain-language
        # notice; raw internal failure reasons stay in server logs.
        assert "could not consolidate" in event[1]
        assert "offline consolidation" not in event[1]
    finally:
        app.dependency_overrides.clear()


def test_beta_feedback_requires_beta_mode(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )
    _disable_beta(monkeypatch, tmp_path, service)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            res = client.post(
                "/api/beta/feedback",
                json={"message": "Nice tool"},
            )
            assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()

def test_beta_feedback_requires_login(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    _enable_beta(monkeypatch, tmp_path, service)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            res = client.post(
                "/api/beta/feedback",
                json={"message": "Nice tool"},
            )
            assert res.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_beta_feedback_stores_event(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )
    _enable_beta(monkeypatch, tmp_path, service)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert (
                client.post(
                    "/api/beta/login", json={"invite_code": "anna-invite"}
                ).status_code
                == 200
            )
            res = client.post(
                "/api/beta/feedback",
                json={"message": "  Sweep triage felt slow.  ", "page": "/beta/feedback"},
            )
            assert res.status_code == 200, res.text
            assert res.json() == {"status": "ok"}

        with sqlite3.connect(tmp_path / "beta.sqlite3") as conn:
            row = conn.execute(
                """
                select tester_id, workspace_id, type, payload_json
                from event
                where type = 'teacher_feedback'
                """
            ).fetchone()
            message_row = conn.execute(
                """
                select mode, role, content, app_session_id
                from message
                where role = 'teacher_feedback'
                """
            ).fetchone()

        assert row is not None
        assert row[0] == "t_anna"
        assert row[1] == "w_anna_chem9b"
        assert row[2] == "teacher_feedback"
        assert '"message": "Sweep triage felt slow."' in row[3]
        assert '"page": "/beta/feedback"' in row[3]
        assert message_row is not None
        assert message_row[0] == "feedback"
        assert message_row[1] == "teacher_feedback"
        assert message_row[2] == "[/beta/feedback] Sweep triage felt slow."
        assert message_row[3] == "feedback"
    finally:
        app.dependency_overrides.clear()


def test_beta_profile_patch_completes_identity_and_stats(
    tmp_path: Path, monkeypatch
):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
        display_label="Anna (seed)",
    )
    login = service.login("anna-invite")
    identity = service.resolve_session_token(login.session_token)
    service.telemetry.record_teacher_feedback(
        identity,
        message="Nice sweep UI",
        page="/beta/feedback",
    )
    service.telemetry.record_app_session(
        identity,
        app_session_id="sess-1",
        class_id=CLASS_ID,
        mode="ingest",
        status="chatting",
    )
    _enable_beta(monkeypatch, tmp_path, service)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            client.post("/api/beta/login", json={"invite_code": "anna-invite"})
            me = client.get("/api/beta/me")
            assert me.status_code == 200
            assert me.json()["profile_complete"] is False
            assert me.json()["display_name"] == "Anna (seed)"

            updated = client.patch(
                "/api/beta/profile",
                json={"display_name": "  Anna K.  "},
            )
            assert updated.status_code == 200
            payload = updated.json()
            assert payload["profile_complete"] is True
            assert payload["display_name"] == "Anna K."
            assert payload["stats"]["feedback_notes"] == 1
            assert payload["stats"]["workflow_sessions"] == 1
            assert payload["member_since"]
    finally:
        app.dependency_overrides.clear()


def test_beta_profile_patch_requires_login(tmp_path: Path):
    service = _service(tmp_path)
    service.provision_tester(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-invite",
    )
    app.dependency_overrides[deps.get_beta_auth_service] = lambda: service
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.patch(
                "/api/beta/profile",
                json={"display_name": "Anna"},
            )
            assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
