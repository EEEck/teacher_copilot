"""Stable sections referencing one canonical reviewed Markdown body."""

import re
import uuid

from app.course_materials.models import SectionDraft


def extract_sections(text: str, pages: list[int]) -> list[SectionDraft]:
    boundaries = list(re.finditer(r"(?m)^## PDF page (\d+)\s*$", text))
    sections = []
    if boundaries:
        for index, match in enumerate(boundaries):
            end = (
                boundaries[index + 1].start()
                if index + 1 < len(boundaries)
                else len(text)
            )
            body = text[match.end() : end].strip().removesuffix("---").strip()
            if not body:
                continue
            heading = re.search(r"(?m)^#{1,6}\s+(.+)", body)
            page = int(match.group(1))
            sections.append(
                SectionDraft(
                    id=f"sec-{uuid.uuid4().hex[:12]}",
                    title=heading.group(1) if heading else f"Page {page}",
                    page_start=page,
                    page_end=page,
                    content=body,
                )
            )
    elif text.strip():
        sections.append(
            SectionDraft(
                id=f"sec-{uuid.uuid4().hex[:12]}",
                title="Document",
                page_start=min(pages or [1]),
                page_end=max(pages or [1]),
                content=text.strip(),
            )
        )
    return sections


def render_sections(sections: list[SectionDraft]) -> str:
    return (
        "\n\n".join(
            f"<!-- course-section:{s.id} -->\n## {s.title}\n\n{s.content.strip()}\n<!-- /course-section -->"
            for s in sections
            if s.included
        )
        + "\n"
    )


def read_section_body(text: str, section_id: str) -> str:
    match = re.search(
        r"<!-- course-section:"
        + re.escape(section_id)
        + r" -->\n## [^\n]+\n\n(.*?)\n<!-- /course-section -->",
        text,
        re.S,
    )
    if match is None:
        raise KeyError("Material section content is unavailable")
    return match.group(1).strip()
