from __future__ import annotations

import pytest

from app.course_network.models import CourseNetworkDocument, NetworkEdge
from app.course_network.review import CourseNetworkReviewJudgement
from app.course_network.seeds import load_seed_for_class
from app.course_network.validation import validate_course_network_draft
from app.services.course_network_service import CourseNetworkService
from app.services.workflow_drafts import (
    WorkflowDraftStore,
    serialize_structured_artifact,
)
from tests.conftest import CLASS_ID


class StubReviewer:
    def __init__(self, decision: str = "accept") -> None:
        self.decision = decision
        self.calls = 0

    async def review(
        self, document: CourseNetworkDocument
    ) -> CourseNetworkReviewJudgement:
        self.calls += 1
        return CourseNetworkReviewJudgement(
            decision=self.decision,
            summary=f"Reviewer decided {self.decision}.",
            findings=[],
        )


def _service(wiki, reviewer: StubReviewer) -> CourseNetworkService:
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    return CourseNetworkService(wiki=wiki, workflow_drafts=store, reviewer=reviewer)


def test_deterministic_validation_rejects_builds_on_cycle_and_unknown_provenance(wiki):
    seed = load_seed_for_class(wiki, CLASS_ID)
    cycle = NetworkEdge(
        id="cycle-back",
        source_id=seed.edges[0].target_id,
        target_id=seed.edges[0].source_id,
        relation="builds_on",
        origin="curriculum",
    )
    payload = seed.model_dump(mode="json")
    payload["route"]["grade"] = 8
    payload["edges"].append(cycle.model_dump(mode="json"))
    payload["nodes"][0]["curriculum_refs"] = [
        {"source_id": "missing-source", "section_id": "missing-section"}
    ]
    invalid = CourseNetworkDocument.for_draft_seed(**payload)

    errors = validate_course_network_draft(wiki, invalid)

    assert {error.code for error in errors} >= {
        "builds_on_cycle",
        "route_mismatch",
        "unknown_curriculum_reference",
    }


@pytest.mark.anyio
async def test_deterministic_provenance_failure_blocks_without_calling_llm(wiki):
    reviewer = StubReviewer()
    service = _service(wiki, reviewer)
    draft = service.open_seed_draft(CLASS_ID)
    payload = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    payload["nodes"][0]["curriculum_refs"] = [
        {"source_id": "not-registered", "section_id": "nope"}
    ]
    service.workflow_drafts.save_from_session(
        draft_id=draft.draft_id,
        status="draft",
        artifact_markdown=serialize_structured_artifact(payload),
        runtime_json={},
        messages_json=[],
        backend_session_id=draft.backend_session_id,
    )

    reviewed = await service.review_seed(CLASS_ID, draft.draft_id)

    assert reviewed.decision == "block"
    assert reviewer.calls == 0
    assert reviewed.findings[0].code == "unknown_curriculum_reference"


@pytest.mark.anyio
@pytest.mark.parametrize("decision", ["revise", "block"])
async def test_non_accepting_llm_review_stops_adoption(wiki, decision):
    reviewer = StubReviewer(decision)
    service = _service(wiki, reviewer)
    draft = service.open_seed_draft(CLASS_ID)
    reviewed = await service.review_seed(CLASS_ID, draft.draft_id)

    with pytest.raises(ValueError, match="course_network_review_not_accepted"):
        service.adopt_seed(
            CLASS_ID,
            draft.draft_id,
            reviewed.artifact_revision,
            reviewed.artifact_hash,
        )

    assert service.get_network(CLASS_ID) is None
