from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.api import ClassBriefAction, ClassBriefResponse
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.models import ClassBriefOutput
from app.teacher_agent.wiki_store import WikiStore


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class ClassBriefService:
    def __init__(self, wiki: WikiStore, agents: AgentRunner) -> None:
        self.wiki = wiki
        self.agents = agents
        self._cache: dict[str, ClassBriefResponse] = {}

    def _response_from_output(
        self, class_id: str, output: ClassBriefOutput, *, cached: bool
    ) -> ClassBriefResponse:
        return ClassBriefResponse(
            class_id=class_id,
            summary=output.summary,
            recommended_action=ClassBriefAction(
                label=output.recommended_action_label,
                href=output.recommended_action_href,
                rationale=output.recommended_action_rationale,
            ),
            reasons=output.reasons,
            watch_items=output.watch_items,
            source_paths=output.source_paths,
            generated_at=_utc_now(),
            cached=cached,
        )

    async def get_brief(self, class_id: str) -> ClassBriefResponse:
        self.wiki.get_class(class_id)
        cached = self._cache.get(class_id)
        if cached is not None:
            return cached.model_copy(update={"cached": True})
        return self._response_from_output(
            class_id, self.agents._class_brief_fallback(class_id), cached=False
        )

    async def refresh_brief(self, class_id: str) -> ClassBriefResponse:
        self.wiki.get_class(class_id)
        output = await self.agents.class_brief(class_id)
        response = self._response_from_output(class_id, output, cached=False)
        self._cache[class_id] = response
        return response
