"""Stacked bars get white segment gaps when the model omits them."""

from __future__ import annotations

from case3.chart_types_coerce import harden_chart_html


def test_harden_stacked_injects_white_segment_borders() -> None:
    html = (
        "<canvas id='c'></canvas><script>"
        "new Chart(c,{type:'bar',data:{labels:['Q1'],datasets:["
        "{label:'A',data:[10],backgroundColor:'#1E8AD4',stack:'s'},"
        "{label:'B',data:[8],backgroundColor:'#E85D04',stack:'s'}"
        "]},options:{scales:{x:{stacked:true},y:{stacked:true}},animation:false}});"
        "</script>"
    )
    out = harden_chart_html(html, "stacked_bar")
    assert "borderColor:'#ffffff'" in out or 'borderColor:"#ffffff"' in out
    assert "borderWidth:1" in out
    assert "data:[10]" in out
    assert "data:[8]" in out


def test_harden_stacked_keeps_existing_white_borders() -> None:
    html = (
        "datasets:[{borderWidth:3,borderColor:'#ffffff',label:'A',stack:'s'},"
        "{borderWidth:3,borderColor:'#ffffff',label:'B',stack:'s'}]"
    )
    out = harden_chart_html(html, "stacked_bar")
    assert out.count("borderColor:'#ffffff'") == 2
    assert "borderWidth:3" in out
