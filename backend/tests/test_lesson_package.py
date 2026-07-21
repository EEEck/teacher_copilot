from app.teacher_agent.lesson_package import (
    AnticipatedStudentIdea,
    ArtifactSection,
    DocumentSection,
    LearningGoal,
    LessonArtifact,
    LessonShared,
    RepresentationChoice,
    SourceRef,
    validate_lesson_artifact,
)


def valid_artifact() -> LessonArtifact:
    return LessonArtifact(
        title="Why do sodium and chlorine form ions?",
        shared=LessonShared(
            subject="chemie",
            grade=9,
            branch="NTG",
            artifact_language="en",
            duration_minutes=45,
            phenomenon_or_context="Salt formation from sodium and chlorine as a particle-model puzzle.",
            central_question="How can electron transfer explain ion formation?",
            big_idea="Electron transfer creates ions and helps explain salt formation.",
            learning_goals=[
                LearningGoal(
                    statement="Explain ion formation with electron transfer.",
                    knowledge="Valence electrons and ion charge.",
                    practice="Read and draw a particle model.",
                    meaning="Use the model to explain a familiar compound.",
                )
            ],
            prerequisites=["Students can read a shortened periodic table."],
            core_evidence_task="Use a before/after particle drawing to justify electron transfer.",
            anticipated_student_ideas=[
                AnticipatedStudentIdea(
                    idea="Atoms exchange whole shells.",
                    why_it_may_appear="Students may overgeneralize the shell diagram.",
                    teacher_move="Compare only the valence-electron change in a paired diagram.",
                )
            ],
            representations=[
                RepresentationChoice(
                    representation="particle drawing",
                    purpose="Make electron transfer visible.",
                    transition_to_or_from="Connect the drawing to ion symbols.",
                )
            ],
            differentiation_invariants=["All students justify the same particle-model evidence."],
            success_criteria=["I can identify electron donor and acceptor."],
            look_fors=["Students distinguish charge from oxidation number."],
            vocabulary=["ion", "electron transfer", "cation", "anion"],
            safety_notes=[],
            exit_ticket=["Draw and label the ions formed from Mg and O."],
        ),
        sections=[
            ArtifactSection(
                audience="teacher",
                title="Teacher Lesson Plan",
                sections=[DocumentSection(title="Lesson flow", items=["Opening: show the phenomenon."])],
            ),
            ArtifactSection(
                audience="student",
                title="Student Materials",
                sections=[DocumentSection(title="Evidence task", items=["Complete the particle drawing."])],
            ),
            ArtifactSection(
                audience="observation",
                title="Observation and Update Capture",
                sections=[DocumentSection(title="What worked", items=["Record the evidence."])],
            ),
        ],
        consulted_sources=[
            SourceRef(
                source_id="by-lehrplanplus-chemie-9-ntg",
                section_id="c9_atombau",
            )
        ],
    )


def test_valid_artifact_has_three_audiences_and_shared_quality_contract():
    assert validate_lesson_artifact(valid_artifact()) == []


def test_practical_artifact_requires_safety_notes():
    artifact = valid_artifact()
    artifact.shared.is_practical = True

    assert validate_lesson_artifact(artifact) == [
        "Practical lessons require at least one safety note."
    ]


def test_artifact_rejects_missing_observation_audience_and_unknown_source():
    artifact = valid_artifact()
    artifact.sections = artifact.sections[:2]

    errors = validate_lesson_artifact(
        artifact, allowed_source_ids={"by-lehrplanplus-chemie-8-ntg"}
    )

    assert "Artifact must contain exactly one teacher, student, and observation section." in errors
    assert "Unknown trusted source: by-lehrplanplus-chemie-9-ntg." in errors


def test_chemie_9_ntg_artifact_requires_ported_quality_contract_fields():
    artifact = valid_artifact()
    artifact.shared.learning_goals = [
        LearningGoal(statement="Explain ion formation.", knowledge="Ion charge.")
    ]
    artifact.shared.representations = []
    artifact.shared.differentiation_invariants = []
    artifact.consulted_sources = []

    errors = validate_lesson_artifact(artifact)

    assert "Each learning goal requires knowledge, practice, and meaning." in errors
    assert "Chemistry 9 NTG artifacts require at least one representation choice." in errors
    assert "Artifact requires differentiation invariants." in errors
    assert "Chemistry 9 NTG artifacts require a consulted trusted source." in errors


def test_plan_readiness_accepts_markdown_only_three_audience_package(wiki):
    markdown = """# Lesson Plan — Organic Chemistry 1: Why carbon makes four bonds

## Teacher

### Learning goals and evidence
- Students use a particle-model drawing to explain carbon bonding.

## Student

### Carbon bond ladder
- Draw and compare single, double, and triple bonds.

## Observation

### Exit evidence
- Explain one drawing using precise vocabulary.
"""

    assert wiki.is_plan_ready(markdown) is True
