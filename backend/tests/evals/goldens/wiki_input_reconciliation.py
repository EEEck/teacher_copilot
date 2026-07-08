"""Wiki-vs-input reconciliation goldens (TARGET behavior — see
docs/mem_v3/input_reconciliation.md).

Principle: the committed wiki is the baseline; teacher input that conflicts with
it (especially a student ID not in the roster) is a *proposed* change, not an
overwrite. The agent should trust the wiki first and **clarify** the
discrepancy, only accepting the deviation on explicit teacher confirmation
("new student joined", "yes this changed"). Detection is deterministic (roster
membership is a fact); the clarifying question is the model's job; the write
waits for HITL.

Status: the deterministic detector + clarify wiring are a tracked follow-up, so
the live judge eval currently xfails the clarify cases (documented target, not a
red regression) — mirroring the capture emission-gap pattern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_STUDENT_ID_RE = re.compile(r"S-\d{3}", re.IGNORECASE)


def student_ids_in(text: str) -> list[str]:
    """Deterministically extract distinct S-### ids from free text (order kept)."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _STUDENT_ID_RE.findall(text or ""):
        sid = match.upper()
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def non_roster_ids(text: str, roster: set[str]) -> list[str]:
    """The whole detection step, deterministic: ids referenced but not enrolled."""
    return [sid for sid in student_ids_in(text) if sid not in roster]


@dataclass(frozen=True)
class WikiReconciliationGolden:
    golden_id: str
    teacher_message: str
    # Student ids in the message that are NOT in the class roster (deterministic
    # vs the seed roster; the stub eval verifies this against the real wiki).
    non_roster_ids: tuple[str, ...]
    # Must the agent clarify a wiki-vs-input discrepancy before writing?
    expect_clarify: bool
    # Any-of phrases a good clarifying reply surfaces (live judge, target).
    expected_reply_signals: tuple[str, ...] = ()
    # Phrases that would signal the WRONG behavior (silent accept / spurious
    # flag / fabrication). Hard-checked where the feature can't regress it.
    forbidden_reply_signals: tuple[str, ...] = ()
    workflow: str = "ingest"
    prior_message: str = ""
    rationale: str = ""


CHEMIE_9B_CLASS_ID = "chemie_9b_2026_27"

WIKI_RECONCILIATION_GOLDENS: tuple[WikiReconciliationGolden, ...] = (
    WikiReconciliationGolden(
        golden_id="non_roster_observation_is_flagged",
        teacher_message=(
            "Log today's alkanes lesson. S-099 did a great job explaining why "
            "oil and water don't mix."
        ),
        non_roster_ids=("S-099",),
        expect_clarify=True,
        expected_reply_signals=("S-099", "roster"),
        forbidden_reply_signals=(),
        rationale=(
            "S-099 is not on the roster. Trust the wiki: flag it as a likely "
            "typo (or a new student) and ask, do not silently record a "
            "non-existent student."
        ),
    ),
    WikiReconciliationGolden(
        golden_id="valid_observation_is_accepted",
        teacher_message=(
            "Log today's alkanes lesson. S-014 helped a peer explain oil and "
            "water separation."
        ),
        non_roster_ids=(),
        expect_clarify=False,
        expected_reply_signals=(),
        # A valid, enrolled id must not be spuriously questioned.
        forbidden_reply_signals=("not in the roster", "isn't in the roster", "likely typo"),
        rationale="S-014 is enrolled; no clarification needed.",
    ),
    WikiReconciliationGolden(
        golden_id="explicit_new_student_is_accepted",
        teacher_message=(
            "A new student joined this week — please add S-099 to the class. "
            "Today S-099 followed the demo really well."
        ),
        non_roster_ids=("S-099",),
        # Explicit teacher intent authorizes the deviation: accept, do not
        # treat it as a typo. The wiki-first default yields to a clear change.
        expect_clarify=False,
        expected_reply_signals=("S-099",),
        forbidden_reply_signals=("typo",),
        rationale=(
            "The teacher explicitly says a new student joined and asks to add "
            "them — the confirmed-change path. Accept it; don't second-guess."
        ),
    ),
)
