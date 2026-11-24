"""Text-only deck IR patches (edit existing slides; bullets may grow or shrink)."""

from __future__ import annotations

import pytest

from case3.slides_ir import DeckIrError
from case3.slides_patch import apply_deck_text_patch


def _base() -> dict:
    return {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "ru",
        "slides": [
            {
                "id": "s01",
                "layout": "title",
                "title": "Old title",
                "subtitle": "Sub",
            },
            {
                "id": "s02",
                "layout": "bullets",
                "title": "Facts",
                "bullets": ["A", "B"],
            },
            {
                "id": "s03",
                "layout": "scorecard",
                "title": "KPI",
                "kpis": [
                    {"label": "Rev", "value": "10", "delta": "+1%", "hint": "y"},
                ],
            },
            {
                "id": "s04",
                "layout": "table_hero",
                "title": "T",
                "rows": [["H1", "H2"], ["1", "2"]],
            },
            {
                "id": "s05",
                "layout": "closing",
                "title": "End",
                "bullets": ["X"],
            },
        ],
    }


def test_patch_title_and_bullet() -> None:
    deck = _base()
    out = apply_deck_text_patch(
        deck,
        {
            "slides": [
                {"id": "s01", "title": "New title"},
                {"id": "s02", "bullets": ["A2", "B"]},
            ]
        },
    )
    assert out["slides"][0]["title"] == "New title"
    assert out["slides"][0]["layout"] == "title"
    assert out["slides"][1]["bullets"] == ["A2", "B"]
    assert len(out["slides"]) == 5


def test_patch_rejects_layout_change() -> None:
    with pytest.raises(DeckIrError, match="layout"):
        apply_deck_text_patch(
            _base(),
            {"slides": [{"id": "s01", "layout": "bullets", "title": "x"}]},
        )


def test_patch_rejects_add_slide() -> None:
    with pytest.raises(DeckIrError, match="slide"):
        apply_deck_text_patch(
            _base(),
            {
                "slides": [
                    {
                        "id": "s99",
                        "layout": "bullets",
                        "title": "Nope",
                        "bullets": ["z"],
                    }
                ]
            },
        )


def test_patch_changes_bullet_count_within_cap() -> None:
    shrunk = apply_deck_text_patch(
        _base(),
        {"slides": [{"id": "s02", "bullets": ["only-one"]}]},
    )
    assert shrunk["slides"][1]["bullets"] == ["only-one"]
    grown = apply_deck_text_patch(
        _base(),
        {"slides": [{"id": "s02", "bullets": ["A", "B", "Новый тезис"]}]},
    )
    assert grown["slides"][1]["bullets"] == ["A", "B", "Новый тезис"]


def test_patch_rejects_bullet_count_outside_cap() -> None:
    with pytest.raises(DeckIrError, match="empty"):
        apply_deck_text_patch(
            _base(),
            {"slides": [{"id": "s02", "bullets": []}]},
        )
    with pytest.raises(DeckIrError, match="exceeds"):
        apply_deck_text_patch(
            _base(),
            {"slides": [{"id": "s02", "bullets": ["1", "2", "3", "4", "5", "6"]}]},
        )


def test_patch_kpi_and_table_cell() -> None:
    out = apply_deck_text_patch(
        _base(),
        {
            "slides": [
                {
                    "id": "s03",
                    "kpis": [
                        {
                            "label": "Revenue",
                            "value": "12",
                            "delta": "+2%",
                            "hint": "y",
                        }
                    ],
                },
                {"id": "s04", "rows": [["H1", "H2"], ["9", "2"]]},
            ]
        },
    )
    assert out["slides"][2]["kpis"][0]["label"] == "Revenue"
    assert out["slides"][2]["kpis"][0]["value"] == "12"
    assert out["slides"][3]["rows"][1][0] == "9"


def test_patch_adds_table_row_and_column() -> None:
    out = apply_deck_text_patch(
        _base(),
        {
            "slides": [
                {
                    "id": "s04",
                    "rows": [
                        ["H1", "H2", "Колонка 3"],
                        ["1", "2", "—"],
                        ["Новая строка", "—", "—"],
                    ],
                }
            ]
        },
    )
    rows = out["slides"][3]["rows"]
    assert rows == [
        ["H1", "H2", "Колонка 3"],
        ["1", "2", "—"],
        ["Новая строка", "—", "—"],
    ]


def test_patch_rejects_table_over_slide_caps() -> None:
    wide = [["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9"], ["1", "2", "3", "4", "5", "6", "7", "8", "9"]]
    with pytest.raises(DeckIrError, match="column"):
        apply_deck_text_patch(_base(), {"slides": [{"id": "s04", "rows": wide}]})
    tall = [["H1", "H2"]] + [[str(i), "x"] for i in range(14)]
    with pytest.raises(DeckIrError, match="row"):
        apply_deck_text_patch(_base(), {"slides": [{"id": "s04", "rows": tall}]})
