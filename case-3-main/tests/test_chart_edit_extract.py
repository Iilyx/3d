from case3.chart_edit import _extract_html_fragment


def test_extract_from_fence() -> None:
    raw = "Sure:\n```html\n<canvas id='c'></canvas><script>new Chart()</script>\n```\n"
    out = _extract_html_fragment(raw)
    assert out.startswith("<canvas")


def test_extract_bare_canvas() -> None:
    raw = "Here you go\n<canvas id='x'></canvas><script>new Chart(x,{})</script>"
    assert _extract_html_fragment(raw).startswith("<canvas")
