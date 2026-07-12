# Evaluator Model Default Design

## Goal

Standardize every evaluation-only fallback on `gpt-5.4-mini` using medium
reasoning.

## Design

- Add a shared evaluator model resolver under `backend/tests/eval/`.
- Default to `gpt-5.4-mini` and `medium`.
- Preserve explicit `DEEPEVAL_MODEL`, `OPENAI_FAST_MODEL`, and explicit function
  model overrides.
- Allow `DEEPEVAL_REASONING_EFFORT` to override the default effort.
- Build DeepEval `GPTModel` instances with `reasoning_effort` in
  `generation_kwargs`.
- Make the direct OpenAI plan judge use the same resolver, omit temperature,
  and pass `reasoning_effort`.

## Verification

Unit tests cover defaults, precedence, effort overrides, and DeepEval model
construction. A repository search must find no legacy evaluator model
fallbacks.
