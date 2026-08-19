import hashlib
from copy import deepcopy

CLASS_8A = "chemie_8a_2026_27"
SEEDED_9B = "chemie_9b_2026_27"

CREATE_8A = {
    "label": "Chemie 8a — 2026/27",
    "subject": "chemie",
    "grade": 8,
    "section": "a",
    "school_year": "2026_27",
    "branch": "NTG",
    "school_type": "Gymnasium",
    "state": "BY",
    "prior_learning": "Atombau und Periodensystem wurden bereits wiederholt.",
    "student_names": ["Ada Beispiel", "Ben Beispiel"],
}


def _tree_digest(root) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_curriculum_routes_are_exactly_chemie_8_and_9_ntg(client):
    response = client.get("/api/classes/curriculum-routes")

    assert response.status_code == 200
    assert response.json() == {
        "routes": [
            {"subject": "chemie", "grade": 8, "branch": "NTG"},
            {"subject": "chemie", "grade": 9, "branch": "NTG"},
        ]
    }


def test_create_class_is_visible_and_starts_empty(client):
    response = client.post("/api/classes", json=CREATE_8A)

    assert response.status_code == 201
    assert response.json() == {
        "id": CLASS_8A,
        "label": "Chemie 8a — 2026/27",
        "subject": "chemie",
    }

    classes = client.get("/api/classes").json()["classes"]
    assert {item["id"] for item in classes} >= {SEEDED_9B, CLASS_8A}

    snapshot = client.get(f"/api/classes/{CLASS_8A}/snapshot")
    assert snapshot.status_code == 200
    data = snapshot.json()
    assert data["class_id"] == CLASS_8A
    assert data["current_unit"] == "Not set"
    assert data["last_lesson_date"] is None
    assert data["last_committed_date"] is None
    assert data["open_loop_count"] == 0
    assert data["top_misconceptions"] == []
    assert data["recent_lessons"] == []

    timeline = client.get(f"/api/classes/{CLASS_8A}/timeline")
    assert timeline.status_code == 200
    assert timeline.json()["entries"] == []
    assert timeline.json()["months"] == []


def test_duplicate_and_unsupported_requests_do_not_mutate_wiki(client, wiki):
    assert client.post("/api/classes", json=CREATE_8A).status_code == 201
    created_root = wiki.class_dir(CLASS_8A)
    before_created = _tree_digest(created_root)
    before_seeded_snapshot = client.get(f"/api/classes/{SEEDED_9B}/snapshot").json()
    before_seeded_timeline = client.get(f"/api/classes/{SEEDED_9B}/timeline").json()

    duplicate = client.post("/api/classes", json=CREATE_8A)
    assert duplicate.status_code == 422
    assert "already exists" in duplicate.json()["detail"]
    assert _tree_digest(created_root) == before_created

    unsupported = deepcopy(CREATE_8A)
    unsupported.update(
        {
            "label": "Chemie 8c — 2026/27",
            "section": "c",
            "branch": "SG",
        }
    )
    rejected = client.post("/api/classes", json=unsupported)
    assert rejected.status_code == 422
    assert "NTG" in rejected.json()["detail"]
    assert not wiki.class_dir("chemie_8c_2026_27").exists()

    assert (
        client.get(f"/api/classes/{SEEDED_9B}/snapshot").json()
        == before_seeded_snapshot
    )
    assert (
        client.get(f"/api/classes/{SEEDED_9B}/timeline").json()
        == before_seeded_timeline
    )
