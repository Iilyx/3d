"""Leaving donut must strip premium donut chrome (layout/legend/center)."""

from __future__ import annotations

import re

from case3.chart_types_coerce import apply_type_to_chart, enhance_donut_html

_BARE_DONUT = (
    '<canvas id="c1" width="520" height="520"></canvas><script>'
    "new Chart(document.getElementById('c1'),{type:'doughnut',data:{"
    "labels:['A','B','C'],datasets:[{data:[40,35,25],"
    "backgroundColor:['#2E4208','#4F6B14','#7A8F3A']}]},"
    "options:{responsive:false,plugins:{legend:{display:false}}}});"
    "</script>"
)


def test_apply_type_donut_to_bar_strips_layout() -> None:
    enhanced = enhance_donut_html(_BARE_DONUT)
    assert "donut-layout" in enhanced
    assert "valued-legend" in enhanced
    chart = {
        "id": "cht_01",
        "type": "donut",
        "caption": "Доли",
        "html": enhanced,
    }
    out = apply_type_to_chart(chart, "bar")
    html = out["html"]
    assert out["type"] == "bar"
    assert "donut-layout" not in html
    assert "valued-legend" not in html
    assert "donut-center" not in html
    assert "type:'bar'" in html or 'type:"bar"' in html
    assert 'width="1100"' in html or "width='1100'" in html
    assert 'height="560"' in html or "height='560'" in html
    # Single-series categorical bar: hide Chart.js legend (else "undefined").
    assert re.search(r"legend\s*:\s*\{[^}]*display\s*:\s*false", html, flags=re.I)


def test_apply_type_to_donut_rebuilds_layout() -> None:
    chart = {
        "id": "cht_01",
        "type": "bar",
        "caption": "Доли",
        "html": (
            '<canvas id="c1" width="900" height="400"></canvas><script>'
            "new Chart(document.getElementById('c1'),{type:'bar',data:{"
            "labels:['A','B'],datasets:[{data:[60,40],"
            "backgroundColor:['#2E4208','#4F6B14']}]},"
            "options:{responsive:false}});</script>"
        ),
    }
    out = apply_type_to_chart(chart, "donut")
    assert out["type"] == "donut"
    assert "donut-layout" in out["html"]
    assert "doughnut" in out["html"]
