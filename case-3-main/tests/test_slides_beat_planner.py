"""Beat planner + IR variety gate (template-free decks)."""

from __future__ import annotations

import pytest

from case3.slides_beat_planner import format_beat_overlay, plan_beats
from case3.slides_ir import DeckIrError, parse_deck_ir


def test_plan_beats_chart_heavy_sources_performance() -> None:
    plan = plan_beats(
        source="Media spend $2.09M. Attributed revenue $6.99M. Blended ROAS 3.34x. Channels Paid Search.",
        intent="Marketing performance readout",
        chart_ids=["cht_01", "cht_02"],
        figure_ids=[],
        diagram_ids=[],
    )
    assert plan.mode == "performance"
    assert plan.pack_hint == "signal"
    assert plan.beats[0] == "title"
    assert plan.beats[-1] == "closing"
    assert "chart_hero" in plan.beats
    assert len(plan.beats) >= 8


def test_plan_beats_survey_percentages() -> None:
    plan = plan_beats(
        source="Survey n=240. CSAT 72%. NPS +25. 68% love task clarity. Friction finding features 45%.",
        intent="Product feedback readout",
        chart_ids=[],
        figure_ids=[],
        diagram_ids=[],
    )
    assert plan.mode == "survey"
    assert plan.pack_hint == "voltage"
    assert "card_row" in plan.beats
    assert "callout" in plan.beats


def test_plan_beats_expands_template_to_requested_count() -> None:
    plan = plan_beats(
        source="Длинный бриф " * 40,
        intent="Нужна подробная преза",
        chart_ids=["cht_01"],
        figure_ids=["usr_01"],
        diagram_ids=[],
        structure_id="workshop",
        target_slides=20,
    )
    assert plan.from_structure is True
    assert len(plan.beats) == 20
    assert plan.beats[0] == "title"
    assert plan.beats[-1] == "closing"
    assert "section" in plan.beats
    assert "media_hero" in plan.beats or "media_split" in plan.beats
    assert plan.beats.count("chart_hero") + plan.beats.count("chart_split") == 1


def test_plan_beats_without_request_stays_in_default_band() -> None:
    plan = plan_beats(
        source="Короткий факт. Выручка 10.",
        intent="",
        chart_ids=[],
        figure_ids=[],
        diagram_ids=[],
    )
    assert 6 <= len(plan.beats) <= 12


def test_hire_words_pick_the_hire_arc() -> None:
    plan = plan_beats(
        source="Нанять двух продавцов или нет. Оффер готов.",
        intent="",
        chart_ids=[],
        figure_ids=[],
        diagram_ids=[],
    )
    assert plan.mode == "hire"
    assert plan.pack_hint == "board"
    assert plan.beats[0] == "title"
    assert plan.beats[-1] == "closing"


def test_plan_beats_respects_explicit_structure() -> None:
    plan = plan_beats(
        source="Anything",
        intent="",
        chart_ids=["cht_01"],
        figure_ids=[],
        diagram_ids=[],
        structure_id="board_update",
    )
    assert plan.mode == "board_update"
    assert plan.pack_hint == "board"
    assert "callout" in plan.beats or "table_hero" in plan.beats


def test_format_beat_overlay_lists_skeleton() -> None:
    plan = plan_beats(
        source="Board ARR $18.4M NRR 117% burn 0.9x. Ask: approve hiring.",
        intent="Board update",
        chart_ids=[],
        figure_ids=[],
        diagram_ids=[],
    )
    text = format_beat_overlay(plan)
    assert "BEAT PLAN" in text
    assert "you choose" in text.lower()
    assert "mandatory skeleton" not in text.lower()
    assert "stat_hero" in text and "timeline" in text and "compare" in text
    assert "title" in text
    assert "closing" in text


def test_ir_rejects_monotone_eight_slide_deck() -> None:
    slides = [
        {"id": "s01", "layout": "title", "title": "Q3"},
        {"id": "s02", "layout": "scorecard", "title": "A", "kpis": [{"label": "A", "value": "1"}]},
        {"id": "s03", "layout": "scorecard", "title": "B", "kpis": [{"label": "B", "value": "2"}]},
        {"id": "s04", "layout": "scorecard", "title": "C", "kpis": [{"label": "C", "value": "3"}]},
        {"id": "s05", "layout": "bullets", "title": "D", "bullets": ["one fact"]},
        {"id": "s06", "layout": "bullets", "title": "E", "bullets": ["two fact"]},
        {"id": "s07", "layout": "bullets", "title": "F", "bullets": ["three"]},
        {"id": "s08", "layout": "closing", "title": "Next", "bullets": ["go"]},
    ]
    # Fix consecutive bullets >2 — use kpi between
    slides[5] = {
        "id": "s06",
        "layout": "kpi_row",
        "title": "E",
        "kpis": [{"label": "X", "value": "1"}],
    }
    with pytest.raises(DeckIrError, match="distinct layouts|variety|monoton"):
        parse_deck_ir(
            {"version": 1, "aspect": "16:9", "palette": "atelier", "slides": slides},
            source="Q3 one fact two fact three go A B C 1 2 3",
        )


def test_ir_allows_zero_padded_kicker_indices() -> None:
    slides = [
        {"id": "s01", "layout": "title", "title": "Quarter readout"},
        {
            "id": "s02",
            "layout": "scorecard",
            "kicker": "01 / HEADLINE",
            "title": "ARR held",
            "kpis": [{"label": "ARR", "value": "18"}],
        },
        {
            "id": "s03",
            "layout": "callout",
            "kicker": "02 / ASK",
            "title": "Ask",
            "term": "ASK",
            "definition": "Approve hiring",
        },
        {
            "id": "s04",
            "layout": "table_hero",
            "title": "Pipe",
            "rows": [["Seg", "Pipe"], ["MM", "4"]],
        },
        {
            "id": "s05",
            "layout": "card_row",
            "title": "Bets",
            "cards": [
                {"title": "A", "body": "one"},
                {"title": "B", "body": "two"},
                {"title": "C", "body": "three"},
            ],
        },
        {"id": "s06", "layout": "section", "chapter": 2, "title": "Plan"},
        {
            "id": "s07",
            "layout": "bullets",
            "title": "Risks",
            "bullets": ["cash burn under 1"],
        },
        {
            "id": "s08",
            "layout": "closing",
            "title": "Decide",
            "bullets": ["approve plan", "name owners", "hold burn"],
        },
    ]
    deck = parse_deck_ir(
        {"version": 1, "aspect": "16:9", "palette": "atelier", "language": "en", "slides": slides},
        source=(
            "ARR 18 Approve hiring Pipe MM 4 one two three "
            "Plan Risks cash burn under 1 Decide approve plan name owners hold burn"
        ),
    )
    assert deck["slides"][1]["kicker"] == "01 / HEADLINE"


def test_ir_accepts_varied_eight_slide_deck() -> None:
    slides = [
        {"id": "s01", "layout": "title", "title": "Q3 readout"},
        {
            "id": "s02",
            "layout": "scorecard",
            "title": "Headline",
            "kpis": [
                {"label": "ARR", "value": "18"},
                {"label": "NRR", "value": "117"},
            ],
        },
        {
            "id": "s03",
            "layout": "callout",
            "title": "Ask",
            "term": "ASK",
            "definition": "Approve hiring plan",
        },
        {
            "id": "s04",
            "layout": "table_hero",
            "title": "Pipe",
            "rows": [["Seg", "Pipe"], ["MM", "4"]],
        },
        {
            "id": "s05",
            "layout": "card_row",
            "title": "Bets",
            "cards": [
                {"title": "A", "body": "one"},
                {"title": "B", "body": "two"},
                {"title": "C", "body": "three"},
            ],
        },
        {
            "id": "s06",
            "layout": "section",
            "chapter": 2,
            "title": "Plan",
        },
        {
            "id": "s07",
            "layout": "bullets",
            "title": "Risks",
            "bullets": ["cash burn under 1"],
        },
        {
            "id": "s08",
            "layout": "closing",
            "title": "Decide",
            "bullets": ["approve plan", "name owners", "hold burn"],
        },
    ]
    deck = parse_deck_ir(
        {"version": 1, "aspect": "16:9", "palette": "atelier", "language": "en", "slides": slides},
        source=(
            "ARR 18 NRR 117 Approve hiring plan Pipe MM 4 one two three 3 "
            "Plan Risks cash burn under 1 Decide approve plan name owners hold burn"
        ),
    )
    assert len(deck["slides"]) == 8
