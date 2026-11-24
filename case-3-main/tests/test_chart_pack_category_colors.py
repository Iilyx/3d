"""Twin HTML: pack colors per category for single-series bar/donut."""

from __future__ import annotations

from case3.chart_style import apply_pack_category_colors_to_html


BAR_SCALAR = """
<script>new Chart(c,{type:'bar',data:{labels:['Пн','Вт','Ср'],
datasets:[{label:'T',data:[1,2,3],backgroundColor:'#112233'}]},options:{}});</script>
"""

DONUT_SCALAR = """
<script>new Chart(c,{type:'doughnut',data:{labels:['A','B','C','D'],
datasets:[{data:[45,30,15,10],backgroundColor:'#112233'}]},options:{}});</script>
"""


def test_bar_gets_per_category_pack_array() -> None:
    pack = ["#2E4208", "#4F6B14", "#7A9A28"]
    out = apply_pack_category_colors_to_html(BAR_SCALAR, pack, chart_type="bar")
    assert "backgroundColor:[" in out.replace(" ", "")
    assert "#2E4208" in out.upper() or "#2E4208" in out
    assert "#4F6B14" in out.upper() or "#4F6B14" in out
    assert "#7A9A28" in out.upper() or "#7A9A28" in out


def test_donut_gets_segment_pack_array() -> None:
    pack = ["#2E4208", "#4F6B14", "#7A9A28", "#B8D45A"]
    out = apply_pack_category_colors_to_html(DONUT_SCALAR, pack, chart_type="donut")
    assert "backgroundColor:[" in out.replace(" ", "")
    for hx in pack:
        assert hx.upper() in out.upper()


def test_grouped_multi_series_left_alone() -> None:
    html = """
    <script>new Chart(c,{type:'bar',data:{labels:['A','B'],
    datasets:[
      {label:'X',data:[1,2],backgroundColor:'#111111'},
      {label:'Y',data:[3,4],backgroundColor:'#222222'}
    ]},options:{}});</script>
    """
    pack = ["#2E4208", "#4F6B14"]
    out = apply_pack_category_colors_to_html(html, pack, chart_type="grouped_bar")
    # Multi-series: do not expand into per-category arrays
    assert out == html or "backgroundColor:[" not in out.replace(" ", "")
