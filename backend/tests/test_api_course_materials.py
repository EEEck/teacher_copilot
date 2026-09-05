from types import SimpleNamespace
from pathlib import Path

import pytest
import yaml

from tests.conftest import CLASS_ID


def test_generation_retry_errors_are_documented(client):
    contract = yaml.safe_load((Path(__file__).resolve().parents[2] / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    runtime = client.app.openapi()
    for path in ["/api/classes/{class_id}/course/changes/generate",
                 "/api/classes/{class_id}/course/network/drafts/{draft_id}/revise"]:
        assert runtime["paths"][path]["post"]["responses"]["502"] == contract["paths"][path]["post"]["responses"]["502"]


def test_course_material_list_is_independent_of_plan_sessions(client):
    response = client.get(f"/api/classes/{CLASS_ID}/course/materials")
    assert response.status_code == 200
    assert response.json()["materials"] == []


def test_course_upload_rejects_non_pdf_and_unknown_class(client):
    response = client.post(
        f"/api/classes/{CLASS_ID}/course/material-imports",
        files={"file": ("bad.txt", b"text", "text/plain")},
    )
    assert response.status_code == 422
    assert client.get("/api/classes/nonexistent/course/materials").status_code == 404


def test_seed_revision_is_reviewable_and_rejects_a_stale_request(client, monkeypatch):
    from app.course_network import generation

    async def generate(wiki, class_id, request, current):
        return generation.CourseGenerationResult(
            changes={
                "class_id": class_id,
                "base_revision": current.revision,
                "summary": "Clarify goal",
                "operations": [
                    {
                        "op": "update_node",
                        "node_id": current.nodes[0].id,
                        "changes": {
                            "learning_goal": "Explain the curriculum concept accurately."
                        },
                    }
                ],
            }
        )

    monkeypatch.setattr(generation, "generate_course_changes", generate)
    base = f"/api/classes/{CLASS_ID}/course/network/drafts"
    row = client.post(base).json()
    body = {
        "expected_revision": row["artifact_revision"],
        "expected_hash": row["artifact_hash"],
    }
    revised = client.post(f"{base}/{row['draft_id']}/revise", json=body)
    assert revised.status_code == 200, revised.text
    assert revised.json()["artifact_revision"] == row["artifact_revision"] + 1
    assert revised.json()["review"] is None
    assert client.post(f"{base}/{row['draft_id']}/revise", json=body).status_code == 409
    assert (
        client.get(f"/api/classes/{CLASS_ID}/course/network").json()["network"] is None
    )


@pytest.mark.parametrize("failure", ["malformed", "schema", "timeout"])
@pytest.mark.parametrize("mode", ["adopted", "seed"])
def test_generation_failure_is_retryable_and_preserves_memory(
    client, wiki, monkeypatch, failure, mode
):
    from agents.exceptions import ModelBehaviorError
    from app.course_network import generation
    from app.course_network.models import CourseNetworkDocument
    from app.course_network.seeds import load_seed_for_class

    base = f"/api/classes/{CLASS_ID}/course"
    seed = load_seed_for_class(wiki, CLASS_ID)
    if mode == "adopted":
        payload = seed.model_dump()
        for node in payload["nodes"]:
            node["status"] = "adopted"
        wiki.write_course_network(CLASS_ID, CourseNetworkDocument.model_validate(payload))
        path, body = base + "/changes/generate", {"purpose": "correction"}
    else:
        row = client.post(base + "/network/drafts").json()
        path = base + f"/network/drafts/{row['draft_id']}/revise"
        body = {"expected_revision": row["artifact_revision"], "expected_hash": row["artifact_hash"]}
    before = client.get(base + "/network").json()

    async def broken(*args, **kwargs):
        if failure == "schema":
            return SimpleNamespace(final_output={"private_provider_detail": "invalid output"})
        if failure == "timeout":
            raise TimeoutError("private_provider_detail")
        raise ModelBehaviorError("private_provider_detail")

    monkeypatch.setattr(generation.Runner, "run", broken)
    response = client.post(path, json=body)
    assert response.status_code == 502
    assert "Try again" in response.json()["error"]["message"]
    assert "private_provider_detail" not in response.text
    assert client.get(base + "/network").json() == before
    assert client.get(base + "/changes").json()["drafts"] == []

    async def valid(*args, **kwargs):
        return SimpleNamespace(final_output={"changes": {
            "class_id": CLASS_ID, "base_revision": seed.revision,
            "summary": "Clarify", "operations": [{"op": "update_node",
                "node_id": seed.nodes[0].id, "changes": {"title": "Clearer concept"}}],
        }})

    monkeypatch.setattr(generation.Runner, "run", valid)
    assert client.post(path, json=body).status_code == 200
    assert client.get(base + "/network").json() == before
