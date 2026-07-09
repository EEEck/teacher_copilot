from app.teacher_agent.wiki.search import (
    ReferenceQuery,
    resolve_wiki_references,
)


ACTIVE_CLASS = "chemie_9b_2026_27"


def _add_other_class(wiki):
    class_id = "chemie_9a_2026_27"
    root = wiki.root / "wiki" / "classes" / class_id
    root.mkdir(parents=True)
    (root / "class_config.md").write_text(
        "# Chemie 9a 2026/27\n\nsubject: chemie\n", encoding="utf-8"
    )
    (root / "students.md").write_text(
        "\n".join(
            [
                "# Students - Chemie 9a",
                "",
                "| Student ID | Name | Summary | Detail |",
                "|---|---|---|---|",
                "| S-099 | Test Student | No summary. | [students/S-099.md](students/S-099.md) |",
            ]
        ),
        encoding="utf-8",
    )
    (root / "timeline.md").write_text(
        "# Lesson Timeline\n\n## 2026-06-01 - Other lesson\n", encoding="utf-8"
    )
    return class_id


def test_student_id_and_name_resolve_in_active_class(wiki):
    result = wiki.resolve_wiki_references(
        ACTIVE_CLASS,
        references=[
            ReferenceQuery(kind="student", value="S-46"),
            ReferenceQuery(kind="student", value="Mira Lange"),
        ],
        scope="active_class",
    )

    assert [item.status for item in result.items] == [
        "active_class_match",
        "active_class_match",
    ]
    assert [item.matches[0].canonical_value for item in result.items] == [
        "S-046",
        "S-046",
    ]


def test_student_reference_can_match_another_class(wiki):
    other_class = _add_other_class(wiki)

    result = resolve_wiki_references(
        wiki,
        active_class_id=ACTIVE_CLASS,
        references=[ReferenceQuery(kind="student", value="S-099")],
        scope="workspace",
    )

    item = result.items[0]
    assert item.status == "cross_class_match"
    assert item.matches[0].class_id == other_class
    assert item.matches[0].evidence_path.endswith(
        f"/classes/{other_class}/students.md"
    )


def test_unknown_student_reference_is_not_reinterpreted(wiki):
    result = resolve_wiki_references(
        wiki,
        active_class_id=ACTIVE_CLASS,
        references=[ReferenceQuery(kind="student", value="S-999")],
        scope="workspace",
    )

    assert result.items[0].status == "unresolved"
    assert result.items[0].matches == []


def test_lesson_date_resolves_against_active_timeline(wiki):
    result = resolve_wiki_references(
        wiki,
        active_class_id=ACTIVE_CLASS,
        references=[ReferenceQuery(kind="lesson", value="2026-05-29")],
        scope="active_class",
    )

    assert result.items[0].status == "active_class_match"
    assert result.items[0].matches[0].canonical_value == "2026-05-29"
