"""Deterministic Markdown renderer for a structured lesson package."""

from __future__ import annotations

from app.teacher_agent.lesson_package import ArtifactSection, LessonArtifact


def _bullets(items: list[str], *, empty: str = "- None.") -> list[str]:
    return [f"- {item}" for item in items] or [empty]


def _document_sections(section: ArtifactSection, *, heading_level: int = 3) -> list[str]:
    lines: list[str] = []
    marker = "#" * heading_level
    for document in section.sections:
        lines.extend([f"{marker} {document.title}", *_bullets(document.items), ""])
    return lines


def _section_by_audience(artifact: LessonArtifact, audience: str) -> ArtifactSection:
    return next(section for section in artifact.sections if section.audience == audience)


def render_markdown_artifact(artifact: LessonArtifact) -> str:
    """Render one teacher/student/observation artifact from shared fields once."""
    shared = artifact.shared
    teacher = _section_by_audience(artifact, "teacher")
    student = _section_by_audience(artifact, "student")
    observation = _section_by_audience(artifact, "observation")
    lines = [
        f"# Lesson Package - {artifact.title}",
        "",
        f"> Duration: {shared.duration_minutes} min | Subject: {shared.subject} | "
        f"Grade: {shared.grade}" + (f" | Branch: {shared.branch}" if shared.branch else ""),
        "",
        "## Teacher Lesson Plan",
        "",
        "### Shared lesson contract",
        f"- Phenomenon or context: {shared.phenomenon_or_context}",
        f"- Central question: {shared.central_question}",
        f"- Big idea: {shared.big_idea}",
        f"- Core evidence task: {shared.core_evidence_task}",
        "",
        "### Learning goals",
    ]
    for goal in shared.learning_goals:
        lines.append(f"- {goal.statement}")
        for label, value in (
            ("Knowledge", goal.knowledge),
            ("Practice", goal.practice),
            ("Meaning", goal.meaning),
        ):
            if value:
                lines.append(f"  - {label}: {value}")
    lines.extend(["", "### Prerequisites", *_bullets(shared.prerequisites), ""])
    lines.append("### Anticipated student ideas")
    for idea in shared.anticipated_student_ideas:
        lines.extend(
            [
                f"- Idea: {idea.idea}",
                f"  - Why it may appear: {idea.why_it_may_appear}",
                f"  - Teacher move: {idea.teacher_move}",
            ]
        )
    if not shared.anticipated_student_ideas:
        lines.append("- None recorded.")
    lines.extend(["", "### Representations and transitions"])
    for choice in shared.representations:
        lines.append(f"- {choice.representation}: {choice.purpose}")
        if choice.transition_to_or_from:
            lines.append(f"  - Transition: {choice.transition_to_or_from}")
    if not shared.representations:
        lines.append("- None recorded.")
    lines.extend(
        [
            "",
            "### Differentiation invariants",
            *_bullets(shared.differentiation_invariants),
            "",
            "### Formative look-fors",
            *_bullets(shared.look_fors),
            "",
        ]
    )
    if shared.safety_notes:
        lines.extend(["### Safety", *_bullets(shared.safety_notes), ""])
    lines.extend(_document_sections(teacher))
    lines.extend(
        [
            "## Student Materials",
            "",
            "### Question and evidence task",
            f"- Question: {shared.central_question}",
            f"- Task: {shared.core_evidence_task}",
            "",
            "### Vocabulary",
            *_bullets(shared.vocabulary),
            "",
            "### Success criteria",
            *_bullets(shared.success_criteria),
            "",
        ]
    )
    if shared.safety_notes:
        lines.extend(["### Safety for students", *_bullets(shared.safety_notes), ""])
    lines.extend(_document_sections(student))
    lines.extend(
        [
            "## Observation and Update Capture",
            "",
            "### What was covered",
            "- Record what students actually worked on and the evidence task completed.",
            "",
            "### Student participation and evidence",
            "- Record participation patterns and evidence from the shared task or exit ticket.",
            "",
            "### Misconceptions or surprises",
            "- Record ideas that appeared, including whether the planned teacher move helped.",
            "",
            "### What worked",
            "- Record which representation, support, grouping, or activity helped learning.",
            "",
            "### Follow-up",
            "- Record the next instructional move, unfinished work, or homework.",
            "",
        ]
    )
    lines.extend(_document_sections(observation))
    lines.extend(["### Exit ticket", *_bullets(shared.exit_ticket), ""])
    if artifact.consulted_sources:
        lines.extend(["### Consulted sources"])
        for source in artifact.consulted_sources:
            ref = source.source_id
            if source.section_id:
                ref += f"#{source.section_id}"
            lines.append(f"- {ref}" + (f": {source.label}" if source.label else ""))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
