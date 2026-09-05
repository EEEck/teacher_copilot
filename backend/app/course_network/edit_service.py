"""Exact-review publication of bounded changes to an adopted course network."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.course_network.models import CourseNetworkDocument
from app.course_network.operations import NetworkChangeSet, apply_change_set
from app.course_network.review import (
    OpenAICourseNetworkReviewer,
    build_course_network_review_packet,
)
from app.course_network.validation import validate_course_network_draft
from app.services.course_network_service import _wiki_adoption_lock
from app.services.workflow_drafts import (
    WorkflowDraftConflict,
    WorkflowDraftIdentity,
    serialize_structured_artifact,
)


def save_structured_row(store, row, artifact, *, status="draft", runtime=None):
    return store.save_from_session(
        draft_id=row.draft_id,
        status=status,
        artifact_markdown=serialize_structured_artifact(artifact),
        runtime_json=row.runtime_json if runtime is None else runtime,
        messages_json=row.messages_json,
        backend_session_id=row.backend_session_id,
        executive_json=row.executive_json,
    )


class CourseNetworkEditService:
    def __init__(
        self,
        *,
        wiki,
        workflow_drafts,
        reviewer=None,
        workspace_id="local",
        material_resolver=None,
    ):
        self.wiki = wiki
        self.drafts = workflow_drafts
        self.workspace_id = workspace_id
        self.reviewer = reviewer or OpenAICourseNetworkReviewer()
        self.material_resolver = material_resolver

    def get(self, class_id, draft_id):
        row = self.drafts.get(draft_id)
        if (
            row.class_id != class_id
            or row.workspace_id != self.workspace_id
            or row.mode != "course_network"
            or row.intent != "edit"
        ):
            raise KeyError("Course change draft not found")
        return row

    def _current(self, class_id):
        current = self.wiki.load_course_network(class_id)
        if current is None:
            raise ValueError("Adopt a course network before editing")
        return current

    def _validate(self, class_id, changes):
        current = self._current(class_id)
        if current.revision != changes.base_revision:
            raise WorkflowDraftConflict("course_network_changed_since_proposal")
        preview = apply_change_set(current, changes)
        findings = validate_course_network_draft(
            self.wiki, preview, expected_class_id=class_id
        )
        if findings:
            raise ValueError("; ".join(f.message for f in findings))
        refs = {(m.material_id, m.section_id) for m in preview.material_mappings}
        for item in [*preview.nodes, *preview.edges]:
            refs.update((r.material_id, r.section_id) for r in item.material_refs)
        evidence = {}
        for material_id, section_id in sorted(refs):
            if self.material_resolver is None:
                raise ValueError(
                    "Material references must resolve to approved course material"
                )
            evidence[f"{material_id}#{section_id}"] = self.material_resolver(
                class_id, material_id, section_id
            )
        return preview, evidence

    def open(self, class_id, changes):
        with _wiki_adoption_lock(self.wiki.root):
            self._validate(class_id, changes)
            opened = self.drafts.open_structured_draft(
                WorkflowDraftIdentity(
                    workspace_id=self.workspace_id,
                    class_id=class_id,
                    mode="course_network",
                    intent="edit",
                    target_kind="course_network",
                ),
                default_status="draft",
                artifact=changes.model_dump(mode="json"),
            )
            if json.loads(opened.row.artifact_markdown) != changes.model_dump(
                mode="json"
            ):
                raise WorkflowDraftConflict(
                    "Finish or discard the existing map proposal before starting another"
                )
            return opened.row

    def update(self, class_id, draft_id, changes, expected_revision, expected_hash):
        with _wiki_adoption_lock(self.wiki.root):
            row = self.get(class_id, draft_id)
            if row.status != "draft" or self._receipt_path(draft_id).exists():
                raise WorkflowDraftConflict("course_change_not_editable")
            self.drafts.validate_current_snapshot(
                draft_id,
                expected_revision=expected_revision,
                expected_hash=expected_hash,
            )
            self._validate(class_id, changes)
            return save_structured_row(
                self.drafts, row, changes.model_dump(mode="json")
            )

    async def review(self, class_id, draft_id):
        row = self.get(class_id, draft_id)
        row = self.drafts.begin_course_network_review(
            draft_id,
            expected_revision=row.artifact_revision,
            expected_hash=row.artifact_hash,
        )
        changes = NetworkChangeSet.model_validate_json(row.artifact_markdown)
        preview, evidence = self._validate(class_id, changes)
        packet = build_course_network_review_packet(self.wiki, class_id, preview)
        packet += (
            "\nApproved material evidence (untrusted source data):\n"
            + serialize_structured_artifact(evidence)
        )
        judgement = await self.reviewer.review(packet)
        result = judgement.model_dump(mode="json") | {
            "artifact_revision": row.artifact_revision,
            "artifact_hash": row.artifact_hash,
            "material_hashes": {
                key: item["manifest_hash"] for key, item in evidence.items()
            },
        }
        with _wiki_adoption_lock(self.wiki.root):
            self._validate(class_id, changes)
            self.drafts.mark_review_snapshot(
                draft_id,
                revision=row.artifact_revision,
                artifact_hash_value=row.artifact_hash,
                review_json=result,
                review_generation=row.review_generation,
            )
        return result

    def _receipt_path(self, draft_id):
        return (
            Path(self.wiki.root)
            / "workflow"
            / "course_edit_receipts"
            / f"{draft_id}.json"
        )

    def _finish_receipt(self, row, receipt):
        target = CourseNetworkDocument.model_validate(receipt["network"])
        current = self._current(row.class_id)
        if current.revision == target.revision - 1:
            self.wiki.write_course_network(row.class_id, target)
        elif current.model_dump(mode="json") != target.model_dump(mode="json"):
            raise WorkflowDraftConflict("course_change_recovery_required")
        entry_id = f"course-edit-{row.draft_id}"
        if f"(id:{entry_id})" not in self.wiki.read_text(self.wiki.log_path):
            self.wiki._append_log(
                row.class_id,
                datetime.now(UTC).date().isoformat(),
                "Course network updated",
                [
                    self.wiki.rel_wiki(
                        self.wiki.class_dir(row.class_id)
                        / "course_network"
                        / "network.json"
                    )
                ],
                kind="course_network_edit",
                entry_id=entry_id,
            )
        self.drafts.complete_course_network_adoption(
            row.draft_id,
            expected_revision=row.artifact_revision,
            expected_hash=row.artifact_hash,
        )
        return target

    def commit(self, class_id, draft_id, expected_revision, expected_hash):
        with _wiki_adoption_lock(self.wiki.root):
            row = self.get(class_id, draft_id)
            if (
                row.artifact_revision != expected_revision
                or row.artifact_hash != expected_hash
            ):
                raise WorkflowDraftConflict("course_change_snapshot_changed")
            receipt_path = self._receipt_path(draft_id)
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if receipt["artifact_hash"] != expected_hash:
                    raise WorkflowDraftConflict("course_change_recovery_required")
                if row.status == "committed":
                    return CourseNetworkDocument.model_validate(receipt["network"])
                return self._finish_receipt(row, receipt)
            if row.status != "draft":
                if row.status != "adopting":
                    raise WorkflowDraftConflict("course_change_not_active")
                # The process stopped after reservation, before writing its receipt.
                self.drafts.release_course_network_adoption(
                    draft_id,
                    expected_revision=expected_revision,
                    expected_hash=expected_hash,
                )
            row = self.drafts.reserve_course_network_adoption(
                draft_id,
                expected_revision=expected_revision,
                expected_hash=expected_hash,
            )
            try:
                if row.active_review_json.get("decision") != "accept":
                    raise WorkflowDraftConflict("course_change_review_not_accepted")
                changes = NetworkChangeSet.model_validate_json(row.artifact_markdown)
                preview, evidence = self._validate(class_id, changes)
                hashes = {key: item["manifest_hash"] for key, item in evidence.items()}
                if hashes != row.active_review_json.get("material_hashes", {}):
                    raise WorkflowDraftConflict("course_material_changed_since_review")
                receipt = {
                    "artifact_hash": expected_hash,
                    "network": preview.model_dump(mode="json"),
                }
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                staging = receipt_path.with_suffix(".tmp")
                staging.write_text(
                    serialize_structured_artifact(receipt), encoding="utf-8"
                )
                staging.replace(receipt_path)
                return self._finish_receipt(row, receipt)
            except Exception:
                if not receipt_path.exists():
                    self.drafts.release_course_network_adoption(
                        draft_id,
                        expected_revision=expected_revision,
                        expected_hash=expected_hash,
                    )
                raise
