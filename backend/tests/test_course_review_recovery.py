import asyncio
from types import SimpleNamespace

import pytest
from agents.exceptions import ModelBehaviorError

from app.course_materials.import_service import DocumentReviewer
from app.course_network import review


@pytest.mark.parametrize("reviewer", [DocumentReviewer, review.OpenAICourseNetworkReviewer])
@pytest.mark.parametrize("failure", ["malformed", "schema", "timeout"])
def test_provider_review_failure_is_safe_and_retryable(monkeypatch, reviewer, failure):
    async def broken(*args, **kwargs):
        if failure == "schema":
            return SimpleNamespace(final_output={"private_provider_detail": "invalid"})
        if failure == "timeout":
            raise TimeoutError("private_provider_detail")
        raise ModelBehaviorError("private_provider_detail")
    monkeypatch.setattr(review.Runner, "run", broken)
    with pytest.raises(RuntimeError, match="Try again") as error:
        asyncio.run(reviewer().review("Synthetic chemistry source"))
    assert "private_provider_detail" not in str(error.value)
    async def usable(*args, **kwargs):
        return SimpleNamespace(final_output=review.CourseNetworkReviewJudgement(decision="accept", summary="Usable"))
    monkeypatch.setattr(review.Runner, "run", usable)
    assert asyncio.run(reviewer().review("Synthetic chemistry source")).decision == "accept"
