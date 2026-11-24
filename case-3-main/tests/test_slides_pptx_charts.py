"""Native OOXML charts land in PPTX when series IR is present."""

from __future__ import annotations

import zipfile
from pathlib import Path

from pptx.dml.color import RGBColor

from case3.slides_pptx_charts import add_native_chart
from case3.slides_pptx_native import build_native_pptx


def test_add_native_chart_embeds_chart_part(tmp_path: Path) -> None:
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "style": {
            "pack_id": "atelier",
            "colors": {
                "primary": "#2E4208",
                "accent": "#4F6B14",
                "ink": "#14161a",
                "ink2": "#2c3028",
                "muted": "#6A7160",
                "paper": "#f0ede4",
                "sheet": "#fffcf7",
                "rule": "#e6e2d8",
            },
            "fonts": {"title": "Georgia", "body": "Calibri", "fallback_pptx": "Calibri"},
            "chart_series": ["#2E4208", "#4F6B14"],
        },
        "slides": [
            {
                "id": "s1",
                "layout": "chart_hero",
                "title": "Revenue",
                "chart_id": "cht_1",
                "takeaway": "Up",
            }
        ],
    }
    series = {
        "type": "bar",
        "categories": ["Q1", "Q2", "Q3"],
        "series": [{"name": "Rev", "values": [10.0, 14.0, 18.0]}],
    }
    dest = tmp_path / "charts.pptx"
    build_native_pptx(deck, dest, chart_series_by_id={"cht_1": series})
    assert dest.is_file()
    with zipfile.ZipFile(dest) as zf:
        charts = [n for n in zf.namelist() if n.startswith("ppt/charts/")]
    assert charts, "expected native ppt/charts/* when series provided"


def test_add_native_chart_rejects_empty() -> None:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    ok = add_native_chart(
        slide,
        {"type": "bar", "categories": [], "series": []},
        left=Inches(1),
        top=Inches(1),
        width=Inches(6),
        height=Inches(4),
        series_colors=[RGBColor(0x2E, 0x42, 0x08)],
    )
    assert ok is False


def test_native_donut_has_percent_labels_and_named_series() -> None:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    ok = add_native_chart(
        slide,
        {
            "type": "donut",
            "categories": ["Продажи", "Маркетинг"],
            "series": [{"name": "Бюджет", "values": [45.0, 55.0]}],
        },
        left=Inches(1),
        top=Inches(1),
        width=Inches(6),
        height=Inches(4),
        series_colors=[RGBColor(0x2E, 0x42, 0x08), RGBColor(0x4F, 0x6B, 0x14)],
    )
    assert ok is True
    chart = slide.shapes[-1].chart
    plot = chart.plots[0]
    assert plot.has_data_labels is True
    assert plot.data_labels.show_percentage is True
    assert chart.has_legend is True
    assert chart.series[0].name == "Бюджет"


def test_every_deck_chart_gets_native_part(tmp_path: Path) -> None:
    """Each cht_* slide with series IR → its own ppt/charts/* part."""
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "style": {
            "pack_id": "atelier",
            "colors": {
                "primary": "#2E4208",
                "accent": "#4F6B14",
                "ink": "#14161a",
                "ink2": "#2c3028",
                "muted": "#6A7160",
                "paper": "#f0ede4",
                "sheet": "#fffcf7",
                "rule": "#e6e2d8",
            },
            "fonts": {"title": "Georgia", "body": "Calibri", "fallback_pptx": "Calibri"},
            "chart_series": ["#2E4208", "#4F6B14", "#7A9A28"],
        },
        "slides": [
            {
                "id": "s1",
                "layout": "chart_hero",
                "title": "Revenue",
                "chart_id": "cht_1",
            },
            {
                "id": "s2",
                "layout": "chart_split",
                "title": "Mix",
                "body": "Offline still leads.",
                "chart_id": "cht_2",
            },
        ],
    }
    series_by_id = {
        "cht_1": {
            "type": "bar",
            "categories": ["Q1", "Q2", "Q3"],
            "series": [{"name": "Rev", "values": [10.0, 14.0, 18.0]}],
        },
        "cht_2": {
            "type": "donut",
            "categories": ["A", "B", "C"],
            "series": [{"name": "Share", "values": [48.0, 35.0, 17.0]}],
        },
    }
    dest = tmp_path / "multi.pptx"
    build_native_pptx(deck, dest, chart_series_by_id=series_by_id)
    with zipfile.ZipFile(dest) as zf:
        charts = [n for n in zf.namelist() if n.startswith("ppt/charts/")]
    assert len(charts) >= 2, f"expected ≥2 native charts, got {charts}"


def test_native_area_chart_colors_fill_and_line() -> None:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    ok = add_native_chart(
        slide,
        {
            "type": "area",
            "categories": ["Q1", "Q2", "Q3"],
            "series": [{"name": "Трафик", "values": [100.0, 150.0, 220.0]}],
        },
        left=Inches(1),
        top=Inches(1),
        width=Inches(6),
        height=Inches(4),
        series_colors=[RGBColor(0x3D, 0x5A, 0x45)],
    )
    assert ok is True
    chart = slide.shapes[-1].chart
    ser = chart.series[0]
    # Area chart should have both fill and line colored
    assert ser.format.fill.fore_color.rgb == RGBColor(0x3D, 0x5A, 0x45)
    assert ser.format.line.color.rgb == RGBColor(0x3D, 0x5A, 0x45)
