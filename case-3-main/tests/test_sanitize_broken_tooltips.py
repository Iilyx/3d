"""LLM often emits broken tooltip/tick callbacks — sanitize must yield valid JS."""

from __future__ import annotations

import subprocess
from pathlib import Path

from case3.chart_html import sanitize_chart_html

FIX = Path(__file__).resolve().parent / "fixtures"


def _script_bodies(html: str) -> str:
    import re

    return "\n".join(re.findall(r"(?is)<script>(.*?)</script>", html))


def _node_syntax_ok(script: str) -> bool:
    r = subprocess.run(
        ["node", "--check"],
        input=script,
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def test_broken_grouped_tooltip_sanitizes_to_valid_js() -> None:
    raw = (FIX / "broken_grouped_tooltip.html").read_text(encoding="utf-8")
    assert not _node_syntax_ok(_script_bodies(raw).split("requestAnimationFrame")[0] + ";")
    out = sanitize_chart_html(raw)
    script = _script_bodies(out)
    assert _node_syntax_ok(script), script[-200:]


def test_broken_line_tooltip_sanitizes_to_valid_js() -> None:
    raw = (FIX / "broken_line_tooltip.html").read_text(encoding="utf-8")
    out = sanitize_chart_html(raw)
    script = _script_bodies(out)
    assert _node_syntax_ok(script), script[-200:]


def test_sanitize_does_not_leave_empty_raf_shell() -> None:
    html = (
        '<canvas id="c1"></canvas><script>'
        "new Chart(document.getElementById('c1'),{type:'bar',data:{labels:[1],datasets:[{data:[1]}]},"
        "options:{animation:false}});"
        "requestAnimationFrame(function(){requestAnimationFrame(function(){"
        "window.__CASE3_CHART_READY=true;});});"
        "</script>"
    )
    out = sanitize_chart_html(html)
    # One defer chain only (not empty shell + new chain).
    assert out.count("requestAnimationFrame") == 2
    assert out.count("__CASE3_CHART_READY") == 1
