"""Donut print canvas must be square — wide 1100×560 attrs make an oval + empty right."""

from __future__ import annotations

import re

from case3.chart_types_coerce import enhance_donut_html


_DONUT = """
<canvas id="c2" width="1100" height="560"></canvas>
<script>
new Chart(document.getElementById('c2'), {
  type: 'doughnut',
  data: {
    labels: ['Онлайн', 'Розница', 'Партнёры'],
    datasets: [{ data: [48, 35, 17], backgroundColor: ['#3F5210', '#5A6E28', '#8A9A5B'] }]
  },
  options: { plugins: { legend: { display: true } } }
});
window.__CASE3_CHART_READY = true;
</script>
"""


def test_enhance_donut_forces_square_canvas() -> None:
    out = enhance_donut_html(_DONUT)
    m = re.search(r'<canvas\b([^>]*)>', out, flags=re.I)
    assert m, out[:200]
    attrs = m.group(1)
    w = re.search(r'\bwidth\s*=\s*["\']?(\d+)', attrs, flags=re.I)
    h = re.search(r'\bheight\s*=\s*["\']?(\d+)', attrs, flags=re.I)
    assert w and h, attrs
    assert int(w.group(1)) == int(h.group(1))
    assert int(w.group(1)) >= 400
    assert "donut-layout" in out
    assert "valued-legend" in out


def test_enhance_donut_parses_ru_comma_space_numbers_and_escapes_html() -> None:
    raw = """
<canvas id="c" width="520" height="520"></canvas>
<script>
new Chart(document.getElementById('c'), {
  type: 'doughnut',
  data: {
    labels: ['Минск <центр>', 'Гомель & юг'],
    datasets: [{ data: ['18 400,5', 6100.5], backgroundColor: ['#3F5210', '#5A6E28'] }]
  },
  options: { plugins: { legend: { display: true } } }
});
</script>
"""
    out = enhance_donut_html(raw)
    assert "donut-layout" in out
    assert "&lt;центр&gt;" in out
    assert "&amp; юг" in out
    assert "18400.5" in out or "18400,5" in out or "75%" in out
    html_part = out.split("<script", 1)[0]
    assert "<центр>" not in html_part
