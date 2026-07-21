"""Resolve diary student references against the active class roster.

Teachers usually write names, not S-### IDs. S-### remains the internal key;
the teacher-facing recommended alias is Firstname plus the shortest unique
surname prefix (or Firstname alone when that is unique in the class).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from rapidfuzz import fuzz

from app.teacher_agent.wiki.constants import STUDENT_ID_RE

Decision = Literal["allow", "suggest", "block"]

_ROSTER_ROW_RE = re.compile(
    r"^\|\s*(S-\d{3})\s*\|\s*([^|]+?)\s*\|", re.MULTILINE | re.IGNORECASE
)
_MALFORMED_STUDENT_ID_RE = re.compile(
    r"(?<![A-Za-z0-9-])S[-_ ]?(\d{3})(?!\d)", re.IGNORECASE
)
_BULLET_LABEL_RE = re.compile(r"^-\s*([^:]{1,80}):", re.MULTILINE)
_NAME_SPAN_RE = re.compile(
    r"(?<![A-Za-zÄÖÜäöüß])"
    r"([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-']{1,40})"
    r"(?:\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-']{1,40}))?"
    r"(?![A-Za-zÄÖÜäöüß])"
)
_HEADING_RE = re.compile(r"^#{1,3}\s+.+$", re.MULTILINE)

_FUZZY_MIN_SCORE = 88
_FUZZY_MARGIN = 6

# Optional extra aliases keyed by student_id (never written to wiki by this pack).
_EXTRA_ALIASES: dict[str, tuple[str, ...]] = {}


@dataclass(frozen=True)
class RosterStudent:
    student_id: str
    full_name: str
    first_name: str
    last_name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolveHit:
    raw: str
    decision: Decision
    student_id: str | None = None
    recommended_alias: str | None = None
    reason: str = ""


@dataclass
class ClassRosterIndex:
    students: list[RosterStudent]
    by_id: dict[str, RosterStudent] = field(default_factory=dict)
    exact_keys: dict[str, str] = field(default_factory=dict)
    ambiguous_keys: set[str] = field(default_factory=set)


def normalize_person_key(text: str) -> str:
    """NFKC + German folding for stable roster matching."""
    raw = unicodedata.normalize("NFKC", (text or "").strip())
    raw = (
        raw.replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    raw = unicodedata.normalize("NFKD", raw)
    diaeresis = "\u0308"
    chars: list[str] = []
    index = 0
    while index < len(raw):
        ch = raw[index]
        nxt = raw[index + 1] if index + 1 < len(raw) else ""
        if nxt == diaeresis and ch in "aouAOU":
            chars.append(ch + "e")
            index += 2
            continue
        if unicodedata.combining(ch):
            index += 1
            continue
        chars.append(ch)
        index += 1
    return re.sub(r"\s+", " ", "".join(chars).casefold()).strip()


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def recommended_alias(student: RosterStudent, roster: ClassRosterIndex) -> str:
    """Firstname + minimal unique last-name prefix (or Firstname if unique)."""
    first = student.first_name
    last = student.last_name
    first_key = normalize_person_key(first)
    same_first = [
        other
        for other in roster.students
        if normalize_person_key(other.first_name) == first_key
    ]
    if len(same_first) <= 1 or not last:
        return first

    last_n = normalize_person_key(last)
    for length in range(1, len(last_n) + 1):
        prefix_n = last_n[:length]
        matches = [
            other
            for other in same_first
            if normalize_person_key(other.last_name).startswith(prefix_n)
        ]
        if len(matches) == 1 and matches[0].student_id == student.student_id:
            # Preserve original orthography prefix length from roster last name.
            return f"{first} {last[:length]}"
    return student.full_name


def load_class_roster(
    wiki, class_id: str, *, extra_aliases: dict[str, tuple[str, ...]] | None = None
) -> ClassRosterIndex:
    roster_md = wiki.read_text(wiki.roll_up_paths(class_id)["students"])
    extras = {**(extra_aliases or {}), **_EXTRA_ALIASES}
    students: list[RosterStudent] = []
    for match in _ROSTER_ROW_RE.finditer(roster_md):
        student_id = match.group(1).upper()
        full_name = " ".join(match.group(2).split())
        first, last = _split_name(full_name)
        students.append(
            RosterStudent(
                student_id=student_id,
                full_name=full_name,
                first_name=first,
                last_name=last,
                aliases=tuple(extras.get(student_id, ())),
            )
        )
    index = ClassRosterIndex(
        students=students,
        by_id={student.student_id: student for student in students},
    )
    _build_exact_keys(index)
    return index


def _register_key(index: ClassRosterIndex, key: str, student_id: str) -> None:
    if not key:
        return
    if key in index.ambiguous_keys:
        return
    existing = index.exact_keys.get(key)
    if existing is None:
        index.exact_keys[key] = student_id
    elif existing != student_id:
        index.exact_keys.pop(key, None)
        index.ambiguous_keys.add(key)


def _build_exact_keys(index: ClassRosterIndex) -> None:
    for student in index.students:
        keys = {
            normalize_person_key(student.full_name),
            normalize_person_key(student.first_name),
            normalize_person_key(student.student_id),
        }
        if student.last_name:
            keys.add(normalize_person_key(student.last_name))
        for alias in student.aliases:
            keys.add(normalize_person_key(alias))
        if student.first_name and student.last_name:
            first_n = normalize_person_key(student.first_name)
            last_n = normalize_person_key(student.last_name)
            for length in range(1, len(last_n) + 1):
                keys.add(f"{first_n} {last_n[:length]}")
        if student.first_name:
            keys.add(normalize_person_key(student.first_name[0]))
        for key in keys:
            _register_key(index, key, student.student_id)


def extract_reference_candidates(diary_markdown: str) -> list[tuple[str, str]]:
    """Return (raw, kind) candidates. kind is id|label|prose."""
    text = diary_markdown or ""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(raw: str, kind: str) -> None:
        cleaned = " ".join(raw.split())
        if not cleaned:
            return
        key = f"{kind}:{cleaned.casefold()}"
        if key in seen:
            return
        seen.add(key)
        found.append((cleaned, kind))

    for match in STUDENT_ID_RE.finditer(text):
        add(match.group(1).upper(), "id")
    for match in _MALFORMED_STUDENT_ID_RE.finditer(text):
        # Avoid double-counting canonical IDs already captured.
        if STUDENT_ID_RE.fullmatch(match.group(0)):
            continue
        add(match.group(0), "id")
    for match in _BULLET_LABEL_RE.finditer(text):
        add(match.group(1), "label")

    prose = _HEADING_RE.sub(" ", text)
    for match in _NAME_SPAN_RE.finditer(prose):
        first, last = match.group(1), match.group(2)
        add(f"{first} {last}" if last else first, "prose")

    return found


def _fuzzy_resolve(raw: str, index: ClassRosterIndex) -> ResolveHit | None:
    needle = normalize_person_key(raw)
    if not needle or len(needle) < 3:
        return None
    scored: list[tuple[int, RosterStudent]] = []
    for student in index.students:
        targets = [
            normalize_person_key(student.full_name),
            normalize_person_key(f"{student.first_name} {student.last_name}"),
            *[normalize_person_key(alias) for alias in student.aliases],
        ]
        best = max(
            (fuzz.WRatio(needle, target) for target in targets if target),
            default=0,
        )
        scored.append((best, student))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return None
    best_score, best_student = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0
    if best_score >= _FUZZY_MIN_SCORE and (best_score - second) >= _FUZZY_MARGIN:
        alias = recommended_alias(best_student, index)
        return ResolveHit(
            raw=raw,
            decision="suggest",
            student_id=best_student.student_id,
            recommended_alias=alias,
            reason=(
                f"typo-like match → use '{alias}' "
                f"(internal {best_student.student_id})"
            ),
        )
    if best_score >= _FUZZY_MIN_SCORE:
        return ResolveHit(
            raw=raw,
            decision="block",
            reason="ambiguous name match",
        )
    return None


def resolve_reference(
    raw: str, index: ClassRosterIndex, *, kind: str = "label"
) -> ResolveHit | None:
    """Resolve one candidate. Returns None to ignore non-student prose noise."""
    text = " ".join((raw or "").split())
    if not text:
        return None

    if STUDENT_ID_RE.fullmatch(text):
        student_id = text.upper()
        student = index.by_id.get(student_id)
        if student is None:
            return ResolveHit(
                raw=text,
                decision="block",
                reason=f"unknown roster ID {student_id}",
            )
        return ResolveHit(
            raw=text,
            decision="allow",
            student_id=student_id,
            recommended_alias=recommended_alias(student, index),
            reason="known roster ID",
        )

    malformed = _MALFORMED_STUDENT_ID_RE.fullmatch(text)
    if malformed:
        student_id = f"S-{malformed.group(1)}"
        student = index.by_id.get(student_id)
        if student is None:
            return ResolveHit(
                raw=text,
                decision="block",
                reason=f"malformed unknown ID {text}",
            )
        alias = recommended_alias(student, index)
        return ResolveHit(
            raw=text,
            decision="suggest",
            student_id=student_id,
            recommended_alias=alias,
            reason=f"malformed ID → use '{alias}' (internal {student_id})",
        )

    key = normalize_person_key(text)
    if key in index.ambiguous_keys:
        # Single-letter / shared first name: only decisive for labels.
        if kind == "prose" and len(key) <= 1:
            return None
        return ResolveHit(raw=text, decision="block", reason="ambiguous roster match")

    student_id = index.exact_keys.get(key)
    if student_id:
        student = index.by_id[student_id]
        return ResolveHit(
            raw=text,
            decision="allow",
            student_id=student_id,
            recommended_alias=recommended_alias(student, index),
            reason="unique roster name/alias",
        )

    fuzzy = _fuzzy_resolve(text, index)
    if fuzzy is not None:
        return fuzzy

    # Labels that do not match the roster are intentional identity issues.
    # Free-prose capitalized tokens without roster affinity are ignored.
    if kind in {"label", "id"}:
        return ResolveHit(raw=text, decision="block", reason="not in roster")
    return None


def resolve_diary_student_references(
    wiki, class_id: str, diary_markdown: str
) -> list[ResolveHit]:
    index = load_class_roster(wiki, class_id)
    hits: list[ResolveHit] = []
    seen: set[str] = set()
    for raw, kind in extract_reference_candidates(diary_markdown):
        hit = resolve_reference(raw, index, kind=kind)
        if hit is None:
            continue
        dedupe = f"{hit.decision}:{normalize_person_key(hit.raw)}:{hit.student_id or ''}"
        if dedupe in seen:
            continue
        seen.add(dedupe)
        hits.append(hit)
    return hits
