"""Teacher-approved adoption boundary for class course-network seeds."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.course_network.models import CourseNetworkDocument
from app.course_network.review import (
    CourseNetworkReviewer,
    CourseNetworkReviewFinding,
    CourseNetworkReviewResult,
    OpenAICourseNetworkReviewer,
)
from app.course_network.seeds import load_seed_for_class
from app.course_network.validation import validate_course_network_draft
from app.services.workflow_drafts import (
    WorkflowDraftConflict,
    WorkflowDraftIdentity,
    WorkflowDraftRow,
    WorkflowDraftStore,
)


class CourseNetworkConflict(ValueError):
    """Raised for a duplicate adoption boundary or mismatched draft."""


@dataclass(frozen=True)
class CourseNetworkAdoption:
    network: CourseNetworkDocument
    draft: WorkflowDraftRow
    log_entry_id: str


@dataclass(frozen=True)
class _FileSnapshot:
    path: Path
    existed: bool
    content: str


_ADOPTION_LOCKS: dict[str, threading.RLock] = {}
_ADOPTION_LOCKS_GUARD = threading.Lock()


def _adoption_lock(wiki_root: Path, class_id: str) -> threading.RLock:
    key = f"{wiki_root.resolve()}::{class_id}"
    with _ADOPTION_LOCKS_GUARD:
        return _ADOPTION_LOCKS.setdefault(key, threading.RLock())


class CourseNetworkService:
    def __init__(
        self,
        *,
        wiki,
        workflow_drafts: WorkflowDraftStore,
        reviewer: CourseNetworkReviewer | None = None,
        workspace_id: str = "local",
    ) -> None:
        self.wiki = wiki
        self.workflow_drafts = workflow_drafts
        self.reviewer = reviewer or OpenAICourseNetworkReviewer()
        self.workspace_id = workspace_id

    def get_network(self, class_id: str) -> CourseNetworkDocument | None:
        return self.wiki.load_course_network(class_id)

    def open_seed_draft(self, class_id: str) -> WorkflowDraftRow:
        if self.get_network(class_id) is not None:
            raise CourseNetworkConflict("course_network_already_adopted")
        seed = load_seed_for_class(self.wiki, class_id)
        opened = self.workflow_drafts.open_structured_draft(
            WorkflowDraftIdentity(
                workspace_id=self.workspace_id,
                class_id=class_id,
                mode="course_network",
                intent="seed_adoption",
                target_kind="course_network",
            ),
            default_status="draft",
            artifact=seed.model_dump(mode="json"),
        )
        return opened.row

    def get_draft(self, class_id: str, draft_id: str) -> WorkflowDraftRow:
        row = self.workflow_drafts.get(draft_id)
        if (
            row.class_id != class_id
            or row.mode != "course_network"
            or row.intent != "seed_adoption"
            or row.target_kind != "course_network"
        ):
            raise KeyError("Course-network draft not found")
        return row

    def _active_draft(self, class_id: str, draft_id: str) -> WorkflowDraftRow:
        row = self.get_draft(class_id, draft_id)
        if row.status != "draft":
            raise WorkflowDraftConflict("course_network_draft_not_active")
        return row

    def _document_from_row(self, row: WorkflowDraftRow) -> CourseNetworkDocument:
        try:
            payload = json.loads(row.artifact_markdown)
            return CourseNetworkDocument.for_draft_seed(**payload)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError("invalid_course_network_draft") from exc

    async def review_seed(
        self, class_id: str, draft_id: str
    ) -> CourseNetworkReviewResult:
        row = self._active_draft(class_id, draft_id)
        row = self.workflow_drafts.begin_course_network_review(
            draft_id,
            expected_revision=row.artifact_revision,
            expected_hash=row.artifact_hash,
        )
        document = self._document_from_row(row)
        deterministic_findings = validate_course_network_draft(
            self.wiki, document, expected_class_id=class_id
        )
        if deterministic_findings:
            result = CourseNetworkReviewResult(
                decision="block",
                summary="Deterministic validation found issues that must be corrected before review.",
                findings=[
                    CourseNetworkReviewFinding(
                        code=finding.code,
                        message=finding.message,
                        severity="block",
                        path=finding.path,
                    )
                    for finding in deterministic_findings
                ],
                artifact_revision=row.artifact_revision,
                artifact_hash=row.artifact_hash,
                deterministic=True,
            )
        else:
            judgement = await self.reviewer.review(document)
            result = CourseNetworkReviewResult(
                **judgement.model_dump(),
                artifact_revision=row.artifact_revision,
                artifact_hash=row.artifact_hash,
            )
        self.workflow_drafts.mark_review_snapshot(
            draft_id,
            revision=result.artifact_revision,
            artifact_hash_value=result.artifact_hash,
            review_json=result.model_dump(mode="json"),
            review_generation=row.review_generation,
        )
        return result

    def adopt_seed(
        self, class_id: str, draft_id: str, expected_revision: int, expected_hash: str
    ) -> CourseNetworkAdoption:
        with _adoption_lock(self.wiki.root, class_id):
            if self.get_network(class_id) is not None:
                raise CourseNetworkConflict("course_network_already_adopted")
            self._active_draft(class_id, draft_id)
            row = self.workflow_drafts.reserve_course_network_adoption(
                draft_id,
                expected_revision=expected_revision,
                expected_hash=expected_hash,
            )
            snapshots = self._adoption_snapshots(class_id)
            try:
                review = CourseNetworkReviewResult.model_validate(
                    row.active_review_json
                )
                if (
                    review.artifact_revision != expected_revision
                    or review.artifact_hash != expected_hash
                    or row.active_review_revision != expected_revision
                    or row.active_review_hash != expected_hash
                ):
                    raise WorkflowDraftConflict(
                        "course_network_review_snapshot_invalid"
                    )
                if review.decision != "accept":
                    raise WorkflowDraftConflict("course_network_review_not_accepted")
                document = self._document_from_row(row)
                findings = validate_course_network_draft(
                    self.wiki, document, expected_class_id=class_id
                )
                if findings:
                    raise WorkflowDraftConflict(
                        "course_network_draft_validation_failed"
                    )
                payload = document.model_dump(mode="json")
                payload["revision"] = 1
                payload["updated_at"] = datetime.now(UTC)
                for node in payload["nodes"]:
                    node["status"] = "adopted"
                adopted = CourseNetworkDocument.model_validate(payload)
                network_dir = self.wiki.class_dir(class_id) / "course_network"
                if (network_dir / "network.json").exists():
                    raise CourseNetworkConflict("course_network_already_adopted")
                network = self.wiki.write_course_network(class_id, adopted)
                log_entry_id = self.wiki._append_log(
                    class_id,
                    datetime.now(UTC).date().isoformat(),
                    "Course network adoption",
                    [
                        self.wiki.rel_wiki(network_dir / "network.json"),
                        self.wiki.rel_wiki(network_dir / "overview.md"),
                    ],
                    kind="course_network_adopt",
                )
                self.wiki.rebuild_index()
                draft = self.workflow_drafts.complete_course_network_adoption(
                    draft_id,
                    expected_revision=expected_revision,
                    expected_hash=expected_hash,
                )
            except Exception:
                try:
                    self._restore_snapshots(snapshots)
                finally:
                    self.workflow_drafts.release_course_network_adoption(
                        draft_id,
                        expected_revision=expected_revision,
                        expected_hash=expected_hash,
                    )
                raise
            return CourseNetworkAdoption(
                network=network, draft=draft, log_entry_id=log_entry_id
            )

    def _adoption_snapshots(self, class_id: str) -> list[_FileSnapshot]:
        network_dir = self.wiki.class_dir(class_id) / "course_network"
        paths = [
            network_dir / "network.json",
            network_dir / "overview.md",
            self.wiki.log_path,
            self.wiki.index_path,
        ]
        return [
            _FileSnapshot(
                path=path, existed=path.exists(), content=self.wiki.read_text(path)
            )
            for path in paths
        ]

    def _restore_snapshots(self, snapshots: list[_FileSnapshot]) -> None:
        for snapshot in reversed(snapshots):
            if snapshot.existed:
                self.wiki.write_text(snapshot.path, snapshot.content)
            else:
                snapshot.path.unlink(missing_ok=True)
