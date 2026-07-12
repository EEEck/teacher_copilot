from __future__ import annotations

from types import SimpleNamespace

from pydantic import SecretStr

from tests.eval.plan_judge import score_lesson_plan_with_llm_judge
from tests.eval.model_config import build_deepeval_model, resolve_eval_model


def test_eval_model_defaults_to_gpt_5_4_mini_medium(monkeypatch):
    monkeypatch.delenv("DEEPEVAL_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_FAST_MODEL", raising=False)
    monkeypatch.delenv("DEEPEVAL_REASONING_EFFORT", raising=False)

    config = resolve_eval_model()

    assert config.model == "gpt-5.4-mini"
    assert config.reasoning_effort == "medium"


def test_eval_model_preserves_explicit_and_environment_overrides(monkeypatch):
    monkeypatch.setenv("DEEPEVAL_MODEL", "env-deepeval")
    monkeypatch.setenv("OPENAI_FAST_MODEL", "env-fast")
    monkeypatch.setenv("DEEPEVAL_REASONING_EFFORT", "high")

    assert resolve_eval_model().model == "env-deepeval"
    assert resolve_eval_model().reasoning_effort == "high"
    assert resolve_eval_model("explicit-model").model == "explicit-model"


def test_deepeval_model_receives_reasoning_effort(monkeypatch):
    monkeypatch.delenv("DEEPEVAL_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_FAST_MODEL", raising=False)
    monkeypatch.delenv("DEEPEVAL_REASONING_EFFORT", raising=False)

    model = build_deepeval_model()

    assert model.name == "gpt-5.4-mini"
    assert model.generation_kwargs["reasoning_effort"] == "medium"


def test_plan_judge_uses_shared_model_and_medium_reasoning(monkeypatch):
    captured: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(content='{"pass": true}')
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)]
            )

    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(
                completions=FakeCompletions()
            )

    monkeypatch.setenv("RUN_LLM_PLAN_JUDGE", "1")
    monkeypatch.delenv("DEEPEVAL_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_FAST_MODEL", raising=False)
    monkeypatch.delenv("DEEPEVAL_REASONING_EFFORT", raising=False)
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(openai_api_key=SecretStr("test-key")),
    )

    result = score_lesson_plan_with_llm_judge("# Plan")

    assert result.passed is True
    assert captured["model"] == "gpt-5.4-mini"
    assert captured["reasoning_effort"] == "medium"
    assert "temperature" not in captured
