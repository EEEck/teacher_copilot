"""Typed, no-tools LLM review for an exact course-network draft artifact."""

from __future__ import annotations

import asyncio
from typing import Literal, Protocol

from agents import Agent, Runner
from pydantic import BaseModel, Field, model_validator

from app.config import Settings, get_settings
from app.course_network.models import CourseNetworkDocument
from app.course_network.prompts import COURSE_NETWORK_REVIEW_SYSTEM
from app.services.workflow_drafts import serialize_structured_artifact

CourseNetworkReviewDecision = Literal["accept", "revise", "block"]
CourseNetworkReviewSeverity = Literal["note", "block"]


class CourseNetworkReviewFinding(BaseModel):
    code: str
    message: str
    severity: CourseNetworkReviewSeverity = "note"
    path: str = ""


class CourseNetworkReviewJudgement(BaseModel):
    """A reviewer conclusion; it deliberately has no artifact rewrite field."""

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
    async def review(
        self, document: CourseNetworkDocument
    ) -> CourseNetworkReviewJudgement: ...


def build_course_network_review_packet(document: CourseNetworkDocument) -> str:
    return (
        "# Course-network review packet\n\n```json\n"
        + serialize_structured_artifact(document.model_dump(mode="json"))
        + "\n```"
    )


class OpenAICourseNetworkReviewer:
    """One bounded utility-model call, with no tools or durable side effects."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def review(
        self, document: CourseNetworkDocument
    ) -> CourseNetworkReviewJudgement:
        from app.teacher_agent.agent import chat_model_settings

        model = self.settings.resolved_utility_model()
        effort = self.settings.resolved_utility_effort()
        model_settings = chat_model_settings(effort, model=model)
        agent = Agent(
            name="KlassenPilot Course Network Reviewer",
            instructions=COURSE_NETWORK_REVIEW_SYSTEM
            + "\n\n"
            + build_course_network_review_packet(document),
            model=model,
            tools=[],
            output_type=CourseNetworkReviewJudgement,
            **({"model_settings": model_settings} if model_settings else {}),
        )
        result = await asyncio.wait_for(
            Runner.run(agent, "Review the supplied course-network seed.", max_turns=1),
            timeout=self.settings.agent_timeout_seconds,
        )
        if not isinstance(result.final_output, CourseNetworkReviewJudgement):
            raise TypeError("Course-network reviewer returned an invalid result")
        return result.final_output
