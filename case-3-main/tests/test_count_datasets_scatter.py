"""Dataset counter must not treat scatter {x,y} points as extra series."""

from __future__ import annotations

from case3.chart_types_coerce import _count_datasets, ensure_legend_and_tooltips


def test_count_datasets_scatter_points_are_one_series() -> None:
    html = (
        "datasets:[{"
        "label:'Месяцы',"
        "data:[{x:3.1,y:41},{x:2.8,y:44},{x:2.4,y:48}],"
        "backgroundColor:'#004D47'"
        "}]"
    )
    assert _count_datasets(html) == 1


def test_count_datasets_grouped_bar_three_series() -> None:
    html = (
        "datasets:["
        "{label:'A',data:[1,2]},"
        "{label:'B',data:[3,4]},"
        "{label:'C',data:[5,6]}"
        "]"
    )
    assert _count_datasets(html) == 3


def test_scatter_single_series_hides_legend() -> None:
    html = (
        "<script>new Chart(c,{type:'scatter',data:{datasets:["
        "{label:'Месяцы',data:[{x:1,y:2},{x:2,y:3}],backgroundColor:'#004D47'}"
        "]},options:{plugins:{legend:{display:true}},animation:false}});</script>"
    )
    out = ensure_legend_and_tooltips(html, "scatter")
    assert "display:false" in out.replace(" ", "")
    assert "tooltip" in out.lower()
