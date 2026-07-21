from pathlib import Path
import sqlite3

from app.services.beta import BetaAuthService, BetaTelemetry, RequestIdentity
from app.services.beta_cli import main as beta_cli_main
from app.services.beta_report import (
    list_beta_testers,
    render_beta_report,
    write_all_beta_reports,
)


def _populate_report_fixture(tmp_path: Path) -> Path:
    db_path = tmp_path / "beta.sqlite3"
    identity = RequestIdentity(
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        role="tester",
        wiki_root=tmp_path / "workspaces" / "w_anna_chem9b" / "wiki",
    )
    telemetry = BetaTelemetry(db_path)
    telemetry.record_app_session(
        identity,
        app_session_id="sess-lesson-1",
        class_id="chemie_9b_2026_27",
        mode="memory",
        status="active",
    )
    telemetry.record_event(
        identity,
        event_type="chat_turn_started",
        class_id="chemie_9b_2026_27",
        app_session_id="sess-lesson-1",
        mode="memory",
        payload={"turn_id": "turn-1"},
    )
    telemetry.record_message(
        identity,
        app_session_id="sess-lesson-1",
        class_id="chemie_9b_2026_27",
        mode="memory",
        role="user",
        content="We reviewed oxidation numbers and I forgot to add S-046.",
    )
    telemetry.record_message(
        identity,
        app_session_id="sess-lesson-1",
        class_id="chemie_9b_2026_27",
        mode="memory",
        role="assistant",
        content="I added the observation to the lesson results draft.",
    )
    telemetry.record_artifact_snapshot(
        identity,
        app_session_id="sess-lesson-1",
        class_id="chemie_9b_2026_27",
        mode="memory",
        artifact_kind="diary",
        markdown="## 2026-07-02\n- S-046 was confused by FCKW electron transfer.",
    )
    telemetry.record_wiki_commit(
        identity,
        app_session_id="sess-lesson-1",
        class_id="chemie_9b_2026_27",
        mode="memory",
        action="memory_apply",
        changed_files=[
            (
                "classes/chemie_9b_2026_27/lessons/2026-07-02/lesson_results.md",
                "## Student observations\n",
                "## Student observations\n- S-046 was confused by FCKW electron transfer.\n",
            ),
            (
                "classes/chemie_9b_2026_27/open_loops.md",
                "## 2026-07-02\n- Check homework.\n",
                "## 2026-07-02\n- Check homework.\n",
            ),
        ],
        metadata={"intent": "correct_existing_results"},
    )
    telemetry.record_teacher_feedback(
        identity,
        message="Timeline felt hard to scan on a phone.",
        page="/classes/chemie_9b_2026_27",
    )
    return db_path


def test_beta_report_summarizes_tester_activity_and_wiki_diff(tmp_path: Path) -> None:
    db_path = _populate_report_fixture(tmp_path)

    report = render_beta_report(
        db_path,
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
    )

    assert "# Beta Telemetry Report" in report
    assert "Tester: `t_anna`" in report
    assert "Workspace: `w_anna_chem9b`" in report
    assert "sess-lesson-1" in report
    assert "We reviewed oxidation numbers" in report
    assert "Artifact snapshots" in report
    assert "memory_apply" in report
    assert "lesson_results.md" in report
    assert "S-046 was confused by FCKW electron transfer" in report
    assert "Incomplete chat turns" in report
    assert "No-op wiki diffs" in report
    assert "open_loops.md" in report
    assert "## Teacher feedback" in report
    assert "Timeline felt hard to scan on a phone." in report
    assert "page=`/classes/chemie_9b_2026_27`" in report


def test_beta_cli_report_writes_markdown_file(tmp_path: Path) -> None:
    db_path = _populate_report_fixture(tmp_path)
    out_path = tmp_path / "beta-report.md"

    result = beta_cli_main(
        [
            "report",
            "--db",
            str(db_path),
            "--tester",
            "t_anna",
            "--workspace",
            "w_anna_chem9b",
            "--out",
            str(out_path),
        ]
    )

    assert result == 0
    report = out_path.read_text(encoding="utf-8")
    assert "# Beta Telemetry Report" in report
    assert "sess-lesson-1" in report


def _provision_tester(
    tmp_path: Path,
    *,
    tester_id: str,
    workspace_id: str,
    invite_code: str,
) -> BetaAuthService:
    seed_wiki = tmp_path / "seed_wiki"
    seed_wiki.mkdir()
    service = BetaAuthService(
        db_path=tmp_path / "beta.sqlite3",
        data_root=tmp_path,
        seed_wiki_root=seed_wiki,
        cookie_name="kp_beta_session",
        session_days=7,
        cookie_secure=False,
    )
    service.provision_tester(
        tester_id=tester_id,
        workspace_id=workspace_id,
        invite_code=invite_code,
    )
    return service


def test_list_beta_testers_skips_disabled_by_default(tmp_path: Path) -> None:
    service = _provision_tester(
        tmp_path,
        tester_id="t_anna",
        workspace_id="w_anna",
        invite_code="anna-code",
    )
    _provision_tester(
        tmp_path,
        tester_id="t_bob",
        workspace_id="w_bob",
        invite_code="bob-code",
    )
    with sqlite3.connect(service.db_path) as conn:
        conn.execute("update tester set disabled = 1 where tester_id = 't_bob'")

    testers = list_beta_testers(service.db_path)

    assert [tester.tester_id for tester in testers] == ["t_anna"]


def test_write_all_beta_reports_writes_one_file_per_tester(tmp_path: Path) -> None:
    db_path = _populate_report_fixture(tmp_path)
    _provision_tester(
        tmp_path,
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-code",
    )
    reports_dir = tmp_path / "reports"

    written = write_all_beta_reports(db_path, reports_dir)

    assert len(written) == 1
    assert written[0] == reports_dir / "t_anna.md"
    report = written[0].read_text(encoding="utf-8")
    assert "Tester: `t_anna`" in report
    assert "sess-lesson-1" in report


def test_beta_cli_report_all_writes_markdown_files(tmp_path: Path, monkeypatch) -> None:
    db_path = _populate_report_fixture(tmp_path)
    _provision_tester(
        tmp_path,
        tester_id="t_anna",
        workspace_id="w_anna_chem9b",
        invite_code="anna-code",
    )
    reports_dir = tmp_path / "reports"

    from app.config import get_settings

    monkeypatch.setenv("BETA_DATA_ROOT", str(tmp_path))

    get_settings.cache_clear()

    result = beta_cli_main(
        [
            "report-all",
            "--db",
            str(db_path),
            "--reports-dir",
            str(reports_dir),
        ]
    )

    assert result == 0
    report_path = reports_dir / "t_anna.md"
    assert report_path.exists()
    assert "sess-lesson-1" in report_path.read_text(encoding="utf-8")
