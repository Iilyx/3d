"""Intent photo blurb is opt-in, not DEFAULT-ON."""

from __future__ import annotations

from case3.intent_compose import build_intent_from_ui


_PHOTO_DEFAULT_ON = "DEFAULT-ON: если в Source есть место"


def test_forbid_images_empty_figures() -> None:
    text = build_intent_from_ui(
        chat="Отчёт",
        chart_types=[],
        max_charts=0,
        max_images=0,
        forbid_charts=True,
        forbid_images=True,
    )
    assert "без фото" in text.lower() or "figures: []" in text
    assert _PHOTO_DEFAULT_ON not in text


def test_max_images_zero_no_generated_fig() -> None:
    text = build_intent_from_ui(
        chat="Отчёт",
        chart_types=[],
        max_charts=2,
        max_images=0,
        forbid_charts=False,
        forbid_images=False,
    )
    assert "fig_*" in text or "сгенерирован" in text.lower()
    assert _PHOTO_DEFAULT_ON not in text


def test_opt_in_budget_asks_for_photos_not_default_on() -> None:
    text = build_intent_from_ui(
        chat="добавь фото офиса",
        chart_types=[],
        max_charts=2,
        max_images=2,
        forbid_charts=False,
        forbid_images=False,
    )
    assert _PHOTO_DEFAULT_ON not in text
    assert "до 2" in text
    assert "запрошено" in text.lower() or "явн" in text.lower()
