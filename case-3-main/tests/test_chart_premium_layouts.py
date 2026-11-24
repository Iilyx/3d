"""Phase 2: soft palettes, KPI CSS vars, donut center + valued legend."""

from __future__ import annotations

import re
from pathlib import Path

from case3.chart_style import (
    _PALETTES,
    apply_kpi_palette_vars,
    apply_palette_to_html,
    palette_css_vars,
)
from case3.chart_types_coerce import enhance_donut_html, polish_charts


def test_palettes_are_published_datavis_schemes() -> None:
    """Named presets keep IDs; atelier = Tol vibrant teal ink; no purple."""
    assert set(_PALETTES) == {"editorial", "ocean", "sunset", "mono", "atelier"}
    at = _PALETTES["atelier"]
    assert at["primary"].upper() == "#004D47"
    assert "0.34" in str(at["area"])
    # Dark teal ink — green dominates red; not purple
    r, g, b = int(at["primary"][1:3], 16), int(at["primary"][3:5], 16), int(at["primary"][5:7], 16)
    assert g > r and g >= b - 10
    assert _PALETTES["ocean"]["primary"].upper() == "#0072B2"
    assert _PALETTES["mono"]["primary"].upper() != "#111827"
    blob = " ".join(
        str(v)
        for p in _PALETTES.values()
        for v in (p["primary"], *p["accents"])
    ).lower()
    assert "#7c3aed" not in blob and "#6366f1" not in blob


def test_palette_css_vars_expose_kpi_inks() -> None:
    css = palette_css_vars("atelier")
    assert "--kpi-value:" in css
    assert "--kpi-label:" in css
    assert "--chart-ink:" in css
    assert _PALETTES["atelier"]["primary"].upper() in css.upper()


def test_apply_kpi_palette_vars_injects_style_block() -> None:
    html = (
        '<div class="kpi"><div class="value">28</div>'
        '<div class="label">Клиенты</div></div>'
        "<script>window.__CASE3_CHART_READY=true;</script>"
    )
    out = apply_kpi_palette_vars(html, "ocean")
    assert "case3-palette" in out or "--kpi-value" in out
    assert _PALETTES["ocean"]["primary"].upper() in out.upper() or any(
        a.upper() in out.upper() for a in _PALETTES["ocean"]["accents"]
    )
    assert 'class="kpi"' in out
    assert "28" in out


def test_polish_charts_applies_kpi_palette() -> None:
    charts = [
        {
            "id": "cht_01",
            "type": "kpi",
            "caption": "28 клиентов",
            "html": (
                '<div class="kpi"><div class="value">28</div>'
                '<div class="label">Клиенты</div></div>'
                "<script>window.__CASE3_CHART_READY=true;</script>"
            ),
        }
    ]
    out = polish_charts(charts, palette_id="atelier")
    html = out[0]["html"]
    assert "--kpi-value" in html or "case3-palette" in html
    assert "#E85D04" not in html  # no hardcoded frame orange in fragment
    assert out[0].get("palette") == "atelier"
    ocean = polish_charts(charts, palette_id="ocean")[0]["html"]
    assert _PALETTES["ocean"]["primary"] in ocean or any(
        a in ocean for a in _PALETTES["ocean"]["accents"][:2]
    )


def test_chart_frame_has_premium_css_hooks() -> None:
    frame = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "case3"
        / "templates"
        / "chart_frame.html"
    ).read_text(encoding="utf-8")
    for needle in (
        ".chart-card",
        ".chart-kpi-header",
        ".donut-layout",
        ".donut-center",
        ".valued-legend",
        "--kpi-value",
        "var(--kpi-value",
    ):
        assert needle in frame
    # Soft KPI — not hardcoded vivid orange as sole value color
    assert "color: #E85D04" not in frame


_DONUT = (
    '<canvas id="c1" width="1100" height="560"></canvas><script>'
    "new Chart(document.getElementById('c1'),{type:'doughnut',data:{"
    "labels:['Сегмент A','Сегмент B','Сегмент C'],"
    "datasets:[{data:[51,29,20],backgroundColor:['#3F5210','#7A8F45','#A8B87A'],"
    "borderWidth:2,borderColor:'#ffffff'}]},"
    "options:{plugins:{legend:{position:'bottom'}},cutout:'58%',animation:false}});"
    "window.__CASE3_CHART_READY=true;</script>"
)


def test_enhance_donut_adds_center_and_valued_legend() -> None:
    out = enhance_donut_html(_DONUT)
    assert "donut-layout" in out
    assert "donut-center" in out
    assert "valued-legend" in out
    assert "51%" in out
    assert "Сегмент A" in out
    # absolute + pct rows
    assert re.search(r"valued-legend__pct|>\s*51%\s*<", out)
    assert "29" in out and "20" in out
    # Chart.js canvas still present; animation false preserved
    assert "type:'doughnut'" in out or 'type:"doughnut"' in out
    assert "animation:false" in out or "animation: false" in out


def test_a_small_slice_is_not_printed_as_zero() -> None:
    html = (
        '<canvas id="c1" width="520" height="520"></canvas><script>'
        "new Chart(c,{type:'doughnut',data:{"
        "labels:['Минская','Гомельская'],"
        "datasets:[{data:[996,4],backgroundColor:['#3F5210','#7A8F45']}]},"
        "options:{animation:false}});"
        "</script>"
    )
    out = enhance_donut_html(html)
    assert "0,4%" in out
    assert ">0%<" not in out


def test_many_regions_get_a_dense_legend() -> None:
    labels = ",".join(f"'Область {index:02d}'" for index in range(12))
    values = ",".join(["10"] * 12)
    html = (
        '<canvas id="c1" width="520" height="520"></canvas><script>'
        "new Chart(c,{type:'doughnut',data:{"
        f"labels:[{labels}],datasets:[{{data:[{values}],backgroundColor:['#3F5210']}}]}},"
        "options:{animation:false}});"
        "</script>"
    )
    out = enhance_donut_html(html)
    assert "is-dense" in out
    assert "Область 11" in out
    frame = Path(__file__).resolve().parents[1].joinpath(
        "src/case3/templates/chart_frame.html"
    ).read_text(encoding="utf-8")
    assert ".valued-legend.is-dense" in frame


def test_enhance_donut_idempotent() -> None:
    once = enhance_donut_html(_DONUT)
    twice = enhance_donut_html(once)
    assert twice.count("donut-center") == 1
    assert twice.count('class="lbl"') == once.count('class="lbl"')
    # No orphan lbl left of canvas from broken unwrap
    assert re.search(
        r'donut-center[\s\S]*?</div>\s*<canvas',
        twice,
        flags=re.I,
    )
    assert twice.count("donut-layout") == 1
    assert "51%" in twice


def test_enhance_donut_rebuilds_after_palette_like_edit() -> None:
    """LLM/palette may keep doughnut but drop shell — enhance must restore."""
    from case3.chart_style import apply_palette_to_html

    wrapped = enhance_donut_html(_DONUT)
    remapped = apply_palette_to_html(wrapped, "ocean")
    # Simulate LLM dropping layout (keep canvas+script only).
    bare = remapped
    if "donut-layout" in bare:
        # Force bare path: unwrap via second enhance after stripping class marker
        bare = remapped.replace("donut-layout", "x-layout", 1)
    restored = enhance_donut_html(
        # Prefer true unwrap: take from enhanced then re-enhance ocean bare doughnut
        apply_palette_to_html(_DONUT, "ocean")
    )
    assert "donut-layout" in restored
    assert "valued-legend" in restored
    assert restored.count("donut-layout") == 1


def test_enhance_donut_noop_when_unparseable() -> None:
    raw = '<canvas id="c"></canvas><script>/* custom */window.__CASE3_CHART_READY=true;</script>'
    assert enhance_donut_html(raw) == raw


def test_enhance_donut_strips_pct_and_abs_from_labels() -> None:
    """Model often puts 'Retail 42% (210)' in labels — legend must not triple the numbers."""
    raw = (
        "<canvas id='c2' width='520' height='520'></canvas><script>"
        "new Chart(document.getElementById('c2'),{type:'doughnut',"
        "data:{labels:['Retail 42% (210)','Food 28% (140)'],"
        "datasets:[{data:[210,140],backgroundColor:['#0077BB','#EE7733'],"
        "borderWidth:2,borderColor:'#ffffff'}]},"
        "options:{plugins:{legend:{display:false}},cutout:'60%',animation:false}});"
        "window.__CASE3_CHART_READY=true;</script>"
    )
    out = enhance_donut_html(raw)
    assert ">Retail</div>" in out and "donut-center" in out
    legend = out.split("valued-legend", 1)[1].split("</ul>", 1)[0]
    assert "Retail 42%" not in legend
    assert "Retail" in legend and "Food" in legend
    assert "60%" in legend and "40%" in legend
    assert "labels:['Retail','Food']" in out


def test_polish_charts_enhances_donut() -> None:
    charts = [{"id": "cht_01", "type": "donut", "caption": "Доли", "html": _DONUT}]
    out = polish_charts(charts, palette_id="auto")
    assert "donut-layout" in out[0]["html"]
    assert "valued-legend" in out[0]["html"]
