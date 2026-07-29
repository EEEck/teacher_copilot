"""Fetch LehrplanPLUS Fachlehrpläne into the wiki's trusted-source layer.

Three artefacts per route:

1. ``raw/sources/bayern/lehrplanplus/{subject}_{grade}_ntg.html`` — the fetched
   page, kept verbatim so any later extraction can be re-derived and audited.
2. ``…​.extracted.md`` — the full German text, faithful to the document.
3. ``wiki/sources/bayern/lehrplanplus/{subject}_{grade}_ntg.md`` — a *draft*
   curated source page carrying the frontmatter contract that
   ``wiki/trusted_sources.py`` parses.

Step 3 is a draft on purpose. The curated pages that ship are compact English
summaries per Lernbereich, not wholesale copies of the source; the script gets
the structure and provenance right, a human condenses the prose and only then
moves ``review_status`` past ``source_imported``.

Route note: subjects differ. Chemie publishes a separate NTG document
(`…/chemie/ch-ntg`); Physik publishes one common Gymnasium plan per grade whose
final Lernbereich is the "Profilbereich am NTG". Routes are therefore listed
explicitly rather than derived from a pattern.

Usage:
    python scripts/ingest_lehrplanplus.py --list
    python scripts/ingest_lehrplanplus.py --subject physik
    python scripts/ingest_lehrplanplus.py --wiki-root backend/teacher_wiki
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import httpx
import lxml.html as LH


BASE = "https://www.lehrplanplus.bayern.de/fachlehrplan/gymnasium"
USER_AGENT = "KlassenPilot-curriculum-ingest/0.1 (teacher copilot; contact via repo)"
SECTION_BUDGET = 1400


@dataclass(frozen=True)
class Route:
    subject: str
    grade: int
    url: str
    title: str

    @property
    def slug(self) -> str:
        return f"{self.subject}_{self.grade}_ntg"

    @property
    def source_id(self) -> str:
        return f"by-lehrplanplus-{self.subject}-{self.grade}-ntg"


# Physik 12/13 redirect to the site root: the Oberstufe uses a different
# structure and is out of scope until someone confirms its shape.
ROUTES: tuple[Route, ...] = (
    *(
        Route("physik", g, f"{BASE}/{g}/physik", f"LehrplanPLUS Physik {g} NTG")
        for g in (8, 9, 10, 11)
    ),
    Route("chemie", 10, f"{BASE}/10/chemie/ch-ntg", "LehrplanPLUS Chemie 10 NTG"),
)


def fetch(url: str) -> str:
    response = httpx.get(
        url, follow_redirects=True, timeout=60, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    if response.url.path in ("/", ""):
        raise RuntimeError(f"{url} redirected to the site root — no such Fachlehrplan.")
    return response.text


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def _section_id(subject: str, grade: int, heading: str) -> str:
    """"Ph9 Lernbereich 1: Energie …" -> "ph9_lb1"."""
    m = re.search(r"Lernbereich\s+(\d+)", heading)
    prefix = ("ph" if subject == "physik" else "c") + str(grade)
    return f"{prefix}_lb{m.group(1)}" if m else f"{prefix}_{_slug(heading)}"


def _section_title(heading: str) -> str:
    """Drop the "Ph9 Lernbereich 1:" prefix and the "(ca. 26 Std.)" suffix."""
    title = re.sub(r"^\s*\w+\d*\s+Lernbereich\s+\d+\s*:\s*", "", heading)
    return re.sub(r"\s*\(ca\.\s*\d+\s*Std\.\)\s*$", "", title).strip()


_CHROME = re.compile(
    r"^\+?\s*(Servicematerialien|Materialien|Aufgaben|Illustrierende Aufgaben"
    r"|Verweise?|Merkliste|Drucken|Seite empfehlen|Zum Seitenanfang)\b",
    re.I,
)


def _is_chrome(text: str) -> bool:
    """Site navigation that sits inside the content region, not curriculum."""
    return bool(_CHROME.match(text)) or len(text) < 3


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:40] or "section"


def parse(html: str, route: Route) -> tuple[str, list[tuple[str, str, str]]]:
    """Return (document title, [(section_id, title, body)]) in document order."""
    doc = LH.fromstring(html)
    for junk in doc.xpath("//script|//style|//nav|//header|//footer"):
        junk.getparent().remove(junk)
    content = (doc.xpath("//*[@id='content']") or doc.xpath("//main") or [doc])[0]

    doc_title = _clean((content.xpath(".//h2/text()") or [route.title])[0])
    sections: list[tuple[str, str, str]] = []
    current: tuple[str, str] | None = None
    body: list[str] = []

    for el in content.iter():
        if el.tag == "h3":
            if current:
                sections.append((*current, "\n".join(body).strip()))
            heading = _clean(el.text_content())
            current = (_section_id(route.subject, route.grade, heading), _section_title(heading))
            body = []
        elif current is not None and el.tag in ("h4", "p", "li"):
            text = _clean(el.text_content())
            if not text or _is_chrome(text):
                continue
            body.append(f"**{text}**" if el.tag == "h4" else f"- {text}" if el.tag == "li" else text)

    if current:
        sections.append((*current, "\n".join(body).strip()))
    return doc_title, sections


def curated_page(route: Route, doc_title: str, sections, retrieved_at: str) -> str:
    """The draft curated page — correct frontmatter, prose still to be condensed."""
    profile = next(
        (title for _, title, _ in sections if "Profilbereich" in title or "NTG" in title),
        "",
    )
    lines = [
        "---",
        f"source_id: {route.source_id}",
        f"title: {route.title}",
        "authority: official_curriculum",
        "jurisdiction: BY",
        f"subject: {route.subject}",
        "school_type: Gymnasium",
        "branch: NTG",
        f"grade: {route.grade}",
        f"canonical_url: {route.url}",
        f"retrieved_at: {retrieved_at}",
        "version_label: current_snapshot",
        "source_format: html",
        "ingestion_method: crawl",
        "review_status: source_imported",
        f"artifact_path: raw/sources/bayern/lehrplanplus/{route.slug}.html",
        f"extracted_markdown_path: raw/sources/bayern/lehrplanplus/{route.slug}.extracted.md",
        "source_language: de",
        "---",
        f"# {route.title}",
        "",
        "## Summary",
        f"{doc_title}. Lernbereiche: "
        + "; ".join(title for _, title, _ in sections)
        + ".",
    ]
    if profile:
        lines.append(
            f"The NTG profile content for this grade is the Lernbereich "
            f"“{profile}”; the remaining Lernbereiche are common to all "
            "Gymnasium branches."
        )
    for section_id, title, body in sections:
        excerpt = body[:SECTION_BUDGET].rsplit("\n", 1)[0] if len(body) > SECTION_BUDGET else body
        lines += ["", f"## Section: {section_id} — {title}", excerpt]
    return "\n".join(lines).rstrip() + "\n"


def ingest(route: Route, wiki_root: Path, retrieved_at: str) -> None:
    html = fetch(route.url)
    doc_title, sections = parse(html, route)
    if not sections:
        raise RuntimeError(f"{route.url}: no Lernbereich sections found.")

    raw_dir = wiki_root / "raw" / "sources" / "bayern" / "lehrplanplus"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{route.slug}.html").write_text(html, encoding="utf-8")
    (raw_dir / f"{route.slug}.extracted.md").write_text(
        f"# {doc_title}\n\n> Source: {route.url}\n> Retrieved: {retrieved_at}\n\n"
        + "\n\n".join(f"## {title}\n\n{body}" for _, title, body in sections)
        + "\n",
        encoding="utf-8",
    )

    wiki_dir = wiki_root / "wiki" / "sources" / "bayern" / "lehrplanplus"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / f"{route.slug}.md").write_text(
        curated_page(route, doc_title, sections, retrieved_at), encoding="utf-8"
    )
    print(f"  {route.source_id}: {len(sections)} sections — {doc_title[:60]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", default="backend/teacher_wiki", type=Path)
    parser.add_argument("--subject", help="only this subject")
    parser.add_argument("--grade", type=int, help="only this grade")
    parser.add_argument("--list", action="store_true", help="show routes and exit")
    args = parser.parse_args()

    routes = [
        r
        for r in ROUTES
        if (not args.subject or r.subject == args.subject)
        and (not args.grade or r.grade == args.grade)
    ]
    if args.list:
        for route in routes:
            print(f"{route.source_id:<36} {route.url}")
        return 0

    retrieved_at = dt.date.today().isoformat()
    failures = 0
    for route in routes:
        print(f"{route.source_id} <- {route.url}")
        try:
            ingest(route, args.wiki_root, retrieved_at)
        except Exception as exc:  # keep going; report at the end
            failures += 1
            print(f"  FAILED: {exc}", file=sys.stderr)
    print(f"\n{len(routes) - failures}/{len(routes)} routes ingested.")
    print("Curated pages are drafts: condense each section, then advance review_status.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
