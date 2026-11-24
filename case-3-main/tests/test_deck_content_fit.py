"""Content fit: one fact per slide, real sides, written numbers, one question."""

from __future__ import annotations

import json

from case3.slides_ir import parse_deck_ir

BOARD = (
    "сделай презентацию для совета директоров слайдов 13. "
    "выручка 18,4 млн при плане 19. к прошлому году +53%. "
    "новых продаж 1,9 млн, это 86% плана. кэш 20,4 млн, хватает на 24 месяца. "
    "nrr 117%. вопрос нанимать двух продажников или нет"
)


def _wrap(slides: list[dict]) -> dict:
    return {"version": 1, "palette": "board", "slides": slides}


def test_body_that_repeats_the_title_is_dropped() -> None:
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Неделя"},
                {
                    "id": "s02",
                    "layout": "bullets",
                    "title": "Поиск хороший",
                    "body": "Поиск хороший",
                    "subtitle": "Поиск хороший",
                    "takeaway": "Баннеры плохие",
                    "bullets": ["Поиск хороший", "Отдача 4,1."],
                },
                {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["Поиск"]},
            ]
        ),
        source="поиск хороший отдача 4,1 баннеры плохие",
    )
    slide = deck["slides"][1]
    assert "body" not in slide
    assert "subtitle" not in slide
    assert slide["takeaway"] == "Баннеры плохие"
    assert slide["bullets"] == ["Отдача 4,1."]


def test_thousands_word_allows_the_absolute_form() -> None:
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Неделя"},
                {
                    "id": "s02",
                    "layout": "bullets",
                    "title": "Расход",
                    "bullets": ["Потратили 86000."],
                },
                {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["Поиск"]},
            ]
        ),
        source="за неделю потратили 86 тысяч, отдача 4,1",
    )
    assert "86000" in deck["slides"][1]["bullets"][0]


def test_bare_fragment_does_not_match_a_larger_integer() -> None:
    import pytest
    from case3.slides_ir import DeckIrError

    with pytest.raises(DeckIrError):
        parse_deck_ir(
            _wrap(
                [
                    {"id": "s01", "layout": "title", "title": "Неделя"},
                    {
                        "id": "s02",
                        "layout": "bullets",
                        "title": "Расход",
                        "bullets": ["Потратили 86."],
                    },
                    {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["Поиск"]},
                ]
            ),
            source="потратили 86000 без слова тысяч",
        )


def test_empty_section_and_echo_slide_drop() -> None:
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Совет", "subtitle": "Выручка 18,4 млн"},
                {
                    "id": "s02",
                    "layout": "section",
                    "title": "Где мы сейчас",
                    "subtitle": "Факты без добавлений",
                },
                {
                    "id": "s03",
                    "layout": "bullets",
                    "title": "Выручка",
                    "bullets": ["Выручка 18,4 млн при плане 19."],
                },
                {
                    "id": "s04",
                    "layout": "bullets",
                    "title": "То же",
                    "bullets": ["Выручка 18,4 млн при плане 19."],
                },
                {"id": "s05", "layout": "closing", "title": "Дальше", "bullets": ["Решение"]},
            ]
        ),
        source=BOARD,
    )
    ids = [s["id"] for s in deck["slides"]]
    assert "s02" not in ids
    assert "s04" not in ids
    assert ids[0] == "s01" and ids[-1] == "s05"


def test_hire_kickers_are_one_question() -> None:
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Совет"},
                {
                    "id": "s02",
                    "layout": "compare",
                    "title": "Нанять vs Не нанимать: ключевые ставки",
                    "cards": [
                        {
                            "title": "Два продавца в штат",
                            "kicker": "НАНЯТЬ",
                            "body": "Касса 20,4 на 24 месяца.",
                        },
                        {
                            "title": "Статус команды",
                            "kicker": "НЕ НАНИМАТЬ",
                            "body": "План выручки 19.",
                        },
                    ],
                },
                {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["Решение"]},
            ]
        ),
        source="нанять двух продавцов или нет. касса 20,4 на 24 месяца. план выручки 19.",
    )
    mid = deck["slides"][1]
    assert mid["layout"] == "callout"
    assert "cards" not in mid


def test_bare_number_does_not_grow_a_unit() -> None:
    source = "план выручки 19, факт 18,4. новые продажи 1,9."
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "План"},
                {
                    "id": "s02",
                    "layout": "scorecard",
                    "title": "Выручка",
                    "kpis": [
                        {
                            "label": "План",
                            "value": "19",
                            "hint": "План выручки составляет 19 млн",
                        }
                    ],
                },
                {
                    "id": "s03",
                    "layout": "closing",
                    "title": "Итог",
                    "bullets": ["Факт выручки — 18,4 млн", "Новые продажи — 1,9 млн"],
                },
            ]
        ),
        source=source,
    )
    blob = json.dumps(deck["slides"], ensure_ascii=False)
    assert "млн" not in blob
    assert "19" in blob and "18,4" in blob


def test_closing_cannot_invent_a_decision() -> None:
    source = (
        "нанять двух продавцов или нет. касса 20,4 на 24 месяца. "
        "план выручки 19, факт 18,4."
    )
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Совет"},
                {
                    "id": "s02",
                    "layout": "callout",
                    "title": "Нанять двух продавцов или нет",
                    "term": "Вопрос",
                    "definition": "Нанять двух продавцов?",
                },
                {
                    "id": "s03",
                    "layout": "callout",
                    "title": "Вопрос",
                    "term": "Вопрос",
                    "definition": "Нанять двух продавцов?",
                },
                {
                    "id": "s04",
                    "layout": "closing",
                    "title": "Решение: отложить найм до закрытия разрыва",
                    "bullets": ["Ждать следующий квартал."],
                },
            ]
        ),
        source=source,
    )
    blob = " ".join(
        f"{s.get('title') or ''} {s.get('definition') or ''} {' '.join(s.get('bullets') or [])}"
        for s in deck["slides"]
    ).casefold()
    assert "отложить" not in blob
    assert "ждать" not in blob
    assert sum(1 for s in deck["slides"] if s["layout"] == "callout") == 1
    assert "20,4" in deck["slides"][-1]["title"] or "18,4" in deck["slides"][-1]["title"]


def test_negated_compare_becomes_one_question() -> None:
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Совет"},
                {
                    "id": "s02",
                    "layout": "compare",
                    "title": "Нанять двух продажников или нет",
                    "cards": [
                        {"title": "Нанять двух продажников", "body": "Вопрос совета."},
                        {"title": "Не нанимать двух продажников", "body": "Вопрос совета."},
                    ],
                },
                {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["Решение"]},
            ]
        ),
        source=BOARD,
    )
    mid = deck["slides"][1]
    assert mid["layout"] == "callout"
    assert "cards" not in mid
    assert "нанимать" in mid["definition"].casefold()


def test_scorecard_title_stops_listing_every_kpi() -> None:
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Совет"},
                {
                    "id": "s02",
                    "layout": "scorecard",
                    "kicker": "Показатели",
                    "title": "Выручка 18,4 млн при плане 19; продажи 1,9 млн",
                    "subtitle": "Выручка 18,4 млн и продажи 1,9 млн.",
                    "kpis": [
                        {"label": "Выручка", "value": "18,4 млн", "hint": "План 19."},
                        {"label": "Продажи", "value": "1,9 млн", "hint": "86% плана."},
                    ],
                },
                {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["Решение"]},
            ]
        ),
        source=BOARD,
    )
    card = deck["slides"][1]
    assert card["title"] == "Показатели"
    assert "subtitle" not in card


def test_source_question_is_its_own_slide_before_closing() -> None:
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Совет", "subtitle": "Выручка 18,4 млн"},
                {
                    "id": "s02",
                    "layout": "bullets",
                    "title": "Кэш",
                    "bullets": ["Кэш 20,4 млн хватает на 24 месяца."],
                },
                {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["Смотреть план"]},
            ]
        ),
        source=BOARD,
    )
    assert deck["slides"][-2]["layout"] == "callout"
    assert "или нет" not in deck["slides"][-2]["definition"]
    assert deck["slides"][-2]["definition"].endswith("?")


def test_locked_arc_drops_a_bullet_list_that_replaced_a_chart() -> None:
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Каналы"},
                {
                    "id": "s02",
                    "layout": "bullets",
                    "title": "План",
                    "bullets": ["План выручки 19."],
                },
                {
                    "id": "s03",
                    "layout": "scorecard",
                    "title": "Факт",
                    "kpis": [{"label": "Факт", "value": "18,4", "hint": "План 19."}],
                },
                {"id": "s04", "layout": "closing", "title": "Дальше"},
            ]
        ),
        source="план выручки 19, факт 18,4.",
        locked_arc=["title", "chart_hero", "scorecard", "closing"],
    )
    layouts = [s["layout"] for s in deck["slides"]]
    assert layouts == ["title", "scorecard", "closing"]


def test_locked_arc_keeps_template_order_and_may_skip_a_slot() -> None:
    deck = parse_deck_ir(
        _wrap(
            [
                {"id": "s01", "layout": "title", "title": "Квартал"},
                {
                    "id": "s02",
                    "layout": "chart_hero",
                    "title": "Каналы",
                    "chart_id": "cht_01",
                },
                {
                    "id": "s03",
                    "layout": "table_hero",
                    "title": "Сетка",
                    "rows": [["Канал", "Факт"], ["Сайт", "6,2"]],
                },
                {"id": "s04", "layout": "closing", "title": "Дальше"},
            ]
        ),
        source="сайт 6,2.",
        allowed_media_ids=frozenset({"cht_01"}),
        locked_arc=["title", "table_hero", "chart_hero", "quote", "closing"],
    )
    assert [s["layout"] for s in deck["slides"]] == [
        "title",
        "table_hero",
        "chart_hero",
        "closing",
    ]
    assert deck["slides"][-1]["layout"] == "closing"
