"""Deck IR parse + Source-bound number gate + arc rules."""

from __future__ import annotations

import re

import pytest

from case3.slides_ir import (
    SLIDE_LAYOUTS,
    DeckIrError,
    parse_deck_ir,
    scrub_invented_numbers,
)

SOURCE = "Выручка 120 млн в 2024 году. Доля 35%. NPS 42."


def _base_slides(**extra: object) -> list[dict]:
    slides = [
        {"id": "s01", "layout": "title", "title": "Итоги", "subtitle": "2024"},
        {
            "id": "s02",
            "layout": "bullets",
            "title": "Факты",
            "bullets": ["Выручка 120 млн", "Доля 35%"],
        },
        {"id": "s03", "layout": "closing", "title": "Далее", "bullets": ["План"]},
    ]
    if extra:
        # replace middle for custom tests via caller
        pass
    return slides


def test_blank_title_is_dropped_and_closing_may_be_title_only() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {"id": "s02", "layout": "bullets", "title": "", "bullets": ["пусто"]},
                {
                    "id": "s03",
                    "layout": "bullets",
                    "kicker": "Факты",
                    "bullets": ["Выручка 120 млн"],
                },
                {"id": "s04", "layout": "closing", "title": "Берём двоих"},
            ],
        },
        source=SOURCE,
    )
    assert [s["id"] for s in ir["slides"]] == ["s01", "s03", "s04"]
    assert ir["slides"][1]["title"] == "Факты"
    assert ir["slides"][2]["layout"] == "closing"
    assert "bullets" not in ir["slides"][2]


def test_layouts_whitelist() -> None:
    assert "kpi_row" in SLIDE_LAYOUTS
    assert "chart_split" in SLIDE_LAYOUTS
    assert "section" in SLIDE_LAYOUTS
    assert "scorecard" in SLIDE_LAYOUTS
    assert "callout" in SLIDE_LAYOUTS
    assert "table_hero" in SLIDE_LAYOUTS


def test_section_scorecard_callout_table() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {
                    "id": "s01",
                    "layout": "title",
                    "title": "Выручка 120 млн — главный итог",
                    "takeaway": "Рост за счёт доли 35%",
                    "subtitle": "2024",
                },
                {
                    "id": "s02",
                    "layout": "section",
                    "chapter": 1,
                    "title": "Цифры",
                    "subtitle": "Что уже в Source",
                },
                {
                    "id": "s03",
                    "layout": "scorecard",
                    "chapter": 1,
                    "title": "Три рычага",
                    "kpis": [
                        {
                            "label": "Выручка",
                            "value": "120 млн",
                            "delta": "+12%",
                            "status": "up",
                        },
                        {"label": "Доля", "value": "35%", "status": "flat"},
                        {"label": "NPS", "value": "42", "delta": "+3", "status": "up"},
                    ],
                },
                {
                    "id": "s04",
                    "layout": "callout",
                    "chapter": 2,
                    "title": "Определение",
                    "term": "Доля",
                    "definition": "Доля 35% — сегмент в Source.",
                },
                {
                    "id": "s05",
                    "layout": "table_hero",
                    "title": "Сводка",
                    "rows": [
                        ["Метрика", "2024"],
                        ["Выручка", "120 млн"],
                        ["Доля", "35%"],
                    ],
                },
                {"id": "s06", "layout": "closing", "title": "Далее", "bullets": ["План"]},
            ],
        },
        source=SOURCE + " Рост +12%. NPS +3.",
    )
    assert ir["slides"][1]["layout"] == "section"
    assert ir["slides"][1]["chapter"] == 1
    assert ir["slides"][2]["kpis"][0]["delta"] == "+12%"
    assert ir["slides"][3]["term"] == "Доля"
    assert len(ir["slides"][4]["rows"]) == 3
    assert ir["slides"][0].get("takeaway")


def test_long_delta_and_bullet_are_clipped() -> None:
    """Qwen 4B overruns the box. The deck must still parse."""
    long_delta = "план против факта за год"
    long_bullet = "А" * 180
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {
                    "id": "s02",
                    "layout": "scorecard",
                    "title": "Цифры",
                    "kpis": [
                        {"label": "Выручка", "value": "120 млн", "delta": long_delta},
                    ],
                },
                {
                    "id": "s03",
                    "layout": "bullets",
                    "title": "Факты",
                    "bullets": ["Доля 35%", "NPS 42", long_bullet, "x", "y", "z"],
                },
                {"id": "s04", "layout": "closing", "title": "Далее", "bullets": ["План"]},
            ],
        },
        source=SOURCE,
    )
    delta = ir["slides"][1]["kpis"][0]["delta"]
    assert len(delta) <= 16
    assert delta.endswith("…")
    bullet = ir["slides"][2]["bullets"][2]
    assert len(bullet) <= 140
    assert bullet.endswith("…")
    assert len(ir["slides"][2]["bullets"]) == 5


def test_slide_table_keeps_fourteen_rows_and_eight_columns() -> None:
    labels = [
        "Минская",
        "Гомельская",
        "Брестская",
        "Витебская",
        "Гродненская",
        "Могилевская",
        "Минск",
        "Молодечно",
        "Борисов",
        "Солигорск",
        "Барановичи",
        "Пинск",
        "Орша",
        "Лида",
    ]
    header = ["Область", "Факт", "План", "Доля", "Год", "Ранг", "Темп", "Итог", "Лишнее"]
    data = [
        [name, "да", "да", "да", "да", "да", "да", "край", "нет"] for name in labels
    ]
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {
                    "id": "s02",
                    "layout": "table_hero",
                    "title": "Области",
                    "rows": [header, *data],
                },
                {"id": "s03", "layout": "closing", "title": "Далее", "bullets": ["План"]},
            ],
        },
        source=SOURCE,
    )
    rows = ir["slides"][1]["rows"]
    assert len(rows) == 14
    assert rows[-1][0] == "Орша"
    assert all(row[0] != "Лида" for row in rows)
    assert len(rows[0]) == 8
    assert rows[0][-1] == "Итог"
    assert rows[1][-1] == "край"


def test_ragged_table_rows_are_padded() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {
                    "id": "s02",
                    "layout": "table_hero",
                    "title": "Сводка",
                    "rows": [
                        ["Метрика", "2024", "План"],
                        ["Выручка", "120 млн"],
                        ["Доля", "35%", "лишнее", "ещё"],
                    ],
                },
                {"id": "s03", "layout": "closing", "title": "Далее", "bullets": ["План"]},
            ],
        },
        source=SOURCE,
    )
    rows = ir["slides"][1]["rows"]
    assert [len(r) for r in rows] == [3, 3, 3]
    assert rows[1][2] == "—"
    assert rows[2][2] == "лишнее"


def test_accepts_arc_title_bullets_closing() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "aspect": "16:9",
            "palette": "atelier",
            "language": "ru",
            "slides": _base_slides(),
        },
        source=SOURCE,
    )
    assert len(ir["slides"]) == 3
    assert ir["slides"][0]["layout"] == "title"
    assert ir["slides"][-1]["layout"] == "closing"


def test_rejects_unknown_layout() -> None:
    with pytest.raises(DeckIrError, match="layout"):
        parse_deck_ir(
            {
                "version": 1,
                "palette": "atelier",
                "slides": [
                    {"id": "s01", "layout": "title", "title": "T"},
                    {"id": "s02", "layout": "agenda", "title": "X"},
                    {"id": "s03", "layout": "closing", "title": "C", "bullets": ["a"]},
                ],
            },
            source=SOURCE,
        )


def test_rejects_invented_number() -> None:
    with pytest.raises(DeckIrError, match="number|Source|source"):
        parse_deck_ir(
            {
                "version": 1,
                "palette": "atelier",
                "slides": [
                    {"id": "s01", "layout": "title", "title": "T"},
                    {
                        "id": "s02",
                        "layout": "bullets",
                        "title": "X",
                        "bullets": ["Выручка 999 млрд"],
                    },
                    {"id": "s03", "layout": "closing", "title": "C", "bullets": ["a"]},
                ],
            },
            source=SOURCE,
        )


def test_rejects_three_consecutive_bullets() -> None:
    with pytest.raises(DeckIrError, match="consecutive"):
        parse_deck_ir(
            {
                "version": 1,
                "palette": "atelier",
                "slides": [
                    {"id": "s01", "layout": "title", "title": "T"},
                    {
                        "id": "s02",
                        "layout": "bullets",
                        "title": "A",
                        "bullets": ["Выручка 120 млн"],
                    },
                    {
                        "id": "s03",
                        "layout": "bullets",
                        "title": "B",
                        "bullets": ["Доля 35%"],
                    },
                    {
                        "id": "s04",
                        "layout": "bullets",
                        "title": "C",
                        "bullets": ["NPS 42"],
                    },
                    {"id": "s05", "layout": "closing", "title": "Z", "bullets": ["ok"]},
                ],
            },
            source=SOURCE,
        )


def test_rejects_missing_closing() -> None:
    with pytest.raises(DeckIrError, match="closing"):
        parse_deck_ir(
            {
                "version": 1,
                "palette": "atelier",
                "slides": [
                    {"id": "s01", "layout": "title", "title": "T"},
                    {
                        "id": "s02",
                        "layout": "bullets",
                        "title": "A",
                        "bullets": ["Выручка 120 млн"],
                    },
                    {
                        "id": "s03",
                        "layout": "bullets",
                        "title": "B",
                        "bullets": ["Доля 35%"],
                    },
                ],
            },
            source=SOURCE,
        )


def test_kpi_row_ok() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "T"},
                {
                    "id": "s02",
                    "layout": "kpi_row",
                    "title": "KPI",
                    "kpis": [
                        {"label": "Выручка", "value": "120 млн", "hint": "2024"},
                        {"label": "Доля", "value": "35%"},
                        {"label": "NPS", "value": "42"},
                    ],
                },
                {"id": "s03", "layout": "closing", "title": "C", "bullets": ["Далее"]},
            ],
        },
        source=SOURCE,
    )
    assert ir["slides"][1]["layout"] == "kpi_row"
    assert len(ir["slides"][1]["kpis"]) == 3


def test_chart_split_ok() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "ocean",
            "slides": [
                {"id": "s01", "layout": "title", "title": "T"},
                {
                    "id": "s02",
                    "layout": "chart_split",
                    "title": "Доля 35%",
                    "chart_id": "cht_01",
                    "body": "Ключевой показатель 2024",
                    "bullets": ["Доля 35%"],
                },
                {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
            ],
        },
        source=SOURCE,
    )
    assert ir["slides"][1]["chart_id"] == "cht_01"


def test_normalize_auto_palette_to_atelier() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "auto",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Hello"},
                {
                    "id": "s02",
                    "layout": "bullets",
                    "title": "A",
                    "bullets": ["no digits here"],
                },
                {"id": "s03", "layout": "closing", "title": "Bye", "bullets": ["x"]},
            ],
        },
        source=SOURCE,
    )
    assert ir["palette"] == "atelier"


def test_scrub_invented_numbers_then_parse() -> None:
    raw = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги 2024"},
            {
                "id": "s02",
                "layout": "scorecard",
                "title": "KPI",
                "takeaway": "Средняя — 5.1 °C",
                "kpis": [
                    {"label": "Выручка", "value": "120"},
                    {"label": "Фейк", "value": "5.1°C"},
                    {"label": "Пусто", "value": "999%"},
                ],
            },
            {
                "id": "s03",
                "layout": "closing",
                "title": "Далее",
                "bullets": [
                    "Держим 120",
                    "Минус 999 тыс. чел.",
                    "Доля 999%",
                ],
            },
        ],
    }
    with pytest.raises(DeckIrError, match="number"):
        parse_deck_ir(raw, source=SOURCE)
    healed = scrub_invented_numbers(raw, source=SOURCE)
    assert healed["slides"][1]["kpis"] == [{"label": "Выручка", "value": "120"}]
    assert "5.1" not in (healed["slides"][1].get("takeaway") or "")
    assert "°C" not in (healed["slides"][1].get("takeaway") or "")
    bullets = healed["slides"][2]["bullets"]
    assert bullets[0] == "Держим 120"
    assert all("тыс" not in b.lower() or "120" in b for b in bullets)
    assert not any(re.search(r"\b999\b", b) for b in bullets)
    deck = parse_deck_ir(healed, source=SOURCE)
    assert len(deck["slides"]) == 3


def test_scrub_unavailable_chart_id_demotes_to_callout() -> None:
    from case3.slides_ir import scrub_unavailable_media

    raw = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги 2024"},
            {
                "id": "s02",
                "layout": "chart_hero",
                "title": "Динамика",
                "chart_id": "cht_01",
                "caption": "Выручка 120",
            },
            {"id": "s03", "layout": "closing", "title": "Далее", "bullets": ["Держим 120"]},
        ],
    }
    with pytest.raises(DeckIrError, match="chart_id"):
        parse_deck_ir(raw, source=SOURCE, allowed_media_ids=frozenset())
    healed = scrub_unavailable_media(raw, allowed_media_ids=frozenset())
    assert healed["slides"][1]["layout"] == "callout"
    assert "chart_id" not in healed["slides"][1]
    deck = parse_deck_ir(healed, source=SOURCE, allowed_media_ids=frozenset())
    assert deck["slides"][1]["layout"] == "callout"


def test_a_table_cell_is_not_a_slide_index():
    raw = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги", "kicker": "01"},
            {
                "id": "s02",
                "layout": "table_hero",
                "title": "Коды",
                "rows": [["Код", "Сумма"], ["07", "12"]],
            },
            {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
        ],
    }
    with pytest.raises(DeckIrError, match="07|12"):
        parse_deck_ir(raw, source="Касса 20.")
    healed = scrub_invented_numbers(raw, source="Касса 20.")
    assert healed["slides"][0]["kicker"] == "01"
    flat = " ".join(
        cell
        for row in healed["slides"][1].get("rows") or []
        for cell in row
    )
    assert "07" not in flat
    assert "12" not in flat


def test_scrub_demotes_broken_table_hero() -> None:
    raw = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги"},
            {
                "id": "s02",
                "layout": "table_hero",
                "title": "Таблица",
                "rows": [
                    ["Метрика", "Значение"],
                    ["Фейк", "5.1"],
                    ["Ещё", "999"],
                ],
            },
            {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
        ],
    }
    healed = scrub_invented_numbers(raw, source=SOURCE)
    assert healed["slides"][1]["layout"] == "bullets"
    deck = parse_deck_ir(healed, source=SOURCE)
    # Title-echo bullets (only remnant after scrub) heal to section, not empty bullets.
    assert deck["slides"][1]["layout"] == "section"


def test_scrub_invented_table_cell_then_parse() -> None:
    """Win desk: invented ``979,72`` → scrub ``—`` → clean ate dash → rows[i][j] required."""
    raw = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги"},
            {
                "id": "s02",
                "layout": "table_hero",
                "title": "Сводка",
                "rows": [
                    ["Метрика", "Факт", "План", "Запас"],
                    ["Выручка", "120", "35%", "979,72"],
                ],
            },
            {"id": "s03", "layout": "closing", "title": "Далее", "bullets": ["План 120"]},
        ],
    }
    with pytest.raises(DeckIrError, match="979,72"):
        parse_deck_ir(raw, source=SOURCE)
    healed = scrub_invented_numbers(raw, source=SOURCE)
    assert healed["slides"][1]["layout"] == "table_hero"
    assert healed["slides"][1]["rows"][1][3] == "—"
    deck = parse_deck_ir(healed, source=SOURCE)
    assert deck["slides"][1]["rows"][1][3] == "—"


def test_empty_table_cell_soft_fills() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {
                    "id": "s02",
                    "layout": "table_hero",
                    "title": "Сводка",
                    "rows": [
                        ["Метрика", "A", "B", "C"],
                        ["Выручка", "120", "35%", ""],
                        ["Доля", "35%", None, "120"],
                    ],
                },
                {"id": "s03", "layout": "closing", "title": "Далее", "bullets": ["План"]},
            ],
        },
        source=SOURCE,
    )
    rows = ir["slides"][1]["rows"]
    assert rows[1][3] == "—"
    assert rows[2][2] == "—"


def test_number_not_allowed_as_substring_of_larger() -> None:
    with pytest.raises(DeckIrError, match="number"):
        parse_deck_ir(
            {
                "version": 1,
                "palette": "atelier",
                "slides": [
                    {"id": "s01", "layout": "title", "title": "Итоги"},
                    {
                        "id": "s02",
                        "layout": "bullets",
                        "title": "X",
                        "bullets": ["Убыль −38 чел."],
                    },
                    {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
                ],
            },
            source="Естественная убыль −38000 чел. Выручка 120.",
            allowed_number_strings=frozenset({"38000", "120"}),
        )


def test_title_echo_bullets_heal_to_section() -> None:
    """LLM often emits bullets that only repeat the title — empty-looking slide."""
    deck = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {
                    "id": "s02",
                    "layout": "bullets",
                    "title": "Этапы процесса данных",
                    "kicker": "Этапы",
                    "bullets": ["Этапы процесса данных"],
                },
                {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
            ],
        },
        source=SOURCE,
    )
    mid = deck["slides"][1]
    assert mid["layout"] == "section"
    assert mid["title"] == "Этапы процесса данных"
    assert mid.get("subtitle") == "Этапы"
    assert "bullets" not in mid


def _region_deck(body: str) -> dict:
    return {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Области"},
            {
                "id": "s02",
                "layout": "card_row",
                "title": "Сравнение",
                "cards": [
                    {"title": "Минская", "body": body},
                    {"title": "Гомельская", "body": "Рядом, без новой цифры."},
                ],
            },
            {"id": "s03", "layout": "closing", "title": "Итог", "bullets": ["ok"]},
        ],
    }


def test_card_row_rejects_a_number_that_is_not_in_source() -> None:
    with pytest.raises(DeckIrError, match="999"):
        parse_deck_ir(
            _region_deck("Собрано 999 тысяч."),
            source="Минская область | 105 865,2",
        )


def test_card_row_keeps_a_spaced_sum_from_source() -> None:
    ir = parse_deck_ir(
        _region_deck("Собрано 105 865,2."),
        source="Минская область | 105 865,2",
    )
    assert ir["slides"][1]["cards"][0]["body"] == "Собрано 105 865,2."


def test_spaced_cell_on_the_slide_matches_the_spaced_source() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {
                    "id": "s02",
                    "layout": "scorecard",
                    "title": "Области",
                    "kpis": [{"label": "Минская", "value": "105 865,2"}],
                },
                {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
            ],
        },
        source="Минская область | 105 865,2",
    )
    assert ir["slides"][1]["kpis"][0]["value"] == "105 865,2"


def test_spaced_thousands_allowed_when_compact_in_source() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {
                    "id": "s02",
                    "layout": "scorecard",
                    "title": "KPI",
                    "kpis": [{"label": "Выручка", "value": "9 330"}],
                },
                {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
            ],
        },
        source="Население 9330 тыс. Выручка 120 млн.",
        allowed_number_strings=frozenset({"9330", "120"}),
    )
    assert ir["slides"][1]["kpis"][0]["value"] == "9 330"


def test_zero_padded_kicker_chrome_allowed() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги", "kicker": "01"},
                {
                    "id": "s02",
                    "layout": "section",
                    "title": "Факты",
                    "kicker": "02",
                    "body": "Выручка 120 млн",
                },
                {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
            ],
        },
        source=SOURCE,
    )
    assert ir["slides"][0]["kicker"] == "01"


def test_bare_slide_index_chrome_1_to_12_allowed() -> None:
    """A kicker that is only the index stays. A sentence that uses 1–24 does not."""
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги", "kicker": "3"},
                {
                    "id": "s02",
                    "layout": "bullets",
                    "title": "Направления",
                    "bullets": ["Фокус из текста", "Выручка 120"],
                },
                {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
            ],
        },
        source=SOURCE,
    )
    assert ir["slides"][0]["kicker"] == "3"
    with pytest.raises(DeckIrError, match="3"):
        parse_deck_ir(
            {
                "version": 1,
                "palette": "atelier",
                "slides": [
                    {"id": "s01", "layout": "title", "title": "Итоги"},
                    {
                        "id": "s02",
                        "layout": "bullets",
                        "title": "Направления",
                        "bullets": ["3 фокуса из текста"],
                    },
                    {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
                ],
            },
            source=SOURCE,
        )
    with pytest.raises(DeckIrError, match="5000"):
        parse_deck_ir(
            {
                "version": 1,
                "palette": "atelier",
                "slides": [
                    {"id": "s01", "layout": "title", "title": "Итоги"},
                    {
                        "id": "s02",
                        "layout": "bullets",
                        "title": "X",
                        "bullets": ["Бюджет 5000"],
                    },
                    {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
                ],
            },
            source=SOURCE,
        )


def test_bare_index_13_to_24_is_chrome_25_is_not() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги", "kicker": "18"},
                {
                    "id": "s02",
                    "layout": "section",
                    "title": "Глава",
                },
                {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
            ],
        },
        source=SOURCE,
    )
    assert ir["slides"][0]["kicker"] == "18"
    with pytest.raises(DeckIrError, match="24"):
        parse_deck_ir(
            {
                "version": 1,
                "palette": "atelier",
                "slides": [
                    {"id": "s01", "layout": "title", "title": "Итоги"},
                    {
                        "id": "s02",
                        "layout": "section",
                        "title": "Глава",
                        "subtitle": "Блок 24",
                    },
                    {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
                ],
            },
            source=SOURCE,
        )
    with pytest.raises(DeckIrError, match="25"):
        parse_deck_ir(
            {
                "version": 1,
                "palette": "atelier",
                "slides": [
                    {"id": "s01", "layout": "title", "title": "Итоги"},
                    {
                        "id": "s02",
                        "layout": "bullets",
                        "title": "X",
                        "bullets": ["Шаг 25"],
                    },
                    {"id": "s03", "layout": "closing", "title": "C", "bullets": ["ok"]},
                ],
            },
            source=SOURCE,
        )


def test_parse_accepts_sixteen_slide_deck() -> None:
    layouts = ["section", "callout", "bullets"]
    slides: list[dict] = [
        {"id": "s01", "layout": "title", "title": "Итоги", "subtitle": "2024"}
    ]
    for i in range(14):
        layout = layouts[i % len(layouts)]
        sid = f"s{i + 2:02d}"
        if layout == "section":
            slides.append({"id": sid, "layout": "section", "title": f"Часть {'абвгдежзиклмно'[i]}"})
        elif layout == "callout":
            slides.append(
                {
                    "id": sid,
                    "layout": "callout",
                    "title": "Тезис",
                    "term": "Факт",
                    "definition": "Выручка 120 млн",
                }
            )
        else:
            slides.append(
                {
                    "id": sid,
                    "layout": "bullets",
                    "title": "Детали",
                    "bullets": ["Доля 35%"],
                }
            )
    slides.append(
        {"id": "s16", "layout": "closing", "title": "Далее", "bullets": ["План"]}
    )
    assert len(slides) == 16
    ir = parse_deck_ir(
        {"version": 1, "palette": "atelier", "slides": slides}, source=SOURCE
    )
    assert ir["slides"][0]["layout"] == "title"
    assert ir["slides"][-1]["layout"] == "closing"
    assert len(ir["slides"]) < 16


def test_multiline_title_takeaway_keeps_hero_metric_pairs() -> None:
    """Newline-separated ``VALUE — label`` lines must survive whitespace
    normalization so the cover still shows one KPI card per metric."""
    from case3.slides_html import parse_hero_metrics

    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {
                    "id": "s01",
                    "layout": "title",
                    "title": "Итоги",
                    "takeaway": "120 млн — Выручка\n35% — Доля\n42 — NPS",
                },
                *_base_slides()[1:],
            ],
        },
        source=SOURCE,
    )
    takeaway = ir["slides"][0]["takeaway"]
    assert parse_hero_metrics(takeaway) == [
        ("120 млн", "Выручка"),
        ("35%", "Доля"),
        ("42", "NPS"),
    ]


def test_parse_deck_ir_preserves_bullet_node_map() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "T"},
                {
                    "id": "s02",
                    "layout": "media_split",
                    "title": "Схема процесса",
                    "media_id": "dia_01",
                    "bullets": ["Первый шаг", "Второй шаг"],
                    "bullet_node_map": {"0": "A", "1": "B"},
                },
                {"id": "s03", "layout": "closing", "title": "C", "bullets": ["Итог"]},
            ],
        },
        source="Схема процесса",
        allowed_media_ids={"dia_01"},
    )
    assert ir["slides"][1]["bullet_node_map"] == {"0": "A", "1": "B"}


def test_clean_source_placeholders() -> None:
    from case3.slides_ir import clean_source_placeholders

    assert clean_source_placeholders("Источник — Source") == ""
    assert clean_source_placeholders("Источник: из Source") == ""
    assert clean_source_placeholders("Цифры из Source") == ""
    assert clean_source_placeholders("Только цифры из Source") == ""
    assert clean_source_placeholders("n только из Source") == "n"
    assert (
        clean_source_placeholders("Выручка 100 млн | Источник — Source")
        == "Выручка 100 млн"
    )
    assert (
        clean_source_placeholders("Выручка 100 млн (из Source)")
        == "Выручка 100 млн"
    )
    assert clean_source_placeholders("DATA") == ""
    assert clean_source_placeholders("Источник") == ""
    assert clean_source_placeholders("Источник: опрос") == "Источник: опрос"


def test_parse_deck_ir_strips_source_placeholders_from_slides() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {
                    "id": "s01",
                    "layout": "title",
                    "title": "Итоги года",
                    "subtitle": "Только цифры из Source",
                },
                {
                    "id": "s02",
                    "layout": "chart_hero",
                    "title": "Динамика выручки",
                    "kicker": "DATA",
                    "caption": "Источник — Source",
                    "takeaway": "Цифры из Source",
                    "chart_id": "cht_01",
                },
                {
                    "id": "s03",
                    "layout": "bullets",
                    "title": "Факторы",
                    "bullets": ["Выручка 120 | Источник: Source"],
                },
                {"id": "s04", "layout": "closing", "title": "C", "bullets": ["Итог"]},
            ],
        },
        source="Выручка 120",
        allowed_media_ids={"cht_01"},
    )
    s1 = ir["slides"][0]
    assert "subtitle" not in s1
    s2 = ir["slides"][1]
    assert "kicker" not in s2
    assert "caption" not in s2
    assert "takeaway" not in s2
    assert s2["title"] == "Динамика выручки"
    s3 = ir["slides"][2]
    assert s3["bullets"] == ["Выручка 120"]


def test_parse_deck_ir_accepts_negative_delta_magnitude_and_verifiable_math() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "Исполнение бюджета"},
                {
                    "id": "s02",
                    "layout": "kpi_row",
                    "title": "Ключевые цифры",
                    "kpis": [
                        {"label": "Дефицит", "value": "656", "status": "down"},
                        {"label": "Итого факт", "value": "18044", "status": "up"},
                    ],
                },
                {"id": "s03", "layout": "closing", "title": "Вывод", "bullets": ["Дефицит 656"]},
            ],
        },
        source=(
            "| Регион | План | Факт | Откл. |\n"
            "| --- | --- | --- | --- |\n"
            "| Гомель | 8200 | 7544 | -656 |\n"
            "| Минск | 10000 | 10500 | +500 |\n"
        ),
    )
    assert ir["slides"][1]["kpis"][0]["value"] == "656"
    assert ir["slides"][1]["kpis"][1]["value"] == "18044"


def test_scrub_invented_numbers_preserves_spaced_thousands_with_decimals_and_allows_derived_means() -> None:
    source = (
        "| Округ | Инспекция | План | Факт | Вып., % |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| Центральный | Минская | 180 000,0 | 192 100,0 | 106,7% |\n"
        "| Восточный | Могилёвская | 120 000,0 | 117 600,0 | 98,0% |\n"
        "| Южный | Гомельская | 200 000,0 | 218 400,0 | 109,2% |\n"
    )
    raw = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги февраля"},
            {
                "id": "s02",
                "layout": "table_hero",
                "title": "Инспекции",
                "rows": [
                    ["Инспекция", "План", "Факт", "Откл."],
                    ["Минская", "180 000,0", "192 100,0", "+12 100,0"],
                    ["Могилёвская", "120 000,0", "117 600,0", "-2 400,0"],
                ],
            },
            {
                "id": "s03",
                "layout": "bullets",
                "title": "Сводка",
                "bullets": [
                    "Среднее выполнение по инспекциям составило 104,6% (около 105%)",
                    "Выдуманный показатель 999999 удаляется",
                ],
            },
            {"id": "s04", "layout": "closing", "title": "Решения", "bullets": ["Контроль Могилёвской 117 600,0"]},
        ],
    }
    healed = scrub_invented_numbers(raw, source=source)
    ir = parse_deck_ir(healed, source=source)
    assert ir["slides"][1]["rows"][1] == ["Минская", "180 000,0", "192 100,0", "+12 100,0"]
    assert "999999" not in str(ir)



