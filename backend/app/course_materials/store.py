"""Authorized reads of approved class materials; never infer approval from OCR."""

import hashlib
from pathlib import Path

from app.course_materials.models import CourseMaterialManifest
from app.course_materials.sections import read_section_body
from app.course_network.models import _validate_slug
from app.services.materials_scratch import wiki_material_dir


def list_course_materials(wiki, class_id):
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
            result.append(manifest)
    return result


def get_course_material(wiki, class_id, material_id):
    _validate_slug(material_id)
    manifest = next(
        (
            m
            for m in list_course_materials(wiki, class_id)
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


def read_course_material_section(wiki, class_id, material_id, section_id):
    manifest = get_course_material(wiki, class_id, material_id)
    section = next((s for s in manifest.sections if s.id == section_id), None)
    if section is None:
        raise KeyError("Approved material section not found")
    root = material_root(wiki, manifest)
    content = read_section_body(
        (root / "document.agent.md").read_text(encoding="utf-8"), section_id
    )
    return section.model_dump() | {
        "material_id": material_id,
        "material_title": manifest.title,
        "content": content,
        "manifest_hash": hashlib.sha256(
            (root / "material.json").read_bytes()
            + (root / "document.agent.md").read_bytes()
        ).hexdigest(),
        "source_path": wiki.rel_wiki(root / "document.agent.md"),
    }


def resolve_course_asset(wiki, class_id, material_id, filename):
    manifest = get_course_material(wiki, class_id, material_id)
    root = material_root(wiki, manifest).resolve()
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
