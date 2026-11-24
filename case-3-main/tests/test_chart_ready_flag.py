"""Missing __CASE3_CHART_READY must be auto-injected."""

from __future__ import annotations

from case3.chart_html import sanitize_chart_html


def test_ready_flag_appended_when_missing() -> None:
    html = (
        '<canvas id="c1" width="1100" height="560"></canvas>'
        "<script>new Chart(document.getElementById('c1'),"
        "{type:'line',data:{labels:['a'],datasets:[{data:[1]}]},"
        "options:{animation:false}});</script>"
    )
    out = sanitize_chart_html(html)
    assert "__CASE3_CHART_READY" in out


def test_ready_flag_not_duplicated() -> None:
    html = (
        '<canvas id="c1" width="1100" height="560"></canvas>'
        "<script>window.__CASE3_CHART_READY=true;</script>"
    )
    out = sanitize_chart_html(html)
    assert out.count("__CASE3_CHART_READY") == 1


def test_tex_decimal_comma_is_plain_text() -> None:
    html = '<div class="kpi"><div class="value">2{,}68</div></div>'
    out = sanitize_chart_html(html)
    assert "2,68" in out
    assert "{,}" not in out
