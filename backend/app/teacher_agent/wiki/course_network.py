"""Durable storage for one adopted course network per class."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

from app.course_network.models import CourseNetworkDocument, canonical_network_json

_TRANSACTION_ARTIFACT_RE = re.compile(
    r"^\.(?:network\.json|overview\.md)\.([0-9a-f]{32})\.(?:new|backup)\.tmp$"
)
_WRITE_LOCKS: dict[str, threading.RLock] = {}
_WRITE_LOCKS_GUARD = threading.Lock()


def course_network_dir(store, class_id: str) -> Path:
    """Return the canonical course-network directory for an existing class."""
    store.get_class(class_id)
    return store.class_dir(class_id) / "course_network"


def _network_path(store, class_id: str) -> Path:
    return course_network_dir(store, class_id) / "network.json"


def _overview_path(store, class_id: str) -> Path:
    return course_network_dir(store, class_id) / "overview.md"


def _reference_text(references) -> str:
    return ", ".join(
        f"`{reference.source_id}#{reference.section_id}`"
        for reference in sorted(
            references, key=lambda item: (item.source_id, item.section_id)
        )
    )


def _material_reference_text(references) -> str:
    rendered = []
    for reference in sorted(
        references,
        key=lambda item: (
            item.material_id,
            item.section_id,
            item.page_start or 0,
            item.page_end or 0,
        ),
    ):
        pages = ""
        if reference.page_start is not None:
            pages = f", pp. {reference.page_start}"
            if (
                reference.page_end is not None
                and reference.page_end != reference.page_start
            ):
                pages += f"–{reference.page_end}"
        rendered.append(f"`{reference.material_id}#{reference.section_id}`{pages}")
    return ", ".join(rendered)


def render_course_network_overview(document: CourseNetworkDocument) -> str:
    """Render the inspectable Markdown view of canonical network data."""
    document = document.validate_for_canonical_write()
    route = document.route
    lines = [
        "# Course Network",
        "",
        f"> Revision: {document.revision}",
        f"> Route: {route.subject.title()} {route.grade} {route.branch}",
        f"> Updated: {document.updated_at.isoformat()}",
        "",
        "## Lernbausteine",
        "",
    ]
    if document.nodes:
        for node in sorted(document.nodes, key=lambda item: item.id):
            lines.extend(
                [
                    f"### {node.title} (`{node.id}`)",
                    f"- Status: {node.status}; origin: {node.origin}",
                ]
            )
            if node.description:
                lines.append(f"- Description: {node.description}")
            if node.learning_goal:
                lines.append(f"- Learning goal: {node.learning_goal}")
            if node.curriculum_refs:
                lines.append(f"- Curriculum: {_reference_text(node.curriculum_refs)}")
            if node.material_refs:
                lines.append(
                    f"- Materials: {_material_reference_text(node.material_refs)}"
                )
            lines.append("")
    else:
        lines.extend(["_No adopted Lernbausteine._", ""])

    lines.extend(["## Relationships", ""])
    if document.edges:
        for edge in sorted(document.edges, key=lambda item: item.id):
            line = (
                f"- `{edge.source_id}` — {edge.relation} → `{edge.target_id}` "
                f"(origin: {edge.origin})"
            )
            if edge.curriculum_refs:
                line += f"; curriculum: {_reference_text(edge.curriculum_refs)}"
            if edge.material_refs:
                line += f"; materials: {_material_reference_text(edge.material_refs)}"
            lines.append(line)
    else:
        lines.append("_No relationships._")
    lines.append("")

    lines.extend(["## Material mappings", ""])
    if document.material_mappings:
        for mapping in sorted(document.material_mappings, key=lambda item: item.id):
            confidence = (
                f"; confidence: {mapping.confidence:g}"
                if mapping.confidence is not None
                else ""
            )
            lines.append(
                f"- `{mapping.material_id}#{mapping.section_id}` — "
                f"{mapping.relation} → `{mapping.node_id}` "
                f"(origin: {mapping.origin}{confidence})"
            )
            if mapping.teacher_note:
                lines.append(f"  - Teacher note: {mapping.teacher_note}")
    else:
        lines.append("_No material mappings._")
    return "\n".join(lines).rstrip() + "\n"


def _replace_file(source: Path, destination: Path) -> None:
    source.replace(destination)


def _temporary_path(destination: Path, transaction_id: str, label: str) -> Path:
    return destination.with_name(f".{destination.name}.{transaction_id}.{label}.tmp")


@contextmanager
def _course_network_write_lock(store, class_id: str):
    key = f"{store.root.resolve()}::{class_id}"
    with _WRITE_LOCKS_GUARD:
        process_lock = _WRITE_LOCKS.setdefault(key, threading.RLock())
    lock_path = store.root / "workflow" / f".course-network-write-{class_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with process_lock, lock_path.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        _lock_file(lock_file)
        try:
            yield
        finally:
            _unlock_file(lock_file)


def _lock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        return
    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _unlock_file(lock_file) -> None:
    lock_file.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _cleanup_stale_transaction_artifacts(
    directory: Path, *, current_transaction_id: str
) -> None:
    for path in directory.iterdir():
        match = _TRANSACTION_ARTIFACT_RE.fullmatch(path.name)
        if (
            path.is_file()
            and match is not None
            and match.group(1) != current_transaction_id
        ):
            path.unlink()


def _write_temporary(
    store, destination: Path, content: str, transaction_id: str
) -> Path:
    temporary = _temporary_path(destination, transaction_id, "new")
    try:
        store.write_text(temporary, content)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _backup_existing(store, destination: Path, transaction_id: str) -> Path | None:
    if not destination.exists():
        return None
    backup = _temporary_path(destination, transaction_id, "backup")
    try:
        store.write_text(backup, destination.read_text(encoding="utf-8"))
    except Exception:
        backup.unlink(missing_ok=True)
        raise
    return backup


def _restore_file(destination: Path, backup: Path | None) -> None:
    if backup is not None and backup.exists():
        _replace_file(backup, destination)
    elif destination.exists():
        destination.unlink()


def load_course_network(store, class_id: str) -> CourseNetworkDocument | None:
    """Load a class's adopted network, or ``None`` if it has not been adopted."""
    path = _network_path(store, class_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        document = CourseNetworkDocument.model_validate(payload)
        if document.class_id != class_id:
            raise ValueError(
                "Stored course network does not match requested class "
                f"{class_id}: {document.class_id}"
            )
        return document
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ValueError(
            f"Invalid stored course network for class {class_id}: {exc}"
        ) from exc


def write_course_network(
    store, class_id: str, document: CourseNetworkDocument
) -> CourseNetworkDocument:
    """Atomically publish canonical JSON and its compiled Markdown overview."""
    directory = course_network_dir(store, class_id)
    if document.class_id != class_id:
        raise ValueError("Course network document class_id must match the target class")
    canonical_document = document.validate_for_canonical_write()
    network_json = canonical_network_json(canonical_document) + "\n"
    overview = render_course_network_overview(canonical_document)

    directory.mkdir(parents=True, exist_ok=True)
    network_path = directory / "network.json"
    overview_path = directory / "overview.md"
    transaction_id = uuid.uuid4().hex
    network_temporary: Path | None = None
    overview_temporary: Path | None = None
    network_backup: Path | None = None
    overview_backup: Path | None = None
    published_network = False
    published_overview = False
    with _course_network_write_lock(store, class_id):
        _cleanup_stale_transaction_artifacts(
            directory, current_transaction_id=transaction_id
        )
        try:
            network_temporary = _write_temporary(
                store, network_path, network_json, transaction_id
            )
            overview_temporary = _write_temporary(
                store, overview_path, overview, transaction_id
            )
            network_backup = _backup_existing(store, network_path, transaction_id)
            overview_backup = _backup_existing(store, overview_path, transaction_id)
            _replace_file(network_temporary, network_path)
            published_network = True
            _replace_file(overview_temporary, overview_path)
            published_overview = True
        except Exception:
            try:
                if published_network:
                    _restore_file(network_path, network_backup)
                if published_overview:
                    _restore_file(overview_path, overview_backup)
            finally:
                for temporary in (
                    network_temporary,
                    overview_temporary,
                    network_backup,
                    overview_backup,
                ):
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
            raise
        else:
            for temporary in (network_backup, overview_backup):
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    return canonical_document


def list_course_network_pages(store, class_id: str) -> list[dict[str, str]]:
    """Return only the compiled overview for normal wiki discovery."""
    overview = _overview_path(store, class_id)
    if not overview.exists():
        return []
    return [
        {
            "kind": "course_network",
            "id": "overview",
            "path": store.rel_wiki(overview),
        }
    ]
