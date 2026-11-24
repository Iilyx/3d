"""Cross-type coerce must leave renderable Chart.js / KPI, not empty or axis-stuck junk."""

from __future__ import annotations

import re

from case3.chart_coerce import apply_type_to_chart
from case3.chart_harden import html_matches_type

_KPI = (
    '<div class="kpi"><div class="value">42</div>'
    '<div class="label">NPS</div></div>'
    "<script>window.__CASE3_CHART_READY=true;</script>"
)

_SCATTER = (
    "<canvas id='c1'></canvas><script>new Chart(document.getElementById('c1'),"
    "{type:'scatter',data:{datasets:[{label:'T',"
    "data:[{x:1,y:12},{x:2,y:19},{x:3,y:15},{x:4,y:28}],"
    "backgroundColor:'#1A4A4B'}]},options:{animation:false}});"
    "window.__CASE3_CHART_READY=true;</script>"
)

_HBAR = (
    "<canvas id='c1'></canvas><script>new Chart(document.getElementById('c1'),"
    "{type:'bar',data:{labels:['Q1','Q2'],datasets:[{data:[10,20],"
    "backgroundColor:['#1A4A4B','#5A6E28']}]},"
    "options:{indexAxis:'y',animation:false}});"
    "window.__CASE3_CHART_READY=true;</script>"
)


def test_kpi_to_bar_builds_chart_js() -> None:
    out = apply_type_to_chart({"id": "c", "type": "kpi", "html": _KPI}, "bar")
    assert out["type"] == "bar"
    assert html_matches_type(out["html"], "bar")
    assert "42" in out["html"]
    assert "new Chart" in out["html"]


def test_dashboard_sum_stays_a_plain_number_on_a_donut() -> None:
    html = (
        "<canvas id='c1'></canvas><script>new Chart(document.getElementById('c1'),"
        "{type:'bar',data:{labels:['Minsk','Gomel'],datasets:[{data:[105865.2,94073],"
        "backgroundColor:['#1A4A4B','#5A6E28']}]},"
        "options:{animation:false}});"
        "window.__CASE3_CHART_READY=true;</script>"
    )
    out = apply_type_to_chart({"id": "c", "type": "bar", "html": html}, "donut")
    assert "105865.2" in out["html"]
    assert "94073" in out["html"]
    assert "e+" not in out["html"].lower()


def test_kpi_to_donut_builds_doughnut() -> None:
    out = apply_type_to_chart({"id": "c", "type": "kpi", "html": _KPI}, "donut")
    assert out["type"] == "donut"
    assert "doughnut" in out["html"]
    assert "42" in out["html"]
    assert "Прочее" not in out["html"]


def test_scatter_to_donut_uses_y_values() -> None:
    out = apply_type_to_chart({"id": "c", "type": "scatter", "html": _SCATTER}, "donut")
    assert out["type"] == "donut"
    assert "doughnut" in out["html"]
    assert not re.search(r"\{\s*x\s*:\s*\d", out["html"])
    assert "12" in out["html"] and "28" in out["html"]
    assert re.search(r"data\s*:\s*\[[^\]]*12", out["html"])


def test_scatter_to_bar_uses_scalar_series() -> None:
    out = apply_type_to_chart({"id": "c", "type": "scatter", "html": _SCATTER}, "bar")
    assert html_matches_type(out["html"], "bar")
    assert not re.search(r"\{\s*x\s*:\s*\d", out["html"])
    assert "12" in out["html"]


def test_horizontal_to_area_drops_index_axis() -> None:
    out = apply_type_to_chart(
        {"id": "c", "type": "horizontal_bar", "html": _HBAR}, "area"
    )
    assert html_matches_type(out["html"], "area")
    assert "indexAxis" not in out["html"]
    assert "fill:true" in out["html"].replace(" ", "")
