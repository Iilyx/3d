"""Native editable PPTX from Liber deck IR (python-pptx shapes + text).

Preview / deck PDF stay HTML→PNG capture. PPTX is intentionally editable —
visual parity with Liber web is not required.

Draw helpers: ``slides_pptx_draw``. Layouts: ``slides_pptx_layouts``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor

from case3 import slides_pptx_draw as draw
from case3.slides_pptx_draw import _colors_from_style, _fonts_from_style, _hex_rgb, _is_dark_pack
from case3.slides_pptx_layouts import (
    _layout_bullets,
    _layout_callout,
    _layout_card_row,
    _layout_closing,
    _layout_kpi,
    _layout_media,
    _layout_compare,
    _layout_quote,
    _layout_section,
    _layout_stat_hero,
    _layout_table,
    _layout_timeline,
    _layout_title,
)

# Re-export for tests / callers that imported helpers from this module.
__all__ = ["build_native_pptx", "_fonts_from_style"]


def build_native_pptx(
    deck: dict[str, Any],
    dest: Path,
    *,
    media_by_id: dict[str, Path] | None = None,
    chart_series_by_id: dict[str, dict[str, Any]] | None = None,
    series_hex_by_id: dict[str, list[str]] | None = None,
    diagrams_by_id: dict[str, dict[str, Any]] | None = None,
) -> Path:
    """Build editable 16:9 PPTX from validated deck IR."""
    media = media_by_id or {}
    chart_series_by_id = chart_series_by_id or {}
    diagrams_by_id = diagrams_by_id or {}
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    colors, title_font, body_font = _colors_from_style(deck)
    series_rgbs: list[RGBColor] = []
    style = deck.get("style") if isinstance(deck.get("style"), dict) else None
    brand_mark = (
        str(style["brand_mark"]).strip()
        if style and isinstance(style.get("brand_mark"), str) and style["brand_mark"].strip()
        else ""
    )
    if style and isinstance(style.get("chart_series"), list):
        for hx in style["chart_series"]:
            try:
                series_rgbs.append(_hex_rgb(str(hx)))
            except Exception:
                continue
    if not series_rgbs:
        series_rgbs = [colors["primary"], colors["accent"]]

    with draw.use_pptx_theme(
        font=body_font or "Calibri",
        title_font=title_font or "Georgia",
        brand_mark=brand_mark,
    ):
        return _build_native_pptx_body(
            deck,
            dest,
            colors=colors,
            style=style,
            series_rgbs=series_rgbs,
            media=media,
            chart_series_by_id=chart_series_by_id,
            series_hex_by_id=series_hex_by_id,
            diagrams_by_id=diagrams_by_id,
        )


def _build_native_pptx_body(
    deck: dict[str, Any],
    dest: Path,
    *,
    colors: dict[str, RGBColor],
    style: dict[str, Any] | None,
    series_rgbs: list[RGBColor],
    media: dict[str, Path],
    chart_series_by_id: dict[str, dict[str, Any]],
    series_hex_by_id: dict[str, list[str]] | None,
    diagrams_by_id: dict[str, dict[str, Any]],
) -> Path:
    prs = Presentation()
    prs.slide_width = draw._SLIDE_W
    prs.slide_height = draw._SLIDE_H
    blank = prs.slide_layouts[6]

    for si, s in enumerate(deck.get("slides") or []):
        if not isinstance(s, dict):
            continue
        slide = prs.slides.add_slide(blank)
        layout = str(s.get("layout") or "")

        if layout == "title":
            mid = str(s.get("media_id") or s.get("chart_id") or "")
            _layout_title(
                slide,
                s,
                colors,
                style=style,
                slide_index=si,
                media_path=media.get(mid) if mid else None,
            )
        elif layout == "section":
            _layout_section(
                slide, s, colors, style=style, slide_index=si
            )
        elif layout == "callout":
            _layout_callout(
                slide, s, colors, style=style, slide_index=si
            )
        elif layout == "table_hero":
            _layout_table(slide, s, colors, style=style)
        elif layout == "closing":
            mid = str(s.get("media_id") or "")
            if _is_dark_pack(style) and mid and media.get(mid):
                # Closing reuses dark hero bleed when media attached.
                _layout_title(
                    slide,
                    {
                        **s,
                        "layout": "title",
                        "kicker": str(s.get("kicker") or "CLOSE"),
                    },
                    colors,
                    style=style,
                    slide_index=si,
                    media_path=media.get(mid),
                )
            else:
                _layout_closing(slide, s, colors, style=style)
        elif layout == "bullets":
            _layout_bullets(slide, s, colors, style=style)
        elif layout == "card_row":
            _layout_card_row(
                slide, s, colors, style=style, slide_index=si
            )
        elif layout == "stat_hero":
            _layout_stat_hero(slide, s, colors, style=style)
        elif layout == "timeline":
            _layout_timeline(slide, s, colors, style=style)
        elif layout == "compare":
            _layout_compare(slide, s, colors, style=style)
        elif layout == "quote":
            _layout_quote(slide, s, colors, style=style)
        elif layout in ("kpi_row", "scorecard"):
            _layout_kpi(
                slide, s, colors, style=style, slide_index=si
            )
        elif layout in ("chart_hero", "media_hero", "chart_split", "media_split"):
            mid = str(s.get("chart_id") or s.get("media_id") or "")
            picked = (series_hex_by_id or {}).get(mid) or []
            picked_rgbs: list[RGBColor] = []
            for hx in picked:
                try:
                    picked_rgbs.append(_hex_rgb(str(hx)))
                except Exception:
                    continue
            _layout_media(
                slide,
                s,
                colors,
                media_path=media.get(mid),
                split=layout in ("chart_split", "media_split"),
                chart_series=chart_series_by_id.get(mid),
                series_colors=picked_rgbs or series_rgbs,
                style=style,
                diagram_spec=diagrams_by_id.get(mid) if mid.startswith("dia_") else None,
            )
        else:
            _layout_bullets(slide, s, colors, style=style)

    prs.save(str(dest))
    return dest
