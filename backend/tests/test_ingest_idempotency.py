"""Revising the same lesson writes only the diff — no duplicated sections.

Teacher scenario (beta 2026-07-07): commit a lesson, then come back later and
correct one student observation for the SAME date. The canonical wiki is keyed
on lesson_date (each rollup replaces its ``## {date}`` section), so a re-commit
must (a) not duplicate any date section and (b) actually reflect the correction.
"""

from __future__ import annotations

from app.schemas.api import ApprovedWikiUpdate
from app.teacher_agent.wiki.commit import commit_ingest, compile_from_diary
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID

DATE = "2026-07-07"


def _diary(s014_obs: str, didnt: str = "Rushed the ending.") -> str:
    return (
        f"# Lesson Results — {DATE} — Alkanes\n\n"
        "## What was covered\n- Introduction to alkanes.\n\n"
        "## Student participation\n- Active discussion.\n\n"
        "## What went well\n- Good energy.\n\n"
        f"## What didn't go well\n- {didnt}\n\n"
        f"## Student observations\n- S-014: {s014_obs}\n\n"
        "## Homework & follow-ups\n- Read chapter 4.\n"
    )


def _commit(wiki: WikiStore, diary: str, session_id: str) -> None:
    _date, proposals = compile_from_diary(wiki, CLASS_ID, diary)
    approved = [
        ApprovedWikiUpdate(
            wiki_path=p.wiki_path, content=p.proposed_content, approved=True
        )
        for p in proposals
    ]
    commit_ingest(wiki, CLASS_ID, diary, approved, session_id)


def test_revising_same_lesson_updates_only_the_diff(wiki: WikiStore):
    _commit(wiki, _diary("helped explain why oil and water separate."), "sess-1")

    s014 = wiki.student_path(CLASS_ID, "S-014")
    first = wiki.read_text(s014)
    assert "oil and water" in first
    assert first.count(f"## {DATE}") == 1

    # Come back later: correct S-014's observation for the SAME lesson date.
    _commit(wiki, _diary("actually led the class discussion confidently."), "sess-2")

    second = wiki.read_text(s014)
    # (a) no duplicated date section
    assert second.count(f"## {DATE}") == 1, "revision duplicated the student date section"
    # (b) the correction is reflected; the stale observation is gone
    assert "led the class discussion" in second, "revision did not update the observation"
    assert "oil and water" not in second, "stale observation was not replaced"


def test_revising_same_lesson_does_not_duplicate_rollup_sections(wiki: WikiStore):
    _commit(wiki, _diary("first note.", didnt="Too much noise."), "sess-1")
    _commit(wiki, _diary("second note.", didnt="Better focus this time."), "sess-2")

    paths = wiki.roll_up_paths(CLASS_ID)
    misc = wiki.read_text(paths["misconceptions"])
    loops = wiki.read_text(paths["open_loops"])
    # Each rollup keeps exactly one section for the revised date.
    assert misc.count(f"## {DATE}") == 1
    assert loops.count(f"## {DATE}") == 1
    # The revised "what didn't go well" content wins; the stale one is gone.
    assert "Better focus this time" in misc
    assert "Too much noise" not in misc
