"""Harden pale fills for all bar-like series; scatter coerce needs {x,y} points."""

from __future__ import annotations

import re

from case3.chart_types_coerce import apply_type_to_chart, harden_chart_html

_GROUPED = (
    '<canvas id="c1" width="1100" height="560"></canvas><script>'
    "new Chart(document.getElementById('c1'),{type:'bar',data:{"
    "labels:['A','B'],datasets:["
    "{label:'X',data:[1,2],backgroundColor:'rgba(0,180,216,0.18)'},"
    "{label:'Y',data:[3,4],backgroundColor:'rgba(10,20,30,0.15)'}]},"
    "options:{responsive:false}});</script>"
)


def test_harden_grouped_bar_solidifies_all_pale_fills() -> None:
    out = harden_chart_html(_GROUPED, "grouped_bar")
    assert "0.18" not in out
    assert "0.15" not in out
    assert out.lower().count("backgroundcolor:'#") >= 2


def test_harden_stacked_bar_solidifies_pale_fills() -> None:
    out = harden_chart_html(_GROUPED, "stacked_bar")
    assert "0.18" not in out
    assert "0.15" not in out


def test_apply_type_to_scatter_converts_scalar_data() -> None:
    chart = {
        "id": "cht_01",
        "type": "bar",
        "caption": "Точки",
        "html": (
            '<canvas id="c1"></canvas><script>'
            "new Chart(document.getElementById('c1'),{type:'bar',data:{"
            "labels:['A','B','C'],datasets:[{data:[10,20,30]}]},"
            "options:{responsive:false}});</script>"
        ),
    }
    out = apply_type_to_chart(chart, "scatter")
    html = out["html"]
    assert "type:'scatter'" in html or 'type:"scatter"' in html
    assert re.search(r"\{\s*x\s*:", html)
    assert "[10,20,30]" not in html.replace(" ", "")
