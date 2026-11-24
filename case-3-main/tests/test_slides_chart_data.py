"""Extract Chart.js series for native PPTX charts."""

from __future__ import annotations

from case3.slides_chart_data import (
    attach_series_ir,
    ensure_deck_charts,
    extract_chart_series,
    series_from_figures_json,
)


LINE_HTML = """
<canvas id="c1"></canvas><script>new Chart(document.getElementById('c1'),{
type:'line',data:{labels:['Q3 2025','Q3 2026'],datasets:[{label:'Выручка',data:[4.1,4.8],
borderColor:'#2E4208'}]},options:{}});</script>
"""

BAR_HTML = """
<script>new Chart(document.getElementById('c2'),{type:'bar',data:{
labels:['Офлайн','Сайт','Маркетплейсы'],
datasets:[{label:'Доля',data:[48,35,17],backgroundColor:['#2E4208','#4F6B14','#7A9A28']}]
},options:{}});</script>
"""


def test_extract_line() -> None:
    ir = extract_chart_series(LINE_HTML, chart_type="line")
    assert ir is not None
    assert ir["type"] == "line"
    assert ir["categories"] == ["Q3 2025", "Q3 2026"]
    assert ir["series"][0]["values"] == [4.1, 4.8]


def test_extract_bar() -> None:
    ir = extract_chart_series(BAR_HTML, chart_type="bar")
    assert ir is not None
    assert ir["type"] == "bar"
    assert len(ir["categories"]) == 3
    assert ir["series"][0]["values"] == [48.0, 35.0, 17.0]


def test_a_second_series_still_reaches_word_when_its_shape_differs() -> None:
    html = (
        "labels:['Минск','Гомель'],datasets:["
        "{label:'План',data:[10,20],backgroundColor:'#111'},"
        "{data:[12,18],label:'Факт',borderColor:{r:1,g:2}}"
        "]"
    )
    ir = extract_chart_series(html, chart_type="grouped_bar")
    assert ir is not None
    assert [item["name"] for item in ir["series"]] == ["План", "Факт"]
    assert ir["series"][1]["values"] == [12.0, 18.0]


def test_spaced_sum_stays_one_point_and_a_null_keeps_its_category() -> None:
    html = """
<script>new Chart(el,{type:'bar',data:{
labels:['Брестская','Витебская','Гомельская'],
datasets:[{label:'Сумма',data:[105 865,2, null, 80100.5]}]
}});</script>
"""
    ir = extract_chart_series(html, chart_type="bar")
    assert ir is not None
    assert ir["categories"] == ["Брестская", "Витебская", "Гомельская"]
    assert ir["series"][0]["values"][0] == 105865.2
    assert ir["series"][0]["values"][1] is None
    assert ir["series"][0]["values"][2] == 80100.5


def test_a_short_decimal_comma_is_one_bar_and_a_bare_pair_stays_two() -> None:
    one = extract_chart_series(
        "labels:['Маржа'],datasets:[{data:[12,5]}]",
        chart_type="bar",
    )
    assert one is not None
    assert one["series"][0]["values"] == [12.5]
    pair = extract_chart_series(
        "labels:['Минская','Гомельская'],datasets:[{data:[100,40]}]",
        chart_type="bar",
    )
    assert pair is not None
    assert pair["series"][0]["values"] == [100.0, 40.0]
    wide = extract_chart_series(
        "labels:['Минская'],datasets:[{data:[105 865,25]}]",
        chart_type="bar",
    )
    assert wide is not None
    assert wide["series"][0]["values"] == [105865.25]


def test_extract_empty() -> None:
    assert extract_chart_series("", chart_type="bar") is None
    assert extract_chart_series("<div/>", chart_type="kpi") is None


def test_attach_series_ir_persists_on_chart() -> None:
    chart = {"id": "cht_01", "type": "bar", "html": BAR_HTML}
    ir = attach_series_ir(chart)
    assert ir is not None
    assert chart["series"]["categories"] == ["Офлайн", "Сайт", "Маркетплейсы"]
    assert chart["series"]["series"][0]["values"] == [48.0, 35.0, 17.0]


def test_series_from_figures_prefers_stored() -> None:
    stored = {
        "type": "bar",
        "categories": ["A", "B"],
        "series": [{"name": "X", "values": [1.0, 2.0]}],
    }
    fj = {
        "charts": [
            {
                "id": "cht_01",
                "type": "bar",
                "html": "<script>broken</script>",
                "series": stored,
            }
        ]
    }
    ir = series_from_figures_json(fj, "cht_01")
    assert ir == stored


def test_ensure_deck_injects_chart_hero_when_missing() -> None:
    deck = {
        "slides": [
            {"id": "s0", "layout": "title", "title": "Hi"},
            {"id": "s1", "layout": "bullets", "title": "Notes", "bullets": ["a"]},
        ]
    }
    series_by_id = {
        "cht_01": {
            "type": "bar",
            "categories": ["Q1", "Q2"],
            "series": [{"name": "Rev", "values": [1.0, 2.0]}],
        }
    }
    assert bool(ensure_deck_charts(deck, series_by_id)) is True
    ids = [
        str(s.get("chart_id") or s.get("media_id") or "")
        for s in deck["slides"]
        if isinstance(s, dict)
    ]
    assert "cht_01" in ids
    layouts = [str(s.get("layout")) for s in deck["slides"] if isinstance(s, dict)]
    assert "chart_hero" in layouts
    injected = [s for s in deck["slides"] if s.get("chart_id") == "cht_01"][0]
    assert "caption" not in injected or injected["caption"] == ""
    assert "takeaway" not in injected or injected["takeaway"] == ""
    assert "kicker" not in injected or injected["kicker"] == ""


def test_ensure_deck_noop_when_chart_present() -> None:
    deck = {
        "slides": [
            {
                "id": "s1",
                "layout": "chart_hero",
                "title": "Rev",
                "chart_id": "cht_01",
            }
        ]
    }
    series_by_id = {
        "cht_01": {
            "type": "bar",
            "categories": ["Q1"],
            "series": [{"name": "Rev", "values": [1.0]}],
        }
    }
    assert bool(ensure_deck_charts(deck, series_by_id)) is False


def test_ensure_deck_charts_injects_missing_ids() -> None:
    """If IR kept one chart but run has two eligible — inject the missing one."""
    deck = {
        "slides": [
            {"id": "s0", "layout": "title", "title": "Hi"},
            {
                "id": "s1",
                "layout": "chart_hero",
                "title": "Only one",
                "chart_id": "cht_01",
            },
            {"id": "s2", "layout": "closing", "title": "Bye"},
        ]
    }
    series_by_id = {
        "cht_01": {
            "type": "bar",
            "categories": ["Q1"],
            "series": [{"name": "A", "values": [1.0]}],
        },
        "cht_02": {
            "type": "donut",
            "categories": ["X", "Y"],
            "series": [{"name": "Series", "values": [60.0, 40.0]}],
        },
    }
    injected = ensure_deck_charts(deck, series_by_id)
    assert injected == ["cht_02"]
    ids = {
        str(s.get("chart_id") or s.get("media_id") or "")
        for s in deck["slides"]
        if isinstance(s, dict)
    }
    assert "cht_01" in ids and "cht_02" in ids


def test_attach_donut_renames_anonymous_series() -> None:
    html = """
    <script>new Chart(c,{type:'doughnut',data:{labels:['A','B'],
    datasets:[{data:[60,40]}]},options:{}});</script>
    """
    chart = {"id": "cht_02", "type": "donut", "html": html, "caption": "Бюджет"}
    ir = attach_series_ir(chart)
    assert ir is not None
    assert ir["series"][0]["name"] == "Бюджет"


def test_attach_series_ir_refreshes_type_after_coerce() -> None:
    """Type edit must update Series IR so native DOCX/PPTX match Liber."""
    from case3.chart_coerce import apply_type_to_chart

    grouped_html = """
    <script>new Chart(c,{type:'bar',data:{labels:['Q1','Q2'],
    datasets:[
      {label:'A',data:[10,20]},
      {label:'B',data:[5,15]}
    ]},options:{}});</script>
    """
    chart = {
        "id": "cht_01",
        "type": "grouped_bar",
        "html": grouped_html,
        "caption": "Выручка",
    }
    assert attach_series_ir(chart) is not None
    assert chart["series"]["type"] == "grouped_bar"
    assert len(chart["series"]["series"]) == 2

    chart = apply_type_to_chart(chart, "donut")
    ir = attach_series_ir(chart)
    assert ir is not None
    assert ir["type"] == "donut"
    assert chart["series"]["type"] == "donut"
    # Coerced donut collapses multi-series — IR must match HTML, not stale bar IR.
    assert len(ir["series"]) == 1


def test_series_from_figures_ignores_stale_type() -> None:
    fj = {
        "charts": [
            {
                "id": "cht_01",
                "type": "line",
                "html": LINE_HTML,
                "series": {
                    "type": "bar",
                    "categories": ["Q3 2025", "Q3 2026"],
                    "series": [{"name": "Выручка", "values": [4.1, 4.8]}],
                },
            }
        ]
    }
    ir = series_from_figures_json(fj, "cht_01")
    assert ir is not None
    assert ir["type"] == "line"


def test_attach_kpi_and_scatter_become_native_ir() -> None:
    chart = {
        "id": "cht_01",
        "type": "kpi",
        "html": '<div class="kpi"><div class="value">42</div><div class="label">NPS</div></div>',
        "series": {
            "type": "bar",
            "categories": ["A"],
            "series": [{"name": "S", "values": [1.0]}],
        },
    }
    ir = attach_series_ir(chart)
    assert ir is not None
    assert ir["type"] == "kpi"
    assert ir["value"] == "42"
    assert ir["label"] == "NPS"

    chart = {
        "id": "cht_02",
        "type": "scatter",
        "html": "<script>new Chart(c,{type:'scatter',data:{datasets:[{label:'Точки',data:[{x:1,y:2},{x:3,y:4}]}]}});</script>",
        "series": {
            "type": "bar",
            "categories": ["A"],
            "series": [{"name": "S", "values": [1.0]}],
        },
    }
    ir = attach_series_ir(chart)
    assert ir is not None
    assert ir["type"] == "scatter"
    assert ir["series"][0]["points"] == [{"x": 1.0, "y": 2.0}, {"x": 3.0, "y": 4.0}]


def test_scatter_and_kpi_land_as_native_shapes() -> None:
    from pptx import Presentation
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches

    from case3.slides_pptx_charts import add_native_chart, add_native_kpi
    from case3.slides_pptx_draw import _hex_rgb

    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    assert add_native_chart(
        slide,
        {
            "type": "scatter",
            "series": [
                {
                    "name": "Точки",
                    "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
                }
            ],
        },
        left=Inches(1),
        top=Inches(1),
        width=Inches(4),
        height=Inches(3),
    )
    assert slide.shapes[-1].chart.chart_type == XL_CHART_TYPE.XY_SCATTER

    kpi = prs.slides.add_slide(blank)
    assert add_native_kpi(
        kpi,
        {"type": "kpi", "value": "42", "label": "NPS"},
        left=Inches(1),
        top=Inches(1),
        width=Inches(4),
        height=Inches(2),
        color=_hex_rgb("#1B3A4B"),
    )
    assert "42" in kpi.shapes[-1].text_frame.text


def test_populate_deck_bullet_node_maps() -> None:
    from case3.slides_chart_data import populate_deck_bullet_node_maps

    deck = {
        "slides": [
            {
                "id": "s1",
                "layout": "media_split",
                "media_id": "dia_01",
                "bullets": ["Первый шаг процесса", "Второй шаг процесса"],
            }
        ]
    }
    diagrams = [
        {
            "id": "dia_01",
            "type": "flowchart",
            "mermaid": "flowchart LR\nStep1[Старт] --> Step2[Финиш]",
        }
    ]
    populate_deck_bullet_node_maps(deck, diagrams)
    assert deck["slides"][0].get("bullet_node_map") == {"0": "Step1", "1": "Step2"}

