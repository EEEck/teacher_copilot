from app.teacher_agent.package_renderer import render_markdown_artifact
from tests.test_lesson_package import valid_artifact


def test_renderer_produces_one_three_audience_markdown_artifact():
    markdown = render_markdown_artifact(valid_artifact())

    assert markdown.startswith("# Lesson Package - Why do sodium and chlorine form ions?")
    assert markdown.count("## Teacher Lesson Plan") == 1
    assert markdown.count("## Student Materials") == 1
    assert markdown.count("## Observation and Update Capture") == 1
    assert "How can electron transfer explain ion formation?" in markdown
    assert "Use a before/after particle drawing to justify electron transfer." in markdown
    assert "### What was covered" in markdown
    assert "### Student participation and evidence" in markdown
    assert "### Misconceptions or surprises" in markdown
    assert "### What worked" in markdown
    assert "### Follow-up" in markdown


def test_renderer_keeps_teacher_moves_out_of_student_materials():
    markdown = render_markdown_artifact(valid_artifact())
    student_materials = markdown.split("## Student Materials", 1)[1].split(
        "## Observation and Update Capture", 1
    )[0]

    assert "Compare only the valence-electron change" not in student_materials
