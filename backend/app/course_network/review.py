"""Typed, no-tools LLM review for an exact course-network draft artifact."""

from __future__ import annotations

import asyncio
from typing import Literal, Protocol

from agents import Agent, Runner
from agents.exceptions import ModelBehaviorError
from pydantic import BaseModel, ConfigDict, Field, model_validator, ValidationError

from app.config import Settings, get_settings
from app.course_network.models import CourseNetworkDocument
from app.course_network.prompts import COURSE_NETWORK_REVIEW_SYSTEM
from app.course_network.validation import route_authorized_curriculum_sections
from app.services.workflow_drafts import serialize_structured_artifact

CourseNetworkReviewDecision = Literal["accept", "revise", "block"]
CourseNetworkReviewSeverity = Literal["note", "block"]
COURSE_NETWORK_SOURCE_EVIDENCE_MAX_CHARS = 12000
COURSE_NETWORK_SOURCE_SECTION_MAX_CHARS = 2400


class CourseReviewError(RuntimeError):
    """A review failed without approving or publishing its input."""


async def run_course_review(agent, packet, timeout):
    try:
        result = await asyncio.wait_for(Runner.run(agent, packet, max_turns=1), timeout=timeout)
        return CourseNetworkReviewJudgement.model_validate(result.final_output)
    except (ModelBehaviorError, ValidationError, TimeoutError) as exc:
        raise CourseReviewError("Could not finish the review. Try again. Your proposal is preserved and nothing has been approved.") from exc


class CourseNetworkReviewFinding(BaseModel):
    code: str
    message: str
    severity: CourseNetworkReviewSeverity = "note"
    path: str = ""


class CourseNetworkReviewJudgement(BaseModel):
    """A reviewer conclusion; it deliberately has no artifact rewrite field."""

    model_config = ConfigDict(extra="forbid")

    decision: CourseNetworkReviewDecision
    summary: str
    findings: list[CourseNetworkReviewFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def accepted_reviews_cannot_contain_blocking_findings(self):
        if self.decision == "accept" and any(
            finding.severity == "block" for finding in self.findings
        ):
            raise ValueError("accept review cannot contain blocking findings")
        return self


class CourseNetworkReviewResult(CourseNetworkReviewJudgement):
    artifact_revision: int = Field(ge=0)
    artifact_hash: str = Field(min_length=1)
    deterministic: bool = False


class CourseNetworkReviewer(Protocol):
    async def review(self, packet: str) -> CourseNetworkReviewJudgement: ...


def build_course_network_review_packet(
    wiki, class_id: str, document: CourseNetworkDocument
) -> str:
    references = sorted(
        {
            (reference.source_id, reference.section_id)
            for items in (document.nodes, document.edges)
            for item in items
            for reference in item.curriculum_refs
        }
    )
    authorized = route_authorized_curriculum_sections(wiki, class_id, document.route)
    missing = [reference for reference in references if reference not in authorized]
    if missing:
        raise ValueError("review packet contains unauthorized curriculum references")
    excerpt_limit = min(
        COURSE_NETWORK_SOURCE_SECTION_MAX_CHARS,
        max(1, COURSE_NETWORK_SOURCE_EVIDENCE_MAX_CHARS // max(1, len(references))),
    )
    excerpts = []
    for source_id, section_id in references:
        source, section = authorized[(source_id, section_id)]
        content = section.body.strip()
        excerpts.append(
            {
                "source_id": source_id,
                "section_id": section_id,
                "source_title": source.title,
                "section_title": section.title,
                "authority": source.authority,
                "content_excerpt": content[:excerpt_limit],
                "truncated": len(content) > excerpt_limit,
            }
        )
    payload = {
        "course_network": document.model_dump(mode="json"),
        # Keep the complete dependency set adjacent, so review need not reconstruct
        # multiple prerequisites from a long interleaved edge/source list.
        "prerequisite_index": {
            node.id: sorted(
                edge.target_id
                for edge in document.edges
                if edge.source_id == node.id and edge.relation == "builds_on"
            )
            for node in document.nodes
        },
        "trusted_source_excerpts": excerpts,
    }
    return (
        "# Course-network review packet\n\n```json\n"
        + serialize_structured_artifact(payload)
        + "\n```"
    )


class OpenAICourseNetworkReviewer:
    """One bounded utility-model call, with no tools or durable side effects."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def review(self, packet: str) -> CourseNetworkReviewJudgement:
        from app.teacher_agent.agent import chat_model_settings

        model = self.settings.resolved_utility_model()
        effort = self.settings.resolved_utility_effort()
        model_settings = chat_model_settings(effort, model=model)
        agent = Agent(
            name="KlassenPilot Course Network Reviewer",
            instructions=COURSE_NETWORK_REVIEW_SYSTEM + "\n\n" + packet,
            model=model,
            tools=[],
            output_type=CourseNetworkReviewJudgement,
            **({"model_settings": model_settings} if model_settings else {}),
        )
        return await run_course_review(agent, "Review the supplied course-network seed.", self.settings.agent_timeout_seconds)
