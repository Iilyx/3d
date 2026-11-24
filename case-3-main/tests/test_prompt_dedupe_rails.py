"""Canonical chart/photo rails appear once in system_tex, not echoed everywhere."""

from __future__ import annotations

from case3.prompts import load


def test_chart_ready_not_repeated_in_hard_rules() -> None:
    text = load(
        "system_tex",
        MAX_IMAGES=2,
        MAX_CHARTS=2,
        MAX_DIAGRAMS=1,
        PALETTE_TABLE="| p |",
        has_user_photos=False,
    )
    # Example in 01 + hard rails in 02 (+ optional short host note in 02).
    assert text.count("__CASE3_CHART_READY") <= 3
    hard = text[text.index("# Hard rules") :]
    assert "__CASE3_CHART_READY" not in hard


def test_photo_anti_slop_lives_in_figures_part_only() -> None:
    with_fig = load(
        "system_tex",
        MAX_IMAGES=2,
        MAX_CHARTS=1,
        MAX_DIAGRAMS=0,
        PALETTE_TABLE="| p |",
    )
    bare = load(
        "system_tex",
        MAX_IMAGES=0,
        MAX_CHARTS=1,
        MAX_DIAGRAMS=0,
        PALETTE_TABLE="| p |",
    )
    assert with_fig.lower().count("handshake") == 1
    assert "handshake" not in bare.lower()
    hard = with_fig[with_fig.index("# Hard rules") :]
    assert "handshake" not in hard.lower()


def test_type_match_donut_mapping_once_in_charts_part() -> None:
    text = load(
        "system_tex",
        MAX_IMAGES=0,
        MAX_CHARTS=2,
        MAX_DIAGRAMS=0,
        PALETTE_TABLE="| p |",
    )
    # One Rules line + mapping table — not a third Hard-rails echo.
    assert text.count("`donut` → `doughnut`") == 1
    assert text.count("indexAxis:'y'") <= 2
