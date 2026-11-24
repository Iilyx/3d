"""Series accents must use distinct hues — luminance ladders look like Mary-blue mush."""

from __future__ import annotations

import colorsys

from case3.chart_style import _PALETTES


def _hue_deg(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    hue, _sat, _val = colorsys.rgb_to_hsv(r, g, b)
    return hue * 360.0


def test_named_palettes_spread_series_hues() -> None:
    """ocean/atelier must not be one-hue ladders (stacked bars become unreadable)."""
    for pid in ("editorial", "ocean", "sunset", "atelier"):
        accents = list(_PALETTES[pid]["accents"])
        assert len(accents) >= 4, pid
        hues = [_hue_deg(a) for a in accents[:4]]
        # 60° hue bins → need ≥3 different families among first 4 accents
        bins = {int(h // 60.0) % 6 for h in hues}
        assert len(bins) >= 3, f"{pid} accents too mono-hue: {accents} bins={bins}"


def test_ocean_includes_non_blue_accent() -> None:
    accents = " ".join(_PALETTES["ocean"]["accents"]).upper()
    # Okabe–Ito: orange / vermillion / green (not blue-only ladder)
    assert any(tok in accents for tok in ("#E69F00", "#D55E00", "#009E73", "#F0E442")), accents


def test_four_chromatic_palettes_cite_datavis_sources() -> None:
    """editorial/ocean/sunset/atelier must stay multi-hue published schemes."""
    assert _PALETTES["ocean"]["primary"].upper() == "#0072B2"  # Okabe–Ito blue
    assert "#EE7733" in [a.upper() for a in _PALETTES["atelier"]["accents"]]  # Tol vibrant
    assert _PALETTES["editorial"]["primary"].upper() == "#4E79A7"  # Tableau 10
    assert "#EE6677" == _PALETTES["sunset"]["primary"].upper()  # Tol bright
