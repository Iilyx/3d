"""Coerce preferred chart types onto HTML + polish pass."""

from __future__ import annotations

import logging
import re
from typing import Any

from case3.chart_html import CHART_TYPES
from case3.chart_style import (
    apply_kpi_palette_vars,
    apply_palette_to_html,
    normalize_palette_id,
)
from case3.chart_harden import (
    _hide_legend_if_unnamed_dataset,
    _is_kpi_html,
    _kpi_html_from_chart,
    _landscape_canvas_if_square,
    _rewrite_js_type,
    chart_html_from_kpi,
    ensure_legend_and_tooltips,
    harden_chart_html,
    html_matches_type,
)
from case3.chart_donut import _unwrap_donut_layout, enhance_donut_html

log = logging.getLogger("case3.charts")

def polish_charts(
    charts: list[dict[str, Any]],
    *,
    palette_id: str = "auto",
) -> list[dict[str, Any]]:
    """Apply intent palette (if set), donut layout enhance, then geometry harden."""
    from case3.tex_safe import multi_chart_max_frac, sanitize_width

    pid = normalize_palette_id(palette_id)
    dense = len(charts or []) >= 2
    max_w = multi_chart_max_frac() if dense else None
    default_w = r"0.82\textwidth" if dense else r"0.85\textwidth"
    out: list[dict[str, Any]] = []
    for chart in charts:
        c = dict(chart)
        ctype = str(c.get("type") or "").strip()
        html = str(c.get("html") or "")
        if html and pid != "auto" and ctype != "kpi":
            html = apply_palette_to_html(html, pid)
        if html and ctype == "donut":
            html = enhance_donut_html(html)
        # CSS vars after layout wrap so #mount{--kpi-*} sits outside .donut-layout.
        if html and pid != "auto":
            html = apply_kpi_palette_vars(html, pid)
        if html:
            html = harden_chart_html(html, ctype, palette_id=pid)
            html = ensure_legend_and_tooltips(html, ctype)
        c["html"] = html
        if pid != "auto":
            c["palette"] = pid
        c["width"] = sanitize_width(
            str(c.get("width") or "") or None,
            default=default_w,
            max_frac=max_w,
        )
        out.append(c)
    return out

def apply_type_to_chart(chart: dict[str, Any], want: str) -> dict[str, Any]:
    """Force catalog type + matching HTML onto one chart dict."""
    if want not in CHART_TYPES:
        return chart
    c = dict(chart)
    html = str(c.get("html") or "")
    if want == "kpi":
        # KPI cards are not Chart.js — drop donut chrome if present.
        html = _unwrap_donut_layout(html) if "donut-layout" in html.lower() else html
        c["html"] = html
        if not _is_kpi_html(html):
            c["html"] = _kpi_html_from_chart(c)
            log.info("forced kpi markup on %s (was type=%s)", c.get("id"), chart.get("type"))
        c["type"] = "kpi"
        return c
    # Leaving KPI → synthesize Chart.js from the card value/label.
    if _is_kpi_html(html):
        html = chart_html_from_kpi(html, want)
        c["html"] = html
        log.info("built %s chart from kpi on %s", want, c.get("id"))
    # Leaving donut (or any leftover Mary wrap) → plain canvas+script first.
    left_donut = False
    if want != "donut" and html and re.search(r"donut-layout", html, flags=re.I):
        html = _unwrap_donut_layout(html)
        html = _landscape_canvas_if_square(html)
        c["html"] = html
        left_donut = True
    if html and not html_matches_type(html, want):
        c["html"] = _rewrite_js_type(html, want)
        log.info(
            "rewrote chart %s html for type %s → %s",
            c.get("id"),
            chart.get("type"),
            want,
        )
    elif html and c.get("type") != want:
        c["html"] = _rewrite_js_type(html, want)
        log.info(
            "coerced chart %s type %s → %s",
            c.get("id"),
            chart.get("type"),
            want,
        )
    c["type"] = want
    html_out = str(c.get("html") or "")
    if want == "donut" and html_out:
        html_out = enhance_donut_html(html_out)
    elif left_donut or (
        want in {"bar", "horizontal_bar", "line", "area"} and html_out
    ):
        html_out = _hide_legend_if_unnamed_dataset(html_out)
    c["html"] = ensure_legend_and_tooltips(harden_chart_html(html_out, want), want)
    return c

def coerce_chart_types(
    charts: list[dict[str, Any]],
    preferred: list[str],
) -> list[dict[str, Any]]:
    """Align charts[i] to preferred[i] when both are whitelisted.

    Also repairs HTML when the model already set the right `type` but left
    mismatched markup (classic: type=kpi + Chart.js canvas bar).
    """
    prefs = [p for p in preferred if p in CHART_TYPES]
    if not prefs or not charts:
        return [ensure_chart_html_matches_declared_type(c) for c in charts]
    out: list[dict[str, Any]] = []
    for i, chart in enumerate(charts):
        want = prefs[i] if i < len(prefs) else None
        if want:
            out.append(apply_type_to_chart(chart, want))
        else:
            out.append(ensure_chart_html_matches_declared_type(chart))
    return out

def ensure_chart_html_matches_declared_type(chart: dict[str, Any]) -> dict[str, Any]:
    """When charts[].type says X, make HTML actually look like X (auto mode too)."""
    want = str(chart.get("type") or "").strip()
    if want not in CHART_TYPES:
        return chart
    html = str(chart.get("html") or "")
    if html_matches_type(html, want):
        return chart
    return apply_type_to_chart(chart, want)

def ensure_all_charts_match_types(charts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [ensure_chart_html_matches_declared_type(c) for c in charts]
