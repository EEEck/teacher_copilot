"""Memory Sweep golden definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from tests.evals.goldens.layer_isolation import CHEMIE_9B_CLASS_ID


@dataclass(frozen=True)
class MemorySweepSeed:
    candidate_id: str
    channel: str
    target: str
    section: str
    content: str
    class_id: str | None = CHEMIE_9B_CLASS_ID
    subject: str | None = "chemie"
    workflow: str = "memory_sweep"
    session_id: str = "golden_memory_sweep"
    source: str = "approved_wiki"
    basis: str = "explicit"
    confidence: str = "high"


@dataclass(frozen=True)
class MemorySweepGolden:
    golden_id: str
    class_id: str
    subject: str
    seeds: tuple[MemorySweepSeed, ...]
    expected_queue_targets: dict[str, tuple[str, ...]] = field(default_factory=dict)
    apply_candidate_ids: tuple[str, ...] = ()
    reject_candidate_ids: tuple[str, ...] = ()
    expected_applied_paths: tuple[str, ...] = ()
    expected_skipped: tuple[str, ...] = ()
    changed_markers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    unchanged_paths: tuple[str, ...] = ()
    absent_after_review: tuple[str, ...] = ()


_SEEDS: tuple[MemorySweepSeed, ...] = (
    MemorySweepSeed(
        candidate_id="golden_teacher_mbb",
        class_id=None,
        subject=None,
        channel="teacher_behavior",
        target="teacher_profile.md",
        section="Communication",
        content="Prefers concise MBB-style planning summaries.",
        workflow="plan",
        source="inferred_from_session",
        basis="repeated_behavior",
        confidence="medium",
    ),
    MemorySweepSeed(
        candidate_id="golden_class_examples",
        channel="class_learning_pattern",
        target="teaching_patterns.md",
        section="What Worked Well",
        content=(
            "Concrete redox examples helped Chemie 9b connect electron transfer "
            "to symbolic oxidation-number work."
        ),
        workflow="ingest",
    ),
    MemorySweepSeed(
        candidate_id="golden_subject_sequence",
        channel="subject_concept",
        target="wiki/subjects/chemie.md",
        section="Common lesson patterns",
        content=(
            "For chemistry classes, introduce oxidation numbers after concrete "
            "electron-transfer examples."
        ),
        workflow="plan",
        source="teacher_explicit",
    ),
    MemorySweepSeed(
        candidate_id="golden_lint_state",
        channel="wiki_lint",
        target="class_state.md",
        section="Current State",
        content="Class is now applying redox vocabulary in worked examples.",
    ),
)


MEMORY_SWEEP_GOLDENS: tuple[MemorySweepGolden, ...] = (
    MemorySweepGolden(
        golden_id="9b_memory_sweep_routes_channels",
        class_id=CHEMIE_9B_CLASS_ID,
        subject="chemie",
        seeds=_SEEDS,
        expected_queue_targets={
            "Teacher/Copilot Preferences": ("teacher_profile.md",),
            "Class Evolution": ("teaching_patterns.md",),
            "Subject Concepts": ("wiki/subjects/chemie.md",),
            "Wiki Review": ("class_state.md",),
        },
    ),
    MemorySweepGolden(
        golden_id="9b_memory_sweep_subject_vs_class_boundary",
        class_id=CHEMIE_9B_CLASS_ID,
        subject="chemie",
        seeds=_SEEDS,
        apply_candidate_ids=("golden_class_examples", "golden_subject_sequence"),
        expected_applied_paths=(
            f"wiki/classes/{CHEMIE_9B_CLASS_ID}/memory/teaching_patterns.md",
            "wiki/subjects/chemie.md",
        ),
        changed_markers={
            f"wiki/classes/{CHEMIE_9B_CLASS_ID}/memory/teaching_patterns.md": (
                "Concrete redox examples helped Chemie 9b",
            ),
            "wiki/subjects/chemie.md": (
                "introduce oxidation numbers after concrete electron-transfer examples",
            ),
        },
        unchanged_paths=(
            f"wiki/classes/{CHEMIE_9B_CLASS_ID}/lessons/2026-05-29/lesson_results.md",
            "wiki/teacher_profile.md",
        ),
    ),
    MemorySweepGolden(
        golden_id="9b_memory_sweep_rejected_stays_rejected",
        class_id=CHEMIE_9B_CLASS_ID,
        subject="chemie",
        seeds=_SEEDS,
        reject_candidate_ids=("golden_teacher_mbb",),
        absent_after_review=("golden_teacher_mbb",),
    ),
)
