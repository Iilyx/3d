"""Slide layout painters for native Liber PPTX.

Imported by ``slides_pptx_native.build_native_pptx``. Draw helpers come from
``slides_pptx_draw``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches

from case3.color_util import accent_fields
from case3.slides_html import _pct_from_kicker, parse_hero_metrics
from case3 import slides_pptx_draw as _pptx_draw
from case3.slides_pptx_draw import (
    _MARGIN_X,
    _SLIDE_H,
    _SLIDE_W,
    _add_bullets,
    _add_textbox,
    _apply_pack_bg,
    _brand,
    _foil_cards,
    _hex_rgb,
    _is_dark_pack,
    _kicker_title,
    _motif_dict,
    _panel_rgb,
    _picture_fit,
    _set_fill_alpha,
    _set_run,
    _set_slide_bg_picture,
    _split_ratio,
    _top_bar,
    _wants_top_bar,
)

def _paint_title_field(slide, s: dict[str, Any], style: dict[str, Any] | None) -> None:
    """Full-bleed accent title with a primary-color rail."""
    raw = style.get("colors") if isinstance(style, dict) else {}
    colors = raw if isinstance(raw, dict) else {}
    fields = accent_fields(colors)
    on = _hex_rgb(fields["on_accent"])
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), _SLIDE_W, _SLIDE_H
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = _hex_rgb(str(colors.get("accent") or "#4F6B14"))
    bg.line.fill.background()
    rail_w = Inches(2.9)
    rail = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, _SLIDE_W - rail_w, Inches(0), rail_w, _SLIDE_H
    )
    rail.fill.solid()
    rail.fill.fore_color.rgb = _hex_rgb(fields["rail"])
    rail.line.fill.background()
    mark = str((style or {}).get("brand_mark") or "").strip()
    y = Inches(1.85)
    if mark:
        _add_textbox(
            slide, Inches(0.95), Inches(1.35), Inches(8.4), Inches(0.32),
            mark.upper(), size_pt=12, bold=True, color=on,
        )
    kicker = str(s.get("kicker") or "").strip()
    if kicker:
        _add_textbox(
            slide, Inches(0.95), y, Inches(8.4), Inches(0.32),
            kicker.upper(), size_pt=14, bold=True, color=on,
        )
        y = Inches(2.3)
    _add_textbox(
        slide, Inches(0.95), y, Inches(8.6), Inches(2.4),
        str(s.get("title") or ""), size_pt=54, bold=True, color=on,
    )
    sub = str(s.get("subtitle") or s.get("takeaway") or "").strip()
    if sub:
        _add_textbox(
            slide, Inches(0.95), Inches(5.15), Inches(8.4), Inches(1.3),
            sub, size_pt=20, color=on,
        )


def _layout_title(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
    slide_index: int = 0,
    media_path: Path | None = None,
) -> None:
    dark = _is_dark_pack(style)
    motif = style.get("motif") if isinstance(style, dict) else {}
    hero_bleed = bool(isinstance(motif, dict) and motif.get("hero_bleed"))
    used_photo = False
    if dark and hero_bleed and media_path:
        # Match HTML title-bleed (right 78%%), contain — not OOXML bg stretch.
        bleed_left = Inches(_SLIDE_W.inches * 0.22)
        bleed_w = Inches(_SLIDE_W.inches * 0.78)
        _picture_fit(slide, Path(media_path), bleed_left, Inches(0), bleed_w, _SLIDE_H)
        used_photo = True
    if not used_photo:
        _apply_pack_bg(slide, colors, style)
    # Dark botanical title: left column copy over a real full-bleed photo.
    if dark and used_photo:
        if used_photo:
            # Twin of HTML title-bleed__veil — left forest wash for ivory type.
            veil = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(6.4), _SLIDE_H
            )
            veil.fill.solid()
            veil.fill.fore_color.rgb = colors["sheet"]
            veil.line.fill.background()
            _set_fill_alpha(veil, 0.12)
            # Soft mid band
            mid = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(5.2), Inches(0), Inches(2.4), _SLIDE_H
            )
            mid.fill.solid()
            mid.fill.fore_color.rgb = colors["sheet"]
            mid.line.fill.background()
            _set_fill_alpha(mid, 0.55)
        _brand(slide, colors)
        kicker = str(s.get("kicker") or "").strip()
        y = Inches(1.7)
        if kicker:
            _add_textbox(
                slide,
                _MARGIN_X,
                Inches(1.35),
                Inches(7),
                Inches(0.3),
                kicker.upper(),
                size_pt=11,
                bold=True,
                color=colors.get("foil", colors["accent"]),
            )
        _add_textbox(
            slide,
            _MARGIN_X,
            y,
            Inches(7.2),
            Inches(1.6),
            str(s.get("title") or ""),
            size_pt=44,
            bold=True,
            color=colors["ink"],
        )
        y2 = Inches(3.5)
        takeaway = str(s.get("takeaway") or "").strip()
        if takeaway:
            _add_textbox(
                slide,
                _MARGIN_X,
                y2,
                Inches(6.5),
                Inches(1.6),
                takeaway.replace(" · ", "\n"),
                size_pt=28,
                bold=True,
                color=colors["ink"],
            )
            y2 = Inches(5.2)
        sub = str(s.get("subtitle") or "").strip()
        if sub:
            _add_textbox(
                slide,
                _MARGIN_X,
                y2,
                Inches(6.2),
                Inches(1.0),
                sub,
                size_pt=16,
                color=colors["muted"],
            )
            y2 = y2 + Inches(0.85)
        bullets = [str(b) for b in (s.get("bullets") or []) if str(b).strip()]
        if bullets:
            _add_bullets(
                slide,
                _MARGIN_X,
                y2,
                Inches(6.5),
                Inches(2.4),
                bullets,
                size_pt=16,
                color=colors["ink2"],
            )
        return
    split = _split_ratio(style)
    if split is None:
        _paint_title_field(slide, s, style)
        return
    left_w = Inches(11.5)
    takeaway = str(s.get("takeaway") or "").strip()
    if split is not None:
        # Julius Split Pastel: cream left + pastel right panel
        panel_w = _SLIDE_W * (1.0 - split)
        panel_left = _SLIDE_W - panel_w
        panel = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, panel_left, Inches(0), panel_w, _SLIDE_H
        )
        panel.fill.solid()
        panel.fill.fore_color.rgb = _panel_rgb(
            colors, style, slide_index=slide_index
        )
        panel.line.fill.background()
        left_w = Inches(max(5.5, 13.333 * split - 1.0))
        metrics = parse_hero_metrics(takeaway)
        if metrics:
            y_m = Inches(1.85)
            for value, label in metrics[:3]:
                _add_textbox(
                    slide,
                    panel_left + Inches(0.45),
                    y_m,
                    panel_w - Inches(0.7),
                    Inches(0.75),
                    value,
                    size_pt=40,
                    bold=True,
                    color=colors["ink"],
                )
                y_m = y_m + Inches(0.62)
                if label:
                    _add_textbox(
                        slide,
                        panel_left + Inches(0.45),
                        y_m,
                        panel_w - Inches(0.7),
                        Inches(0.4),
                        label,
                        size_pt=14,
                        color=colors["ink2"],
                    )
                    y_m = y_m + Inches(0.7)
                else:
                    y_m = y_m + Inches(0.35)
        elif takeaway:
            _add_textbox(
                slide,
                panel_left + Inches(0.45),
                Inches(2.4),
                panel_w - Inches(0.7),
                Inches(2.2),
                takeaway,
                size_pt=22,
                bold=True,
                color=colors["ink"],
            )
    elif _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    kicker = str(s.get("kicker") or "").strip()
    y = Inches(2.2)
    if kicker:
        _add_textbox(
            slide,
            _MARGIN_X,
            Inches(1.55) if split else Inches(1.9),
            left_w,
            Inches(0.3),
            kicker.upper(),
            size_pt=12,
            bold=True,
            color=colors["muted"] if split else colors["accent"],
        )
        y = Inches(2.05) if split else Inches(2.35)
    _add_textbox(
        slide,
        _MARGIN_X,
        y,
        left_w,
        Inches(2.0) if split else Inches(1.5),
        str(s.get("title") or ""),
        size_pt=44 if split else 40,
        bold=True,
        color=colors["ink"],
    )
    y2 = y + (Inches(2.1) if split else Inches(1.45))
    if not split and takeaway:
        _add_textbox(
            slide,
            _MARGIN_X,
            y2,
            left_w,
            Inches(0.55),
            takeaway,
            size_pt=16,
            color=colors["ink2"],
        )
        y2 = y2 + Inches(0.55)
    sub = str(s.get("subtitle") or "").strip()
    if sub:
        _add_textbox(
            slide,
            _MARGIN_X,
            y2,
            left_w,
            Inches(1.2),
            sub,
            size_pt=18 if not split else 20,
            color=colors["muted"],
        )


def _layout_section(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
    slide_index: int = 0,
) -> None:
    _apply_pack_bg(slide, colors, style)
    if _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    sub = str(s.get("subtitle") or s.get("takeaway") or "").strip()
    # Accent panel — sentence on the color field, not a bare chapter number.
    panel = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(8.55), Inches(0), Inches(4.8), _SLIDE_H
    )
    panel.fill.solid()
    panel.fill.fore_color.rgb = colors["accent"]
    panel.line.fill.background()
    if sub:
        raw = style.get("colors") if isinstance(style, dict) else {}
        cmap = raw if isinstance(raw, dict) else {}
        on = _hex_rgb(accent_fields(cmap)["on_accent"]) if cmap else colors["sheet"]
        _add_textbox(
            slide,
            Inches(8.9),
            Inches(3.6),
            Inches(4.1),
            Inches(2.4),
            sub,
            size_pt=22,
            bold=True,
            color=on,
        )
    _add_textbox(
        slide,
        _MARGIN_X,
        Inches(2.6),
        Inches(7.4),
        Inches(1.4),
        str(s.get("title") or ""),
        size_pt=36,
        bold=True,
        color=colors["ink"],
    )


def _layout_callout(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
    slide_index: int = 0,
) -> None:
    raw = style.get("colors") if isinstance(style, dict) else {}
    cmap = raw if isinstance(raw, dict) else {}
    fields = accent_fields(cmap)
    on = _hex_rgb(fields["on_accent"])
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), _SLIDE_W, _SLIDE_H
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = _hex_rgb(str(cmap.get("accent") or "#4F6B14"))
    bg.line.fill.background()
    rail_w = Inches(2.9)
    rail = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, _SLIDE_W - rail_w, Inches(0), rail_w, _SLIDE_H
    )
    rail.fill.solid()
    rail.fill.fore_color.rgb = _hex_rgb(fields["rail"])
    rail.line.fill.background()
    mark = str((style or {}).get("brand_mark") or "").strip()
    if mark:
        _add_textbox(
            slide, Inches(0.95), Inches(1.45), Inches(8.4), Inches(0.32),
            mark.upper(), size_pt=12, bold=True, color=on,
        )
    term = str(s.get("term") or "")
    definition = str(s.get("definition") or "")
    body = str(s.get("body") or "").strip()
    _add_textbox(
        slide,
        Inches(0.95),
        Inches(2.05),
        Inches(8.6),
        Inches(0.35),
        term.upper(),
        size_pt=14,
        bold=True,
        color=on,
    )
    _add_textbox(
        slide,
        Inches(0.95),
        Inches(2.55),
        Inches(8.6),
        Inches(2.4),
        definition,
        size_pt=32,
        bold=True,
        color=on,
    )
    if body:
        _add_textbox(
            slide,
            Inches(0.95),
            Inches(5.2),
            Inches(8.6),
            Inches(1.2),
            body,
            size_pt=18,
            color=on,
        )


def _layout_table(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None,
) -> None:
    from case3.slides_pptx_tables import add_native_table, table_block_inches

    _apply_pack_bg(slide, colors, style)
    if _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    y_in = _kicker_title(
        slide,
        colors,
        kicker=str(s.get("kicker") or ""),
        title=str(s.get("title") or ""),
        takeaway=str(s.get("takeaway") or ""),
        chapter=s.get("chapter") if isinstance(s.get("chapter"), int) else None,
    )
    rows = s.get("rows") or []
    table_style = (style or {}).get("table") if isinstance(style, dict) else {}
    header_fill = colors["primary"]
    header_ink = colors["sheet"]
    grid = colors["rule"]
    body_fill: RGBColor | None = None
    if _is_dark_pack(style):
        body_fill = colors.get("panel") or colors.get("paper")
    if isinstance(table_style, dict):
        if table_style.get("header_fill"):
            header_fill = _hex_rgb(str(table_style["header_fill"]))
        if table_style.get("header_ink"):
            header_ink = _hex_rgb(str(table_style["header_ink"]))
        if table_style.get("grid"):
            grid = _hex_rgb(str(table_style["grid"]))
        if table_style.get("body_fill"):
            body_fill = _hex_rgb(str(table_style["body_fill"]))
    row_list = rows if isinstance(rows, list) else []
    top = Inches(max(y_in, 1.7))
    height = Inches(table_block_inches(len(row_list) if row_list else 2))
    body_rows = max(0, len(row_list) - 1)
    add_native_table(
        slide,
        row_list,
        left=_MARGIN_X,
        top=top,
        width=Inches(11.9),
        height=height,
        header_fill=header_fill,
        header_ink=header_ink,
        body_ink=colors["ink"],
        body_fill=body_fill,
        grid=grid,
        font_name=_pptx_draw.active_pptx_font(),
        font_pt=18 if body_rows <= 5 else 14,
    )
    cap = str(s.get("caption") or "").strip()
    if cap:
        _add_textbox(
            slide,
            _MARGIN_X,
            top + height + Inches(0.12),
            Inches(11.9),
            Inches(0.4),
            cap,
            size_pt=11,
            color=colors["muted"],
        )


def _rect(slide, left, top, width, height, fill: RGBColor):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    return shape


def _paint_bands(slide, bullets: list[str], *, left, top, width, colors: dict[str, RGBColor]) -> None:
    """One paper band per line: number on the accent, phrase beside it."""
    band_h = Inches(0.78)
    gap = Inches(0.12)
    y = top
    for i, item in enumerate(bullets[:6]):
        _rect(slide, left, y, width, band_h, colors["paper"])
        _rect(slide, left, y, Inches(0.08), band_h, colors["accent"])
        _add_textbox(
            slide,
            left + Inches(0.22),
            y + Inches(0.18),
            Inches(0.7),
            Inches(0.42),
            f"{i + 1:02d}",
            size_pt=16,
            bold=True,
            color=colors["accent"],
        )
        _add_textbox(
            slide,
            left + Inches(1.05),
            y + Inches(0.16),
            width - Inches(1.25),
            Inches(0.5),
            item,
            size_pt=18,
            color=colors["ink"],
        )
        y = y + band_h + gap


def _layout_bullets(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    closing: bool = False,
    style: dict[str, Any] | None = None,
) -> None:
    _apply_pack_bg(slide, colors, style)
    if _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    y_in = _kicker_title(
        slide,
        colors,
        kicker=str(s.get("kicker") or ""),
        title=str(s.get("title") or ""),
        takeaway=str(s.get("takeaway") or ""),
        chapter=s.get("chapter") if isinstance(s.get("chapter"), int) else None,
    )
    bullets = [str(b) for b in (s.get("bullets") or []) if str(b).strip()]
    _paint_bands(
        slide,
        bullets,
        left=_MARGIN_X,
        top=Inches(max(y_in, 1.7)),
        width=Inches(11.6),
        colors=colors,
    )


def _layout_closing(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
) -> None:
    """Two plaques: the number on the accent, the decision on paper."""
    _apply_pack_bg(slide, colors, style)
    takeaway = str(s.get("takeaway") or "").strip()
    metrics = parse_hero_metrics(takeaway)
    hero_value = ""
    if metrics:
        hero_value = metrics[0][0]
    elif takeaway and len(takeaway) <= 24 and "\n" not in takeaway:
        hero_value = takeaway
    title = str(s.get("title") or "").strip()
    bullets = [str(b) for b in (s.get("bullets") or []) if str(b).strip()]
    decision = " ".join(bullets) or title
    left_text = hero_value or title
    raw = style.get("colors") if isinstance(style, dict) else {}
    cmap = raw if isinstance(raw, dict) else {}
    on = _hex_rgb(accent_fields(cmap)["on_accent"]) if cmap.get("accent") else RGBColor(0xF4, 0xF0, 0xE6)
    half = Inches(6.4)
    _rect(slide, Inches(0), Inches(0), half, _SLIDE_H, colors["accent"])
    _rect(slide, half, Inches(0), _SLIDE_W - half, _SLIDE_H, colors["paper"])
    mark = str((style or {}).get("brand_mark") or "").strip()
    if mark:
        _add_textbox(
            slide, Inches(0.55), Inches(0.4), Inches(5.2), Inches(0.32),
            mark, size_pt=11, bold=True, color=on,
        )
    _add_textbox(
        slide, Inches(0.55), Inches(2.6), Inches(5.3), Inches(1.8),
        left_text, size_pt=40, bold=True, color=on, title=True,
    )
    _add_textbox(
        slide, half + Inches(0.45), Inches(2.7), Inches(5.6), Inches(2.2),
        decision, size_pt=28, color=colors["ink"], title=True,
    )
    if hero_value and title and title != decision:
        _add_textbox(
            slide, half + Inches(0.45), Inches(2.15), Inches(5.6), Inches(0.4),
            title, size_pt=14, bold=True, color=colors["muted"],
        )


def _layout_card_row(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
    slide_index: int = 0,
) -> None:
    """Julius VESPER 3-up narrative cards + optional gold gate caption."""
    _apply_pack_bg(slide, colors, style)
    if _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    y_in = _kicker_title(
        slide,
        colors,
        kicker=str(s.get("kicker") or ""),
        title=str(s.get("title") or ""),
        takeaway=str(s.get("subtitle") or s.get("takeaway") or ""),
        chapter=s.get("chapter") if isinstance(s.get("chapter"), int) else None,
    )
    cards = [c for c in (s.get("cards") or []) if isinstance(c, dict)][:3]
    n = max(1, len(cards))
    gap = Inches(0.28)
    usable = Inches(11.9)
    card_w = Emu(int((usable - gap * (n - 1)) / n))
    left = _MARGIN_X
    top = Inches(max(y_in + 0.12, 2.15))
    max_body = max((len(str(c.get("body") or "").strip()) for c in cards), default=0)
    has_pct = any(_pct_from_kicker(str(c.get("kicker") or "")) is not None for c in cards)
    if max_body == 0 and not has_pct:
        card_h = Inches(1.85)
    elif max_body <= 85 and not has_pct:
        card_h = Inches(2.55)
    else:
        card_h = Inches(3.55)
    foil = colors.get("foil", colors["accent"])
    for i, c in enumerate(cards):
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, left, top, card_w, card_h
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = _panel_rgb(colors, style, slide_index=i)
        if _foil_cards(style):
            shape.line.color.rgb = foil
        else:
            shape.line.fill.background()
        y_t = top + Inches(0.22)
        kicker = str(c.get("kicker") or "").strip()
        pct = _pct_from_kicker(kicker)
        if kicker:
            _add_textbox(
                slide,
                Emu(int(left) + int(Inches(0.22))),
                y_t,
                Emu(int(card_w) - int(Inches(0.4))),
                Inches(0.55) if pct is not None else Inches(0.35),
                kicker if pct is not None else kicker.upper(),
                size_pt=28 if pct is not None else 11,
                bold=True,
                color=foil,
            )
            y_t = y_t + (Inches(0.62) if pct is not None else Inches(0.4))
        if pct is not None:
            track_w = Emu(int(card_w) - int(Inches(0.44)))
            track = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Emu(int(left) + int(Inches(0.22))),
                y_t,
                track_w,
                Inches(0.09),
            )
            track.fill.solid()
            track.fill.fore_color.rgb = colors.get("rule", colors["muted"])
            track.line.fill.background()
            fill_w = Emu(max(1, int(int(track_w) * (pct / 100.0))))
            fill = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Emu(int(left) + int(Inches(0.22))),
                y_t,
                fill_w,
                Inches(0.09),
            )
            fill.fill.solid()
            fill.fill.fore_color.rgb = foil
            fill.line.fill.background()
            y_t = y_t + Inches(0.28)
        _add_textbox(
            slide,
            Emu(int(left) + int(Inches(0.22))),
            y_t,
            Emu(int(card_w) - int(Inches(0.4))),
            Inches(0.7),
            str(c.get("title") or ""),
            size_pt=20,
            bold=True,
            color=colors["ink"],
        )
        body = str(c.get("body") or "").strip()
        if body:
            _add_textbox(
                slide,
                Emu(int(left) + int(Inches(0.22))),
                y_t + Inches(0.75),
                Emu(int(card_w) - int(Inches(0.4))),
                Inches(2.15),
                body,
                size_pt=15,
                color=colors["muted"],
            )
        left = Emu(int(left) + int(card_w) + int(gap))
    gate = str(s.get("caption") or "").strip()
    if gate:
        _add_textbox(
            slide,
            _MARGIN_X,
            Inches(6.15),
            Inches(11.9),
            Inches(0.45),
            gate.upper(),
            size_pt=12,
            bold=True,
            color=foil,
        )


def _layout_kpi(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
    slide_index: int = 0,
) -> None:
    _apply_pack_bg(slide, colors, style)
    use_pastel = False
    if isinstance(style, dict):
        motif = style.get("motif") if isinstance(style.get("motif"), dict) else {}
        use_pastel = bool(motif.get("panels"))
    if _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    y_in = _kicker_title(
        slide,
        colors,
        kicker=str(s.get("kicker") or ""),
        title=str(s.get("title") or ""),
        takeaway=str(s.get("takeaway") or ""),
        chapter=s.get("chapter") if isinstance(s.get("chapter"), int) else None,
    )
    kpis = [k for k in (s.get("kpis") or []) if isinstance(k, dict)][:4]
    n = max(1, len(kpis))
    gap = Inches(0.28)
    usable = Inches(11.9)
    card_w = Emu(int((usable - gap * (n - 1)) / n))
    left = _MARGIN_X
    has_extra = any(str(k.get("hint") or "").strip() or str(k.get("delta") or "").strip() for k in kpis)
    card_h = Inches(1.75) if has_extra else Inches(1.35)
    top = Inches(max(y_in + 0.18, 2.05))
    for i, k in enumerate(kpis):
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, left, top, card_w, card_h
        )
        shape.fill.solid()
        # Split Pastel scorecard: rotate motif panels across cards.
        if use_pastel:
            # Card row uses panel 0..n (distinct pastels), not slide_index offset.
            card_fill = _panel_rgb(colors, style, slide_index=i)
            shape.fill.fore_color.rgb = card_fill
            if _foil_cards(style):
                shape.line.color.rgb = colors.get("foil", colors["accent"])
            else:
                shape.line.fill.background()
        else:
            card_fill = colors["sheet"]
            shape.fill.fore_color.rgb = card_fill
            shape.line.color.rgb = colors["rule"]
            accent = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, left, top, Inches(0.08), card_h
            )
            accent.fill.solid()
            accent.fill.fore_color.rgb = colors["accent"]
            accent.line.fill.background()

        tf = shape.text_frame
        tf.clear()
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.alignment = PP_ALIGN.LEFT
        r0 = p0.add_run()
        r0.text = str(k.get("value") or "")
        _set_run(r0, size_pt=32, bold=True, color=colors["ink"])
        p1 = tf.add_paragraph()
        r1 = p1.add_run()
        r1.text = str(k.get("label") or "")
        _set_run(r1, size_pt=14, bold=True, color=colors["ink2"])
        hint = str(k.get("hint") or "").strip()
        if hint:
            p_h = tf.add_paragraph()
            r_h = p_h.add_run()
            r_h.text = hint
            _set_run(r_h, size_pt=13, color=colors["ink2"])
        delta = str(k.get("delta") or "").strip()
        if delta:
            p_d = tf.add_paragraph()
            r_d = p_d.add_run()
            r_d.text = delta
            _set_run(r_d, size_pt=13, bold=True, color=colors["accent"])
        tf.margin_left = Inches(0.28)
        tf.margin_top = Inches(0.22)
        left = Emu(int(left) + int(card_w) + int(gap))


def _layout_media(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    media_path: Path | None,
    split: bool,
    chart_series: dict[str, Any] | None = None,
    series_colors: list[RGBColor] | None = None,
    style: dict[str, Any] | None = None,
    diagram_spec: dict[str, Any] | None = None,
) -> None:
    _apply_pack_bg(slide, colors, style)
    if _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    kicker = str(s.get("kicker") or "")
    title = str(s.get("title") or "")
    cap = str(s.get("caption") or "").strip()
    body = str(s.get("body") or "").strip()
    bullets = [str(b) for b in (s.get("bullets") or []) if str(b).strip()]

    takeaway = str(s.get("takeaway") or "")
    chapter = s.get("chapter") if isinstance(s.get("chapter"), int) else None
    if split:
        y_in = _kicker_title(
            slide,
            colors,
            kicker=kicker,
            title=title,
            takeaway=takeaway,
            chapter=chapter,
        )
        # left copy
        top = Inches(max(y_in, 1.9))
        if body:
            _add_textbox(
                slide,
                _MARGIN_X,
                top,
                Inches(5.4),
                Inches(1.4),
                body,
                size_pt=16,
                color=colors["ink2"],
            )
            top = top + Inches(1.3)
        if bullets:
            _paint_bands(
                slide,
                bullets,
                left=_MARGIN_X,
                top=top,
                width=Inches(5.2),
                colors=colors,
            )
        mid = str(s.get("media_id") or s.get("chart_id") or "")
        is_dia = mid.startswith("dia_")
        is_cht = mid.startswith("cht_")
        # Diagrams get a wider right column so flowcharts stay readable.
        pic_left = Inches(5.4) if is_dia else Inches(6.6)
        pic_w = Inches(7.1) if is_dia else Inches(5.9)
        pic_h = Inches(5.0) if is_dia else Inches(4.6)
        placed = False
        if is_dia and diagram_spec:
            from case3.slides_pptx_diagrams import add_native_diagram

            pack = str((style or {}).get("pack_id") or (style or {}).get("theme_pack") or "atelier")
            placed = add_native_diagram(
                slide,
                diagram_spec,
                left=pic_left,
                top=Inches(1.55),
                width=pic_w,
                height=pic_h,
                colors=colors,
                palette=pack,
                font_name=_pptx_draw.active_pptx_font(),
            )
        elif is_cht and chart_series and str(chart_series.get("type") or "") == "kpi":
            from case3.slides_pptx_charts import add_native_kpi

            placed = add_native_kpi(
                slide,
                chart_series,
                left=pic_left,
                top=Inches(1.55),
                width=pic_w,
                height=pic_h,
                color=colors["ink"],
            )
        elif is_cht and chart_series:
            from case3.slides_pptx_charts import add_native_chart

            placed = add_native_chart(
                slide,
                chart_series,
                left=pic_left,
                top=Inches(1.55),
                width=pic_w,
                height=pic_h,
                series_colors=series_colors,
            )
        if not placed:
            _picture_fit(
                slide,
                media_path,  # type: ignore[arg-type]
                pic_left,
                Inches(1.55),
                pic_w,
                pic_h,
            )
        if cap and not bullets:
            _add_textbox(
                slide,
                _MARGIN_X,
                Inches(6.2),
                Inches(5.2),
                Inches(0.7),
                cap,
                size_pt=16,
                color=colors["ink"],
            )
    else:
        mid = str(s.get("media_id") or s.get("chart_id") or "")
        is_dia = mid.startswith("dia_")
        is_cht = mid.startswith("cht_")
        # Same split as the HTML twin: copy on the left, photo on the right.
        y = 1.35
        if kicker:
            _add_textbox(
                slide, Inches(0.55), Inches(y), Inches(4.3), Inches(0.32),
                kicker.upper(), size_pt=12, bold=True, color=colors["accent"],
            )
            y += 0.42
        if title:
            _add_textbox(
                slide, Inches(0.55), Inches(y), Inches(4.3), Inches(1.8),
                title, size_pt=32, bold=True, color=colors["ink"], title=True,
            )
            y += 1.9
        if body:
            _add_textbox(
                slide, Inches(0.55), Inches(y), Inches(4.3), Inches(1.2),
                body, size_pt=16, color=colors["ink2"],
            )
            y += 1.2
        if cap and cap != title:
            _add_textbox(
                slide, Inches(0.55), Inches(min(y, 5.6)), Inches(4.3), Inches(1.2),
                cap, size_pt=16, color=colors["ink"],
            )
        pic_left = Inches(5.15)
        pic_w = Inches(7.6)
        pic_h = Inches(6.2) if is_dia else Inches(5.6)
        placed = False
        if is_dia and diagram_spec:
            from case3.slides_pptx_diagrams import add_native_diagram

            pack = str((style or {}).get("pack_id") or (style or {}).get("theme_pack") or "atelier")
            placed = add_native_diagram(
                slide,
                diagram_spec,
                left=pic_left,
                top=Inches(0.7),
                width=pic_w,
                height=Inches(5.8),
                colors=colors,
                palette=pack,
                font_name=_pptx_draw.active_pptx_font(),
            )
        elif is_cht and chart_series and str(chart_series.get("type") or "") == "kpi":
            from case3.slides_pptx_charts import add_native_kpi

            placed = add_native_kpi(
                slide,
                chart_series,
                left=pic_left,
                top=Inches(1.55),
                width=pic_w,
                height=pic_h,
                color=colors["ink"],
            )
        elif is_cht and chart_series:
            from case3.slides_pptx_charts import add_native_chart

            placed = add_native_chart(
                slide,
                chart_series,
                left=pic_left,
                top=Inches(0.85),
                width=pic_w,
                height=Inches(5.5),
                series_colors=series_colors,
            )
        if not placed:
            _picture_fit(
                slide,
                media_path,  # type: ignore[arg-type]
                pic_left,
                Inches(0.7),
                pic_w,
                Inches(5.8),
            )


def _layout_stat_hero(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
) -> None:
    """One number on the accent, Source notes on the rail."""
    raw = style.get("colors") if isinstance(style, dict) else {}
    cmap = raw if isinstance(raw, dict) else {}
    fields = accent_fields(cmap)
    on = _hex_rgb(fields["on_accent"])
    on_rail = _hex_rgb(fields["on_rail"])
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), _SLIDE_W, _SLIDE_H
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = _hex_rgb(str(cmap.get("accent") or "#4F6B14"))
    bg.line.fill.background()
    rail_w = Inches(5.4)
    rail = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, _SLIDE_W - rail_w, Inches(0), rail_w, _SLIDE_H
    )
    rail.fill.solid()
    rail.fill.fore_color.rgb = _hex_rgb(fields["rail"])
    rail.line.fill.background()
    kpi = next((k for k in (s.get("kpis") or []) if isinstance(k, dict)), {})
    mark = str((style or {}).get("brand_mark") or "").strip()
    kicker = str(s.get("kicker") or "").strip()
    title = str(s.get("title") or "").strip()
    if kicker or title:
        y = 0.48
        if mark:
            _add_textbox(
                slide, Inches(0.85), Inches(y), Inches(6.4), Inches(0.28),
                mark.upper(), size_pt=12, bold=True, color=on,
            )
            y += 0.34
        if kicker:
            _add_textbox(
                slide, Inches(0.85), Inches(y), Inches(6.4), Inches(0.28),
                kicker.upper(), size_pt=13, bold=True, color=on,
            )
            y += 0.32
        if title:
            _add_textbox(
                slide, Inches(0.8), Inches(y), Inches(6.6), Inches(0.78),
                title, size_pt=22, bold=True, color=on,
            )
            y += 0.86
        _add_textbox(
            slide, Inches(0.8), Inches(y), Inches(6.6), Inches(1.35),
            str(kpi.get("value") or ""), size_pt=56, bold=True, color=on,
        )
        label_top = y + 1.4
    else:
        if mark:
            _add_textbox(
                slide, Inches(0.85), Inches(1.7), Inches(6.4), Inches(0.32),
                mark.upper(), size_pt=12, bold=True, color=on,
            )
        _add_textbox(
            slide, Inches(0.8), Inches(2.15), Inches(6.6), Inches(1.8),
            str(kpi.get("value") or ""), size_pt=72, bold=True, color=on,
        )
        label_top = 4.15
    _add_textbox(
        slide, Inches(0.85), Inches(label_top), Inches(6.2), Inches(0.45),
        str(kpi.get("label") or ""), size_pt=20, bold=True, color=on,
    )
    foot = " · ".join(
        p for p in (str(kpi.get("delta") or "").strip(), str(kpi.get("hint") or "").strip()) if p
    )
    if foot:
        _add_textbox(
            slide, Inches(0.85), Inches(label_top + 0.55), Inches(6.2), Inches(0.6),
            foot, size_pt=16, color=on,
        )
    bullets = [str(b) for b in (s.get("bullets") or []) if str(b).strip()]
    _add_bullets(
        slide, _SLIDE_W - rail_w + Inches(0.4), Inches(2.3),
        rail_w - Inches(0.7), Inches(3.4),
        bullets, size_pt=18, color=on_rail,
    )


def _layout_timeline(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
) -> None:
    """Vertical agenda: time, title, one sentence."""
    _apply_pack_bg(slide, colors, style)
    if _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    y_in = _kicker_title(
        slide,
        colors,
        kicker=str(s.get("kicker") or ""),
        title=str(s.get("title") or ""),
        takeaway=str(s.get("takeaway") or ""),
        chapter=s.get("chapter") if isinstance(s.get("chapter"), int) else None,
    )
    cards = [c for c in (s.get("cards") or []) if isinstance(c, dict)][:6]
    top = Inches(max(y_in + 0.35, 2.15))
    n = max(1, len(cards))
    gap = Inches(0.22)
    usable = Inches(11.9)
    col_w = Emu(int((usable - gap * (n - 1)) / n))
    left = _MARGIN_X
    for c in cards:
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, col_w, Inches(0.045)
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = colors["accent"]
        bar.line.fill.background()
        dot = slide.shapes.add_shape(
            MSO_SHAPE.OVAL, left, Emu(int(top) - int(Inches(0.06))), Inches(0.16), Inches(0.16)
        )
        dot.fill.solid()
        dot.fill.fore_color.rgb = colors["accent"]
        dot.line.fill.background()
        _add_textbox(
            slide,
            left,
            top + Inches(0.28),
            col_w,
            Inches(0.32),
            str(c.get("kicker") or "").upper(),
            size_pt=12,
            bold=True,
            color=colors["accent"],
        )
        _add_textbox(
            slide,
            left,
            top + Inches(0.62),
            Emu(int(col_w) - int(Inches(0.12))),
            Inches(0.7),
            str(c.get("title") or ""),
            size_pt=18,
            bold=True,
            color=colors["ink"],
        )
        body = str(c.get("body") or "").strip()
        if body:
            _add_textbox(
                slide,
                left,
                top + Inches(1.4),
                Emu(int(col_w) - int(Inches(0.12))),
                Inches(1.6),
                body,
                size_pt=13,
                color=colors["muted"],
            )
        left = Emu(int(left) + int(col_w) + int(gap))


def _layout_compare(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
) -> None:
    """Two columns: scale vs pause, wins vs misses, loves vs friction."""
    _apply_pack_bg(slide, colors, style)
    if _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    y_in = _kicker_title(
        slide,
        colors,
        kicker=str(s.get("kicker") or ""),
        title=str(s.get("title") or ""),
        takeaway=str(s.get("takeaway") or ""),
        chapter=s.get("chapter") if isinstance(s.get("chapter"), int) else None,
    )
    cards = [c for c in (s.get("cards") or []) if isinstance(c, dict)][:2]
    raw = style.get("colors") if isinstance(style, dict) else {}
    fields = accent_fields(raw if isinstance(raw, dict) else {})
    top = Inches(max(y_in + 0.12, 1.85))
    height = _SLIDE_H - top
    gap = Inches(0)
    card_w = Inches(_SLIDE_W.inches / 2)
    left = Inches(0)
    for i, c in enumerate(cards):
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, card_w, height
        )
        shape.fill.solid()
        if i == 0:
            shape.fill.fore_color.rgb = _hex_rgb(str((raw or {}).get("accent") or "#4F6B14"))
            ink = _hex_rgb(fields["on_accent"])
        else:
            shape.fill.fore_color.rgb = _hex_rgb(fields["field_b"])
            ink = _hex_rgb(fields["on_field_b"])
        shape.line.fill.background()
        _add_textbox(
            slide,
            Emu(int(left) + int(Inches(0.55))),
            top + Inches(0.4),
            Inches(5.5),
            Inches(0.32),
            str(c.get("kicker") or "").upper(),
            size_pt=13,
            bold=True,
            color=ink,
        )
        _add_textbox(
            slide,
            Emu(int(left) + int(Inches(0.55))),
            top + Inches(0.85),
            Inches(5.5),
            Inches(1.4),
            str(c.get("title") or ""),
            size_pt=36,
            bold=True,
            color=ink,
        )
        body = str(c.get("body") or "").strip()
        if body:
            _add_textbox(
                slide,
                Emu(int(left) + int(Inches(0.55))),
                top + Inches(2.35),
                Inches(5.5),
                Inches(1.4),
                body,
                size_pt=18,
                color=ink,
            )
        _add_textbox(
            slide,
            Emu(int(left) + int(Inches(0.5))),
            top + height - Inches(1.35),
            Inches(3),
            Inches(1.1),
            f"{i + 1:02d}",
            size_pt=60,
            bold=True,
            color=ink,
        )
        left = Emu(int(left) + int(card_w) + int(gap))


def _layout_quote(
    slide,
    s: dict[str, Any],
    colors: dict[str, RGBColor],
    *,
    style: dict[str, Any] | None = None,
) -> None:
    """Pull quote: the sentence is the slide, attribution sits under it."""
    _apply_pack_bg(slide, colors, style)
    if _wants_top_bar(style):
        _top_bar(slide, colors, style)
    _brand(slide, colors)
    y_in = _kicker_title(
        slide,
        colors,
        kicker=str(s.get("kicker") or ""),
        title=str(s.get("title") or ""),
        takeaway="",
        chapter=s.get("chapter") if isinstance(s.get("chapter"), int) else None,
    )
    top = Inches(max(y_in + 0.2, 2.15))
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, _MARGIN_X, top, Inches(0.06), Inches(3.2)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = colors["accent"]
    bar.line.fill.background()
    _add_textbox(
        slide,
        Inches(1.05),
        top,
        Inches(11),
        Inches(2.2),
        str(s.get("definition") or ""),
        size_pt=28,
        bold=True,
        color=colors["ink"],
    )
    term = str(s.get("term") or "").strip()
    if term:
        _add_textbox(
            slide,
            Inches(1.05),
            Inches(4.6),
            Inches(10),
            Inches(0.35),
            term.upper(),
            size_pt=13,
            bold=True,
            color=colors["accent"],
        )
    note = str(s.get("body") or "").strip()
    if note:
        _add_textbox(
            slide,
            Inches(1.05),
            Inches(5.05),
            Inches(10),
            Inches(0.7),
            note,
            size_pt=15,
            color=colors["muted"],
        )


