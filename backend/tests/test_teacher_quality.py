from pathlib import Path

from app.teacher_agent.quality import (
    load_rubric,
    validate_lesson_duration,
    validate_source_citations,
)


RUBRICS = Path(__file__).parent / "evals" / "rubrics"


def test_adapted_rubrics_keep_the_p_r_o_m_schema():
    rubric = load_rubric(RUBRICS / "chemie_bayern_planning.csv")
    assert {item.bucket for item in rubric} == {"P", "R", "O", "M"}
    assert any(item.criterion_id == "P-CHEM-1" for item in rubric)


def test_source_citations_must_have_been_read_in_the_session():
    markdown = "Source: by-lehrplanplus-chemie-9-ntg#c9_atombau"
    consulted = [{"source_id": "by-lehrplanplus-chemie-9-ntg", "section_id": "c9_atombau"}]
    assert validate_source_citations(markdown, consulted, require=True) == []
    assert validate_source_citations(markdown, [], require=True)


def test_lesson_duration_guard_detects_an_inconsistent_flow():
    plan = "> Duration: 45 min\n\n- Einstieg (10 min)\n- Erarbeitung (30 min)\n- Sicherung (10 min)"
    assert validate_lesson_duration(plan) == [
        "Lesson-flow phases total 50 min, but the duration is 45 min."
    ]
