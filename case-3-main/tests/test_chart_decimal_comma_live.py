"""Real Chromium: a short decimal comma is one bar, a bare pair stays two."""

from __future__ import annotations

from pathlib import Path

from case3.charts import render_chart_png
from case3.fact_ground import ground_generated
from case3.slides_chart_data import extract_chart_series

_TEX = r"""
\documentclass{article}
\begin{document}
Проверка графика.
\end{document}
"""


def _page(labels: str, data: str) -> str:
    return (
        '<canvas id="c1"></canvas>'
        "<script>new Chart(document.getElementById('c1'),{type:'bar',data:{"
        "labels:[LABELS],datasets:[{label:'Ряд',data:[DATA],backgroundColor:'#3F5210'}]},"
        "options:{animation:false}});window.__CASE3_CHART_READY=true;</script>"
    ).replace("LABELS", labels).replace("DATA", data)


def _ground(html: str, source: str) -> str:
    _tex, charts, _figures, _diagrams, _dropped = ground_generated(
        _TEX,
        [{"id": "cht_01", "caption": "Проверка", "html": html}],
        [],
        [],
        source=source,
        intent="Сделай отчёт.",
    )
    return str(charts[0]["html"])


def _plot(html: str, dest: Path) -> list[list[float | None]]:
    series: list[list[float | None]] = []
    render_chart_png(html, dest, work_dir=dest.parent / "work", series_out=series)
    assert dest.is_file()
    assert dest.stat().st_size >= 800
    assert dest.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    return series


def test_live_short_decimal_comma_is_one_bar(tmp_path: Path) -> None:
    html = _ground(_page("'Маржа'", "12,5"), "Маржа 12,5.")
    assert "data:[12.5]" in html.replace(" ", "")
    series = _plot(html, tmp_path / "margin.png")
    assert series == [[12.5]]
    word = extract_chart_series(html, chart_type="bar")
    assert word is not None
    assert word["series"][0]["values"] == [12.5]


def test_live_bare_pair_stays_two_bars(tmp_path: Path) -> None:
    html = _ground(
        _page("'Минская','Гомельская'", "100,40"),
        "| Область | Сумма |\n| --- | --- |\n| Минская | 100 |\n| Гомельская | 40 |\n",
    )
    assert "100.40" not in html
    series = _plot(html, tmp_path / "pair.png")
    assert series == [[100.0, 40.0]]
    word = extract_chart_series(html, chart_type="bar")
    assert word is not None
    assert word["series"][0]["values"] == [100.0, 40.0]


def test_live_spaced_thousands_stay_one_bar(tmp_path: Path) -> None:
    html = _ground(_page("'Минская'", "105 865,2"), "Минская 105 865,2.")
    assert "105865.2" in html
    series = _plot(html, tmp_path / "sum.png")
    assert series == [[105865.2]]
    word = extract_chart_series(html, chart_type="bar")
    assert word is not None
    assert word["series"][0]["values"] == [105865.2]
