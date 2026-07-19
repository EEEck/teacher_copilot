from pathlib import Path
import asyncio

from pydantic import SecretStr

from app.config import Settings
from app.schemas.api import ChatMessage
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.class_discussion_state import ClassDiscussionRuntime
from app.teacher_agent.citation_presentation import (
    render_reviewed_source_footer,
    validate_discussion_source_presentation,
)
from app.teacher_agent.models import ClassDiscussionTurnOutput
from app.teacher_agent.wiki_store import WikiStore


CLASS_ID = "chemie_9b_2026_27"
_WIKI_ROOT = Path(__file__).resolve().parent.parent / "teacher_wiki"
_ATOMIC_SOURCE = [
    {"source_id": "by-lehrplanplus-chemie-9-ntg", "section_id": "c9_atombau"}
]


def test_discussion_rejects_model_written_source_urls_and_unread_citations():
    reply = (
        "According to the official curriculum.\n"
        "Source: by-lehrplanplus-chemie-9-ntg#c9_molekuele\n"
        "https://www.lehrplanplus.bayern.de/fachlehrplan/gymnasium/9/chemie/ch-ntg"
    )

    errors = validate_discussion_source_presentation(reply, _ATOMIC_SOURCE)

    assert "was not read in this session" in " ".join(errors)
    assert any("source URLs" in error for error in errors)


def test_discussion_footer_uses_reviewed_summary_label_and_registry_link():
    footer = render_reviewed_source_footer(
        WikiStore(root=_WIKI_ROOT), CLASS_ID, _ATOMIC_SOURCE
    )

    assert "KlassenPilot reviewed English summary" in footer
    assert "LehrplanPLUS Chemie 9 NTG" in footer
    assert "Atombau und gekürztes Periodensystem" in footer
    assert "https://www.lehrplanplus.bayern.de/fachlehrplan/gymnasium/9/chemie/ch-ntg" in footer


def test_discussion_retries_invalid_citation_then_appends_backend_footer(
    wiki, monkeypatch
):
    runner = AgentRunner(
        settings=Settings(openai_api_key=SecretStr("test-key")), wiki=wiki
    )
    runtime = ClassDiscussionRuntime()
    runtime.record_source_read("by-lehrplanplus-chemie-9-ntg", "c9_atombau")
    inputs: list[str] = []
    outputs = iter(
        [
            ClassDiscussionTurnOutput(
                reply=(
                    "According to the official curriculum, use particle diagrams.\n"
                    "Source: by-lehrplanplus-chemie-9-ntg#c9_atombau\n"
                    "https://example.invalid/source"
                )
            ),
            ClassDiscussionTurnOutput(
                reply=(
                    "Use particle diagrams first. KlassenPilot reviewed English summary: "
                    "students connect experimental findings to atomic models."
                )
            ),
        ]
    )

    async def fake_run(_agent, user_input: str):
        inputs.append(user_input)
        return next(outputs)

    monkeypatch.setattr(runner, "_run_structured", fake_run)

    reply = asyncio.run(
        runner.discuss_chat(
            CLASS_ID,
            [ChatMessage(role="user", content="What does the curriculum say?")],
            runtime=runtime,
        )
    )

    assert len(inputs) == 2
    assert "Citation presentation correction" in inputs[1]
    assert "https://example.invalid/source" not in reply
    assert "KlassenPilot reviewed English summary" in reply
    assert "Official German source" in reply


def test_discussion_uses_footer_after_second_invalid_citation(wiki, monkeypatch):
    runner = AgentRunner(
        settings=Settings(openai_api_key=SecretStr("test-key")), wiki=wiki
    )
    runtime = ClassDiscussionRuntime()
    runtime.record_source_read("by-lehrplanplus-chemie-9-ntg", "c9_atombau")
    inputs: list[str] = []
    outputs = iter(
        [
            ClassDiscussionTurnOutput(
                reply="Source: by-lehrplanplus-chemie-9-ntg#c9_atombau\nhttps://example.invalid/one"
            ),
            ClassDiscussionTurnOutput(
                reply="Source: by-lehrplanplus-chemie-9-ntg#c9_atombau\nhttps://example.invalid/two"
            ),
        ]
    )

    async def fake_run(_agent, user_input: str):
        inputs.append(user_input)
        return next(outputs)

    monkeypatch.setattr(runner, "_run_structured", fake_run)

    reply = asyncio.run(
        runner.discuss_chat(
            CLASS_ID,
            [ChatMessage(role="user", content="What does the curriculum say?")],
            runtime=runtime,
        )
    )

    assert len(inputs) == 2
    assert "example.invalid" not in reply
    assert "## Sources consulted" in reply
    assert "Official German source" in reply
