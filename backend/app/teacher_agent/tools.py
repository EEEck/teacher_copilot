"""OpenAI Agents SDK tools for wiki read/query (no direct writes)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from agents import function_tool

from app.teacher_agent.executive_verification import (
    ExecutiveFinding,
    ExecutiveRuntime,
    FindingSeverity,
    VerificationCategory,
)
from app.teacher_agent.memory_update_state import MemoryRuntime
from app.teacher_agent.planning_state import PlanRuntime
from app.teacher_agent.wiki.search import ReferenceQuery, ReferenceScope
from app.teacher_agent.wiki_store import WikiStore


@dataclass
class WikiToolContext:
    wiki: WikiStore
    class_id: str
    # When set (planning chat), tool outputs are captured into raw_store under a
    # raw_ref so the model can summarize them into compact evidence briefs and
    # fetch the raw later via get_raw_evidence (progressive exposure).
    planning: Optional[PlanRuntime] = None
    # Update-memory chat uses the same progressive exposure pattern for target
    # discovery and lesson evidence, but keeps state separate from planning.
    memory: Optional[MemoryRuntime] = None
    executive: ExecutiveRuntime = field(default_factory=ExecutiveRuntime)
    # This turn's latest teacher message — the ground truth the remember(...)
    # tool validates quotes against.
    teacher_message: str = ""


def create_remember_tool(ctx: WikiToolContext) -> list:
    """The explicit durable-memory capture tool (mem_v3 PR4).

    Capture used to be a passive output field the model had to remember to fill
    while doing planning/ingest work, so durable teacher instructions were
    routinely dropped (the emission gap). This makes capture an explicit tool
    call the model invokes the moment the teacher gives a standing instruction,
    with quote-provenance validation + retry feedback grounded in the teacher's
    words. The staged candidate flows through the same review path as before.
    """
    from app.teacher_agent.memory_capture import validate_remember_call

    @function_tool
    def remember(
        target: str,
        content: str,
        speech_act: str,
        quote: str,
        routing_reason: str,
    ) -> str:
        """Save a durable instruction the teacher just gave YOU, for their review.

        Call this the moment the teacher tells you how to behave, states a
        standing preference, or asks you to remember/add something — anything
        NOT bounded to the current lesson or document. Do NOT call it for
        one-off requests about this plan/diary, or for things that merely
        happened in class.

        Args:
            target: where it belongs — teacher_profile.md (how to communicate
                with the teacher), copilot_profile.md (how to plan for this
                class), teaching_patterns.md (how this class learns),
                planning_brief.md (current planning priorities), or
                wiki/subjects/<subject>.md (subject-wide guidance).
            content: the durable fact/instruction, in your own concise words.
            speech_act: "conduct_request" if the teacher directed your behavior,
                or "store_request" if they explicitly asked you to remember it.
            quote: the teacher's exact sentence that asked for this, verbatim.
            routing_reason: one compact internal sentence explaining why this
                target was chosen. Do not include hidden reasoning; just the
                routing basis, such as "class learning pattern plus immediate
                next-block priority".

        Routing detail: a memory target is chosen by the fact's durable
        purpose, not by surface wording like "next", "remember", or "for this
        lesson".

        Target routing:
        - teacher_profile.md: global teacher preferences across classes.
        - copilot_profile.md: class-specific instructions for how the copilot
          should plan, respond, or avoid behaving.
        - teaching_patterns.md: class-specific evidence about how this class
          learns and which teaching moves, materials, scaffolds, pacing, or
          activity formats work or fail. Temporal teaching preferences can live
          here when scoped to an upcoming block; keep that scope in content.
        - planning_brief.md: near-term class planning priorities, open loops,
          misconception focus, assessment readiness, and immediate next steps.
        - wiki/subjects/<subject>.md: subject-wide reusable guidance only when
          the teacher frames it as applying across classes in that subject.

        Overlap examples:
        - "Remember for the next electricity block: start with real circuit
          kits before Ohm's law equations." Save both teaching_patterns.md
          ("This class benefits from hands-on circuit kits before formal
          electricity equations.") and planning_brief.md ("Upcoming electricity
          block should start with real circuit-kit work before Ohm's law
          equations.").
        - "For 10c, don't open physics plans with a broad discussion question;
          give me a quick misconception check first because they otherwise drift
          into guesses." Save copilot_profile.md for the planning behavior and
          teaching_patterns.md for the class learning pattern.
        - "In physics generally, students mix up velocity and acceleration..."
          Save wiki/subjects/physik.md, not teaching_patterns.md, unless the
          teacher scopes it to this class.

        Nothing is written to memory now — it goes to the teacher's review.
        """
        runtime = ctx.memory or ctx.planning
        candidate, error = validate_remember_call(
            target=target,
            content=content,
            quote=quote,
            speech_act=speech_act,
            routing_reason=routing_reason,
            teacher_message=ctx.teacher_message,
        )
        if error:
            return f"Not saved. {error}"
        if runtime is None:
            return "Noted, but there is no active session to save it to."
        runtime.memory_candidates.append(candidate)
        return (
            f"Saved for the teacher's review: \"{candidate.candidate_update}\" "
            f"→ {candidate.target}. Do not mention this unless the teacher asks."
        )

    return [remember]


def create_executive_verification_tools(ctx: WikiToolContext) -> list:
    """Shared deterministic lookup and finding-capture tools."""

    @function_tool
    def resolve_wiki_references(
        references: list[ReferenceQuery],
        scope: ReferenceScope = "active_class",
    ) -> str:
        """Resolve class, student, or lesson references against committed wiki indexes.

        Call when a teacher-provided identifier may be unknown, ambiguous, or
        from another class. Start with active_class; use workspace only when a
        cross-class mix-up is plausible. This resolves identifiers only. Use
        search/read tools for concepts, teaching history, and preferences.
        """
        result = ctx.wiki.resolve_wiki_references(
            ctx.class_id, references=references, scope=scope
        )
        return _capture(
            ctx.memory or ctx.planning,
            "reference",
            result.model_dump_json(indent=2),
        )

    @function_tool
    def report_verification_finding(
        finding_id: str,
        category: VerificationCategory,
        severity: FindingSeverity,
        summary: str,
        question: str = "",
        evidence_refs: list[str] | None = None,
    ) -> str:
        """Record a consequential discrepancy found while doing the main task.

        Use blocking only when the unresolved decision changes class scope,
        student attribution, lesson history, an important planning assumption,
        artifact correctness, or a durable write. Use advisory when the work
        remains correct and can continue. Do not call for aligned facts or
        harmless uncertainty.
        """
        finding = ExecutiveFinding(
            finding_id=finding_id,
            category=category,
            severity=severity,
            summary=summary,
            question=question,
            evidence_refs=evidence_refs or [],
        )
        ctx.executive.findings[finding.finding_id] = finding
        return f"Recorded {finding.severity} finding {finding.finding_id}."

    return [resolve_wiki_references, report_verification_finding]


def _capture(
    planning: Optional[PlanRuntime | MemoryRuntime], kind: str, payload: str
) -> str:
    """Stash a raw tool output under a raw_ref and prefix the ref for the model."""
    if planning is None:
        return payload
    raw_ref = planning.add_raw(kind, payload)
    return f"raw_ref: {raw_ref}\n{payload}"


def lookup_raw_evidence(
    planning: Optional[PlanRuntime | MemoryRuntime], raw_ref: str
) -> str:
    """Return the captured raw output for a raw_ref (progressive exposure)."""
    if planning is None:
        return "Error: no evidence store for this session."
    raw = planning.raw_store.get(raw_ref.strip())
    if raw is None:
        available = ", ".join(sorted(planning.raw_store)) or "(none)"
        return f"Error: unknown raw_ref '{raw_ref}'. Available: {available}"
    return raw


def _lesson_paths(
    class_id: str, lesson_date: str, *, status: str, has_plan: bool
) -> list[str]:
    paths = []
    if status == "taught":
        paths.append(f"wiki/classes/{class_id}/lessons/{lesson_date}/lesson_results.md")
    if has_plan:
        paths.append(f"wiki/classes/{class_id}/lessons/{lesson_date}/lesson_plan.md")
    return paths


def _lesson_matches_topic(entry, topic: str) -> bool:
    q = topic.strip().lower()
    if not q:
        return True
    haystack = "\n".join(
        [
            entry.title,
            entry.summary,
            "\n".join(entry.covered),
            "\n".join(entry.highlights),
            "\n".join(entry.issues),
            "\n".join(entry.follow_ups),
        ]
    ).lower()
    return q in haystack


def _lesson_body_matches_topic(wiki: WikiStore, paths: list[str], topic: str) -> bool:
    q = topic.strip().lower()
    if not q:
        return True
    for path in paths:
        try:
            text = wiki.read_text(wiki.resolve_path(path))
        except ValueError:
            continue
        if q in text.lower():
            return True
    return False


def _list_lessons_payload(
    wiki: WikiStore,
    class_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    topic: str = "",
    max_results: int = 12,
) -> dict:
    start = start_date.isoformat() if start_date else None
    end = end_date.isoformat() if end_date else None
    if start and end and start > end:
        return {"lessons": [], "warnings": ["start_date must be on or before end_date"]}

    limit = max(1, min(max_results or 12, 30))
    timeline = wiki.get_timeline(class_id)
    lessons = []
    matched_before_limit = 0
    for entry in sorted(timeline.entries, key=lambda e: e.date):
        if start and entry.date < start:
            continue
        if end and entry.date > end:
            continue
        paths = entry.wiki_paths or _lesson_paths(
            class_id, entry.date, status=entry.status, has_plan=entry.has_plan
        )
        if not _lesson_matches_topic(entry, topic) and not _lesson_body_matches_topic(
            wiki, paths, topic
        ):
            continue
        matched_before_limit += 1
        if len(lessons) >= limit:
            continue
        lessons.append(
            {
                "date": entry.date,
                "title": entry.title,
                "status": entry.status,
                "summary": entry.summary,
                "covered": entry.covered[:5],
                "homework": entry.homework,
                "paths": paths,
            }
        )

    warnings = []
    if not lessons:
        warnings.append("No lessons found for the requested range/topic.")
    elif matched_before_limit > len(lessons):
        warnings.append(
            f"Returned {len(lessons)} of {matched_before_limit} matching lessons; narrow the range if more detail is needed."
        )
    return {
        "range": {"start_date": start, "end_date": end, "topic": topic.strip()},
        "lessons": lessons,
        "warnings": warnings,
    }


def _lesson_detail_payload(wiki: WikiStore, class_id: str, lesson_date: str) -> dict:
    detail = wiki.get_lesson_detail(class_id, lesson_date)
    paths = []
    if detail.primary_markdown:
        paths.append(f"wiki/classes/{class_id}/lessons/{lesson_date}/lesson_results.md")
    if detail.lesson_plan_markdown:
        paths.append(f"wiki/classes/{class_id}/lessons/{lesson_date}/lesson_plan.md")
    return {
        "date": detail.date,
        "title": detail.title,
        "source_paths": paths,
        "diary_markdown": detail.diary_markdown[:6000],
        "lesson_plan_markdown": (detail.lesson_plan_markdown or "")[:2500],
        "rollup_excerpts": [
            {"path": e.wiki_path, "label": e.label, "markdown": e.markdown[:1500]}
            for e in detail.rollup_excerpts
        ],
    }


def create_wiki_tools(ctx: WikiToolContext) -> list:
    wiki = ctx.wiki
    class_id = ctx.class_id

    @function_tool
    def read_wiki_page(path: str) -> str:
        """Read a markdown file under teacher_wiki by relative path (e.g. index.md or wiki/classes/...)."""
        try:
            return wiki.read_wiki_page(path)
        except ValueError as e:
            return f"Error: {e}"

    @function_tool
    def read_wiki_index() -> str:
        """Read the class wiki index. Rarely needed — index is already in the prompt context."""
        return wiki.read_wiki_index(class_id)

    @function_tool
    def list_class_pages(kind: str = "") -> str:
        """List wiki page paths. Use only when you need a path before read_wiki_page; avoid browsing."""
        k = kind.strip().lower() or None
        if k == "timeline":
            k = "rollups"
        pages = wiki.list_class_pages(class_id, kind=k)
        return json.dumps(pages, indent=2)

    @function_tool
    def get_class_snapshot() -> str:
        """Summary of class memory: unit, open loops, misconceptions, recent lessons."""
        snap = wiki.get_snapshot(class_id)
        return snap.model_dump_json(indent=2)

    @function_tool
    def get_lesson_detail(lesson_date: str) -> str:
        """Lesson diary + rollups for YYYY-MM-DD. Use when that date is not in the context pack."""
        try:
            detail = wiki.get_lesson_detail(class_id, lesson_date)
            payload = {
                "date": detail.date,
                "title": detail.title,
                "diary_markdown": detail.diary_markdown[:6000],
                "rollup_excerpts": [
                    {"path": e.wiki_path, "markdown": e.markdown[:1500]}
                    for e in detail.rollup_excerpts
                ],
            }
            return json.dumps(payload, indent=2)
        except KeyError as e:
            return f"Error: {e}"

    @function_tool
    def search_wiki(query: str) -> str:
        """Search class wiki markdown. Use for a specific missing fact, not exploratory browsing."""
        hits = wiki.search_wiki(class_id, query)
        return json.dumps(hits, indent=2)

    @function_tool
    def find_in_memory(query: str) -> str:
        """Rank class wiki paths for a topic; returns source-bearing candidates for read_wiki_page."""
        hits = wiki.find_in_memory(class_id, query)
        return json.dumps(hits, indent=2)

    return [
        read_wiki_page,
        read_wiki_index,
        list_class_pages,
        get_class_snapshot,
        get_lesson_detail,
        search_wiki,
        find_in_memory,
    ]


def create_memory_update_tools(ctx: WikiToolContext) -> list:
    """Class-scoped read tools for the update-memory chat."""
    wiki = ctx.wiki
    class_id = ctx.class_id

    @function_tool
    def list_memory_targets(
        start_date: date | None = None,
        end_date: date | None = None,
        topic: str = "",
        status: str = "",
        max_results: int = 12,
    ) -> str:
        """Find candidate lessons that might be updated.

        Use this when the teacher says "today", "last class", gives a vague
        date, mentions an older missing class, or wants to correct prior notes.
        status may be empty, "planned", or "taught".
        """
        payload = _list_lessons_payload(
            wiki, class_id, start_date, end_date, topic, max_results
        )
        wanted = status.strip().lower()
        if wanted in {"planned", "taught"}:
            payload["lessons"] = [
                lesson
                for lesson in payload.get("lessons", [])
                if lesson.get("status") == wanted
            ]
        return _capture(
            ctx.memory, "list_memory_targets", json.dumps(payload, indent=2)
        )

    @function_tool
    def read_memory_target(lesson_date: date) -> str:
        """Read one candidate lesson target by date.

        Returns existing lesson results when present, the saved lesson plan when
        present, rollup excerpts, and source paths. Use before correcting an
        existing lesson or filling results for a planned lesson.
        """
        try:
            payload = _lesson_detail_payload(wiki, class_id, lesson_date.isoformat())
            return _capture(
                ctx.memory, "read_memory_target", json.dumps(payload, indent=2)
            )
        except KeyError as e:
            return f"Error: {e}"

    @function_tool
    def search_memory(query: str, max_results: int = 8) -> str:
        """Find relevant class wiki pages for a topic, student ID, or misconception."""
        limit = max(1, min(max_results or 8, 20))
        hits = wiki.find_in_memory(class_id, query, max_results=limit)
        return _capture(ctx.memory, "memory_search", json.dumps(hits, indent=2))

    @function_tool
    def read_memory_page(path: str) -> str:
        """Read exact wording from one class wiki page returned by search/list tools."""
        if not wiki.is_class_memory_path(class_id, path):
            return f"Error: path must be under wiki/classes/{class_id}/"
        try:
            return _capture(ctx.memory, "read_memory_page", wiki.read_wiki_page(path))
        except ValueError as e:
            return f"Error: {e}"

    @function_tool
    def get_raw_evidence(raw_ref: str) -> str:
        """Fetch full raw output for a captured update-memory evidence raw_ref."""
        return lookup_raw_evidence(ctx.memory, raw_ref)

    return [
        list_memory_targets,
        read_memory_target,
        search_memory,
        read_memory_page,
        get_raw_evidence,
        *create_executive_verification_tools(ctx),
        *create_remember_tool(ctx),
    ]


def create_chat_wiki_tools(ctx: WikiToolContext) -> list:
    """Class-scoped read tools for lesson-planning chat."""
    wiki = ctx.wiki
    class_id = ctx.class_id

    @function_tool
    def list_lessons(
        start_date: date | None = None,
        end_date: date | None = None,
        topic: str = "",
        max_results: int = 12,
    ) -> str:
        """Map the class lesson sequence.

        Use this before reading details when the teacher asks about recent/older
        lessons, a date range, a review of prior lectures, what has been taught,
        or what class history should shape a new plan. Returns dates, titles,
        summaries, covered topics, homework, and source paths.
        """
        payload = _list_lessons_payload(
            wiki, class_id, start_date, end_date, topic, max_results
        )
        return _capture(ctx.planning, "list_lessons", json.dumps(payload, indent=2))

    @function_tool
    def read_lesson(lesson_date: date) -> str:
        """Read evidence for one known lesson date.

        Use after list_lessons/search_memory when one lesson needs source-level
        detail. Returns lesson notes, saved lesson plan, misconception/open-loop
        rollup excerpts, and source paths.
        """
        try:
            payload = _lesson_detail_payload(wiki, class_id, lesson_date.isoformat())
            return _capture(ctx.planning, "read_lesson", json.dumps(payload, indent=2))
        except KeyError as e:
            return f"Error: {e}"

    @function_tool
    def read_lesson_range(
        start_date: date,
        end_date: date,
        topic: str = "",
        max_lessons: int = 12,
    ) -> str:
        """Read evidence across multiple lessons in a date range.

        Use when the teacher asks to build from several lessons, review recent
        lectures, diagnose recurring student confusion, plan a test/quiz, or
        synthesize what was taught across weeks. Returns compact lesson notes,
        covered topics, rollup excerpts, warnings, and source paths.
        """
        listed = _list_lessons_payload(
            wiki, class_id, start_date, end_date, topic, max_lessons
        )
        lessons = []
        for lesson in listed.get("lessons", []):
            try:
                detail = wiki.get_lesson_detail(class_id, lesson["date"])
            except KeyError:
                continue
            source_paths = []
            if detail.primary_markdown:
                source_paths.append(
                    f"wiki/classes/{class_id}/lessons/{detail.date}/lesson_results.md"
                )
            if detail.lesson_plan_markdown:
                source_paths.append(
                    f"wiki/classes/{class_id}/lessons/{detail.date}/lesson_plan.md"
                )
            lessons.append(
                {
                    "date": detail.date,
                    "title": detail.title,
                    "source_paths": source_paths,
                    "summary": lesson.get("summary", ""),
                    "covered": lesson.get("covered", []),
                    "lesson_notes_excerpt": detail.diary_markdown[:2500],
                    "rollup_excerpts": [
                        {
                            "path": e.wiki_path,
                            "label": e.label,
                            "markdown": e.markdown[:800],
                        }
                        for e in detail.rollup_excerpts[:3]
                    ],
                }
            )
        payload = {
            "range": listed.get("range", {}),
            "lessons": lessons,
            "warnings": listed.get("warnings", []),
        }
        return _capture(
            ctx.planning, "read_lesson_range", json.dumps(payload, indent=2)
        )

    @function_tool
    def search_memory(query: str, max_results: int = 8) -> str:
        """Find relevant class wiki pages for a broad topic.

        Use as the pathfinder when the teacher names a topic, misconception,
        skill, or application and you do not yet know which wiki pages matter.
        Returns ranked source-bearing results: path, kind, title, score,
        matched_terms, source, and snippet.
        """
        limit = max(1, min(max_results or 8, 20))
        hits = wiki.find_in_memory(class_id, query, max_results=limit)
        return _capture(ctx.planning, "wiki_search", json.dumps(hits, indent=2))

    @function_tool
    def read_memory_page(path: str) -> str:
        """Read exact wording from one class wiki page.

        Use for a path returned by search_memory/list_lessons when the snippet
        is not enough, when provenance matters, or when you need exact rollup or
        compact-memory wording. Path must stay under the selected class wiki.
        """
        if not wiki.is_class_memory_path(class_id, path):
            return f"Error: path must be under wiki/classes/{class_id}/"
        try:
            return _capture(ctx.planning, "read_memory_page", wiki.read_wiki_page(path))
        except ValueError as e:
            return f"Error: {e}"

    @function_tool
    def get_raw_evidence(raw_ref: str) -> str:
        """Fetch full raw output for a previously captured evidence raw_ref.

        Use only when a compact evidence brief is ambiguous, contradictory, or
        needs exact wording/provenance. Normal planning should use the compact
        evidence briefs already injected into the prompt.
        """
        return lookup_raw_evidence(ctx.planning, raw_ref)

    return [
        list_lessons,
        read_lesson,
        read_lesson_range,
        search_memory,
        read_memory_page,
        get_raw_evidence,
        *create_executive_verification_tools(ctx),
        *create_remember_tool(ctx),
    ]
