"""Durable storage contract for adopted class course networks."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.course_network.models import (
    CourseNetworkDocument,
    CurriculumReference,
    CurriculumRouteRef,
    LearningBlock,
    NetworkEdge,
    canonical_network_json,
)
from app.teacher_agent.wiki import course_network
from app.teacher_agent.wiki_store import WikiStore

CLASS_ID = "chemie_9b_2026_27"
FIXED_TIME = datetime(2026, 8, 18, 12, 30, tzinfo=UTC)


@pytest.fixture
def wiki(tmp_path: Path) -> WikiStore:
    seed = Path(__file__).resolve().parent.parent / "teacher_wiki"
    root = tmp_path / "teacher_wiki"
    shutil.copytree(seed, root)
    return WikiStore(root=root)


def _document(**changes) -> CourseNetworkDocument:
    values = {
        "class_id": CLASS_ID,
        "route": CurriculumRouteRef(subject="chemie", grade=9, branch="NTG"),
        "updated_at": FIXED_TIME,
        "nodes": [
            LearningBlock(
                id="activation-energy",
                title="Aktivierungsenergie",
                description="Energiebarriere chemischer Reaktionen.",
                curriculum_refs=[
                    CurriculumReference(
                        source_id="lehrplanplus", section_id="reaction-rates"
                    )
                ],
            ),
            LearningBlock(id="reaction-rate", title="Reaktionsgeschwindigkeit"),
        ],
        "edges": [
            NetworkEdge(
                id="activation-builds-rate",
                source_id="activation-energy",
                target_id="reaction-rate",
                relation="builds_on",
                curriculum_refs=[
                    CurriculumReference(
                        source_id="lehrplanplus", section_id="reaction-rates"
                    )
                ],
            )
        ],
    }
    values.update(changes)
    return CourseNetworkDocument(**values)


def test_load_course_network_returns_none_when_class_has_no_adopted_network(wiki):
    assert wiki.load_course_network(CLASS_ID) is None
    assert not (wiki.class_dir(CLASS_ID) / "course_network").exists()


def test_write_course_network_round_trips_canonical_adopted_document(wiki):
    document = _document()

    persisted = wiki.write_course_network(CLASS_ID, document)

    assert persisted == document
    assert wiki.load_course_network(CLASS_ID) == document


def test_write_course_network_uses_canonical_json_with_one_trailing_newline(wiki):
    document = _document()

    wiki.write_course_network(CLASS_ID, document)

    network_path = wiki.class_dir(CLASS_ID) / "course_network" / "network.json"
    assert (
        network_path.read_text(encoding="utf-8")
        == canonical_network_json(document) + "\n"
    )


def test_write_course_network_rejects_mismatched_class_and_proposed_nodes(wiki):
    with pytest.raises(ValueError, match="class_id"):
        wiki.write_course_network(CLASS_ID, _document(class_id="other-class"))

    draft_values = _document().model_dump()
    draft_values["nodes"][0]["status"] = "proposed"
    draft = CourseNetworkDocument.for_draft_seed(**draft_values)
    with pytest.raises(ValueError, match="proposed"):
        wiki.write_course_network(CLASS_ID, draft)

    assert wiki.load_course_network(CLASS_ID) is None


def test_write_course_network_renders_inspectable_overview_with_sources(wiki):
    wiki.write_course_network(CLASS_ID, _document())

    overview = (wiki.class_dir(CLASS_ID) / "course_network" / "overview.md").read_text(
        encoding="utf-8"
    )

    assert "Aktivierungsenergie" in overview
    assert "lehrplanplus#reaction-rates" in overview
    assert "builds_on" in overview
    assert "network.json" not in overview


def test_catalog_and_corpus_include_only_compiled_network_overview(wiki):
    wiki.write_course_network(CLASS_ID, _document())

    pages = wiki.list_class_pages(CLASS_ID)
    corpus = wiki.build_class_relevance_corpus(CLASS_ID)

    overview_path = f"wiki/classes/{CLASS_ID}/course_network/overview.md"
    raw_path = f"wiki/classes/{CLASS_ID}/course_network/network.json"
    assert {page["path"] for page in pages if page["kind"] == "course_network"} == {
        overview_path
    }
    assert overview_path in {doc["path"] for doc in corpus["docs"]}
    assert raw_path not in {doc["path"] for doc in corpus["docs"]}


def test_second_replace_failure_restores_existing_network_and_removes_temporaries(
    wiki, monkeypatch
):
    original = _document(revision=1)
    replacement = _document(revision=2)
    wiki.write_course_network(CLASS_ID, original)
    network_dir = wiki.class_dir(CLASS_ID) / "course_network"
    before = {
        path.name: path.read_text(encoding="utf-8")
        for path in network_dir.iterdir()
        if path.is_file()
    }
    replace_file = course_network._replace_file

    def fail_overview_replace(source: Path, destination: Path) -> None:
        if destination.name == "overview.md":
            raise OSError("injected overview replacement failure")
        replace_file(source, destination)

    monkeypatch.setattr(course_network, "_replace_file", fail_overview_replace)

    with pytest.raises(OSError, match="injected overview"):
        wiki.write_course_network(CLASS_ID, replacement)

    after = {
        path.name: path.read_text(encoding="utf-8")
        for path in network_dir.iterdir()
        if path.is_file()
    }
    assert after == before
    assert not list(network_dir.glob("*.tmp"))


def test_temporary_write_failure_preserves_existing_network_and_removes_temporaries(
    wiki, monkeypatch
):
    original = _document(revision=1)
    wiki.write_course_network(CLASS_ID, original)
    network_dir = wiki.class_dir(CLASS_ID) / "course_network"
    before = {
        path.name: path.read_text(encoding="utf-8")
        for path in network_dir.iterdir()
        if path.is_file()
    }
    write_text = wiki.write_text

    def fail_overview_temporary(path: Path, content: str) -> None:
        if path.name.startswith(".overview.md.") and path.name.endswith(".new.tmp"):
            raise OSError("injected overview temporary write failure")
        write_text(path, content)

    monkeypatch.setattr(wiki, "write_text", fail_overview_temporary)

    with pytest.raises(OSError, match="injected overview temporary"):
        wiki.write_course_network(CLASS_ID, _document(revision=2))

    after = {
        path.name: path.read_text(encoding="utf-8")
        for path in network_dir.iterdir()
        if path.is_file()
    }
    assert after == before
    assert not list(network_dir.glob("*.tmp"))
