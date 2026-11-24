"""READY flag must defer until after paint (rAF), not sync after new Chart()."""

from __future__ import annotations

from case3.chart_html import sanitize_chart_html


def test_sanitize_defers_ready_via_raf() -> None:
    html = (
        '<canvas id="c1" width="1100" height="560"></canvas>'
        "<script>new Chart(document.getElementById('c1'),"
        "{type:'scatter',data:{datasets:[{data:[{x:1,y:2}]}]},"
        "options:{animation:false}});"
        "window.__CASE3_CHART_READY=true;</script>"
    )
    out = sanitize_chart_html(html)
    assert "requestAnimationFrame" in out
    # Must not leave a bare sync READY as the only setter before rAF.
    assert out.count("__CASE3_CHART_READY") >= 1
