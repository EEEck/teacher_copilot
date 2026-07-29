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


OBERSTUFE = (
    "https://www.lehrplanplus.bayern.de/schulart/gymnasium/jgs/{grade}/fach/physik"
    "/inhalt/fachlehrplaene?w_schulart=gymnasium&wt_1=schulart&w_fach=physik"
    "&wt_2=fach&w_jgs={grade}&wt_3=jgs&w_auspraegung={auspraegung}"
)


@dataclass(frozen=True)
class Route:
    subject: str
    grade: int
    url: str
    title: str
    branch: str = "NTG"

    @property
    def slug(self) -> str:
        # Oberstufe has no NTG branch — the Ausprägung is carried by the subject.
        suffix = "_ntg" if self.branch == "NTG" else ""
        return f"{self.subject}_{self.grade}{suffix}"

    @property
    def source_id(self) -> str:
        return "by-lehrplanplus-" + self.slug.replace("_", "-")


# The Oberstufe Ausprägungen are separate courses, not branches of one course, so
# each is its own subject: a teacher picks "Physik 12 (erhöhtes Anforderungsniveau)"
# the way they would pick a subject. Biophysik exists only in grade 12.
ROUTES: tuple[Route, ...] = (
    *(
        Route("physik", g, f"{BASE}/{g}/physik", f"LehrplanPLUS Physik {g} NTG")
        for g in (8, 9, 10, 11)
    ),
    # Chemie is NTG-only in 8 and 11, so those grades have no ch-ntg document;
    # 9 and 10 do, and their plain paths redirect to the site root.
    Route("chemie", 8, f"{BASE}/8/chemie", "LehrplanPLUS Chemie 8 NTG"),
    Route("chemie", 9, f"{BASE}/9/chemie/ch-ntg", "LehrplanPLUS Chemie 9 NTG"),
    Route("chemie", 10, f"{BASE}/10/chemie/ch-ntg", "LehrplanPLUS Chemie 10 NTG"),
    Route("chemie", 11, f"{BASE}/11/chemie", "LehrplanPLUS Chemie 11 NTG"),
    *(
        Route(
            subject,
            grade,
            OBERSTUFE.format(grade=grade, auspraegung=auspraegung),
            f"LehrplanPLUS {label} {grade}",
            branch="Oberstufe",
        )
        for subject, auspraegung, label, grades in (
            ("physik_grundlegend", "grundlegend", "Physik grundlegendes Anforderungsniveau", (12, 13)),
            ("physik_grundlegend_bio", "grundlegend-bio", "Physik grundlegendes Anforderungsniveau Biophysik", (12,)),
            ("physik_erhoeht", "erhoeht", "Physik erhöhtes Anforderungsniveau", (12, 13)),
        )
        for grade in grades
    ),
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
    """"Ph9 Lernbereich 1: Energie …" -> "ph9_lb1".

    The document supplies its own prefix ("Ph9", "C10"), which stays right for
    the Oberstufe Ausprägungen where the subject slug no longer matches it.
    """
    prefix_m = re.match(r"\s*([A-Za-zÄÖÜäöü]+\d+)\b", heading)
    prefix = prefix_m.group(1).lower() if prefix_m else f"{subject}{grade}"
    lb = re.search(r"Lernbereich\s+(\d+)", heading)
    return f"{prefix}_lb{lb.group(1)}" if lb else f"{prefix}_{_slug(heading)}"


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
        f"branch: {route.branch}",
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


def ingest(route: Route, wiki_root: Path, retrieved_at: str, force_curated: bool = False) -> None:
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
    curated = wiki_dir / f"{route.slug}.md"
    note = ""
    if _is_hand_curated(curated) and not force_curated:
        # Some curated pages were condensed into English by hand. A crawl draft is
        # strictly worse than reviewed prose, so refuse to overwrite one.
        note = "  [kept hand-curated page; raw artefacts refreshed]"
    else:
        curated.write_text(
            curated_page(route, doc_title, sections, retrieved_at), encoding="utf-8"
        )
    print(f"  {route.source_id}: {len(sections)} sections — {doc_title[:52]}{note}")


def _is_hand_curated(path: Path) -> bool:
    if not path.exists():
        return False
    head = path.read_text(encoding="utf-8")[:1200]
    # Exact match: "crawl_then_manual_summary" contains "crawl", and a substring
    # test here silently overwrites the condensed pages this guard protects.
    return not re.search(r"^ingestion_method:\s*crawl\s*$", head, re.M)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", default="backend/teacher_wiki", type=Path)
    parser.add_argument("--subject", help="only this subject")
    parser.add_argument("--grade", type=int, help="only this grade")
    parser.add_argument("--list", action="store_true", help="show routes and exit")
    parser.add_argument("--force-curated", action="store_true",
                        help="overwrite hand-curated source pages with crawl drafts")
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
            ingest(route, args.wiki_root, retrieved_at, args.force_curated)
        except Exception as exc:  # keep going; report at the end
            failures += 1
            print(f"  FAILED: {exc}", file=sys.stderr)
    print(f"\n{len(routes) - failures}/{len(routes)} routes ingested.")
    print("Curated pages are drafts: condense each section, then advance review_status.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
