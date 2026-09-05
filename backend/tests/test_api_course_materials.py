from tests.conftest import CLASS_ID


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
