"""Plan-session materials scratch (outside wiki) until promote-on-save."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.config import Settings, get_settings
from app.services.materials_ocr import run_mistral_ocr_on_pdf
from app.services.materials_ocr_prompts import MaterialsOcrContext

MaterialArmName = Literal["textbook", "personal"]


@dataclass
class SessionMaterialEntry:
    material_id: str
    arm: MaterialArmName
    title: str
    summary: str
    page_numbers: list[int] = field(default_factory=list)
    scratch_path: str = ""
    page_count: int = 0
    asset_counts: dict[str, int] = field(default_factory=dict)
    promoted: bool = False
    wiki_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMaterialEntry:
        arm = str(data.get("arm") or "textbook")
        if arm not in {"textbook", "personal"}:
            arm = "textbook"
        pages = data.get("page_numbers") or []
        if not isinstance(pages, list):
            pages = []
        counts = data.get("asset_counts") or {}
        if not isinstance(counts, dict):
            counts = {}
        return cls(
            material_id=str(data.get("material_id") or "").strip(),
            arm=arm,  # type: ignore[arg-type]
            title=str(data.get("title") or "").strip(),
            summary=str(data.get("summary") or "").strip(),
            page_numbers=[int(p) for p in pages if str(p).strip().isdigit() or isinstance(p, int)],
            scratch_path=str(data.get("scratch_path") or ""),
            page_count=int(data.get("page_count") or 0),
            asset_counts={str(k): int(v) for k, v in counts.items()},
            promoted=bool(data.get("promoted")),
            wiki_path=str(data.get("wiki_path") or ""),
        )


def new_material_id() -> str:
    return f"mat_{uuid.uuid4().hex[:12]}"


def scratch_root(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    root = Path(settings.materials_scratch_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def material_scratch_dir(
    session_id: str, material_id: str, *, settings: Settings | None = None
) -> Path:
    return scratch_root(settings) / session_id / material_id


def _title_from_summary_md(summary_md: str) -> str:
    for line in summary_md.splitlines():
        if line.lower().startswith("- chapter/topic:"):
            topic = line.split(":", 1)[1].strip()
            if topic and topic != "(unknown)":
                return topic
    return "Uploaded material"


def _summary_blurb(summary_md: str) -> str:
    match = re.search(
        r"^##\s+Summary\s*$([\s\S]*?)(?=^##\s+|\Z)", summary_md, re.M | re.I
    )
    if match:
        return " ".join(match.group(1).split())[:500]
    return " ".join(summary_md.split())[:500]


def _asset_counts(package_dir: Path) -> dict[str, int]:
    assets = package_dir / "assets"
    if not assets.is_dir():
        return {"images": 0, "tables": 0, "table_crops": 0}
    images = 0
    tables = 0
    crops = 0
    for path in assets.iterdir():
        if path.name == "manifest.json":
            continue
        name = path.name.lower()
        if name.startswith("tbl-") and name.endswith(".html"):
            tables += 1
        elif name.startswith("tbl-") and name.endswith((".jpg", ".jpeg", ".png")):
            crops += 1
        elif path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            images += 1
    return {"images": images, "tables": tables, "table_crops": crops}


def ocr_pdf_to_scratch(
    *,
    pdf_bytes: bytes,
    filename: str,
    session_id: str,
    class_id: str,
    arm: MaterialArmName,
    ocr_context: MaterialsOcrContext | None = None,
    page_range: str | None = None,
    original_page_numbers: list[int] | None = None,
    settings: Settings | None = None,
    material_id: str | None = None,
    ocr_runner=None,
) -> SessionMaterialEntry:
    """Run OCR into session scratch and return an inventory entry."""
    del class_id  # reserved for future class-scoped scratch layout
    settings = settings or get_settings()
    material_id = material_id or new_material_id()
    out_dir = material_scratch_dir(session_id, material_id, settings=settings)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(filename or "upload.pdf").name
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"
    upload_path = out_dir / "upload.pdf"
    upload_path.write_bytes(pdf_bytes)

    runner = ocr_runner or run_mistral_ocr_on_pdf
    package = runner(
        upload_path,
        out_dir=out_dir,
        original_page_numbers=original_page_numbers,
        page_range=page_range,
        settings=settings,
        ocr_context=ocr_context or MaterialsOcrContext(arm=arm),
        arm=arm,
        material_id=material_id,
        session_id=session_id,
        copy_source_pdf=True,
    )

    summary_md = ""
    if package.summary_md_path and package.summary_md_path.is_file():
        summary_md = package.summary_md_path.read_text(encoding="utf-8")
    pages = list(original_page_numbers or [])
    if not pages and package.provenance_path and package.provenance_path.is_file():
        prov = json.loads(package.provenance_path.read_text(encoding="utf-8"))
        pages = [int(p) for p in prov.get("original_page_numbers") or []]

    return SessionMaterialEntry(
        material_id=material_id,
        arm=arm,
        title=_title_from_summary_md(summary_md),
        summary=_summary_blurb(summary_md),
        page_numbers=pages,
        scratch_path=str(out_dir),
        page_count=len(pages) if pages else 0,
        asset_counts=_asset_counts(out_dir),
        promoted=False,
    )


_ASSET_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def resolve_material_asset_file(
    *,
    session_id: str,
    material_id: str,
    filename: str,
    entry: SessionMaterialEntry | None = None,
    wiki_root: Path | None = None,
    class_id: str | None = None,
    settings: Settings | None = None,
) -> Path:
    """Resolve a safe image path under scratch or promoted wiki assets/."""
    name = Path(filename or "").name
    if not name or name != filename.replace("\\", "/").split("/")[-1]:
        raise ValueError("Invalid asset filename")
    if Path(name).suffix.lower() not in _ASSET_SUFFIXES:
        raise ValueError("Unsupported asset type")

    candidates: list[Path] = []
    if entry and entry.scratch_path:
        candidates.append(Path(entry.scratch_path) / "assets" / name)
    else:
        candidates.append(
            material_scratch_dir(session_id, material_id, settings=settings)
            / "assets"
            / name
        )
    if entry and entry.promoted and entry.wiki_path and wiki_root and class_id:
        candidates.append(Path(wiki_root) / entry.wiki_path / "assets" / name)
        candidates.append(
            wiki_material_dir(wiki_root, class_id, entry.arm, material_id) / "assets" / name
        )

    for path in candidates:
        if not path.is_file():
            continue
        # Path traversal guard: must stay under an assets directory.
        try:
            path.resolve().relative_to(path.parent.resolve())
        except ValueError as exc:
            raise ValueError("Invalid asset path") from exc
        if path.parent.name != "assets":
            raise ValueError("Invalid asset path")
        return path
    raise FileNotFoundError(f"Asset not found: {filename}")


def attach_prebuilt_package(
    *,
    session_id: str,
    package_src: Path,
    arm: MaterialArmName = "textbook",
    material_id: str | None = None,
    settings: Settings | None = None,
) -> SessionMaterialEntry:
    """Copy a prebuilt OCR package into session scratch (evals / offline seed)."""
    settings = settings or get_settings()
    src = Path(package_src)
    if not src.is_dir():
        raise FileNotFoundError(f"package missing: {src}")
    material_id = material_id or new_material_id()
    out_dir = material_scratch_dir(session_id, material_id, settings=settings)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(src, out_dir)
    summary_md = ""
    summary_path = out_dir / "summary.md"
    if summary_path.is_file():
        summary_md = summary_path.read_text(encoding="utf-8")
    pages: list[int] = []
    prov_path = out_dir / "provenance.json"
    if prov_path.is_file():
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
            pages = [int(p) for p in prov.get("original_page_numbers") or []]
        except (json.JSONDecodeError, TypeError, ValueError):
            pages = []
    return SessionMaterialEntry(
        material_id=material_id,
        arm=arm,
        title=_title_from_summary_md(summary_md) or src.name,
        summary=_summary_blurb(summary_md),
        page_numbers=pages,
        scratch_path=str(out_dir),
        page_count=len(pages),
        asset_counts=_asset_counts(out_dir),
        promoted=False,
    )


def arm_dir_name(arm: MaterialArmName) -> str:
    return "textbooks" if arm == "textbook" else "personal"


def wiki_material_dir(wiki_root: Path, class_id: str, arm: MaterialArmName, material_id: str) -> Path:
    return (
        Path(wiki_root)
        / "wiki"
        / "classes"
        / class_id
        / "materials"
        / arm_dir_name(arm)
        / material_id
    )


def promote_scratch_material(
    *,
    wiki_root: Path,
    class_id: str,
    entry: SessionMaterialEntry,
) -> SessionMaterialEntry:
    """Copy scratch package into durable class materials tree."""
    src = Path(entry.scratch_path)
    if not src.is_dir():
        raise FileNotFoundError(f"scratch package missing: {src}")
    dest = wiki_material_dir(wiki_root, class_id, entry.arm, entry.material_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    # Prefer canonical source.pdf name after promote.
    upload = dest / "upload.pdf"
    source = dest / "source.pdf"
    if upload.is_file() and not source.is_file():
        upload.rename(source)
    rel = f"wiki/classes/{class_id}/materials/{arm_dir_name(entry.arm)}/{entry.material_id}"
    entry.promoted = True
    entry.wiki_path = rel
    return entry


def write_lesson_materials_json(
    *,
    wiki_root: Path,
    class_id: str,
    lesson_date: str,
    material_ids: list[str],
) -> Path:
    lesson_dir = Path(wiki_root) / "wiki" / "classes" / class_id / "lessons" / lesson_date
    lesson_dir.mkdir(parents=True, exist_ok=True)
    path = lesson_dir / "materials.json"
    existing: list[str] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            existing = list(data.get("material_ids") or [])
        except json.JSONDecodeError:
            existing = []
    merged = list(dict.fromkeys([*existing, *material_ids]))
    path.write_text(
        json.dumps({"material_ids": merged}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_lesson_material_ids(
    wiki_root: Path, class_id: str, lesson_date: str
) -> list[str]:
    path = (
        Path(wiki_root)
        / "wiki"
        / "classes"
        / class_id
        / "lessons"
        / lesson_date
        / "materials.json"
    )
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [str(x) for x in data.get("material_ids") or [] if str(x).strip()]
