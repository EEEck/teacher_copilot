from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from app.api import deps
from app.course_network.review import CourseNetworkReviewJudgement
from app.main import app
from app.services.course_network_service import CourseNetworkService
from app.services.workflow_drafts import serialize_structured_artifact
from tests.conftest import CLASS_ID


def _resolved_error_response(spec, response):
    if "$ref" in response:
        response = spec["components"]["responses"][response["$ref"].rsplit("/", 1)[1]]
    schema = response["content"]["application/json"]["schema"]
    return response["description"], schema["$ref"]


def test_runtime_openapi_matches_course_network_draft_and_error_contracts(client):
    contract = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    runtime = client.app.openapi()

    assert runtime["components"]["schemas"]["CourseNetworkDraftResponse"]["properties"][
        "network"
    ] == {"$ref": "#/components/schemas/CourseNetworkDraftDocument"}
    source_contract_path = (
        "/api/classes/{classId}/course/network/sources/{sourceId}/sections/{sectionId}"
    )
    source_runtime_path = (
        "/api/classes/{class_id}/course/network/sources/"
        "{source_id}/sections/{section_id}"
    )
    assert contract["paths"][source_contract_path]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CourseNetworkSourceSectionResponse"
    }
    assert runtime["paths"][source_runtime_path]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/CourseNetworkSourceSectionResponse"}

    routes = [
        (
            "/api/classes/{classId}/course/network",
            "/api/classes/{class_id}/course/network",
            "get",
        ),
        (
            "/api/classes/{classId}/course/network/sources/{sourceId}/sections/{sectionId}",
            "/api/classes/{class_id}/course/network/sources/{source_id}/sections/{section_id}",
            "get",
        ),
        (
            "/api/classes/{classId}/course/network/drafts",
            "/api/classes/{class_id}/course/network/drafts",
            "post",
        ),
        (
            "/api/classes/{classId}/course/network/drafts/{draftId}",
            "/api/classes/{class_id}/course/network/drafts/{draft_id}",
            "get",
        ),
        (
            "/api/classes/{classId}/course/network/drafts/{draftId}/review",
            "/api/classes/{class_id}/course/network/drafts/{draft_id}/review",
            "post",
        ),
        (
            "/api/classes/{classId}/course/network/drafts/{draftId}/adopt",
            "/api/classes/{class_id}/course/network/drafts/{draft_id}/adopt",
            "post",
        ),
    ]
    for contract_path, runtime_path, method in routes:
        contract_responses = contract["paths"][contract_path][method]["responses"]
        expected_errors = {
            status: _resolved_error_response(contract, response)
            for status, response in contract_responses.items()
            if status in {"404", "409", "422"}
        }
        runtime_responses = runtime["paths"][runtime_path][method]["responses"]
        actual_errors = {
            status: _resolved_error_response(runtime, runtime_responses[status])
            for status in expected_errors
            if status in runtime_responses
        }
        assert actual_errors == expected_errors, f"{method.upper()} {contract_path}"


def test_course_network_source_section_returns_exact_class_authorized_evidence(
    client, wiki, workflow_drafts
):
    _service_override(wiki, workflow_drafts)
    expected = wiki.read_trusted_source(
        CLASS_ID,
        "by-lehrplanplus-chemie-9-ntg",
        "c9_ionen_redox",
    )

    with patch.object(
        wiki, "read_trusted_source", wraps=wiki.read_trusted_source
    ) as read_source:
        response = client.get(
            f"/api/classes/{CLASS_ID}/course/network/sources/"
            "by-lehrplanplus-chemie-9-ntg/sections/c9_ionen_redox"
        )

    read_source.assert_called_once_with(
        CLASS_ID,
        "by-lehrplanplus-chemie-9-ntg",
        "c9_ionen_redox",
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "source_id": "by-lehrplanplus-chemie-9-ntg",
        "source_title": "LehrplanPLUS Chemie 9 NTG",
        "section_id": "c9_ionen_redox",
        "section_title": "Donator-Akzeptor-Konzept (Ionen und Redox)",
        "content": (
            "Students explain ion formation and electron transfer with the "
            "donor\u2013acceptor\nconcept, including salt formation, electrolysis of "
            "solutions or melts, redox\nhalf-equations, and everyday links such as "
            "batteries and rechargeable cells.\nThey connect forced and spontaneous "
            "redox processes and interpret metal\nbehaviour in metal-salt solutions at "
            "the particle level."
        ),
        "provenance": {
            "authority": "official_curriculum",
            "jurisdiction": "BY",
            "canonical_url": (
                "https://www.lehrplanplus.bayern.de/"
                "fachlehrplan/gymnasium/9/chemie/ch-ntg"
            ),
            "retrieved_at": "2026-07-18",
            "version_label": "current_snapshot",
            "content_hash": expected["content_hash"],
        },
    }
    assert "path" not in response.text


def test_course_network_source_section_hides_linked_but_route_unauthorized_evidence(
    client, wiki, workflow_drafts
):
    _service_override(wiki, workflow_drafts)

    response = client.get(
        f"/api/classes/{CLASS_ID}/course/network/sources/"
        "by-lehrplanplus-chemie-8-ntg/sections/c8_reactions"
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["message"] == (
        "course_network_source_section_not_found"
    )

    unknown_section = client.get(
        f"/api/classes/{CLASS_ID}/course/network/sources/"
        "by-lehrplanplus-chemie-9-ntg/sections/not-a-real-section"
    )
    assert unknown_section.status_code == 404, unknown_section.text
    assert unknown_section.json()["error"]["message"] == (
        "course_network_source_section_not_found"
    )


class AcceptingReviewer:
    async def review(self, packet: str) -> CourseNetworkReviewJudgement:
        return CourseNetworkReviewJudgement(
            decision="accept", summary="The reviewed seed is suitable.", findings=[]
        )


def _service_override(wiki, workflow_drafts):
    service = CourseNetworkService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=AcceptingReviewer()
    )
    app.dependency_overrides[deps.get_course_network_service] = lambda: service
    return service


def test_concept_lessons_are_class_scoped_read_only_and_unknown_nodes_are_not_found(client, wiki, workflow_drafts):
    from app.course_network.lesson_refs import write_plan_course_refs
    from tests.test_course_planning_context import topic_network

    _service_override(wiki, workflow_drafts)
    topic_network(wiki)
    lesson = wiki.lesson_dir(CLASS_ID, "2026-10-05")
    lesson.mkdir(parents=True, exist_ok=True)
    (lesson / "lesson_plan.md").write_text("pH plan", encoding="utf-8")
    write_plan_course_refs(wiki, CLASS_ID, "2026-10-05", "pH plan", {"class_id": CLASS_ID, "node_ids": ["z-ph"]})
    before = {str(p): p.read_bytes() for p in wiki.class_dir(CLASS_ID).rglob("*") if p.is_file()}
    response = client.get(f"/api/classes/{CLASS_ID}/course/network/nodes/z-ph/lessons")
    assert response.status_code == 200, response.text
    assert response.json()["associations"][0]["kind"] == "planned"
    assert response.json()["associations"][0]["lesson_date"] == "2026-10-05"
    assert client.get(f"/api/classes/{CLASS_ID}/course/network/nodes/a-salts/lessons").json()["associations"] == []
    assert client.get(f"/api/classes/{CLASS_ID}/course/network/nodes/unknown/lessons").status_code == 404
    assert client.get("/api/classes/unknown/course/network/nodes/z-ph/lessons").status_code == 404
    assert before == {str(p): p.read_bytes() for p in wiki.class_dir(CLASS_ID).rglob("*") if p.is_file()}


def test_concept_lessons_api_preserves_distinct_saved_material_relation(client, wiki, workflow_drafts):
    from app.course_network.lesson_refs import build_plan_course_refs, write_plan_course_refs
    from tests.test_course_lesson_refs import _material_linked_network

    _service_override(wiki, workflow_drafts)
    network, material = _material_linked_network(wiki, workflow_drafts)
    plan = f"Material: {material.material_id}"
    lesson = wiki.lesson_dir(CLASS_ID, "2026-10-05")
    lesson.mkdir(parents=True, exist_ok=True)
    (lesson / "lesson_plan.md").write_text(plan, encoding="utf-8")
    write_plan_course_refs(wiki, CLASS_ID, lesson.name, plan, build_plan_course_refs(wiki, CLASS_ID, plan))
    response = client.get(f"/api/classes/{CLASS_ID}/course/network/nodes/{network.nodes[0].id}/lessons")
    assert response.status_code == 200, response.text
    assert [(item["kind"], item["relation"]) for item in response.json()["associations"]] == [("planned", "uses_linked_material")]


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
