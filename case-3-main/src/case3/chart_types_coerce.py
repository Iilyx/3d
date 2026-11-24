"""Chart type coerce / harden / donut — façade (prefer chart_coerce / chart_harden / chart_donut)."""

from __future__ import annotations

from case3.chart_coerce import (
    apply_type_to_chart,
    coerce_chart_types,
    ensure_all_charts_match_types,
    ensure_chart_html_matches_declared_type,
    polish_charts,
)
from case3.chart_donut import enhance_donut_html
from case3.chart_harden import (
    _count_datasets,
    ensure_legend_and_tooltips,
    harden_chart_html,
    html_matches_type,
)

__all__ = [
    "apply_type_to_chart",
    "coerce_chart_types",
    "enhance_donut_html",
    "ensure_all_charts_match_types",
    "ensure_chart_html_matches_declared_type",
    "ensure_legend_and_tooltips",
    "harden_chart_html",
    "html_matches_type",
    "polish_charts",
    "_count_datasets",
]
