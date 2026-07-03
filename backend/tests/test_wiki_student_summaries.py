"""Student summary contracts for student pages, index rebuilds, and sweep apply."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.schemas.api import ApprovedWikiUpdate
from app.services.memory_apply import apply_memory_sweep_decisions
from app.services.memory_candidate_ledger import MemoryCandidateLedger
from app.services.memory_sweep import (
    build_student_summary_sweep_proposals,
    memory_sweep_target_excerpts,
)
from app.teacher_agent.wiki_store import WikiStore
from tests.wiki_fixtures import CLASS_ID, DIARY, SEED_WIKI


@dataclass(frozen=True)
class _SweepDecision:
    action: str
    target: str
    section: str
    content: str
    candidate_ids: list[str]
    operation: str = "add"
    replaces_content: str = ""


def _copy_wiki(tmp_path: Path) -> WikiStore:
    root = tmp_path / "wiki"
    shutil.copytree(SEED_WIKI, root)
    return WikiStore(root=root)


def test_students_index_uses_student_summary_not_dated_observation(tmp_path: Path):
    wiki = _copy_wiki(tmp_path)
    path = wiki.student_path(CLASS_ID, "S-014")
    wiki.write_text(
        path,
        "# Alex Weber\n\n"
        f"> Class: {CLASS_ID}\n\n"
        "## Student Summary\n"
        "- Uses symbolic chemistry confidently when checks stay explicit.\n\n"
        "## 2026-04-24\n"
        "- Stale first weekly note should not appear in the class index.\n",
    )

    index = wiki._rebuild_students_index(CLASS_ID, previews={})

    assert "Uses symbolic chemistry confidently when checks stay explicit." in index
    assert "Stale first weekly note" not in index


def test_students_index_falls_back_when_summary_missing(tmp_path: Path):
    wiki = _copy_wiki(tmp_path)
    path = wiki.student_path(CLASS_ID, "S-014")
    wiki.write_text(
        path,
        "# Alex Weber\n\n"
        f"> Class: {CLASS_ID}\n\n"
        "## 2026-04-24\n"
        "- Old dated observation should not become durable summary.\n",
    )

    index = wiki._rebuild_students_index(CLASS_ID, previews={})

    assert "No approved summary yet." in index
    assert "Old dated observation" not in index


def test_compile_from_diary_adds_summary_section_without_rewriting_it(tmp_path: Path):
    wiki = _copy_wiki(tmp_path)
    student_path = wiki.student_path(CLASS_ID, "S-014")
    original_summary = "Uses symbolic chemistry confidently when checks stay explicit."
    wiki.write_text(
        student_path,
        "# Alex Weber\n\n"
        f"> Class: {CLASS_ID}\n\n"
        "## Student Summary\n"
        f"- {original_summary}\n\n"
        "## 2026-04-24\n"
        "- Fast with symbols and helped set up the first skeleton equations.\n",
    )

    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    student_prop = next(p for p in proposals if p.wiki_path.endswith("students/S-014.md"))

    assert f"- {original_summary}" in student_prop.proposed_content
    assert student_prop.proposed_content.index("## Student Summary") < (
        student_prop.proposed_content.index("## 2026-04-24")
    )
    assert "## 2026-10-01" in student_prop.proposed_content
    assert "- Excellent" in student_prop.proposed_content


def test_compile_from_diary_adds_empty_summary_section_to_existing_student_page(
    tmp_path: Path,
):
    wiki = _copy_wiki(tmp_path)
    wiki.write_text(
        wiki.student_path(CLASS_ID, "S-021"),
        "# Kathy Braun\n\n"
        f"> Class: {CLASS_ID}\n\n"
        "## 2026-04-24\n"
        "- Needed prompts for formula order and symbol placement.\n",
    )

    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    student_prop = next(p for p in proposals if p.wiki_path.endswith("students/S-021.md"))

    assert "## Student Summary\n- No approved summary yet." in student_prop.proposed_content
    assert student_prop.proposed_content.index("## Student Summary") < (
        student_prop.proposed_content.index("## 2026-04-24")
    )


def test_commit_preserves_student_summary_while_appending_observations(tmp_path: Path):
    wiki = _copy_wiki(tmp_path)
    student_path = wiki.student_path(CLASS_ID, "S-014")
    original_summary = "Uses symbolic chemistry confidently when checks stay explicit."
    wiki.write_text(
        student_path,
        "# Alex Weber\n\n"
        f"> Class: {CLASS_ID}\n\n"
        "## Student Summary\n"
        f"- {original_summary}\n\n"
        "## 2026-04-24\n"
        "- Fast with symbols and helped set up the first skeleton equations.\n",
    )
    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    approved = [
        ApprovedWikiUpdate(
            wiki_path=p.wiki_path,
            content=p.proposed_content,
            approved=True,
        )
        for p in proposals
    ]

    wiki.commit_ingest(CLASS_ID, DIARY, approved, "student-summary-session")

    written = wiki.read_text(student_path)
    assert f"- {original_summary}" in written
    assert "## 2026-10-01" in written
    assert "- Excellent" in written


def test_memory_sweep_student_excerpt_includes_summary_and_recent_observations(
    tmp_path: Path,
):
    wiki = _copy_wiki(tmp_path)

    excerpts = memory_sweep_target_excerpts(wiki, CLASS_ID, {"students/S-014.md"})

    excerpt = excerpts["students/S-014.md"]
    assert "## Student Summary" in excerpt
    assert "## 2026-05-29" in excerpt
    assert "Quick on the chloride" in excerpt


def test_memory_sweep_builds_student_summary_proposals_from_dated_observations(
    tmp_path: Path,
):
    wiki = _copy_wiki(tmp_path)

    grouped = build_student_summary_sweep_proposals(wiki, CLASS_ID)

    proposals = grouped["Student Memory"]
    proposal = next(p for p in proposals if p.target == "students/S-014.md")
    assert proposal.candidate_ids == [proposal.candidate_id]
    assert proposal.section == "Student Summary"
    assert "balanced trajectory" in proposal.content
    assert "2026-05-29" in proposal.evidence_summary
    assert f"wiki/classes/{CLASS_ID}/students/S-014.md" in proposal.evidence_refs


def test_memory_sweep_adjusts_student_summary_and_rebuilds_students_index(
    tmp_path: Path,
):
    wiki = _copy_wiki(tmp_path)
    student_path = wiki.student_path(CLASS_ID, "S-014")
    wiki.write_text(
        student_path,
        "# Alex Weber\n\n"
        f"> Class: {CLASS_ID}\n\n"
        "## Student Summary\n"
        "- Uses symbolic chemistry confidently when checks stay explicit.\n\n"
        "## 2026-05-29\n"
        "- Quick on the chloride, oxide, and phosphate comparison.\n",
    )

    applied, skipped, warnings, successful = apply_memory_sweep_decisions(
        wiki,
        CLASS_ID,
        [
            _SweepDecision(
                action="apply",
                target="students/S-014.md",
                section="Student Summary",
                operation="adjust",
                replaces_content=(
                    "Uses symbolic chemistry confidently when checks stay explicit."
                ),
                content=(
                    "Uses symbolic chemistry confidently and benefits from explicit "
                    "check steps during comparisons."
                ),
                candidate_ids=["student_summary_s014"],
            )
        ],
    )

    assert skipped == []
    assert warnings == []
    assert successful == [0]
    assert f"wiki/classes/{CLASS_ID}/students/S-014.md" in applied
    assert f"wiki/classes/{CLASS_ID}/students.md" in applied
    student_text = wiki.read_text(student_path)
    assert "benefits from explicit check steps" in student_text
    students_index = wiki.read_text(wiki.roll_up_paths(CLASS_ID)["students"])
    assert "benefits from explicit check steps" in students_index


def test_memory_sweep_api_accepts_synthetic_student_summary_candidate(
    tmp_path: Path,
):
    from app.api import deps
    from app.main import app

    wiki = _copy_wiki(tmp_path)
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    student_path = wiki.student_path(CLASS_ID, "S-014")
    wiki.write_text(
        student_path,
        "# Alex Weber\n\n"
        f"> Class: {CLASS_ID}\n\n"
        "## Student Summary\n"
        "- Uses symbolic chemistry confidently when checks stay explicit.\n\n"
        "## 2026-05-29\n"
        "- Quick on the chloride, oxide, and phosphate comparison.\n",
    )

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    try:
        from fastapi.testclient import TestClient

        with TestClient(app, raise_server_exceptions=False) as local_client:
            response = local_client.post(
                f"/api/classes/{CLASS_ID}/memory/sweep/apply",
                json={
                    "review_batch_id": "student_sweep_test",
                    "decisions": [
                        {
                            "card_id": "student_card_s014",
                            "action": "apply",
                            "target": "students/S-014.md",
                            "section": "Student Summary",
                            "operation": "adjust",
                            "replaces_content": (
                                "Uses symbolic chemistry confidently when checks stay explicit."
                            ),
                            "content": (
                                "Uses symbolic chemistry confidently and benefits from "
                                "explicit check steps during comparisons."
                            ),
                            "candidate_ids": [
                                f"student_summary:{CLASS_ID}:S-014"
                            ],
                        }
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert f"wiki/classes/{CLASS_ID}/students/S-014.md" in body["applied_wiki_paths"]
    assert body["updated_candidate_ids"] == []
