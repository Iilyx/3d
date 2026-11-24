"""Type coerce → donut must not leave multi-dataset concentric rings («мишень»)."""

from __future__ import annotations

from case3.chart_coerce import apply_type_to_chart

_GROUPED_BAR = (
    '<canvas id="c1" width="1100" height="560"></canvas>'
    "<script>new Chart(document.getElementById('c1'),"
    "{type:'bar',data:{labels:['Q1','Q2','Q3','Q4'],datasets:["
    "{label:'План',data:[10,20,15,25],backgroundColor:'#1A4A4B'},"
    "{label:'Факт',data:[12,18,22,30],backgroundColor:'#5A6E28'}"
    "]},options:{animation:false,scales:{x:{},y:{}}}});"
    "window.__CASE3_CHART_READY=true;</script>"
)

_LINE_MANY = (
    '<canvas id="c1" width="1100" height="560"></canvas>'
    "<script>new Chart(document.getElementById('c1'),"
    "{type:'line',data:{labels:['Янв','Фев','Мар','Апр','Май','Июн',"
    "'Июл','Авг','Сен','Окт','Ноя','Дек'],"
    "datasets:[{label:'Выручка',data:[1,2,3,4,5,6,7,8,9,10,11,12],"
    "borderColor:'#1A4A4B'}]},options:{animation:false}});"
    "window.__CASE3_CHART_READY=true;</script>"
)


def _dataset_count(html: str) -> int:
    # Count `{label:` or `{data:` objects inside datasets:[...]
    import re

    m = re.search(r"datasets\s*:\s*\[(.*)\]\s*,?\s*\}", html, flags=re.I | re.S)
    if not m:
        return 0
    body = m.group(1)
    # crude: number of data:[...] inside datasets
    return len(re.findall(r"data\s*:\s*\[", body, flags=re.I))


def test_grouped_bar_to_donut_collapses_to_one_ring() -> None:
    chart = {"id": "cht_01", "type": "grouped_bar", "html": _GROUPED_BAR}
    out = apply_type_to_chart(chart, "donut")
    html = out["html"]
    assert out["type"] == "donut"
    assert "doughnut" in html
    assert _dataset_count(html) == 1, html[:500]
    # Values summed per quarter: 10+12=22, 20+18=38, 15+22=37, 25+30=55
    assert "22" in html and "38" in html and "37" in html and "55" in html
    assert "cutout" in html.lower()


def test_line_to_donut_keeps_single_series_values() -> None:
    chart = {"id": "cht_02", "type": "line", "html": _LINE_MANY}
    out = apply_type_to_chart(chart, "donut")
    html = out["html"]
    assert out["type"] == "donut"
    assert "doughnut" in html
    assert _dataset_count(html) == 1
    assert "12" in html  # last month value preserved


_STACKED = (
    '<canvas id="c1" width="1100" height="560"></canvas>'
    "<script>new Chart(document.getElementById('c1'),"
    "{type:'bar',data:{labels:['Сев','Юг','Вост'],datasets:["
    "{label:'A',data:[30,20,25],backgroundColor:'#1A4A4B'},"
    "{label:'B',data:[20,35,15],backgroundColor:'#5A6E28'},"
    "{label:'C',data:[10,5,20],backgroundColor:'#8B5A2B'}"
    "]},options:{animation:false,scales:{x:{stacked:true},y:{stacked:true}}}});"
    "window.__CASE3_CHART_READY=true;</script>"
)


def test_stacked_to_donut_hides_cartesian_axes() -> None:
    chart = {"id": "cht_03", "type": "stacked_bar", "html": _STACKED}
    html = apply_type_to_chart(chart, "donut")["html"]
    assert _dataset_count(html) == 1
    assert "stacked" not in html.lower()
    assert "x:{display:false}" in html.replace(" ", "")
    assert "y:{display:false}" in html.replace(" ", "")
