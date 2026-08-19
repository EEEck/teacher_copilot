import hashlib
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

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
    assert data["last_committed_at"] is None
    assert data["last_committed_title"] is None
    assert data["open_loop_count"] == 0
    assert data["top_misconceptions"] == []
    assert data["recent_lessons"] == []

    timeline = client.get(f"/api/classes/{CLASS_8A}/timeline")
    assert timeline.status_code == 200
    assert timeline.json()["entries"] == []
    assert timeline.json()["months"] == []


def test_created_class_wiki_catalog_includes_profile_and_trusted_sources(client):
    assert client.post("/api/classes", json=CREATE_8A).status_code == 201

    response = client.get(f"/api/classes/{CLASS_8A}/wiki/pages")

    assert response.status_code == 200
    catalog = {item["path"]: item["kind"] for item in response.json()["pages"]}
    assert catalog[f"wiki/classes/{CLASS_8A}/curriculum_profile.md"] == "meta"
    assert catalog[f"wiki/classes/{CLASS_8A}/trusted_sources.md"] == "meta"


def test_duplicate_and_unsupported_requests_do_not_mutate_wiki(client, wiki):
    assert client.post("/api/classes", json=CREATE_8A).status_code == 201
    created_root = wiki.class_dir(CLASS_8A)
    before_created = _tree_digest(created_root)
    before_seeded_snapshot = client.get(f"/api/classes/{SEEDED_9B}/snapshot").json()
    before_seeded_timeline = client.get(f"/api/classes/{SEEDED_9B}/timeline").json()

    duplicate = client.post("/api/classes", json=CREATE_8A)
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["type"] == "http_error"
    assert "already exists" in duplicate.json()["error"]["message"]
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
    assert rejected.json()["error"]["type"] == "http_error"
    assert "NTG" in rejected.json()["error"]["message"]
    assert not wiki.class_dir("chemie_8c_2026_27").exists()

    assert (
        client.get(f"/api/classes/{SEEDED_9B}/snapshot").json()
        == before_seeded_snapshot
    )
    assert (
        client.get(f"/api/classes/{SEEDED_9B}/timeline").json()
        == before_seeded_timeline
    )


def test_create_class_domain_and_request_validation_share_error_envelope(client):
    unsupported = deepcopy(CREATE_8A)
    unsupported["branch"] = "SG"

    domain = client.post("/api/classes", json=unsupported)
    request_validation = client.post(
        "/api/classes", json={"subject": "chemie", "grade": 8}
    )

    assert domain.status_code == request_validation.status_code == 422
    assert domain.json() == {
        "error": {
            "type": "http_error",
            "message": "Only the NTG branch is supported.",
            "detail": None,
        }
    }
    validation_body = request_validation.json()
    assert validation_body["error"]["type"] == "validation_error"
    assert validation_body["error"]["message"] == "Request validation failed"
    assert "label" in validation_body["error"]["detail"]


def test_create_class_schema_accepts_999_roster_entries(client, wiki):
    payload = deepcopy(CREATE_8A)
    payload["student_names"] = [f"Student {index}" for index in range(1, 1000)]

    response = client.post("/api/classes", json=payload)

    assert response.status_code == 201
    assert wiki.student_path(CLASS_8A, "S-999").exists()


def test_create_class_schema_rejects_1000_roster_entries(client, wiki):
    payload = deepcopy(CREATE_8A)
    payload["student_names"] = [f"Student {index}" for index in range(1, 1001)]

    response = client.post("/api/classes", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"
    assert not wiki.class_dir(CLASS_8A).exists()


@pytest.mark.parametrize("name", ["Ada | Beispiel", "Ada\nBeispiel"])
def test_create_class_schema_rejects_table_sensitive_roster_names(client, wiki, name):
    payload = deepcopy(CREATE_8A)
    payload["student_names"] = [name]

    response = client.post("/api/classes", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"
    assert not wiki.class_dir(CLASS_8A).exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("label", "L" * 121),
        ("school_year", "Y" * 21),
        ("prior_learning", "P" * 4001),
        ("student_names", ["S" * 121]),
    ],
)
def test_create_class_schema_rejects_oversized_text(client, wiki, field, value):
    payload = deepcopy(CREATE_8A)
    payload[field] = value

    response = client.post("/api/classes", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"
    assert not wiki.class_dir(CLASS_8A).exists()


def test_static_and_runtime_openapi_document_the_create_class_422_envelope(client):
    contract_path = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    runtime = client.app.openapi()

    response_schema = contract["paths"]["/api/classes"]["post"]["responses"]["422"][
        "content"
    ]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/ErrorEnvelope"}
    assert (
        runtime["paths"]["/api/classes"]["post"]["responses"]["422"]["content"][
            "application/json"
        ]["schema"]
        == response_schema
    )
    for schema_name in ("ErrorEnvelope", "ErrorBody"):
        assert (
            contract["components"]["schemas"][schema_name]["required"]
            == runtime["components"]["schemas"][schema_name]["required"]
        )
