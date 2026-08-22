from __future__ import annotations

import asyncio
import json
import threading

import pytest

from app.course_network.models import CourseNetworkDocument, NetworkEdge
from app.course_network.review import CourseNetworkReviewJudgement
from app.course_network.seeds import load_seed_for_class, load_seed_for_route
from app.course_network.validation import validate_course_network_draft
from app.services.class_provisioning import ClassSpec, create_class
from app.services.course_network_service import (
    CourseNetworkConflict,
    CourseNetworkService,
)
from app.services.workflow_drafts import (
    WorkflowDraftConflict,
    WorkflowDraftStore,
    serialize_structured_artifact,
)
from app.teacher_agent.wiki import indexing
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


class WaitingReviewer(StubReviewer):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def review(
        self, document: CourseNetworkDocument
    ) -> CourseNetworkReviewJudgement:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return CourseNetworkReviewJudgement(
            decision="accept", summary="Reviewed after waiting.", findings=[]
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

    errors = validate_course_network_draft(wiki, invalid, expected_class_id=CLASS_ID)

    assert {error.code for error in errors} >= {
        "builds_on_cycle",
        "route_mismatch",
        "unknown_curriculum_reference",
    }


@pytest.mark.anyio
async def test_review_blocks_class_mismatch_and_prior_route_provenance(wiki):
    reviewer = StubReviewer()
    service = _service(wiki, reviewer)
    draft = service.open_seed_draft(CLASS_ID)
    grade_8 = load_seed_for_route(wiki, "chemie", 8, "NTG")
    payload = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    payload["class_id"] = "another-class"
    payload["nodes"][0]["curriculum_refs"] = [
        grade_8.nodes[0].curriculum_refs[0].model_dump(mode="json")
    ]
    service.workflow_drafts.save_from_session(
        draft_id=draft.draft_id,
        status="draft",
        artifact_markdown=serialize_structured_artifact(payload),
        runtime_json={},
        messages_json=[],
        backend_session_id=draft.backend_session_id,
    )

    result = await service.review_seed(CLASS_ID, draft.draft_id)

    assert result.decision == "block"
    assert reviewer.calls == 0
    assert {finding.code for finding in result.findings} >= {
        "class_mismatch",
        "unauthorized_curriculum_reference",
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


@pytest.mark.anyio
async def test_stale_reviewer_completion_cannot_restore_invalidated_snapshot(wiki):
    reviewer = WaitingReviewer()
    service = _service(wiki, reviewer)
    draft = service.open_seed_draft(CLASS_ID)
    reviewing = asyncio.create_task(service.review_seed(CLASS_ID, draft.draft_id))
    await reviewer.started.wait()
    changed = service.workflow_drafts.save_from_session(
        draft_id=draft.draft_id,
        status="draft",
        artifact_markdown=draft.artifact_markdown.replace(
            "Chemische", "Chemische (spät)"
        ),
        runtime_json={},
        messages_json=[],
        backend_session_id=draft.backend_session_id,
    )
    reviewer.release.set()

    with pytest.raises(
        WorkflowDraftConflict, match="draft_changed_since_review_created"
    ):
        await reviewing

    assert changed.active_review_json == {}
    assert service.get_draft(CLASS_ID, draft.draft_id).active_review_json == {}


@pytest.mark.anyio
async def test_older_concurrent_review_cannot_replace_newer_review_snapshot(wiki):
    reviewer = WaitingReviewer()
    service = _service(wiki, reviewer)
    draft = service.open_seed_draft(CLASS_ID)
    first = asyncio.create_task(service.review_seed(CLASS_ID, draft.draft_id))
    await reviewer.started.wait()
    second = asyncio.create_task(service.review_seed(CLASS_ID, draft.draft_id))
    for _ in range(100):
        if reviewer.calls == 2:
            break
        await asyncio.sleep(0)
    assert reviewer.calls == 2
    reviewer.release.set()

    results = await asyncio.gather(first, second, return_exceptions=True)

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert any(
        isinstance(result, WorkflowDraftConflict)
        and "draft_changed_since_review_created" in str(result)
        for result in results
    )
    stored = service.get_draft(CLASS_ID, draft.draft_id)
    assert stored.active_review_revision == draft.artifact_revision
    assert stored.active_review_hash == draft.artifact_hash


@pytest.mark.anyio
async def test_unchanged_stale_save_cannot_decrease_review_generation(
    wiki, monkeypatch
):
    reviewer = WaitingReviewer()
    service = _service(wiki, reviewer)
    draft = service.open_seed_draft(CLASS_ID)
    first = asyncio.create_task(service.review_seed(CLASS_ID, draft.draft_id))
    await reviewer.started.wait()

    save_read = threading.Event()
    release_save = threading.Event()
    save_outcome = []
    original_get = service.workflow_drafts.get

    def pause_stale_save(draft_id):
        row = original_get(draft_id)
        if threading.current_thread().name == "stale-save" and not save_read.is_set():
            save_read.set()
            assert release_save.wait(timeout=5)
        return row

    monkeypatch.setattr(service.workflow_drafts, "get", pause_stale_save)

    def save_unchanged() -> None:
        try:
            service.workflow_drafts.save_from_session(
                draft_id=draft.draft_id,
                status="draft",
                artifact_markdown=draft.artifact_markdown,
                runtime_json={},
                messages_json=[],
                backend_session_id=draft.backend_session_id,
            )
        except WorkflowDraftConflict as exc:
            save_outcome.append(exc)

    save_thread = threading.Thread(target=save_unchanged, name="stale-save")
    save_thread.start()
    assert save_read.wait(timeout=5)
    second = asyncio.create_task(service.review_seed(CLASS_ID, draft.draft_id))
    for _ in range(100):
        if reviewer.calls == 2:
            break
        await asyncio.sleep(0)
    assert reviewer.calls == 2
    release_save.set()
    save_thread.join(timeout=5)
    reviewer.release.set()

    results = await asyncio.gather(first, second, return_exceptions=True)

    assert len(save_outcome) == 1
    assert "draft_changed_since_save_started" in str(save_outcome[0])
    assert sum(not isinstance(result, Exception) for result in results) == 1
    stored = service.get_draft(CLASS_ID, draft.draft_id)
    assert stored.review_generation == 2
    assert stored.active_review_revision == draft.artifact_revision


@pytest.mark.anyio
async def test_save_read_before_adoption_reservation_cannot_cancel_adoption(
    wiki, monkeypatch
):
    service = _service(wiki, StubReviewer())
    draft = service.open_seed_draft(CLASS_ID)
    review = await service.review_seed(CLASS_ID, draft.draft_id)
    save_read = threading.Event()
    release_save = threading.Event()
    adoption_reserved = threading.Event()
    release_adoption = threading.Event()
    save_outcome = []
    original_get = service.workflow_drafts.get
    original_write = wiki.write_course_network

    def pause_stale_save(draft_id):
        row = original_get(draft_id)
        if threading.current_thread().name == "stale-save" and not save_read.is_set():
            save_read.set()
            assert release_save.wait(timeout=5)
        return row

    def pause_adoption_write(*args, **kwargs):
        adoption_reserved.set()
        assert release_adoption.wait(timeout=5)
        return original_write(*args, **kwargs)

    monkeypatch.setattr(service.workflow_drafts, "get", pause_stale_save)
    monkeypatch.setattr(wiki, "write_course_network", pause_adoption_write)

    def save_changed() -> None:
        try:
            service.workflow_drafts.save_from_session(
                draft_id=draft.draft_id,
                status="draft",
                artifact_markdown=draft.artifact_markdown.replace("Chemische", "Late"),
                runtime_json={},
                messages_json=[],
                backend_session_id=draft.backend_session_id,
            )
        except WorkflowDraftConflict as exc:
            save_outcome.append(exc)

    save_thread = threading.Thread(target=save_changed, name="stale-save")
    adoption_outcome = []
    save_thread.start()
    assert save_read.wait(timeout=5)

    def adopt() -> None:
        adoption_outcome.append(
            service.adopt_seed(
                CLASS_ID,
                draft.draft_id,
                review.artifact_revision,
                review.artifact_hash,
            )
        )

    adoption_thread = threading.Thread(target=adopt)
    adoption_thread.start()
    assert adoption_reserved.wait(timeout=5)
    release_save.set()
    save_thread.join(timeout=5)
    release_adoption.set()
    adoption_thread.join(timeout=5)

    assert len(save_outcome) == 1
    assert "draft_adoption_in_progress" in str(save_outcome[0])
    assert len(adoption_outcome) == 1
    assert service.get_draft(CLASS_ID, draft.draft_id).status == "committed"


def test_review_snapshot_rejects_contradictory_accept_report(wiki):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    service = CourseNetworkService(
        wiki=wiki, workflow_drafts=store, reviewer=StubReviewer()
    )
    draft = service.open_seed_draft(CLASS_ID)
    contradictory = {
        "decision": "accept",
        "summary": "Contradictory.",
        "findings": [{"code": "unsafe", "message": "Unsafe", "severity": "block"}],
        "artifact_revision": draft.artifact_revision,
        "artifact_hash": draft.artifact_hash,
    }

    with pytest.raises(ValueError, match="accept"):
        store.mark_review_snapshot(
            draft.draft_id,
            revision=draft.artifact_revision,
            artifact_hash_value=draft.artifact_hash,
            review_json=contradictory,
        )


def test_concurrent_review_reservations_claim_distinct_generations(wiki):
    service = _service(wiki, StubReviewer())
    draft = service.open_seed_draft(CLASS_ID)
    barrier = threading.Barrier(2)
    claimed = []

    def reserve() -> None:
        barrier.wait(timeout=5)
        claimed.append(
            service.workflow_drafts.begin_course_network_review(
                draft.draft_id,
                expected_revision=draft.artifact_revision,
                expected_hash=draft.artifact_hash,
            ).review_generation
        )

    first = threading.Thread(target=reserve)
    second = threading.Thread(target=reserve)
    first.start()
    second.start()
    first.join(timeout=5)
    second.join(timeout=5)

    assert sorted(claimed) == [1, 2]


@pytest.mark.anyio
async def test_failed_log_append_before_return_preserves_existing_log_entries(
    wiki, monkeypatch
):
    service = _service(wiki, StubReviewer())
    draft = service.open_seed_draft(CLASS_ID)
    review = await service.review_seed(CLASS_ID, draft.draft_id)
    wiki._append_log(
        "other-class", "2026-01-01", "Other completed work", ["wiki/other.md"], "ingest"
    )
    log_before = wiki.read_text(wiki.log_path)

    def partial_then_fail(class_id, lesson_date, title, applied, kind, entry_id=None):
        wiki.log_path.write_text(
            wiki.read_text(wiki.log_path)
            + "\n## [2026-01-01T00:00:00] course_network_adopt | 2026-01-01"
            + f" â€” {title} (id:{entry_id})\n> Class: {class_id}\n",
            encoding="utf-8",
        )
        raise OSError("injected partial log append failure")

    monkeypatch.setattr(wiki, "_append_log", partial_then_fail)

    with pytest.raises(OSError, match="partial log append failure"):
        service.adopt_seed(
            CLASS_ID, draft.draft_id, review.artifact_revision, review.artifact_hash
        )

    assert wiki.read_text(wiki.log_path) == log_before
    assert service.get_network(CLASS_ID) is None
    assert service.get_draft(CLASS_ID, draft.draft_id).status == "draft"


def test_atomic_log_removal_is_bound_to_class_kind_and_full_operation_id(wiki):
    shared_id = "a" * 32
    wiki.write_text(
        wiki.log_path,
        "# Wiki Log\n\n"
        f"## [2026-01-01T00:00:00] course_network_adopt | x (id:{shared_id})\n"
        "> Class: first-class\n\n"
        f"## [2026-01-01T00:00:01] course_network_adopt | x (id:{shared_id})\n"
        "> Class: second-class\n",
    )

    indexing.remove_log_entry(
        wiki,
        entry_id=shared_id,
        class_id="first-class",
        kind="course_network_adopt",
    )

    log = wiki.read_text(wiki.log_path)
    assert "> Class: first-class" not in log
    assert "> Class: second-class" in log


@pytest.mark.anyio
async def test_log_compensation_failure_leaves_a_durable_recovery_marker(
    wiki, monkeypatch
):
    service = _service(wiki, StubReviewer())
    draft = service.open_seed_draft(CLASS_ID)
    review = await service.review_seed(CLASS_ID, draft.draft_id)
    original_atomic_write = indexing._write_text_atomically
    log_writes = 0

    def fail_completion(*args, **kwargs):
        raise WorkflowDraftConflict("injected completion failure")

    def fail_log_removal(store, path, content):
        nonlocal log_writes
        if path == wiki.log_path:
            log_writes += 1
            if log_writes == 2:
                raise OSError("injected log compensation failure")
        return original_atomic_write(store, path, content)

    monkeypatch.setattr(
        service.workflow_drafts, "complete_course_network_adoption", fail_completion
    )
    monkeypatch.setattr(indexing, "_write_text_atomically", fail_log_removal)

    with pytest.raises(
        WorkflowDraftConflict, match="course_network_adoption_recovery_required"
    ):
        service.adopt_seed(
            CLASS_ID, draft.draft_id, review.artifact_revision, review.artifact_hash
        )

    stored = service.get_draft(CLASS_ID, draft.draft_id)
    assert stored.status == "adopting"
    marker = stored.pending_turn_json["course_network_adoption_recovery"]
    assert marker["expected_revision"] == review.artifact_revision
    assert marker["expected_hash"] == review.artifact_hash
    assert marker["operation_id"]
    assert service.get_network(CLASS_ID) is None


@pytest.mark.anyio
@pytest.mark.parametrize("terminal", ["discarded", "committed"])
async def test_terminal_course_network_drafts_cannot_reenter_review_or_adoption(
    wiki, terminal
):
    service = _service(wiki, StubReviewer())
    draft = service.open_seed_draft(CLASS_ID)
    if terminal == "committed":
        service.workflow_drafts.mark_committed(draft.draft_id)
    else:
        service.workflow_drafts.discard(draft.draft_id)

    with pytest.raises(WorkflowDraftConflict, match="course_network_draft_not_active"):
        await service.review_seed(CLASS_ID, draft.draft_id)
    with pytest.raises(WorkflowDraftConflict, match="course_network_draft_not_active"):
        service.adopt_seed(CLASS_ID, draft.draft_id, 0, draft.artifact_hash)


@pytest.mark.anyio
async def test_adoption_rejects_tampered_review_snapshot_and_releases_reservation(wiki):
    service = _service(wiki, StubReviewer())
    draft = service.open_seed_draft(CLASS_ID)
    review = await service.review_seed(CLASS_ID, draft.draft_id)
    tampered = {
        **review.model_dump(mode="json"),
        "artifact_hash": "not-the-reviewed-artifact",
    }
    with service.workflow_drafts._connect() as conn:
        conn.execute(
            "UPDATE workflow_draft SET active_review_json = ? WHERE draft_id = ?",
            (json.dumps(tampered), draft.draft_id),
        )

    with pytest.raises(
        WorkflowDraftConflict, match="course_network_review_snapshot_invalid"
    ):
        service.adopt_seed(
            CLASS_ID, draft.draft_id, review.artifact_revision, review.artifact_hash
        )

    assert service.get_network(CLASS_ID) is None
    assert service.get_draft(CLASS_ID, draft.draft_id).status == "draft"


@pytest.mark.anyio
async def test_adoption_rolls_back_network_log_index_and_reservation_on_failure(
    wiki, monkeypatch
):
    service = _service(wiki, StubReviewer())
    draft = service.open_seed_draft(CLASS_ID)
    review = await service.review_seed(CLASS_ID, draft.draft_id)
    log_before = wiki.read_text(wiki.log_path)
    index_before = wiki.read_text(wiki.index_path)

    def fail_rebuild_index(*args, **kwargs):
        raise OSError("injected index failure")

    monkeypatch.setattr(wiki, "rebuild_index", fail_rebuild_index)

    with pytest.raises(OSError, match="injected index failure"):
        service.adopt_seed(
            CLASS_ID, draft.draft_id, review.artifact_revision, review.artifact_hash
        )

    assert wiki.load_course_network(CLASS_ID) is None
    assert wiki.read_text(wiki.log_path) == log_before
    assert wiki.read_text(wiki.index_path) == index_before
    assert service.get_draft(CLASS_ID, draft.draft_id).status == "draft"


@pytest.mark.anyio
async def test_completion_failure_restores_prior_index_without_second_rebuild(
    wiki, monkeypatch
):
    service = _service(wiki, StubReviewer())
    draft = service.open_seed_draft(CLASS_ID)
    review = await service.review_seed(CLASS_ID, draft.draft_id)
    index_before = wiki.read_text(wiki.index_path)
    original_rebuild = wiki.rebuild_index
    rebuild_calls = 0

    def fail_completion(*args, **kwargs):
        raise WorkflowDraftConflict("injected completion failure")

    def fail_if_rebuilt_twice(*args, **kwargs):
        nonlocal rebuild_calls
        rebuild_calls += 1
        if rebuild_calls > 1:
            raise OSError("compensating rebuild must not run")
        return original_rebuild(*args, **kwargs)

    monkeypatch.setattr(
        service.workflow_drafts, "complete_course_network_adoption", fail_completion
    )
    monkeypatch.setattr(wiki, "rebuild_index", fail_if_rebuilt_twice)

    with pytest.raises(WorkflowDraftConflict, match="injected completion failure"):
        service.adopt_seed(
            CLASS_ID, draft.draft_id, review.artifact_revision, review.artifact_hash
        )

    assert rebuild_calls == 1
    assert wiki.read_text(wiki.index_path) == index_before
    assert service.get_network(CLASS_ID) is None
    assert service.get_draft(CLASS_ID, draft.draft_id).status == "draft"


@pytest.mark.anyio
async def test_failed_adoption_preserves_other_class_global_log_and_index(
    wiki, monkeypatch
):
    other_class_id = create_class(
        wiki,
        ClassSpec(
            label="Chemie 8a â€” 2026/27",
            subject="chemie",
            grade=8,
            section="a",
            school_year="2026_27",
        ),
    ).id
    first = _service(wiki, StubReviewer())
    second = _service(wiki, StubReviewer())
    first_draft = first.open_seed_draft(CLASS_ID)
    second_draft = second.open_seed_draft(other_class_id)
    first_review = await first.review_seed(CLASS_ID, first_draft.draft_id)
    second_review = await second.review_seed(other_class_id, second_draft.draft_id)
    first_rebuild_started = threading.Event()
    second_started = threading.Event()
    outcomes = []
    original_rebuild = wiki.rebuild_index
    calls = 0

    def fail_first_rebuild(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            first_rebuild_started.set()
            assert second_started.wait(timeout=5)
            raise OSError("first adoption index failure")
        return original_rebuild(*args, **kwargs)

    monkeypatch.setattr(wiki, "rebuild_index", fail_first_rebuild)

    def adopt_first() -> None:
        with pytest.raises(OSError, match="first adoption index failure"):
            first.adopt_seed(
                CLASS_ID,
                first_draft.draft_id,
                first_review.artifact_revision,
                first_review.artifact_hash,
            )
        outcomes.append("first_failed")

    def adopt_second() -> None:
        second_started.set()
        adoption = second.adopt_seed(
            other_class_id,
            second_draft.draft_id,
            second_review.artifact_revision,
            second_review.artifact_hash,
        )
        outcomes.append(adoption)

    first_thread = threading.Thread(target=adopt_first)
    second_thread = threading.Thread(target=adopt_second)
    first_thread.start()
    assert first_rebuild_started.wait(timeout=5)
    second_thread.start()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert "first_failed" in outcomes
    assert len([outcome for outcome in outcomes if outcome != "first_failed"]) == 1
    assert first.get_network(CLASS_ID) is None
    assert second.get_network(other_class_id) is not None
    log_text = wiki.read_text(wiki.log_path)
    assert f"> Class: {other_class_id}" in log_text
    assert log_text.count("Course network adoption") == 1
    assert f"wiki/classes/{other_class_id}/course_network/network.json" in log_text
    assert f"## Class: {other_class_id}" in wiki.read_text(wiki.index_path)


@pytest.mark.anyio
async def test_concurrent_adoption_has_one_winner_and_rejects_mutation(
    wiki, monkeypatch
):
    service = _service(wiki, StubReviewer())
    draft = service.open_seed_draft(CLASS_ID)
    review = await service.review_seed(CLASS_ID, draft.draft_id)
    entered_write = threading.Event()
    release_write = threading.Event()
    original_write = wiki.write_course_network

    def pause_write(*args, **kwargs):
        entered_write.set()
        assert release_write.wait(timeout=5)
        return original_write(*args, **kwargs)

    monkeypatch.setattr(wiki, "write_course_network", pause_write)
    outcomes = []

    def adopt() -> None:
        try:
            outcomes.append(
                service.adopt_seed(
                    CLASS_ID,
                    draft.draft_id,
                    review.artifact_revision,
                    review.artifact_hash,
                )
            )
        except (CourseNetworkConflict, WorkflowDraftConflict) as exc:
            outcomes.append(exc)

    first = threading.Thread(target=adopt)
    second = threading.Thread(target=adopt)
    first.start()
    assert entered_write.wait(timeout=5)
    with pytest.raises(WorkflowDraftConflict, match="draft_adoption_in_progress"):
        service.workflow_drafts.save_from_session(
            draft_id=draft.draft_id,
            status="draft",
            artifact_markdown=draft.artifact_markdown.replace("Chemische", "Late"),
            runtime_json={},
            messages_json=[],
            backend_session_id=draft.backend_session_id,
        )
    second.start()
    release_write.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert (
        len([outcome for outcome in outcomes if not isinstance(outcome, Exception)])
        == 1
    )
    assert any(isinstance(outcome, CourseNetworkConflict) for outcome in outcomes)
