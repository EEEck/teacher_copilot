"""Course HTTP boundaries use the authenticated wiki, even when IDs collide."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import pytest
from app.course_materials.import_service import DocumentReviewer
from app.course_materials.models import MaterialImportArtifact, SectionDraft
from app.course_materials.sections import render_sections
from app.course_network.lesson_refs import write_plan_course_refs
from app.course_network.models import CourseNetworkDocument
from app.course_network.review import (
    CourseNetworkReviewJudgement,
    OpenAICourseNetworkReviewer,
)
from app.course_network.seeds import load_seed_for_class
from app.main import app
from app.services.workflow_drafts import (
    WorkflowDraftIdentity,
    WorkflowDraftStore,
    default_workflow_draft_store_path,
)
from app.teacher_agent.wiki_store import WikiStore
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from tests.test_beta_auth_telemetry import CLASS_ID, _enable_beta, _service

BASE = f"/api/classes/{CLASS_ID}/course"
MATERIAL_ID = "same-material"
SECTION_ID = "same-section"
NODE_ID = "same-concept"
IMPORT_ID = "11111111-1111-4111-8111-111111111111"
CHANGE_ID = "22222222-2222-4222-8222-222222222222"
SEED_ID = "33333333-3333-4333-8333-333333333333"
PRIVATE_ID = "44444444-4444-4444-8444-444444444444"


def _pdf(marker):
    writer = PdfWriter()
    writer.add_blank_page(width=120, height=120)
    writer.add_metadata({"/Title": marker})
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _artifact(marker, material_id):
    return MaterialImportArtifact(
        class_id=CLASS_ID,
        material_id=material_id,
        title=marker,
        arm="personal",
        source_filename="chapter.pdf",
        source_hash=marker,
        sections=[
            SectionDraft(
                id=SECTION_ID,
                title=marker,
                page_start=1,
                page_end=1,
                content=f"{marker} private chapter evidence.",
            )
        ],
    )


def _draft(
    store, workspace_id, draft_id, artifact, *, mode, intent, target_kind, runtime=None
):
    # Deliberate collisions exercise real independent databases, not mocked services.
    with patch("app.services.workflow_drafts.uuid.uuid4", return_value=UUID(draft_id)):
        return store.open_structured_draft(
            WorkflowDraftIdentity(
                workspace_id=workspace_id,
                class_id=CLASS_ID,
                mode=mode,
                intent=intent,
                target_kind=target_kind,
            ),
            default_status="draft",
            artifact=artifact,
            runtime_json=runtime or {},
        ).row


def _prepare_account(identity, marker):
    wiki = WikiStore(root=identity.wiki_root)
    drafts = WorkflowDraftStore(default_workflow_draft_store_path(wiki.root))
    drafts.initialize()
    source = _pdf(marker)
    material = _artifact(marker, MATERIAL_ID)
    root = wiki.class_dir(CLASS_ID) / "materials/personal" / MATERIAL_ID
    root.mkdir(parents=True)
    (root / "material.json").write_text(
        material.manifest(approved_at=datetime.now(UTC)).model_dump_json(),
        encoding="utf-8",
    )
    (root / "document.agent.md").write_text(
        render_sections(material.sections), encoding="utf-8"
    )
    (root / "source.pdf").write_bytes(source)
    (root / "provenance.json").write_text(
        '{"original_page_numbers": [1]}', encoding="utf-8"
    )
    network = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    network.update(
        nodes=[
            {
                "id": NODE_ID,
                "title": marker,
                "learning_goal": f"Explain {marker}",
                "origin": "teacher",
                "status": "adopted",
            }
        ],
        edges=[],
        material_mappings=[],
        positions={},
    )
    wiki.write_course_network(CLASS_ID, CourseNetworkDocument.model_validate(network))
    lesson = wiki.lesson_dir(CLASS_ID, "2026-10-05")
    lesson.mkdir(parents=True, exist_ok=True)
    plan = f"{marker}: Course: {NODE_ID}"
    (lesson / "lesson_plan.md").write_text(plan, encoding="utf-8")
    (lesson / "lesson_results.md").write_text(
        f"{marker}: experiment unfinished.", encoding="utf-8"
    )
    write_plan_course_refs(
        wiki,
        CLASS_ID,
        "2026-10-05",
        plan,
        {"class_id": CLASS_ID, "node_ids": [NODE_ID]},
    )
    pending = _artifact(marker, "same-pending-material")
    _draft(
        drafts,
        identity.workspace_id,
        IMPORT_ID,
        pending.model_dump(),
        mode="course_material",
        intent="import",
        target_kind=pending.material_id,
        runtime={"stage": "document_review", "pages": [1]},
    )
    package = wiki.root / "workflow/course_imports" / IMPORT_ID / "package"
    package.mkdir(parents=True)
    (package / "source.pdf").write_bytes(source)
    (package / "document.agent.md").write_text(
        render_sections(pending.sections), encoding="utf-8"
    )
    (package / "provenance.json").write_text(
        '{"original_page_numbers": [1]}', encoding="utf-8"
    )
    changes = {
        "class_id": CLASS_ID,
        "base_revision": 1,
        "summary": marker,
        "operations": [
            {
                "op": "update_node",
                "node_id": NODE_ID,
                "changes": {"learning_goal": f"{marker} revised goal"},
            }
        ],
    }
    _draft(
        drafts,
        identity.workspace_id,
        CHANGE_ID,
        changes,
        mode="course_network",
        intent="edit",
        target_kind="course_network",
    )
    seed = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    seed["nodes"][0]["title"] = marker
    _draft(
        drafts,
        identity.workspace_id,
        SEED_ID,
        seed,
        mode="course_network",
        intent="seed_adoption",
        target_kind="course_network",
    )
    return SimpleNamespace(
        identity=identity, wiki=wiki, drafts=drafts, marker=marker, source=source
    )


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    prior_overrides = dict(app.dependency_overrides)
    service = _service(tmp_path)
    accounts = []
    for name in ("alpha", "beta"):
        identity = service.provision_tester(
            tester_id=name, workspace_id=name, invite_code=f"{name}-invite"
        )
        accounts.append(_prepare_account(identity, f"PRIVATE_{name.upper()}"))

    async def accept(_self, _packet):
        return CourseNetworkReviewJudgement(decision="accept", summary="Offline review")

    monkeypatch.setattr(DocumentReviewer, "review", accept)
    monkeypatch.setattr(OpenAICourseNetworkReviewer, "review", accept)
    _enable_beta(monkeypatch, tmp_path, service)
    try:
        with TestClient(app) as alpha, TestClient(app) as beta:
            for account, client in zip(accounts, (alpha, beta)):
                assert (
                    client.post(
                        "/api/beta/login",
                        json={"invite_code": f"{account.identity.tester_id}-invite"},
                    ).status_code
                    == 200
                )
                account.client = client
            yield accounts
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prior_overrides)


def _get(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response


def _snapshot(row):
    return {
        "expected_revision": row["artifact_revision"],
        "expected_hash": row["artifact_hash"],
    }


def test_identical_course_ids_resolve_to_each_authenticated_material_source_and_map(
    accounts,
):
    alpha, beta = accounts
    # Alternate accounts to exercise warm dependency caches as well as first reads.
    for own, other in ((alpha, beta), (beta, alpha), (alpha, beta)):
        for path in (
            f"{BASE}/materials",
            f"{BASE}/materials/{MATERIAL_ID}/sections/{SECTION_ID}",
            f"{BASE}/network",
            f"{BASE}/network/nodes/{NODE_ID}/lessons",
        ):
            response = _get(own.client, path)
            assert own.marker in response.text
            assert other.marker not in response.text
        assert (
            _get(own.client, f"{BASE}/materials/{MATERIAL_ID}/files/source.pdf").content
            == own.source
        )
    response = alpha.client.patch(
        f"{BASE}/materials/{MATERIAL_ID}/archive", json={"archived": True}
    )
    assert response.status_code == 200, response.text
    assert (
        _get(alpha.client, f"{BASE}/materials").json()["materials"][0]["archived"]
        is True
    )
    assert (
        _get(beta.client, f"{BASE}/materials").json()["materials"][0]["archived"]
        is False
    )
    assert (
        _get(alpha.client, f"{BASE}/materials/{MATERIAL_ID}/files/source.pdf").content
        == alpha.source
    )


def test_identical_draft_ids_keep_status_sources_updates_reviews_and_publication_isolated(
    accounts,
):
    alpha, beta = accounts
    paths = (
        f"{BASE}/material-imports/{IMPORT_ID}",
        f"{BASE}/changes/{CHANGE_ID}",
        f"{BASE}/network/drafts/{SEED_ID}",
    )
    before_beta = {path: _get(beta.client, path).json() for path in paths}
    beta_map = _get(beta.client, f"{BASE}/network").json()
    for own, other in ((alpha, beta), (beta, alpha)):
        for path in (*paths, f"{BASE}/material-imports", f"{BASE}/changes"):
            response = _get(own.client, path)
            assert own.marker in response.text
            assert other.marker not in response.text
        assert (
            _get(own.client, f"{BASE}/material-imports/{IMPORT_ID}/source").content
            == own.source
        )

    imported = _get(alpha.client, paths[0]).json()
    imported["artifact"]["sections"][0]["content"] = (
        f"{alpha.marker} corrected extraction"
    )
    # The foreign account's snapshot cannot authorize an edit even when IDs match.
    rejected = alpha.client.put(
        paths[0],
        json={**_snapshot(before_beta[paths[0]]), "artifact": imported["artifact"]},
    )
    assert rejected.status_code == 409, rejected.text
    changed = alpha.client.put(
        paths[0], json={**_snapshot(imported), "artifact": imported["artifact"]}
    )
    assert changed.status_code == 200, changed.text
    reviewed = alpha.client.post(f"{paths[0]}/review")
    assert reviewed.status_code == 200, reviewed.text
    approved = alpha.client.post(f"{paths[0]}/approve", json=_snapshot(reviewed.json()))
    assert approved.status_code == 200, approved.text
    published = f"{BASE}/materials/same-pending-material/sections/{SECTION_ID}"
    assert alpha.marker in _get(alpha.client, published).text
    assert beta.client.get(published).status_code == 404

    changes = _get(alpha.client, paths[1]).json()
    changes["artifact"]["operations"][0]["changes"]["learning_goal"] = (
        f"{alpha.marker} corrected map goal"
    )
    updated = alpha.client.put(
        paths[1], json={**_snapshot(changes), "changes": changes["artifact"]}
    )
    assert updated.status_code == 200, updated.text
    reviewed = alpha.client.post(f"{paths[1]}/review")
    assert reviewed.status_code == 200, reviewed.text
    committed = alpha.client.post(f"{paths[1]}/commit", json=_snapshot(reviewed.json()))
    assert committed.status_code == 200, committed.text
    assert "corrected map goal" in _get(alpha.client, f"{BASE}/network").text
    assert _get(beta.client, f"{BASE}/network").json() == beta_map
    for path in paths:
        assert _get(beta.client, path).json() == before_beta[path]


def test_other_workspace_only_draft_is_unavailable_for_read_source_and_update(accounts):
    alpha, beta = accounts
    artifact = _artifact(alpha.marker, "alpha-only-material")
    _draft(
        alpha.drafts,
        alpha.identity.workspace_id,
        PRIVATE_ID,
        artifact.model_dump(),
        mode="course_material",
        intent="import",
        target_kind=artifact.material_id,
        runtime={"stage": "document_review", "pages": [1]},
    )
    path = f"{BASE}/material-imports/{PRIVATE_ID}"
    own = _get(alpha.client, path).json()
    assert beta.client.get(path).status_code == 404
    assert beta.client.get(f"{path}/source").status_code == 404
    assert (
        beta.client.put(
            path, json={**_snapshot(own), "artifact": own["artifact"]}
        ).status_code
        == 404
    )
    assert beta.client.post(f"{path}/review").status_code == 404
    assert beta.client.post(f"{path}/approve", json=_snapshot(own)).status_code == 404
    assert _get(alpha.client, path).json() == own


def test_course_reads_require_beta_authentication(accounts):
    with TestClient(app) as anonymous:
        for path in (
            f"{BASE}/materials",
            f"{BASE}/network",
            f"{BASE}/materials/{MATERIAL_ID}/files/source.pdf",
            f"{BASE}/materials/{MATERIAL_ID}/sections/{SECTION_ID}",
            f"{BASE}/material-imports/{IMPORT_ID}",
            f"{BASE}/material-imports/{IMPORT_ID}/source",
            f"{BASE}/changes/{CHANGE_ID}",
            f"{BASE}/network/drafts/{SEED_ID}",
        ):
            assert anonymous.get(path).status_code == 401
