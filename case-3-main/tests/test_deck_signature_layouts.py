"""Signature layouts: Northstar split, stat hero, timeline, compare, status chips."""

from __future__ import annotations

from case3.deck_theme import resolve_deck_theme
from case3.slides_html import render_slide_html
from case3.slides_ir import SLIDE_LAYOUTS, parse_deck_ir

SOURCE = "Выручка 120 млн в 2024 году. Доля 35%. NPS 42. Запас 18 мес."


def _deck(slides: list[dict]) -> dict:
    return parse_deck_ir(
        {"version": 1, "palette": "atelier", "slides": slides},
        source=SOURCE,
    )


def test_board_title_splits() -> None:
    tok = resolve_deck_theme("board")
    assert tok.motif.get("split") == 0.55


def test_signature_layouts_are_allowed() -> None:
    for name in ("stat_hero", "timeline", "compare"):
        assert name in SLIDE_LAYOUTS


def test_stat_hero_parses_one_kpi_and_bullets() -> None:
    ir = _deck(
        [
            {"id": "s01", "layout": "title", "title": "Квартал"},
            {
                "id": "s02",
                "layout": "stat_hero",
                "title": "Выручка держит темп",
                "kpis": [
                    {
                        "label": "Выручка",
                        "value": "120 млн",
                        "delta": "+35%",
                        "hint": "к 2024 году",
                    }
                ],
                "bullets": [
                    "Доля 35% в целевом сегменте.",
                    "NPS 42 при запасе 18 мес.",
                ],
            },
            {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["План"]},
        ]
    )
    slide = ir["slides"][1]
    assert slide["layout"] == "stat_hero"
    assert len(slide["kpis"]) == 1
    assert len(slide["bullets"]) == 2


def test_timeline_keeps_up_to_six_steps() -> None:
    ir = parse_deck_ir(
        {
            "version": 1,
            "palette": "atelier",
            "slides": [
                {"id": "s01", "layout": "title", "title": "День"},
                {
                    "id": "s02",
                    "layout": "timeline",
                    "title": "Поток дня",
                    "cards": [
                        {"kicker": "15 мин", "title": "Старт", "body": "Цели на день."},
                        {"kicker": "40 мин", "title": "Карта", "body": "Формулировка проблемы."},
                        {"kicker": "45 мин", "title": "Стена", "body": "Варианты без оценки."},
                        {"kicker": "20 мин", "title": "Финиш", "body": "Владельцы шагов."},
                    ],
                },
                {"id": "s03", "layout": "closing", "title": "Выходы", "bullets": ["План"]},
            ],
        },
        source=SOURCE + " Тайминг: 15 мин старт, 40 мин карта, 45 мин стена, 20 мин финиш.",
    )
    assert len(ir["slides"][1]["cards"]) == 4


def test_compare_keeps_two_columns() -> None:
    ir = _deck(
        [
            {"id": "s01", "layout": "title", "title": "Неделя"},
            {
                "id": "s02",
                "layout": "compare",
                "title": "Куда уходит бюджет",
                "cards": [
                    {
                        "kicker": "Масштаб",
                        "title": "Поиск",
                        "body": "Доля 35% при выручке 120 млн.",
                    },
                    {
                        "kicker": "Пауза",
                        "title": "Баннер",
                        "body": "NPS 42 не окупает запас 18 мес.",
                    },
                    {
                        "kicker": "Лишнее",
                        "title": "Третья",
                        "body": "Не должна попасть на слайд.",
                    },
                ],
            },
            {"id": "s03", "layout": "closing", "title": "Пятница", "bullets": ["План"]},
        ]
    )
    assert len(ir["slides"][1]["cards"]) == 2


def test_html_renders_signature_blocks_and_status_chip() -> None:
    hero = render_slide_html(
        {
            "id": "s1",
            "layout": "stat_hero",
            "title": "Одна цифра",
            "kpis": [{"label": "Выручка", "value": "120 млн", "delta": "+35%"}],
            "bullets": ["Доля 35%."],
        },
        palette="ink",
    )
    assert 'data-layout="stat_hero"' in hero
    assert "stat-hero--field" in hero
    assert "120 млн" in hero

    line = render_slide_html(
        {
            "id": "s2",
            "layout": "timeline",
            "title": "Повестка",
            "cards": [
                {"kicker": "15 мин", "title": "Старт", "body": "Цели."},
                {"kicker": "40 мин", "title": "Карта", "body": "Проблема."},
            ],
        },
        palette="studio",
    )
    assert "timeline" in line
    assert "15 мин" in line

    table = render_slide_html(
        {
            "id": "s3",
            "layout": "table_hero",
            "title": "Креативы",
            "rows": [
                ["Креатив", "Статус"],
                ["Поиск", "Масштаб"],
                ["Баннер", "Пауза"],
            ],
        },
        palette="atelier",
    )
    assert "status-chip is-scale" in table
    assert "status-chip is-pause" in table

    score = render_slide_html(
        {
            "id": "s4",
            "layout": "scorecard",
            "title": "Сводка",
            "kpis": [
                {
                    "label": "Выручка",
                    "value": "120 млн",
                    "delta": "+35%",
                    "hint": "к плану года",
                    "status": "up",
                }
            ],
        },
        palette="board",
    )
    card = score.split('class="kpi-card"', 1)[1]
    assert card.find('class="hint"') < card.find("kpi-foot")


def test_stat_hero_accepts_flat_value_label() -> None:
    ir = _deck(
        [
            {"id": "s01", "layout": "title", "title": "Неделя"},
            {
                "id": "s02",
                "layout": "stat_hero",
                "title": "Отдача держится",
                "value": "120 млн",
                "label": "Выручка",
                "bullets": ["Доля 35%.", "NPS 42 при запасе 18 мес."],
            },
            {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["План"]},
        ]
    )
    assert ir["slides"][1]["kpis"][0]["value"] == "120 млн"


def test_quote_layout_parses_and_renders() -> None:
    ir = _deck(
        [
            {"id": "s01", "layout": "title", "title": "Голос"},
            {
                "id": "s02",
                "layout": "quote",
                "title": "Клиенты говорят про ясность",
                "term": "Операционный лид",
                "definition": "Запас 18 мес. держит план, если доля 35% не просядет.",
                "body": "NPS 42, выручка 120 млн.",
            },
            {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["План"]},
        ]
    )
    assert ir["slides"][1]["layout"] == "quote"
    html = render_slide_html(ir["slides"][1], palette="voltage")
    assert 'data-layout="quote"' in html
    assert "pull-quote" in html
    assert "Операционный лид" in html
