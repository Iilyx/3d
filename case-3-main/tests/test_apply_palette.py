"""Local palette remap must recolor Chart.js HTML without touching data."""

from __future__ import annotations

from case3.chart_style import _PALETTES, apply_palette_to_html


def test_apply_palette_replaces_hex_with_ocean_inks() -> None:
    html = (
        "<canvas id='c'></canvas><script>"
        "new Chart(c,{type:'bar',data:{labels:['A'],datasets:["
        "{label:'X',data:[1],backgroundColor:'#E85D04',borderColor:'#0F3D3E'}"
        "]},options:{scales:{y:{grid:{color:'rgba(15,61,62,0.08)'}}}}});"
        "</script>"
    )
    out = apply_palette_to_html(html, "ocean")
    # Okabe–Ito ocean — primary #0072B2 / sky #56B4E9
    assert "#0072B2" in out.upper() or "#56B4E9" in out.upper()
    assert "data:[1]" in out
    assert "labels:['A']" in out
    assert "#E85D04" not in out


def test_named_green_paints_bars_that_had_no_color() -> None:
    from case3.chart_style import hue_from_text, hue_prompt_line, paint_hue_on_html

    html = (
        "<canvas id='c'></canvas><script>"
        "new Chart(c,{type:'bar',data:{labels:['Минск','Брест','Гомель'],datasets:["
        "{label:'Факт',data:[10,20,30]}]},options:{responsive:false}});"
        "</script>"
    )
    assert hue_from_text("столбцы зеленые") == "green"
    assert hue_from_text("перекрась графики в закат") == ""
    painted = paint_hue_on_html(html, "green")
    assert "backgroundColor:[" in painted
    assert "#1F8A45" in painted.upper()
    assert "data:[10,20,30]" in painted
    line = hue_prompt_line("сделай в зеленых цветах")
    assert "#1F8A45" in line.upper()
    assert "числа и type не меняй" in line


def test_apply_palette_noop_for_auto() -> None:
    html = "backgroundColor:'#E85D04'"
    assert apply_palette_to_html(html, "auto") == html


def test_atelier_palette_is_tol_vibrant() -> None:
    html = (
        "backgroundColor:'#111111';"
        "backgroundColor:'#888888';"
        "backgroundColor:'#CCCCCC'"
    )
    out = apply_palette_to_html(html, "atelier")
    up = out.upper()
    assert "#004D47" in up
    assert "#0077BB" in up or "#EE7733" in up or "#009988" in up
    assert "#111111" not in up


def test_atelier_keeps_white_borders_and_readable_labels() -> None:
    html = (
        "backgroundColor:['#111111','#444444','#888888','#CCCCCC'],"
        "borderColor:'#FFFFFF',"
        "labels:{color:'#333333'},"
        "ticks:{color:'#555555'}"
    )
    out = apply_palette_to_html(html, "atelier")
    up = out.upper()
    assert "#FFFFFF" in up
    assert "#5A706C" in up
    assert "#333333" not in up


def test_vivid_palettes_use_punchy_area_alpha() -> None:
    """Print≈preview: area fills ~0.34, not washed 0.16."""
    for pid in ("editorial", "ocean", "sunset", "atelier"):
        area = str(_PALETTES[pid]["area"])
        assert "0.34" in area, pid
        assert _PALETTES[pid]["primary"].startswith("#")
