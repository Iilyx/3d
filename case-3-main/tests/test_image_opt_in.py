"""Generated fig_* only on explicit Intent/Source opt-in (lexicon)."""

from __future__ import annotations

import pytest

from case3.image_opt_in import wants_generated_images


@pytest.mark.parametrize(
    "intent,source,expected",
    [
        ("Сделай отчёт", "Выручка 2023: 10, 2024: 12, 2025: 15", False),
        ("Сделай отчёт по цифрам", "Офис на Невском, 120 сотрудников", False),
        ("добавь фото здания", "Выручка 10", True),
        ("Сделай отчёт", "Нужен внешний вид продукта на обложке", True),
        ("illustration of the plant", "Q1 revenue 12", True),
        ("Show the appearance of the lobby", "facts…", True),
        ("Сделай отчёт с визуализацией данных", "a=1 b=2", False),
        ("без фото, только цифры", "добавь фото здания в отчёт", False),
        ("no photos please", "photograph the facade", False),
        ("", "Покажи здание штаб-квартиры в начале", True),
        ("Картинку офиса пожалуйста", "числа 1 2 3", True),
        ("Сделай рисунок процесса сборки", "шаги 1–5", True),
    ],
)
def test_wants_generated_images(intent: str, source: str, expected: bool) -> None:
    assert wants_generated_images(intent, source) is expected


def test_composed_ui_block_does_not_fake_opt_in() -> None:
    """Pipeline may pass full Intent; only chat before «Требования UI» counts."""
    intent = (
        "Сделай отчёт по KPI\n\nТребования UI:\n"
        "- до 2 фото/иллюстраций (figures); DEFAULT-ON: …"
    )
    assert wants_generated_images(intent, "Выручка 1 2 3") is False


def test_apply_gen_image_budget_keeps_uploads() -> None:
    from case3.image_opt_in import apply_gen_image_budget

    llm, merge = apply_gen_image_budget(
        images_budget=2,
        n_user=2,
        mode="report",
        opt_in=False,
    )
    assert llm == 0
    assert merge == 2


def test_apply_gen_image_budget_opt_in_preserves_split() -> None:
    from case3.image_opt_in import apply_gen_image_budget

    llm, merge = apply_gen_image_budget(
        images_budget=3,
        n_user=1,
        mode="report",
        opt_in=True,
    )
    assert llm == 2
    assert merge == 3
