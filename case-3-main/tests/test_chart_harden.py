"""Chart hardening tests for chat canvas, scales merge, hbar multi-series, and RU label wrap."""

from __future__ import annotations

from case3.chart_harden import (
    _colorize_hbar_categories,
    _relax_vertical_bar_labels,
    full_chat_canvas,
)


def test_full_chat_canvas_is_type_aware() -> None:
    kpi = '<div class="kpi-card"><div class="kpi-val">7544</div><div class="kpi-lbl">Гомель</div></div>'
    assert "<canvas" not in full_chat_canvas(kpi, chart_type="kpi")
    assert full_chat_canvas(kpi, chart_type="kpi") == kpi

    donut = '<div class="chart-card donut-layout"><div class="donut-viz"><canvas id="c" width="520" height="520"></canvas></div></div>'
    donut_out = full_chat_canvas(donut, chart_type="donut")
    assert 'width="520"' in donut_out
    assert 'height="520"' in donut_out
    assert "1100" not in donut_out

    hbar = '<canvas id="c" width="600" height="720"></canvas><script>new Chart(c,{type:"bar",options:{indexAxis:"y"}});</script>'
    hbar_out = full_chat_canvas(hbar, chart_type="horizontal_bar")
    assert 'height="720"' in hbar_out
    assert 'width="1100"' in hbar_out


def test_relax_vertical_bar_labels_merges_existing_scales_and_wraps_long_ru() -> None:
    labels = [
        "Минская область северный участок",
        "Гомельская область центральный округ",
        "Брестская область",
        "Витебская область",
        "Гродненская область",
        "Могилевская область",
        "г. Минск",
        "Республиканский центр",
    ]
    lbl_js = ",".join(f"'{x}'" for x in labels)
    raw = (
        f"<canvas id='c'></canvas><script>new Chart(document.getElementById('c'),"
        f"{{type:'bar',data:{{labels:[{lbl_js}],datasets:[{{label:'Факт',data:[1,2,3,4,5,6,7,8]}}]}},"
        f"options:{{scales:{{y:{{beginAtZero:true}}}},plugins:{{legend:{{display:false}}}}}}}});</script>"
    )
    out = _relax_vertical_bar_labels(raw)
    # Must NOT emit a duplicate top-level `scales:` key inside options!
    assert out.count("scales:") == 1
    assert "beginAtZero:true" in out
    assert "maxRotation:" in out
    assert "layout:" in out or "padding:" in out


def test_colorize_hbar_categories_skips_multi_dataset_series() -> None:
    raw = (
        "<canvas id='c'></canvas><script>new Chart(c,{type:'bar',"
        "data:{labels:['Минск','Гомель','Брест'],"
        "datasets:[{label:'План',data:[100,200,300],backgroundColor:'#4E79A7'},"
        "{label:'Факт',data:[110,180,290],backgroundColor:'#F28E2B'}]},"
        "options:{indexAxis:'y'}});</script>"
    )
    out = _colorize_hbar_categories(raw, "atelier")
    assert "backgroundColor:'#4E79A7'" in out
    assert "backgroundColor:'#F28E2B'" in out
