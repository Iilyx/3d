"""Add native OOXML charts to Liber PPTX slides."""

from __future__ import annotations

import logging
from typing import Any

from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.util import Inches, Pt

log = logging.getLogger("case3.slides_pptx_charts")


def _chart_type(ir_type: str):
    t = (ir_type or "bar").lower()
    if t == "line":
        return XL_CHART_TYPE.LINE_MARKERS
    if t == "area":
        return XL_CHART_TYPE.AREA
    if t in ("stacked_bar",):
        return XL_CHART_TYPE.COLUMN_STACKED
    if t == "horizontal_bar":
        return XL_CHART_TYPE.BAR_CLUSTERED
    if t == "donut":
        return XL_CHART_TYPE.DOUGHNUT
    if t in ("grouped_bar", "bar"):
        return XL_CHART_TYPE.COLUMN_CLUSTERED
    return XL_CHART_TYPE.COLUMN_CLUSTERED


def _is_line_like(chart_type) -> bool:
    return chart_type in (
        XL_CHART_TYPE.LINE_MARKERS,
        XL_CHART_TYPE.LINE,
    )


def _series_display_name(raw: str, *, chart_type, series_ir: dict[str, Any]) -> str:
    name = (raw or "").strip()
    if name and name.lower() not in ("series", "dataset", "data"):
        return name
    title = str(series_ir.get("title") or "").strip()
    if title:
        return title[:48]
    if chart_type == XL_CHART_TYPE.DOUGHNUT:
        return "Доля"
    return name or "Series"


def _color_series(
    chart,
    chart_type,
    *,
    series_colors: list[RGBColor],
    n_categories: int,
) -> None:
    """Apply pack colors: multi-series by series; single series by category point."""
    if not series_colors:
        return
    try:
        series_list = list(chart.series)
    except Exception:
        log.debug("pptx chart: cannot list series", exc_info=True)
        return
    if not series_list:
        return

    point_color_types = {
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        XL_CHART_TYPE.BAR_CLUSTERED,
        XL_CHART_TYPE.DOUGHNUT,
        XL_CHART_TYPE.PIE,
    }

    # One series → color each category/point from the pack (Julius-like bars/donut).
    if len(series_list) == 1 and chart_type in point_color_types and n_categories > 1:
        ser = series_list[0]
        try:
            for i, pt in enumerate(ser.points):
                color = series_colors[i % len(series_colors)]
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = color
                try:
                    pt.format.line.fill.background()
                except Exception:
                    log.debug("pptx chart: point line clear failed", exc_info=True)
        except Exception:
            # Fallback: whole series one color
            log.debug("pptx chart: point colors failed; solid series", exc_info=True)
            try:
                ser.format.fill.solid()
                ser.format.fill.fore_color.rgb = series_colors[0]
            except Exception:
                log.debug("pptx chart: solid series fallback failed", exc_info=True)
        return

    for i, ser in enumerate(series_list):
        color = series_colors[i % len(series_colors)]
        try:
            if chart_type == XL_CHART_TYPE.AREA:
                ser.format.fill.solid()
                ser.format.fill.fore_color.rgb = color
                ser.format.line.color.rgb = color
                ser.format.line.width = Pt(1.5)
            elif _is_line_like(chart_type):
                ser.format.line.color.rgb = color
                ser.format.line.width = Pt(2.25)
            else:
                ser.format.fill.solid()
                ser.format.fill.fore_color.rgb = color
        except Exception:
            log.debug("pptx chart: series color failed i=%s", i, exc_info=True)
            continue


def _style_donut_labels(plot) -> None:
    """Percent labels on donut slices (twin has center %; OOXML ≈ labels)."""
    try:
        plot.has_data_labels = True
        labels = plot.data_labels
        labels.show_percentage = True
        labels.show_value = False
        labels.show_category_name = False
        labels.show_series_name = False
        try:
            labels.font.size = Pt(11)
            labels.font.bold = True
        except Exception:
            log.debug("pptx chart: donut label font failed", exc_info=True)
    except Exception:
        log.debug("pptx chart: donut labels failed", exc_info=True)


def _add_scatter(slide, series_ir: dict[str, Any], *, left, top, width, height) -> bool:
    data = XyChartData()
    added = False
    for s in series_ir.get("series") or []:
        if not isinstance(s, dict):
            continue
        points = [p for p in (s.get("points") or []) if isinstance(p, dict)]
        if len(points) < 2:
            continue
        series = data.add_series(str(s.get("name") or "Точки"))
        for p in points:
            series.add_data_point(float(p["x"]), float(p["y"]))
        added = True
    if not added:
        return False
    try:
        slide.shapes.add_chart(
            XL_CHART_TYPE.XY_SCATTER, left, top, width, height, data
        )
    except Exception:
        log.debug("pptx scatter failed", exc_info=True)
        return False
    return True


def add_native_kpi(slide, series_ir: dict[str, Any], *, left, top, width, height, color: RGBColor) -> bool:
    """KPI is a number, not a chart picture."""
    value = str(series_ir.get("value") or "").strip()
    if not value:
        return False
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.clear()
    p = frame.paragraphs[0]
    run = p.add_run()
    run.text = value
    run.font.size = Pt(60)
    run.font.bold = True
    run.font.color.rgb = color
    run.font.name = "Georgia"
    label = str(series_ir.get("label") or "").strip()
    if label:
        p2 = frame.add_paragraph()
        run2 = p2.add_run()
        run2.text = label
        run2.font.size = Pt(18)
        run2.font.color.rgb = color
        run2.font.name = "Calibri"
    return True


def add_native_chart(
    slide,
    series_ir: dict[str, Any],
    *,
    left,
    top,
    width,
    height,
    series_colors: list[RGBColor] | None = None,
) -> bool:
    """Embed a native chart; return False if data unusable."""
    if str(series_ir.get("type") or "").lower() == "scatter":
        return _add_scatter(
            slide, series_ir, left=left, top=top, width=width, height=height
        )
    cats = list(series_ir.get("categories") or [])
    series = list(series_ir.get("series") or [])
    if not cats or not series:
        return False
    chart_type = _chart_type(str(series_ir.get("type") or "bar"))
    data = CategoryChartData()
    data.categories = cats
    for s in series:
        name = _series_display_name(
            str(s.get("name") or ""),
            chart_type=chart_type,
            series_ir=series_ir,
        )
        vals = list(s.get("values") or [])
        if len(vals) < len(cats):
            vals = vals + [None] * (len(cats) - len(vals))
        data.add_series(name, vals[: len(cats)])

    try:
        graphic = slide.shapes.add_chart(
            chart_type, left, top, width, height, data
        )
    except Exception:
        log.debug("pptx chart: add_chart failed type=%s", chart_type, exc_info=True)
        return False
    chart = graphic.chart
    try:
        chart.has_legend = len(series) > 1 or chart_type == XL_CHART_TYPE.DOUGHNUT
        if chart.has_legend:
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.include_in_layout = False
    except Exception:
        log.debug("pptx chart: legend style failed", exc_info=True)

    _color_series(
        chart,
        chart_type,
        series_colors=list(series_colors or []),
        n_categories=len(cats),
    )

    try:
        plot = chart.plots[0]
        if chart_type == XL_CHART_TYPE.DOUGHNUT:
            _style_donut_labels(plot)
        else:
            plot.has_data_labels = False
        if chart_type in (
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            XL_CHART_TYPE.BAR_CLUSTERED,
            XL_CHART_TYPE.COLUMN_STACKED,
        ):
            try:
                plot.gap_width = 80
            except Exception:
                log.debug("pptx chart: gap_width failed", exc_info=True)
    except Exception:
        log.debug("pptx chart: plot style failed", exc_info=True)

    try:
        chart.font.size = Pt(10)
        if chart_type == XL_CHART_TYPE.BAR_CLUSTERED and len(cats) >= 8:
            chart.category_axis.tick_labels.font.size = Pt(9)
    except Exception:
        log.debug("pptx chart: font size failed", exc_info=True)

    return True
