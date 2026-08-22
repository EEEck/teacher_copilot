"""Teacher-approved adoption boundary for class course-network seeds."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

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
        ):
            raise KeyError("Course-network draft not found")
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
        row = self.get_draft(class_id, draft_id)
        document = self._document_from_row(row)
        deterministic_findings = validate_course_network_draft(self.wiki, document)
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
        )
        return result

    def adopt_seed(
        self, class_id: str, draft_id: str, expected_revision: int, expected_hash: str
    ) -> CourseNetworkAdoption:
        if self.get_network(class_id) is not None:
            raise CourseNetworkConflict("course_network_already_adopted")
        row = self.get_draft(class_id, draft_id)
        row = self.workflow_drafts.validate_review_snapshot(
            draft_id, expected_revision=expected_revision, expected_hash=expected_hash
        )
        try:
            review = CourseNetworkReviewResult.model_validate(row.active_review_json)
        except ValueError as exc:
            raise WorkflowDraftConflict("course_network_review_missing") from exc
        if review.decision != "accept":
            raise WorkflowDraftConflict("course_network_review_not_accepted")
        document = self._document_from_row(row)
        findings = validate_course_network_draft(self.wiki, document)
        if findings:
            raise WorkflowDraftConflict("course_network_draft_validation_failed")
        payload = document.model_dump(mode="json")
        payload["revision"] = 1
        payload["updated_at"] = datetime.now(UTC)
        for node in payload["nodes"]:
            node["status"] = "adopted"
        adopted = CourseNetworkDocument.model_validate(payload)
        network = self.wiki.write_course_network(class_id, adopted)
        network_dir = self.wiki.class_dir(class_id) / "course_network"
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
        return CourseNetworkAdoption(
            network=network,
            draft=self.workflow_drafts.mark_committed(draft_id),
            log_entry_id=log_entry_id,
        )
