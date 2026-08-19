"""Direct regression coverage for isolated layer-trace scoring."""

from __future__ import annotations

import pytest

from tests.evals.contracts.layer_contract import (
    LayerExpectation,
    LayerScope,
    score_layer_context,
)


def _trace(*, text: str, sections: list[dict] | None = None) -> dict:
    return {"text": text, "sections": sections or []}


@pytest.mark.parametrize(
    ("scope", "core_trace"),
    [
        (LayerScope.GLOBAL_ONLY, None),
        (
            LayerScope.GLOBAL_PLUS_CLASS,
            _trace(
                text="class marker",
                sections=[{"text": "class marker", "included": True}],
            ),
        ),
    ],
)
def test_non_subject_scopes_do_not_score_the_separate_subject_trace(
    scope: LayerScope, core_trace: dict | None
) -> None:
    result = score_layer_context(
        teacher_trace=_trace(text="teacher marker"),
        core_trace=core_trace,
        subject_trace=_trace(
            text="subject-only marker",
            sections=[
                {
                    "name": "Subject guide: chemie",
                    "text": "subject-only marker",
                    "included": True,
                }
            ],
        ),
        expectation=LayerExpectation(
            golden_id=f"isolation-{scope.value}",
            class_id="class-id",
            layer_scope=scope,
            required_markers=("teacher marker",),
            forbidden_markers=("subject-only marker",),
        ),
    )

    assert result.passed, result.failures


@pytest.mark.parametrize(
    ("subject_trace", "expected_failure"),
    [
        (
            None,
            "subject-separation: missing included subject guide section for 'chemie'",
        ),
        (
            _trace(
                text="wrong subject content",
                sections=[
                    {
                        "name": "Subject guide: chemie",
                        "text": "wrong subject content",
                        "included": True,
                    }
                ],
            ),
            "subject-separation subject: missing content marker 'subject marker'",
        ),
    ],
)
def test_subject_scope_rejects_missing_or_incomplete_subject_trace(
    subject_trace: dict | None, expected_failure: str
) -> None:
    result = score_layer_context(
        teacher_trace=_trace(text="teacher marker"),
        core_trace=_trace(
            text="class marker", sections=[{"text": "class marker", "included": True}]
        ),
        subject_trace=subject_trace,
        expectation=LayerExpectation(
            golden_id="subject-separation",
            class_id="class-id",
            layer_scope=LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT,
            required_markers=("teacher marker", "class marker"),
            subject_id="chemie",
            subject_required_markers=("subject marker",),
        ),
    )

    assert not result.passed
    assert expected_failure in result.failures


def test_subject_scope_requires_and_scores_a_separate_subject_trace() -> None:
    result = score_layer_context(
        teacher_trace=_trace(text="teacher marker"),
        core_trace=_trace(
            text="class marker", sections=[{"text": "class marker", "included": True}]
        ),
        subject_trace=_trace(
            text="subject marker",
            sections=[
                {
                    "name": "Subject guide: chemie",
                    "text": "subject marker",
                    "included": True,
                }
            ],
        ),
        expectation=LayerExpectation(
            golden_id="subject-separation",
            class_id="class-id",
            layer_scope=LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT,
            required_markers=("teacher marker", "class marker"),
            subject_id="chemie",
            subject_required_markers=("subject marker",),
        ),
    )

    assert result.passed, result.failures
