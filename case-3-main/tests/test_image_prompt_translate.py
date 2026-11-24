"""RU→EN image prompt translation for Liber photo edit."""

from __future__ import annotations

from typing import Any

import pytest

from case3.image_prompt import (
    ImagePromptError,
    ensure_english_image_prompt,
    needs_english_translation,
)


def test_needs_english_when_cyrillic() -> None:
    assert needs_english_translation("сделай свет теплее") is True
    assert needs_english_translation("warmer desk light, soft window") is False
    assert needs_english_translation("") is False


def test_ensure_passthrough_english_skips_llm() -> None:
    calls: list[Any] = []

    class FakeLLM:
        def complete(self, **kwargs: Any) -> str:
            calls.append(kwargs)
            return "SHOULD NOT RUN"

    out = ensure_english_image_prompt(
        "sharp photo of oak desk, daylight",
        llm=FakeLLM(),  # type: ignore[arg-type]
    )
    assert out == "sharp photo of oak desk, daylight"
    assert calls == []


def test_ensure_translates_russian_via_llm() -> None:
    class FakeLLM:
        def complete(self, **kwargs: Any) -> str:
            assert "translate" in (kwargs.get("system") or "").lower()
            assert "теплее" in (kwargs.get("user_text") or "")
            return "make the lighting warmer, soft daylight"

    out = ensure_english_image_prompt(
        "сделай свет теплее, мягкий дневной",
        llm=FakeLLM(),  # type: ignore[arg-type]
    )
    assert "warmer" in out.lower()
    assert not any("\u0400" <= ch <= "\u04FF" for ch in out)


def test_ensure_rejects_empty_translation() -> None:
    class FakeLLM:
        def complete(self, **kwargs: Any) -> str:
            return "   "

    with pytest.raises(ImagePromptError, match="empty|перевод|English"):
        ensure_english_image_prompt("сделай теплее", llm=FakeLLM())  # type: ignore[arg-type]
