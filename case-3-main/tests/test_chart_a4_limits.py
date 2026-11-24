"""D7: chart geometry must fit A4 — clamp width and tall canvases."""

from __future__ import annotations

import re
from pathlib import Path

from case3.chart_types_coerce import harden_chart_html, polish_charts
from case3.tex_safe import sanitize_width


def test_sanitize_width_clamps_above_max() -> None:
    assert sanitize_width(r"0.99\textwidth") == r"0.92\textwidth"
    assert sanitize_width(r"1\textwidth") == r"0.92\textwidth"


def test_sanitize_width_keeps_sane_fraction() -> None:
    assert sanitize_width(r"0.85\textwidth") == r"0.85\textwidth"
    assert sanitize_width(r"0.92\textwidth") == r"0.92\textwidth"


def test_sanitize_width_multi_chart_cap() -> None:
    assert sanitize_width(r"0.92\textwidth", max_frac=0.82) == r"0.82\textwidth"
    assert sanitize_width(r"0.80\textwidth", max_frac=0.82) == r"0.80\textwidth"


def test_harden_caps_tall_bar_canvas() -> None:
    html = (
        '<canvas id="c1" width="1100" height="720"></canvas><script>'
        "new Chart(c,{type:'bar',data:{labels:['A'],datasets:[{data:[1]}]}});"
        "</script>"
    )
    out = harden_chart_html(html, "bar")
    m = re.search(r'height="(\d+)"', out)
    assert m and int(m.group(1)) <= 560


def test_polish_multi_chart_narrows_width() -> None:
    charts = [
        {"id": "cht_01", "type": "bar", "html": "<canvas></canvas>", "width": r"0.92\textwidth"},
        {"id": "cht_02", "type": "line", "html": "<canvas></canvas>", "width": r"0.90\textwidth"},
    ]
    out = polish_charts(charts, palette_id="auto")
    assert out[0]["width"] == r"0.82\textwidth"
    assert out[1]["width"] == r"0.82\textwidth"


def test_donut_legend_column_has_min_width() -> None:
    frame = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "case3"
        / "templates"
        / "chart_frame.html"
    ).read_text(encoding="utf-8")
    assert "minmax(320px, 1fr)" in frame