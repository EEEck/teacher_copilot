import pytest

from app.course_materials.sections import (
    extract_sections,
    render_sections,
    read_section_body,
)
from app.course_materials.models import SectionDraft, CourseMaterialManifest


def test_duplicate_headings_get_stable_distinct_ids_after_rename():
    sections = extract_sections(
        "## PDF page 4\n# Energy\nActivation barrier.\n## PDF page 5\n# Energy\nCatalysts lower it.",
        [4, 5],
    )
    assert len(sections) == 2
    assert sections[0].id != sections[1].id
    saved_id = sections[0].id
    sections[0].title = "Activation energy"
    text = render_sections(sections)
    assert read_section_body(text, saved_id) == "# Energy\nActivation barrier."
    assert sections[0].page_start == 4


def test_missing_section_does_not_return_entire_document():
    with pytest.raises(KeyError):
        read_section_body("Some text", "nonexistent")


def test_invalid_page_ranges_are_rejected():
    with pytest.raises(ValueError):
        SectionDraft(id="s1", title="Energy", page_start=5, page_end=4, content="Text")
