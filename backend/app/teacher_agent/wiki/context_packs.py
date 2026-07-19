"""Wiki context packs operations (delegated from WikiStore)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional


from app.context_limits import apply_char_limit, get_context_limits
from app.teacher_agent.wiki.constants import (
    LESSON_RESULTS_SECTIONS,
    ROLLUP_LABELS,
)


def _recent_taught_entries(store, class_id: str, limit: int = 2):
    entries = [e for e in store.get_timeline(class_id).entries if e.status == "taught"]
    return entries[:limit]


def _compact_memory_section(
    store, class_id: str, *, max_chars: int = 1400
) -> list[str]:
    excerpts = store.compact_memory_excerpts(class_id, max_chars=max_chars)
    if not excerpts:
        return [
            "## Compact class memory",
            "- No compact memory pages found yet. Use the manual compact endpoint after lessons accumulate.",
            "",
        ]
    parts = ["## Compact class memory"]
    for rel, text in excerpts:
        parts.extend([f"### {rel}", text, ""])
    return parts


def _memory_page_excerpt(store, class_id: str, key: str, max_chars: int = 1200) -> str:
    path = store.memory_paths(class_id).get(key)
    if not path:
        return ""
    return store.read_text(path).strip()[:max_chars]


def _lesson_sequence_lines(store, class_id: str, limit: int = 6) -> list[str]:
    entries = [e for e in store.get_timeline(class_id).entries if e.status == "taught"]
    return [
        f"- {entry.date}: {entry.title} - {entry.summary}" for entry in entries[:limit]
    ]


def build_planning_query_pack(store, class_id: str) -> str:
    """AutoSci-style derived read-only pack for planning retrieval orientation."""
    snapshot = store.get_snapshot(class_id)
    parts = [
        "# Planning Query Pack",
        "Purpose: orient lesson planning before broader wiki search.",
        "",
        "## Recent taught sequence",
    ]
    sequence = _lesson_sequence_lines(store, class_id, limit=6)
    parts.extend(sequence or ["- No taught lessons found."])
    parts.extend(["", "## Misconception priorities"])
    parts.extend(
        [f"- {m}" for m in snapshot.top_misconceptions[:6]]
        if snapshot.top_misconceptions
        else ["- None listed."]
    )
    parts.extend(
        [
            "",
            "## Planning brief",
            _memory_page_excerpt(store, class_id, "planning_brief", 1200)
            or "- No compact planning brief yet.",
            "",
            "## Teaching patterns",
            _memory_page_excerpt(store, class_id, "teaching_patterns", 1200)
            or "- No compact teaching patterns yet.",
            "",
            "## Open loops",
            store.read_text(store.roll_up_paths(class_id)["open_loops"])[:1200],
        ]
    )
    return "\n".join(parts)


def build_ingest_query_pack(store, class_id: str) -> str:
    """AutoSci-style derived read-only pack for memory-update orientation."""
    snapshot = store.get_snapshot(class_id)
    parts = [
        "# Ingest Query Pack",
        "Purpose: orient lesson logging while keeping durable writes approval-gated.",
        "",
        "## Previous lesson",
    ]
    if snapshot.last_committed_date:
        try:
            detail = store.get_lesson_detail(class_id, snapshot.last_committed_date)
            parts.extend(
                [
                    f"### {snapshot.last_committed_date} - {detail.title}",
                    detail.diary_markdown[:1600],
                ]
            )
        except KeyError:
            parts.append("- Previous lesson detail not found.")
    else:
        parts.append("- No previous lesson found.")
    parts.extend(
        [
            "",
            "## Student roster excerpt",
            store.read_text(store.roll_up_paths(class_id)["students"])[:1600],
            "",
            "## Course state (current unit & progression)",
            store.read_text(store.roll_up_paths(class_id)["course_state"])[:1000]
            or "- No course state recorded yet.",
            "",
            "## Open loops",
            store.read_text(store.roll_up_paths(class_id)["open_loops"])[:900],
        ]
    )
    return "\n".join(parts)


def build_review_query_pack(store, class_id: str) -> str:
    """AutoSci-style derived read-only pack for reviews or assessment spanning memory."""
    snapshot = store.get_snapshot(class_id)
    # taught_so_far.md was retired; derive the sequence from the canonical
    # lesson timeline instead of a curated compact twin.
    taught = "\n".join(_lesson_sequence_lines(store, class_id, limit=10))
    parts = [
        "# Review Query Pack",
        "Purpose: orient reviews, assessments, or cross-lesson synthesis.",
        "",
        "## Taught-so-far sequence",
        taught or "- No taught sequence available.",
        "",
        "## Recurring misconceptions",
    ]
    parts.extend(
        [f"- {m}" for m in snapshot.top_misconceptions[:8]]
        if snapshot.top_misconceptions
        else ["- None listed."]
    )
    parts.extend(
        [
            "",
            "## Unresolved issues and planning priorities",
            _memory_page_excerpt(store, class_id, "planning_brief", 1400)
            or store.read_text(store.roll_up_paths(class_id)["open_loops"])[:1400],
        ]
    )
    return "\n".join(parts)


def build_base_class_context(store, class_id: str) -> str:
    """Small class-scoped context shared by workflow packages."""
    snapshot = store.get_snapshot(class_id)
    cls = store.get_class(class_id)
    subject_guide = store.read_text(
        store.root / "wiki" / "subjects" / f"{cls.subject}.md"
    )
    parts = [
        f"# Base class context - {snapshot.label} ({class_id})",
        f"Subject: {cls.subject}",
        f"Current unit: {snapshot.current_unit}",
        f"Last committed lesson: {snapshot.last_committed_date or 'None'}",
        f"Open loops (count): {snapshot.open_loop_count}",
        "",
        "## Recent timeline",
    ]
    if snapshot.recent_lessons:
        parts.extend(f"- {line}" for line in snapshot.recent_lessons[:5])
    else:
        parts.append("- No recent lessons")
    parts.extend(["", "## Core misconceptions"])
    if snapshot.top_misconceptions:
        parts.extend(f"- {m}" for m in snapshot.top_misconceptions[:6])
    else:
        parts.append("- None listed")
    parts.extend(
        [
            "",
            "## Class copilot profile",
            store.read_copilot_profile(class_id)[:1800] or "- No copilot profile yet.",
            "",
            f"## Subject guide: {cls.subject} (excerpt)",
            subject_guide[:1400],
        ]
    )
    return "\n".join(parts)


def build_context_package(store, class_id: str, mode: str) -> str:
    """Named frozen context package for a workflow session."""
    normalized = mode.strip().lower()
    if normalized in {"ingest", "memory", "update_memory"}:
        return build_ingest_context_slim(store, class_id)
    if normalized in {"plan", "planning"}:
        return build_plan_context_slim(store, class_id)
    raise ValueError(f"Unknown context package mode: {mode}")


def _trace_section(
    *,
    name: str,
    function: str,
    source: str,
    text: str,
    authority: str,
    included: bool = True,
) -> dict:
    return {
        "name": name,
        "function": function,
        "source": source,
        "authority": authority,
        "included": included,
        "chars": len(text or ""),
        "text": text or "",
    }


def build_teacher_context_trace(store) -> dict:
    """Return the global teacher profile as a traceable prompt layer."""
    from app.teacher_agent.wiki import memory as _mem

    path = _mem.user_profile_path(store)
    text = store.read_text(path).strip()
    rendered = "# Teacher context (global)\n" + (
        _mem.clamp_memory_page("user", text).rstrip()
        if text
        else "- No teacher profile yet."
    )
    return {
        "function": "build_teacher_context_trace",
        "chars": len(rendered),
        "text": rendered,
        "sections": [
            _trace_section(
                name="Teacher profile",
                function="build_teacher_context_trace",
                source=store.rel_wiki(path),
                text=rendered,
                authority="curated_advisory",
                included=bool(text),
            )
        ],
    }


def _memory_context_key(path: Path) -> str:
    from app.teacher_agent.wiki import memory as _mem

    for key, filename in _mem.COMPACT_MEMORY_FILES.items():
        if path.name == filename:
            return key
    return path.stem


_MEMORY_SECTION_LABELS: dict[str, str] = {
    "planning_brief": "Planning brief",
    "teaching_patterns": "Teaching patterns",
    "copilot_profile": "Class copilot profile",
    "session_summaries": "Session summaries",
}


def _active_memory_files(store, class_id: str) -> list[Path]:
    """Return class-core memory, excluding subject-expert-only adjustments."""
    from app.teacher_agent.wiki import memory as _mem

    memory_root = store.memory_dir(class_id)
    subject_expert_only = {"teaching_framework_adjustments.md"}
    known = [
        path
        for path in store.memory_paths(class_id).values()
        if path.exists() and path.name not in subject_expert_only
    ]
    known_names = {path.name for path in known}
    extras = []
    if memory_root.exists():
        extras = [
            path
            for path in sorted(memory_root.glob("*.md"))
            if path.name not in known_names
            and path.name not in subject_expert_only
        ]
    order = {
        filename: idx for idx, filename in enumerate(_mem.COMPACT_MEMORY_FILES.values())
    }
    return sorted(
        known + extras,
        key=lambda path: (order.get(path.name, 999), path.name),
    )


def build_trusted_source_context_trace(store, class_id: str) -> dict:
    """Build the bounded profile/source TOC injected into class context.

    This intentionally exposes only metadata and section labels.  Source bodies
    stay behind the typed trusted-source tools and the session raw-evidence
    store, matching the existing progressive-exposure contract.
    """
    lim = get_context_limits()
    profile_path = store.class_dir(class_id) / "curriculum_profile.md"
    toc_path = store.class_dir(class_id) / "trusted_sources.md"
    profile = store.get_curriculum_profile(class_id)
    sources = store.list_trusted_sources(class_id, "all")
    profile_text = store.read_text(profile_path).strip()
    if not profile_text and not sources:
        return {"text": "", "sections": []}

    profile_lines = [
        "## Curriculum profile",
        f"State: {profile.state or 'Unspecified'} | School type: {profile.school_type or 'Unspecified'}",
        f"Branch: {profile.branch or 'Unspecified'} | Grade: {profile.grade or 'Unspecified'}",
        f"Subject: {profile.subject or 'Unspecified'}",
    ]
    if profile_text:
        profile_lines.append("Profile note: " + " ".join(profile_text.split())[:420])
    source_lines = ["## Trusted source index"]
    for source in sources:
        sections = ", ".join(section.id for section in source.sections[:5]) or "summary"
        source_lines.append(
            f"- {source.source_id} | {source.authority} | {source.jurisdiction} "
            f"{source.school_type} {source.branch} Grade {source.grade} | sections: {sections}"
        )
    source_lines.append(
        "Read a source section through trusted-source tools before making a curriculum claim."
    )
    text = "\n".join(profile_lines + [""] + source_lines)
    text = apply_char_limit(text, lim.trusted_source_index_chars)
    sections = [
        _trace_section(
            name="Curriculum profile",
            function="build_trusted_source_context_trace",
            source=store.rel_wiki(profile_path),
            text="\n".join(profile_lines),
            authority="class_configuration",
            included=bool(profile_text),
        ),
        _trace_section(
            name="Trusted source index",
            function="build_trusted_source_context_trace",
            source=store.rel_wiki(toc_path),
            text="\n".join(source_lines),
            authority="official_source_index",
            included=bool(sources),
        ),
    ]
    return {"text": text, "sections": sections}


def _subject_routing_context_trace(store, class_id: str) -> dict:
    """Describe the configured subject route without injecting pedagogy."""
    class_config = store.get_class(class_id)
    curriculum = store.get_curriculum_profile(class_id)
    profile_path = store.class_dir(class_id) / "curriculum_profile.md"
    text = "\n".join(
        [
            "## Subject routing",
            "Subject route: "
            f"{class_config.subject} | Grade: {curriculum.grade or 'Unspecified'} | "
            f"Branch: {curriculum.branch or 'Unspecified'}",
        ]
    )
    return {
        "text": text,
        "sections": [
            _trace_section(
                name="Subject route",
                function="build_subject_knowledge_trace",
                source=store.rel_wiki(profile_path),
                text=text,
                authority="class_configuration",
            )
        ],
    }


def build_active_subject_expert_context_trace(store, class_id: str, *, purpose: str) -> dict:
    """Build the bounded subject layer for a workflow purpose.

    The effective profile is assembled in memory from the shared Grade summary
    and the dedicated class adjustment page; no generated profile is persisted.
    """
    from app.teacher_agent.wiki import memory as _mem

    normalized = purpose.strip().lower()
    routing = _subject_routing_context_trace(store, class_id)
    class_config = store.get_class(class_id)
    subject_path = store.root / "wiki" / "subjects" / f"{class_config.subject}.md"
    sections = list(routing["sections"])
    parts = ["# Active subject expert", routing["text"]]
    full_pedagogy = normalized in {"plan", "differentiation"}
    front_door_only = normalized == "plan_opening"

    if full_pedagogy or front_door_only:
        subject_text = store.read_text(subject_path).strip()
        if subject_text:
            subject_text = _mem.clamp_memory_page("subject_guide", subject_text).rstrip()
            sections.append(
                _trace_section(
                    name=f"Subject guide: {class_config.subject}",
                    function="build_active_subject_expert_context_trace",
                    source=store.rel_wiki(subject_path),
                    text=subject_text,
                    authority="curated_guidance",
                )
            )
            parts.extend(["", f"## Subject guide: {class_config.subject}", subject_text])

    if full_pedagogy:
        from app.teacher_agent.wiki.subject_frameworks import framework_for_class

        framework = framework_for_class(store, class_id)
        adjustments_path = store.memory_paths(class_id)["teaching_framework_adjustments"]
        adjustments = store.read_text(adjustments_path).strip()
        profile_text = "\n\n".join(
            part for part in (framework.text.strip(), adjustments) if part
        )
        if profile_text:
            profile_text = _mem.clamp_memory_page(
                "effective_subject_framework", profile_text
            ).rstrip()
            sections.append(
                _trace_section(
                    name="Selected teaching framework",
                    function="build_active_subject_expert_context_trace",
                    source=framework.path,
                    text=framework.text.strip(),
                    authority="curated_guidance",
                )
            )
            sections.append(
                _trace_section(
                    name="Class teaching framework adjustments",
                    function="build_active_subject_expert_context_trace",
                    source=store.rel_wiki(adjustments_path),
                    text=adjustments,
                    authority="teacher_adjusted_class_profile",
                )
            )
            parts.extend(["", "## Effective teaching framework", profile_text])
        else:
            sections.append(
                _trace_section(
                    name="Selected teaching framework",
                    function="build_active_subject_expert_context_trace",
                    source=framework.path,
                    text="",
                    authority="curated_guidance",
                    included=False,
                )
            )
            sections.append(
                _trace_section(
                    name="Class teaching framework adjustments",
                    function="build_active_subject_expert_context_trace",
                    source=store.rel_wiki(adjustments_path),
                    text="",
                    authority="teacher_adjusted_class_profile",
                    included=False,
                )
            )
        source_trace = build_trusted_source_context_trace(store, class_id)
        sections.extend(source_trace["sections"])
        if source_trace["text"]:
            parts.extend(["", source_trace["text"]])

    rendered = "\n".join(parts)
    return {
        "function": "build_active_subject_expert_context_trace",
        "chars": len(rendered),
        "text": rendered,
        "sections": sections,
    }


def build_subject_knowledge_trace(store, class_id: str, *, purpose: str) -> dict:
    """Public semantic alias used by callers that need subject provenance."""
    return build_active_subject_expert_context_trace(store, class_id, purpose=purpose)


def build_base_assistant_context_trace(store, class_id: str, *, purpose: str) -> dict:
    """Compose teacher, class, and purpose-specific subject layers explicitly."""
    teacher = build_teacher_context_trace(store)
    class_core = build_active_class_core_context_trace(store, class_id)
    subject = build_active_subject_expert_context_trace(store, class_id, purpose=purpose)
    rendered = "\n\n".join(
        part for part in (teacher["text"], class_core["text"], subject["text"]) if part
    )
    return {
        "function": "build_base_assistant_context_trace",
        "chars": len(rendered),
        "text": rendered,
        "sections": teacher["sections"] + class_core["sections"] + subject["sections"],
        "nested": {
            "teacher_layer": teacher,
            "active_class_core": class_core,
            "active_subject_expert": subject,
        },
    }


def build_active_class_core_context_trace(store, class_id: str) -> dict:
    """Return only class facts and compact class memory.

    Subject guidance has a separate authority and is composed purposefully by
    ``build_active_subject_expert_context_trace``. Canonical lessons, roll-ups,
    student pages, and raw diaries remain on-demand tool evidence.
    """
    from app.teacher_agent.wiki import memory as _mem

    snapshot = store.get_snapshot(class_id)
    cls = store.get_class(class_id)
    sections: list[dict] = []
    parts: list[str] = []

    def add_section(
        name: str,
        source: str,
        lines: list[str],
        *,
        authority: str = "committed_wiki",
        included: bool = True,
        function: str = "build_active_class_core_context_trace",
    ) -> None:
        labeled_lines = [f"[authority={authority}; source={source}]", *lines]
        text = "\n".join(labeled_lines)
        sections.append(
            _trace_section(
                name=name,
                function=function,
                source=source,
                text=text,
                authority=authority,
                included=included,
            )
        )
        if included:
            parts.extend(labeled_lines)

    add_section(
        "Class identity snapshot",
        "get_snapshot() + get_class()",
        [
            f"# Active class core context - {snapshot.label} ({class_id})",
            f"Subject: {cls.subject} | Current unit: {snapshot.current_unit}",
            f"Last committed lesson: {snapshot.last_committed_date or 'None'} | "
            f"Open loops: {snapshot.open_loop_count}",
        ],
    )
    add_section(
        "Top misconceptions",
        "snapshot.top_misconceptions",
        [
            "",
            "## Top misconceptions",
            *([f"- {m}" for m in snapshot.top_misconceptions[:6]] or ["- None listed"]),
        ],
    )
    if snapshot.recent_lessons:
        add_section(
            "Recent lessons",
            "snapshot.recent_lessons",
            [
                "",
                "## Recent lessons",
                *[f"- {line}" for line in snapshot.recent_lessons[:3]],
            ],
        )

    memory_files = _active_memory_files(store, class_id)
    seen_memory = False
    for path in memory_files:
        text = store.read_text(path).strip()
        key = _memory_context_key(path)
        label = _MEMORY_SECTION_LABELS.get(key, path.stem.replace("_", " ").title())
        source = store.rel_wiki(path)
        if text:
            seen_memory = True
            add_section(
                f"Class memory: {path.name}",
                source,
                ["", f"## {label}", _mem.clamp_memory_page(key, text).rstrip()],
                authority="curated_advisory",
            )
        else:
            sections.append(
                _trace_section(
                    name=f"Class memory: {path.name}",
                    function="build_active_class_core_context_trace",
                    source=source,
                    text="",
                    authority="curated_advisory",
                    included=False,
                )
            )

    if not seen_memory:
        add_section(
            "Compact class memory",
            f"wiki/classes/{class_id}/memory/",
            [
                "",
                "## Compact class memory",
                "- No compact class memory pages found yet.",
            ],
            authority="curated_advisory",
        )

    rendered = "\n".join(parts)
    return {
        "function": "build_active_class_core_context_trace",
        "chars": len(rendered),
        "text": rendered,
        "sections": sections,
    }


def build_plan_context_slim_trace(store, class_id: str) -> dict:
    """Return the slim planning context plus a section-by-section debug trace.

    Backward-compatible wrapper over the shared active-class core layer.
    """
    core = build_active_class_core_context_trace(store, class_id)
    subject = build_active_subject_expert_context_trace(store, class_id, purpose="plan")
    rendered = "\n\n".join(part for part in (core["text"], subject["text"]) if part)
    sections = [
        {**section, "function": "build_plan_context_slim"}
        for section in core["sections"] + subject["sections"]
    ]
    return {
        "function": "build_plan_context_slim",
        "chars": len(rendered),
        "text": rendered,
        "sections": sections,
    }


def build_plan_context_slim(store, class_id: str) -> str:
    """Deduped, budgeted compact class slice for the planning chat prompt."""
    return build_plan_context_slim_trace(store, class_id)["text"]


def build_ingest_task_context_trace(store, class_id: str) -> dict:
    """Return Update Memory task context that is not part of class core."""
    lim = get_context_limits()
    snapshot = store.get_snapshot(class_id)
    rollups = store.roll_up_paths(class_id)
    sections: list[dict] = []
    parts: list[str] = [
        "# Update Memory task context",
        "Use this context for continuity only. Log only what the teacher says happened.",
        "Use pseudonymous student IDs only (S-001 style IDs).",
        "",
    ]

    def add_section(
        name: str, source: str, lines: list[str], included: bool = True
    ) -> None:
        labeled_lines = [f"[authority=committed_wiki; source={source}]", *lines]
        text = "\n".join(labeled_lines)
        sections.append(
            _trace_section(
                name=name,
                function="build_ingest_task_context_trace",
                source=source,
                text=text,
                authority="committed_wiki",
                included=included,
            )
        )
        if included:
            parts.extend(labeled_lines)

    if snapshot.last_committed_date:
        try:
            detail = store.get_lesson_detail(class_id, snapshot.last_committed_date)
            previous = apply_char_limit(
                detail.diary_markdown, lim.ingest_previous_lesson_chars
            )
            add_section(
                "Previous lesson",
                f"wiki/classes/{class_id}/lessons/{snapshot.last_committed_date}/lesson_results.md",
                [
                    f"## Previous lesson ({snapshot.last_committed_date})",
                    previous or "- Previous lesson detail is empty.",
                    "",
                ],
            )
        except KeyError:
            add_section(
                "Previous lesson",
                "snapshot.last_committed_date",
                ["## Previous lesson", "- Previous lesson detail not found.", ""],
            )
    else:
        add_section(
            "Previous lesson",
            "snapshot.last_committed_date",
            ["## Previous lesson", "- No previous lesson found.", ""],
        )

    add_section(
        "Student roster excerpt",
        store.rel_wiki(rollups["students"]),
        [
            "## Student roster excerpt",
            apply_char_limit(
                store.read_text(rollups["students"]), lim.ingest_student_roster_chars
            )
            or "- No student roster found.",
            "",
        ],
    )

    planned = [e for e in store.get_timeline(class_id).entries if e.has_plan][:1]
    if planned:
        for entry in planned:
            try:
                detail = store.get_lesson_detail(class_id, entry.date)
            except KeyError:
                continue
            if detail.lesson_plan_markdown:
                add_section(
                    "Most recent saved plan",
                    f"wiki/classes/{class_id}/lessons/{entry.date}/lesson_plan.md",
                    [
                        f"## Most recent saved plan ({entry.date})",
                        apply_char_limit(
                            detail.lesson_plan_markdown, lim.ingest_saved_plan_chars
                        ),
                        "",
                    ],
                )
                break

    rendered = "\n".join(parts)
    return {
        "function": "build_ingest_task_context_trace",
        "chars": len(rendered),
        "text": rendered,
        "sections": sections,
    }


def build_ingest_context_slim_trace(store, class_id: str) -> dict:
    """Return the shared class core plus small Update Memory task context."""
    core = build_active_class_core_context_trace(store, class_id)
    subject = build_active_subject_expert_context_trace(store, class_id, purpose="ingest")
    task = build_ingest_task_context_trace(store, class_id)
    rendered = "\n\n".join(
        part for part in (core["text"], subject["text"], task["text"]) if part.strip()
    )
    return {
        "function": "build_ingest_context_slim",
        "chars": len(rendered),
        "text": rendered,
        "sections": [
            _trace_section(
                name="Active class core",
                function="build_active_class_core_context_trace",
                source=f"wiki/classes/{class_id}/memory/*.md + selected subject guide",
                text=core["text"],
                authority="mixed_wiki",
            ),
            _trace_section(
                name="Subject routing",
                function="build_active_subject_expert_context_trace",
                source=f"wiki/classes/{class_id}/curriculum_profile.md",
                text=subject["text"],
                authority="class_configuration",
            ),
            _trace_section(
                name="Update Memory task context",
                function="build_ingest_task_context_trace",
                source="recent lesson/roster/saved plan",
                text=task["text"],
                authority="committed_wiki",
            ),
        ],
        "nested": {
            "active_class_core": core,
            "subject_routing": subject,
            "task_context": task,
        },
    }


def build_ingest_context_slim(store, class_id: str) -> str:
    """Deduped class core + task slice for lesson-memory ingest chat."""
    return build_ingest_context_slim_trace(store, class_id)["text"]


def build_plan_context(store, class_id: str) -> str:
    """Memory pack for planning the *next* lesson — forward-looking rollups + last real lesson."""
    snapshot = store.get_snapshot(class_id)
    cls = store.get_class(class_id)
    timeline = store.get_timeline(class_id)
    parts = [
        f"# Session: Plan next lesson — {snapshot.label} ({class_id})",
        f"Subject: {cls.subject} | Current unit: {snapshot.current_unit}",
        f"Open loops (count): {snapshot.open_loop_count}",
        "",
        "Use this to propose activities, timing, and homework for the upcoming lesson.",
        "",
        "## Top misconceptions to address",
    ]
    if snapshot.top_misconceptions:
        parts.extend(f"- {m}" for m in snapshot.top_misconceptions)
    else:
        parts.append("- None listed")
    parts.append("")

    if snapshot.recent_lessons:
        parts.extend(
            [
                "## Recent lessons (titles)",
                *[f"- {line}" for line in snapshot.recent_lessons],
                "",
            ]
        )

    parts.extend([build_planning_query_pack(store, class_id), ""])

    recent_taught = _recent_taught_entries(store, class_id, limit=2)
    if recent_taught:
        parts.append("## Last 2 taught lessons")
    for entry in recent_taught:
        try:
            detail = store.get_lesson_detail(class_id, entry.date)
            parts.extend(
                [
                    f"### {entry.date} - {entry.title}",
                    detail.diary_markdown[:3000],
                    "",
                ]
            )
            if detail.lesson_plan_markdown:
                parts.extend(
                    [
                        f"#### Saved plan ({entry.date})",
                        detail.lesson_plan_markdown[:1800],
                        "",
                    ]
                )
        except KeyError:
            continue

    parts.extend(_compact_memory_section(store, class_id, max_chars=1800))

    for key in ("course_state", "students", "open_loops", "misconceptions"):
        path = store.roll_up_paths(class_id)[key]
        label = ROLLUP_LABELS.get(key, key)
        parts.extend([f"## {label}", store.read_text(path)[:2500], ""])

    planned = [e for e in timeline.entries if e.has_plan][:3]
    if planned:
        parts.append("## Lessons that already have a saved plan")
        for e in planned:
            parts.append(f"- {e.date} — {e.title}")
        parts.append("")

    parts.extend(
        [
            "## Teacher profile (excerpt)",
            store.read_text(store.root / "wiki" / "teacher_profile.md")[:1200],
            "",
            f"## Subject guide: {cls.subject} (excerpt)",
            store.read_text(store.root / "wiki" / "subjects" / f"{cls.subject}.md")[
                :1200
            ],
        ]
    )
    return "\n".join(parts)


def build_ingest_context(store, class_id: str) -> str:
    """Memory pack for logging today's lesson — student IDs, prior lesson, light rollups."""
    snapshot = store.get_snapshot(class_id)
    cls = store.get_class(class_id)
    parts = [
        f"# Session: Update lesson notes — {snapshot.label} ({class_id})",
        f"Subject: {cls.subject} | Current unit: {snapshot.current_unit}",
        "",
        "Help the teacher record what happened today. Use only what they say; use context for IDs and continuity.",
        "Use pseudonyms only for student references (S-001 style IDs).",
        "",
        "## Student notes / roster",
        store.read_text(store.roll_up_paths(class_id)["students"])[:4500],
        "",
        "## Course state",
        store.read_text(store.roll_up_paths(class_id)["course_state"])[:2000],
        "",
    ]

    parts.extend([build_ingest_query_pack(store, class_id), ""])

    if snapshot.last_committed_date:
        try:
            detail = store.get_lesson_detail(class_id, snapshot.last_committed_date)
            parts.extend(
                [
                    f"## Previous lesson ({snapshot.last_committed_date}) — continuity only",
                    detail.diary_markdown[:3500],
                    "",
                ]
            )
        except KeyError:
            pass

    planned = [e for e in store.get_timeline(class_id).entries if e.has_plan][:3]
    if planned:
        parts.append("## Recent saved plans (continuity only)")
        for entry in planned:
            try:
                detail = store.get_lesson_detail(class_id, entry.date)
            except KeyError:
                continue
            if detail.lesson_plan_markdown:
                parts.extend(
                    [
                        f"### {entry.date} - {entry.title}",
                        detail.lesson_plan_markdown[:1200],
                        "",
                    ]
                )

    parts.extend(_compact_memory_section(store, class_id, max_chars=1200))

    parts.extend(
        [
            "## Open loops (teacher may close or add while logging)",
            store.read_text(store.roll_up_paths(class_id)["open_loops"])[:1500],
            "",
            "## Misconceptions (brief — note new ones if the teacher reports them)",
        ]
    )
    if snapshot.top_misconceptions:
        parts.extend(f"- {m}" for m in snapshot.top_misconceptions[:5])
    else:
        parts.append("- None listed yet")
    return "\n".join(parts)


def empty_plan_template(store, lesson_date: Optional[str] = None) -> str:
    d = lesson_date or date.today().isoformat()
    return (
        f"# Lesson Plan — Next lesson\n\n"
        f"> Duration: 45 min | Target date: {d}\n\n"
        "## Learning goals\n\n\n"
        "## Lesson flow\n\n"
        "- **Opening** (5 min):\n\n"
        "- **Main teaching** (25 min):\n\n"
        "- **Practice** (10 min):\n\n"
        "- **Close** (5 min):\n\n"
        "## Warmup\n\n\n"
        "## Practice tasks\n\n-\n\n"
        "## Homework\n\n\n"
        "## Teacher notes\n\n"
    )


def is_plan_ready(store, plan_md: str) -> bool:
    text = plan_md.lower()
    legacy_required = ("## learning goals", "## lesson flow", "## warmup")
    package_required = (
        "# lesson package",
        "## teacher lesson plan",
        "## student materials",
        "## observation and update capture",
        "core evidence task:",
        "### exit ticket",
    )
    three_audience_fallback_required = (
        "# lesson plan",
        "## teacher plan",
        "## student materials",
        "## observation / update",
        "### exit evidence",
    )
    return (
        all(heading in text for heading in legacy_required)
        or all(heading in text for heading in package_required)
        or all(heading in text for heading in three_audience_fallback_required)
    ) and len(plan_md.strip()) > 200


def load_index_context(
    store, class_id: str, max_chars: int = 4000, *, for_tool_loop: bool = False
) -> str:
    """Index-first context bundled into chat prompts."""
    cls = store.get_class(class_id)
    index_hint = (
        "read pages via tools as needed"
        if for_tool_loop
        else "see sections below for detail"
    )
    parts = [
        f"# Wiki index ({index_hint})",
        f"Class: {cls.label} ({class_id})",
        "",
        store.read_wiki_index(class_id)[:max_chars],
        "",
        "## Roll-up excerpts",
        store.read_text(store.roll_up_paths(class_id)["course_state"])[:1500],
        "",
        store.read_text(store.roll_up_paths(class_id)["open_loops"])[:1000],
    ]
    return "\n".join(parts)


def empty_diary_template(store, lesson_date: Optional[str] = None) -> str:
    d = lesson_date or date.today().isoformat()
    lines = [f"# Lesson Results — {d} — ", ""]
    for _, label, _ in LESSON_RESULTS_SECTIONS:
        lines.extend([f"## {label}", "", ""])
    return "\n".join(lines)
