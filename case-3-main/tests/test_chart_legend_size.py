"""Print frame legend must be readable on A4 (not tiny vs donut)."""

from __future__ import annotations

from pathlib import Path

import re

FRAME = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "case3"
    / "templates"
    / "chart_frame.html"
)


def test_valued_legend_font_is_print_readable() -> None:
    css = FRAME.read_text(encoding="utf-8")
    # Row font ≥ 18px; swatch ≥ 14px
    m = re.search(
        r"\.valued-legend(?:\s+li|,|\s+\.valued-legend__row)[^}]*font-size:\s*(\d+)px",
        css,
    )
    assert m, "valued-legend font-size missing"
    assert int(m.group(1)) >= 18
    sw = re.search(r"\.valued-legend__swatch\s*\{[^}]*width:\s*(\d+)px", css)
    assert sw and int(sw.group(1)) >= 14


def test_chart_js_default_legend_labels_bumped() -> None:
    css = FRAME.read_text(encoding="utf-8")
    assert "Chart.defaults.font.size = 17" in css or "Chart.defaults.font.size=17" in css
    assert "boxWidth = 16" in css or "boxWidth=16" in css
