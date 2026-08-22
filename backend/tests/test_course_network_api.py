from __future__ import annotations

from app.api import deps
from app.course_network.models import CourseNetworkDocument
from app.course_network.review import CourseNetworkReviewJudgement
from app.main import app
from app.services.course_network_service import CourseNetworkService
from app.services.workflow_drafts import serialize_structured_artifact
from tests.conftest import CLASS_ID


class AcceptingReviewer:
    async def review(
        self, document: CourseNetworkDocument
    ) -> CourseNetworkReviewJudgement:
        return CourseNetworkReviewJudgement(
            decision="accept", summary="The reviewed seed is suitable.", findings=[]
        )


def _service_override(wiki, workflow_drafts):
    service = CourseNetworkService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=AcceptingReviewer()
    )
    app.dependency_overrides[deps.get_course_network_service] = lambda: service
    return service


def test_course_network_open_review_and_teacher_adoption_are_explicit(
    client, wiki, workflow_drafts
):
    _service_override(wiki, workflow_drafts)
    base = f"/api/classes/{CLASS_ID}/course/network"

    before = client.get(base)
    opened = client.post(f"{base}/drafts")

    assert before.status_code == 200, before.text
    assert before.json()["network"] is None
    assert opened.status_code == 201, opened.text
    assert wiki.load_course_network(CLASS_ID) is None
    assert opened.json()["artifact_markdown"] == serialize_structured_artifact(
        opened.json()["network"]
    )

    draft = opened.json()
    reviewed = client.post(f"{base}/drafts/{draft['draft_id']}/review")
    assert reviewed.status_code == 200, reviewed.text
    review = reviewed.json()["review"]
    assert review["decision"] == "accept"
    assert review["artifact_revision"] == draft["artifact_revision"]
    assert review["artifact_hash"] == draft["artifact_hash"]
    assert wiki.load_course_network(CLASS_ID) is None

    adopted = client.post(
        f"{base}/drafts/{draft['draft_id']}/adopt",
        json={
            "expected_revision": review["artifact_revision"],
            "expected_hash": review["artifact_hash"],
        },
    )

    assert adopted.status_code == 200, adopted.text
    assert adopted.json()["network"]["revision"] == 1
    assert {node["status"] for node in adopted.json()["network"]["nodes"]} == {
        "adopted"
    }
    assert "course_network_adopt" in wiki.read_text(wiki.log_path)
    assert client.post(f"{base}/drafts").status_code == 409


def test_course_network_adoption_rejects_stale_review_snapshot(
    client, wiki, workflow_drafts
):
    service = _service_override(wiki, workflow_drafts)
    base = f"/api/classes/{CLASS_ID}/course/network"
    opened = client.post(f"{base}/drafts").json()
    review = client.post(f"{base}/drafts/{opened['draft_id']}/review").json()["review"]
    changed_network = opened["network"]
    changed_network["nodes"][0]["title"] += " (späte Änderung)"
    service.workflow_drafts.save_from_session(
        draft_id=opened["draft_id"],
        status="draft",
        artifact_markdown=serialize_structured_artifact(changed_network),
        runtime_json={},
        messages_json=[],
        backend_session_id=opened["backend_session_id"],
    )

    stale = client.post(
        f"{base}/drafts/{opened['draft_id']}/adopt",
        json={
            "expected_revision": review["artifact_revision"],
            "expected_hash": review["artifact_hash"],
        },
    )

    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["message"] == "draft_changed_since_review_created"
    assert wiki.load_course_network(CLASS_ID) is None
