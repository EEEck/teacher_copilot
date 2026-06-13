"""Tests for central context limit policy."""

from __future__ import annotations

from app.context_limits import apply_char_limit, get_context_limits


def test_apply_char_limit_zero_means_unlimited():
    long_text = "x" * 50_000
    assert apply_char_limit(long_text, 0) == long_text


def test_apply_char_limit_truncates_when_set():
    text = "abcdefghij"
    out = apply_char_limit(text, 5)
    assert out.startswith("abcde")
    assert "backstop" in out.lower()


def test_defaults_disable_blunt_backstops():
    lim = get_context_limits()
    assert lim.plan_current_chars == 0
    assert lim.plan_instructions_backstop == 0
    assert lim.ingest_context_backstop == 0
    assert lim.ingest_draft_chars == 0
    assert lim.upload_attachment_chars == 0
