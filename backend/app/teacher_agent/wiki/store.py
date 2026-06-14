"""WikiStore facade — delegates to wiki submodules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.schemas.api import (
    ApprovedWikiUpdate,
    ClassMemorySnapshot,
    ClassSummary,
    ClassTimeline,
    CompletenessChecklist,
    LessonDetail,
    WikiUpdateProposal,
)

from . import (
    commit,
    context_packs,
    diary,
    indexing,
    memory,
    parsing,
    paths_io,
    read_api,
    registry,
    rollups,
    search,
)


@dataclass
class WikiStore:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    def class_dir(self, class_id):
        return paths_io.class_dir(self, class_id)

    def lesson_dir(self, class_id, lesson_date):
        return paths_io.lesson_dir(self, class_id, lesson_date)

    def students_dir(self, class_id):
        return paths_io.students_dir(self, class_id)

    def student_path(self, class_id, student_id):
        return paths_io.student_path(self, class_id, student_id)

    def timeline_path(self, class_id):
        return paths_io.timeline_path(self, class_id)

    def class_config_path(self, class_id):
        return paths_io.class_config_path(self, class_id)

    def roll_up_paths(self, class_id):
        return paths_io.roll_up_paths(self, class_id)

    def rel_wiki(self, path):
        return paths_io.rel_wiki(self, path)

    def read_text(self, path):
        return paths_io.read_text(self, path)

    def write_text(self, path, content):
        return paths_io.write_text(self, path, content)

    def resolve_path(self, relative_path):
        return paths_io.resolve_path(self, relative_path)

    def read_wiki_page(self, relative_path, max_chars=12000):
        return paths_io.read_wiki_page(self, relative_path, max_chars)

    def read_wiki_index(self, class_id):
        return paths_io.read_wiki_index(self, class_id)

    def list_class_pages(self, class_id, kind=None):
        return search.list_class_pages(self, class_id, kind)

    def find_in_memory(self, class_id, query, max_results=5):
        return search.find_in_memory(self, class_id, query, max_results)

    def build_class_relevance_corpus(self, class_id):
        return search.build_class_relevance_corpus(self, class_id)

    def search_wiki(self, class_id, query, max_results=15):
        return search.search_wiki(self, class_id, query, max_results)

    def is_class_memory_path(self, class_id, relative_path):
        return search.is_class_memory_path(self, class_id, relative_path)

    def list_classes(self):
        return registry.list_classes(self)

    def _read_class_meta(self, class_id):
        return registry._read_class_meta(self, class_id)

    def get_class(self, class_id):
        return registry.get_class(self, class_id)

    def get_timeline(self, class_id):
        return read_api.get_timeline(self, class_id)

    def get_snapshot(self, class_id):
        return read_api.get_snapshot(self, class_id)

    def get_lesson_detail(self, class_id, lesson_date):
        return read_api.get_lesson_detail(self, class_id, lesson_date)

    def revise_lesson(self, class_id, lesson_date, diary_md):
        return read_api.revise_lesson(self, class_id, lesson_date, diary_md)

    def checklist_from_diary(self, diary_md):
        return diary.checklist_from_diary(self, diary_md)

    def is_diary_complete(self, diary_md):
        return diary.is_diary_complete(self, diary_md)

    def compile_from_diary(self, class_id, diary_md, lesson_date=None):
        return commit.compile_from_diary(self, class_id, diary_md, lesson_date)

    def commit_ingest(self, class_id, diary_md, approved, session_id):
        return commit.commit_ingest(self, class_id, diary_md, approved, session_id)

    def save_lesson_plan(self, class_id, lesson_date, content):
        return commit.save_lesson_plan(self, class_id, lesson_date, content)

    def memory_dir(self, class_id):
        return memory.memory_dir(self, class_id)

    def memory_paths(self, class_id):
        return memory.memory_paths(self, class_id)

    def compact_memory_excerpts(self, class_id, max_chars=1600):
        return memory.compact_memory_excerpts(self, class_id, max_chars)

    def read_copilot_profile(self, class_id):
        return memory.read_copilot_profile(self, class_id)

    def read_user_profile(self):
        return memory.read_user_profile(self)

    def add_profile_conclusion(self, class_id, section, content, *, source_path=None):
        return memory.add_profile_conclusion(
            self, class_id, section, content, source_path=source_path
        )

    def add_user_profile_conclusion(self, section, content):
        return memory.add_user_profile_conclusion(self, section, content)

    def search_personal_memory(self, class_id, query, max_results=5):
        return memory.search_personal_memory(self, class_id, query, max_results)

    def build_memory_compaction_source_packet(self, class_id, start_date=None, end_date=None):
        return memory.build_memory_compaction_source_packet(
            self, class_id, start_date, end_date
        )

    def commit_memory_compaction(self, class_id, pages, *, source_paths=None):
        return memory.commit_memory_compaction(
            self, class_id, pages, source_paths=source_paths
        )

    def build_teacher_context_trace(self):
        return context_packs.build_teacher_context_trace(self)

    def build_active_class_core_context_trace(self, class_id):
        return context_packs.build_active_class_core_context_trace(self, class_id)

    def build_ingest_task_context_trace(self, class_id):
        return context_packs.build_ingest_task_context_trace(self, class_id)

    def build_ingest_context_slim_trace(self, class_id):
        return context_packs.build_ingest_context_slim_trace(self, class_id)

    def build_plan_context(self, class_id):
        return context_packs.build_plan_context(self, class_id)

    def build_plan_context_slim(self, class_id):
        return context_packs.build_plan_context_slim(self, class_id)

    def build_plan_context_slim_trace(self, class_id):
        return context_packs.build_plan_context_slim_trace(self, class_id)

    def build_ingest_context(self, class_id):
        return context_packs.build_ingest_context(self, class_id)

    def build_ingest_context_slim(self, class_id):
        return context_packs.build_ingest_context_slim(self, class_id)

    def build_context_package(self, class_id, mode):
        return context_packs.build_context_package(self, class_id, mode)

    def build_planning_query_pack(self, class_id):
        return context_packs.build_planning_query_pack(self, class_id)

    def build_ingest_query_pack(self, class_id):
        return context_packs.build_ingest_query_pack(self, class_id)

    def build_review_query_pack(self, class_id):
        return context_packs.build_review_query_pack(self, class_id)

    def empty_plan_template(self, lesson_date=None):
        return context_packs.empty_plan_template(self, lesson_date)

    def is_plan_ready(self, plan_md):
        return context_packs.is_plan_ready(self, plan_md)

    def load_index_context(self, class_id, max_chars=4000, *, for_tool_loop=False):
        return context_packs.load_index_context(
            self, class_id, max_chars, for_tool_loop=for_tool_loop
        )

    def empty_diary_template(self, lesson_date=None):
        return context_packs.empty_diary_template(self, lesson_date)

    def extract_title(self, text):
        return parsing.extract_title(text)

    def extract_date_from_diary(self, text):
        return parsing.extract_date_from_diary(text)

    def _format_lesson_results(self, class_id, subject, diary_md, lesson_date, title):
        return rollups._format_lesson_results(self, class_id, subject, diary_md, lesson_date, title)

    def _compile_rollups(self, class_id, diary_md, lesson_date, title):
        return rollups._compile_rollups(self, class_id, diary_md, lesson_date, title)

    def _upsert_course_state(self, current, lesson_date, title, unit, followups):
        return rollups._upsert_course_state(self, current, lesson_date, title, unit, followups)

    def _append_bullets(self, existing, new_bullets, lesson_date):
        return rollups._append_bullets(self, existing, new_bullets, lesson_date)

    def _parse_student_observations(self, students_block):
        return parsing.parse_student_observations(students_block)

    def _upsert_student_entity(self, class_id, student_id, lesson_date, bullets):
        return rollups._upsert_student_entity(self, class_id, student_id, lesson_date, bullets)

    def _rebuild_students_index(self, class_id, previews):
        return rollups._rebuild_students_index(self, class_id, previews)

    def _compile_timeline_entry(self, class_id, lesson_date, title, diary_md):
        return rollups._compile_timeline_entry(self, class_id, lesson_date, title, diary_md)

    def _upsert_timeline_md(self, class_id, lesson_date, title, diary_md):
        return rollups._upsert_timeline_md(self, class_id, lesson_date, title, diary_md)

    def _compile_students_and_timeline(self, class_id, diary_md, lesson_date, title):
        return rollups._compile_students_and_timeline(self, class_id, diary_md, lesson_date, title)

    def _finalize_lesson_writes(self, class_id, diary_md, lesson_date, title, applied):
        return rollups._finalize_lesson_writes(self, class_id, diary_md, lesson_date, title, applied)

    def _lines_to_bullets(self, text):
        return parsing.lines_to_bullets(text)

    def _extract_title(self, text):
        return parsing.extract_title(text)

    def _extract_date_from_diary(self, text):
        return parsing.extract_date_from_diary(text)

    def _extract_section_body(self, text, heading):
        return parsing.extract_section_body(text, heading)

    def _extract_section_bullets(self, text, heading):
        return parsing.extract_section_bullets(text, heading)

    def _extract_homework(self, text):
        return parsing.extract_homework(text)

    def _extract_raw_link(self, text):
        return parsing.extract_raw_link(text)

    def _slugify(self, title):
        return parsing.slugify(title)

    def _one_line(self, text, max_len=120):
        return parsing.one_line(text, max_len)

    def _build_timeline_summary(self, lesson_results):
        return parsing.build_timeline_summary(lesson_results)

    def _diary_body_from_lesson_results(self, lesson_results, lesson_date, title):
        return parsing.diary_body_from_lesson_results(lesson_results, lesson_date, title)

    def _extract_date_section(self, text, lesson_date):
        return parsing.extract_date_section(text, lesson_date)

    def _remove_date_section(self, text, lesson_date):
        return parsing.remove_date_section(text, lesson_date)

    def _parse_log_entry(self, header, block):
        return parsing.parse_log_entry(header, block)

    def _parse_log_by_date(self):
        return indexing._parse_log_by_date(self)

    def _latest_log_commit(self):
        return indexing._latest_log_commit(self)

    def _append_log(self, class_id, lesson_date, title, applied, kind):
        return indexing._append_log(self, class_id, lesson_date, title, applied, kind)

    def rebuild_index(self, class_id=None):
        return indexing.rebuild_index(self, class_id)

    def _update_index(self, class_id):
        return indexing._update_index(self, class_id)

    @property
    def index_path(self) -> Path:
        return paths_io.index_path(self)

    @property
    def log_path(self) -> Path:
        return paths_io.log_path(self)

