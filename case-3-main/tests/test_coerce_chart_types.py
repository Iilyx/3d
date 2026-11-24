"""Preferred UI chart types must win over model guesses."""

from __future__ import annotations

from case3.chart_types_coerce import coerce_chart_types
from case3.generate import preferred_types_from_intent


def test_preferred_types_from_intent() -> None:
    intent = (
        "Требования UI:\n"
        "- ОБЯЗАТЕЛЬНО типы графиков по порядку (charts[0], charts[1], …): "
        "bar, horizontal_bar — не подменяй\n"
    )
    assert preferred_types_from_intent(intent) == ["bar", "horizontal_bar"]


def test_coerce_rewrites_type_field_and_html() -> None:
    charts = [
        {
            "id": "cht_01",
            "type": "line",
            "caption": "A",
            "html": (
                "<canvas id=\"c1\" width=\"1100\" height=\"560\"></canvas>"
                "<script>new Chart(document.getElementById('c1'),"
                "{type:'line',data:{labels:['a'],datasets:[{data:[1]}]},"
                "options:{animation:false}});"
                "window.__CASE3_CHART_READY=true;</script>"
            ),
        },
        {
            "id": "cht_02",
            "type": "grouped_bar",
            "caption": "B",
            "html": (
                "<canvas id=\"c2\" width=\"1100\" height=\"560\"></canvas>"
                "<script>new Chart(document.getElementById('c2'),"
                "{type:'bar',data:{labels:['a'],datasets:[{data:[1]},{data:[2]}]},"
                "options:{animation:false}});"
                "window.__CASE3_CHART_READY=true;</script>"
            ),
        },
    ]
    out = coerce_chart_types(charts, preferred=["bar", "horizontal_bar"])
    assert out[0]["type"] == "bar"
    assert "type:'bar'" in out[0]["html"] or 'type:"bar"' in out[0]["html"]
    assert out[1]["type"] == "horizontal_bar"
    assert "indexAxis" in out[1]["html"]


def test_coerce_noop_when_auto_or_empty() -> None:
    charts = [{"id": "cht_01", "type": "donut", "html": "<div class='kpi'>1</div>"}]
    assert coerce_chart_types(charts, preferred=[])[0]["type"] == "donut"


def test_coerce_kpi_replaces_line_with_kpi_markup() -> None:
    charts = [
        {
            "id": "cht_01",
            "type": "line",
            "caption": "Доля продаж 45%",
            "html": (
                "<canvas id=\"c1\" width=\"1100\" height=\"560\"></canvas>"
                "<script>new Chart(document.getElementById('c1'),"
                "{type:'line',data:{labels:['a'],datasets:[{data:[45]}]},"
                "options:{animation:false}});</script>"
            ),
        }
    ]
    out = coerce_chart_types(charts, preferred=["kpi"])
    assert out[0]["type"] == "kpi"
    assert 'class="kpi"' in out[0]["html"] or "class='kpi'" in out[0]["html"]
    assert "45" in out[0]["html"]


def test_coerce_kpi_when_type_already_kpi_but_canvas() -> None:
    """Model often labels type=kpi while emitting a bar canvas — must rebuild cards."""
    from case3.chart_types_coerce import ensure_all_charts_match_types

    charts = [
        {
            "id": "cht_01",
            "type": "kpi",
            "caption": "Выручка 152 млн",
            "html": (
                "<canvas id=\"c1\" width=\"1100\" height=\"560\"></canvas>"
                "<script>new Chart(document.getElementById('c1'),"
                "{type:'bar',data:{labels:['Q1'],datasets:[{data:[152]}]},"
                "options:{animation:false}});</script>"
            ),
        }
    ]
    # Preferred path
    out = coerce_chart_types(charts, preferred=["kpi"])
    assert out[0]["type"] == "kpi"
    assert 'class="kpi"' in out[0]["html"]
    assert "<canvas" not in out[0]["html"]
    assert "152" in out[0]["html"]
    # Auto path (type already kpi)
    out2 = ensure_all_charts_match_types(charts)
    assert out2[0]["type"] == "kpi"
    assert 'class="kpi"' in out2[0]["html"]
    assert "<canvas" not in out2[0]["html"]


def test_coerce_donut_when_type_matches_but_js_is_bar() -> None:
    charts = [
        {
            "id": "cht_01",
            "type": "donut",
            "caption": "Доли",
            "html": (
                "<canvas id=\"c1\"></canvas><script>new Chart(c,"
                "{type:'bar',data:{labels:['a'],datasets:[{data:[1]}]},"
                "options:{}});</script>"
            ),
        }
    ]
    out = coerce_chart_types(charts, preferred=["donut"])
    assert out[0]["type"] == "donut"
    assert "doughnut" in out[0]["html"]
