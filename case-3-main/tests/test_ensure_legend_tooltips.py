"""Polish must turn on Chart.js legend + tooltips for multi-series charts."""

from __future__ import annotations

from case3.chart_types_coerce import ensure_legend_and_tooltips, polish_charts


def test_ensure_enables_tooltip_when_missing() -> None:
    html = (
        "<canvas id='c'></canvas><script>"
        "new Chart(c,{type:'bar',data:{labels:['A','B'],datasets:["
        "{label:'X',data:[1,2],backgroundColor:'#0077BB'},"
        "{label:'Y',data:[3,4],backgroundColor:'#EE7733'}"
        "]},options:{plugins:{legend:{display:false}},animation:false}});"
        "</script>"
    )
    out = ensure_legend_and_tooltips(html, "grouped_bar")
    assert "tooltip" in out.lower()
    assert re_search_enabled_true(out, "tooltip")
    assert re_search_display_true(out, "legend")


def test_ensure_keeps_donut_chartjs_legend_off_with_valued_list() -> None:
    html = (
        '<ul class="valued-legend"><li>A</li></ul>'
        "<script>new Chart(c,{type:'doughnut',data:{labels:['A'],datasets:[{data:[1]}]},"
        "options:{plugins:{legend:{display:false}},animation:false}});</script>"
    )
    out = ensure_legend_and_tooltips(html, "donut")
    assert "valued-legend" in out
    assert re_search_display_false(out, "legend")
    assert re_search_enabled_true(out, "tooltip")


def test_polish_turns_on_legend_for_stacked() -> None:
    charts = [
        {
            "id": "cht_01",
            "type": "stacked_bar",
            "caption": "Stack",
            "html": (
                "<canvas id='c'></canvas><script>"
                "new Chart(c,{type:'bar',data:{labels:['Q1'],datasets:["
                "{label:'A',data:[10],backgroundColor:'#0077BB',stack:'s'},"
                "{label:'B',data:[8],backgroundColor:'#EE7733',stack:'s'}"
                "]},options:{plugins:{legend:{display:false}},"
                "scales:{x:{stacked:true},y:{stacked:true}},animation:false}});"
                "</script>"
            ),
        }
    ]
    out = polish_charts(charts, palette_id="atelier")
    html = out[0]["html"]
    assert re_search_display_true(html, "legend")
    assert re_search_enabled_true(html, "tooltip")


def re_search_enabled_true(html: str, plugin: str) -> bool:
    import re

    return bool(
        re.search(
            rf"{plugin}\s*:\s*\{{[^}}]*enabled\s*:\s*true",
            html,
            flags=re.I | re.S,
        )
    )


def re_search_display_true(html: str, plugin: str) -> bool:
    import re

    return bool(
        re.search(
            rf"{plugin}\s*:\s*\{{[^}}]*display\s*:\s*true",
            html,
            flags=re.I | re.S,
        )
    )


def re_search_display_false(html: str, plugin: str) -> bool:
    import re

    return bool(
        re.search(
            rf"{plugin}\s*:\s*\{{[^}}]*display\s*:\s*false",
            html,
            flags=re.I | re.S,
        )
    )
