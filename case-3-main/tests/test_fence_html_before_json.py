"""```html drafts must not swallow the following ```json fence."""

from __future__ import annotations

import json

from case3.parse_output import parse_model_output


def test_thinking_html_fence_does_not_eat_json_charts() -> None:
    """Model often pastes ```html drafts, then ```latex, then more ```html, then ```json.

    Closing ``` of a draft must not be the opening backticks of ```json.
    """
    chart_html = (
        '<canvas id="c1" width="1100" height="560"></canvas>'
        "<script>new Chart(document.getElementById('c1'),"
        "{type:'bar',data:{labels:['2019','2020'],datasets:[{data:[10,20],"
        "backgroundColor:'#0072B2'}]},options:{animation:false}});"
        "window.__CASE3_CHART_READY=true;</script>"
    )
    payload = {
        "figures": [],
        "charts": [
            {
                "id": "cht_01",
                "type": "bar",
                "caption": "Test",
                "width": "0.8\\textwidth",
                "html": chart_html,
            }
        ],
        "diagrams": [],
    }
    raw = (
        "Thinking…\n"
        "```html\n"
        f"{chart_html}\n"
        "```\n"
        "```latex\n"
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "Hi\n"
        "%CASE3_CHART:cht_01%\n"
        "\\end{document}\n"
        "```\n"
        "Draft again:\n"
        "```html\n"
        '<canvas id="c2"></canvas>\n'
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```\n"
    )
    tex, _figs, charts, _dias, _drops = parse_model_output(
        raw, max_images=0, max_charts=2
    )
    assert [c["id"] for c in charts] == ["cht_01"]
    assert "%CASE3_CHART:cht_01%" in tex
