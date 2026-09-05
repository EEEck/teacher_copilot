"""Authorized reads of approved class materials; never infer approval from OCR."""

import hashlib
import json
import uuid
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.course_materials.models import CourseMaterialManifest
from app.course_materials.sections import read_section_body
from app.course_network.models import _validate_slug
from app.services.materials_scratch import _title_from_summary_md, wiki_material_dir


def list_course_materials(wiki, class_id, *, include_archived=False):
    wiki.get_class(class_id)
    result = []
    for path in sorted(
        (wiki.class_dir(class_id) / "materials").glob("*/*/material.json")
    ):
        try:
            manifest = CourseMaterialManifest.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (ValueError, OSError):
            continue
        if (
            manifest.approved_at
            and manifest.class_id == class_id
            and manifest.material_id == path.parent.name
        ):
            if not include_archived and is_course_material_archived(
                wiki, class_id, manifest.material_id
            ):
                continue
            result.append(manifest)
    return result


def get_course_material(wiki, class_id, material_id):
    _validate_slug(material_id)
    manifest = next(
        (
            m
            for m in list_course_materials(wiki, class_id, include_archived=True)
            if m.material_id == material_id
        ),
        None,
    )
    if manifest is None:
        raise KeyError("Approved course material not found")
    return manifest


def material_root(wiki, manifest):
    return wiki_material_dir(
        wiki.root, manifest.class_id, manifest.arm, manifest.material_id
    )


def saved_material_root(wiki, class_id, material_id):
    wiki.get_class(class_id)
    _validate_slug(material_id)
    base = (wiki.class_dir(class_id) / "materials").resolve()
    for arm in ("textbook", "personal"):
        root = wiki_material_dir(wiki.root, class_id, arm, material_id).resolve()
        if root.is_relative_to(base) and (root / "document.agent.md").is_file():
            return root, arm
    raise KeyError("Saved class material not found")


def approved_document_path(root):
    # Normalizing an older lesson package preserves its original OCR/citations.
    reviewed = root / "document.course.md"
    return reviewed if reviewed.is_file() else root / "document.agent.md"


def is_course_material_archived(wiki, class_id, material_id):
    root, _ = saved_material_root(wiki, class_id, material_id)
    path = root / "course-lifecycle.json"
    if not path.exists():
        return False
    # Invalid lifecycle state must not silently re-enable automatic retrieval.
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("archived") is not False
    except (ValueError, OSError):
        return True


def set_course_material_archived(wiki, class_id, material_id, archived):
    from app.services.course_network_service import _wiki_adoption_lock

    with _wiki_adoption_lock(wiki.root):
        root, _ = saved_material_root(wiki, class_id, material_id)
        temporary = root / f".lifecycle-{uuid.uuid4().hex}.json"
        temporary.write_text(json.dumps({"archived": bool(archived)}), encoding="utf-8")
        temporary.replace(root / "course-lifecycle.json")
    return {"material_id": material_id, "archived": bool(archived)}


def list_material_library(wiki, class_id):
    wiki.get_class(class_id)
    approved = {
        m.material_id: m
        for m in list_course_materials(wiki, class_id, include_archived=True)
    }
    result = []
    for path in sorted(
        (wiki.class_dir(class_id) / "materials").glob("*/*/document.agent.md")
    ):
        material_id = path.parent.name
        try:
            root, arm = saved_material_root(wiki, class_id, material_id)
            archived = is_course_material_archived(wiki, class_id, material_id)
            if material_id in approved:
                item = approved[material_id].model_dump(mode="json") | {
                    "library_status": "approved"
                }
            elif not (root / "material.json").exists():
                title = material_id
                summary = root / "summary.md"
                if summary.is_file():
                    title = _title_from_summary_md(summary.read_text(encoding="utf-8"))
                item = {
                    "class_id": class_id,
                    "material_id": material_id,
                    "arm": arm,
                    "title": title,
                    "sections": [],
                    "library_status": "saved",
                }
            else:
                continue
            result.append(item | {"archived": archived})
        except (KeyError, ValueError, OSError):
            continue
    return result


def read_course_material_section(wiki, class_id, material_id, section_id):
    manifest = get_course_material(wiki, class_id, material_id)
    section = next((s for s in manifest.sections if s.id == section_id), None)
    if section is None:
        raise KeyError("Approved material section not found")
    root = material_root(wiki, manifest)
    content = read_section_body(
        approved_document_path(root).read_text(encoding="utf-8"), section_id
    )
    try:
        page_map = source_page_map(root / "source.pdf")
    except (ValueError, OSError):
        page_map = {}
    return section.model_dump() | {
        "source_page_start": page_map.get(section.page_start),
        "source_page_end": page_map.get(section.page_end),
        "material_id": material_id,
        "material_title": manifest.title,
        "content": content,
        "manifest_hash": hashlib.sha256(
            (root / "material.json").read_bytes()
            + approved_document_path(root).read_bytes()
        ).hexdigest(),
        "source_path": wiki.rel_wiki(approved_document_path(root)),
    }


def source_page_map(source, *, original_pages=None, full_document=False):
    """Map citation page numbers to the actual PDF, including old OCR subsets."""
    try:
        reader = PdfReader(source)
        count = len(reader.pages)
    except PdfReadError as exc:
        raise ValueError("The source PDF cannot be read") from exc
    if full_document or source.name == "upload.pdf":
        return {page: page for page in range(1, count + 1)}
    layout_path = source.parent / "source-layout.json"
    if layout_path.is_file():
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        if layout.get("kind") == "full_original":
            return {page: page for page in range(1, count + 1)}
        if layout.get("kind") != "selected_pages":
            raise ValueError("Unknown source PDF layout")
        original_pages = layout.get("original_page_numbers", [])
        if len(original_pages) != count:
            raise ValueError("Selected-page source layout does not match the PDF")
    elif (source.parent / "material.json").is_file() and not (
        source.parent / "document.course.md"
    ).is_file():
        # Pre-layout standalone approvals restored the full original PDF too.
        # Normalized legacy subsets retain a distinct document.course.md marker.
        return {page: page for page in range(1, count + 1)}
    if original_pages is None:
        provenance = source.parent / "provenance.json"
        original_pages = (
            json.loads(provenance.read_text(encoding="utf-8")).get(
                "original_page_numbers", []
            )
            if provenance.is_file()
            else []
        )
    pages = [int(page) for page in original_pages]
    if not pages or len(pages) != len(set(pages)) or any(page < 1 for page in pages):
        return {}
    # Legacy OCR packages predate explicit source layout metadata. OCR writes
    # selected pages in provenance order; larger legacy files retain full offsets.
    if count == len(pages):
        return {original: physical for physical, original in enumerate(pages, 1)}
    if count > len(pages) and max(pages) <= count:
        return {page: page for page in pages}
    return {}


def resolve_course_asset(wiki, class_id, material_id, filename):
    root, _ = saved_material_root(wiki, class_id, material_id)
    if filename == "source.pdf":
        target = root / "source.pdf"
    else:
        if Path(filename).name != filename or "\\" in filename:
            raise KeyError("Material asset not found")
        target = root / "assets" / filename
    resolved = target.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise KeyError("Material asset not found")
    return resolved
