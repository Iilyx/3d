"""Shared PPTX draw helpers for native Liber decks.

Fonts, shapes, backgrounds, brand. Layout painters live in
``slides_pptx_layouts``; public entry is ``slides_pptx_native.build_native_pptx``.
"""

from __future__ import annotations

from case3.color_util import hex_to_rgb

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Inches, Pt

from case3.chart_style import _PALETTES, normalize_palette_id
from case3.slides_html import _pct_from_kicker, parse_hero_metrics

_SLIDE_W = Inches(13.333)
_SLIDE_H = Inches(7.5)
_MARGIN_X = Inches(0.7)
_MARGIN_TOP = Inches(0.55)


def _as_inches(val: Any) -> float:
    """python-pptx Length: ``float(Inches(0.85))`` is EMUs (~777240), not 0.85.

    Subtraction of two lengths returns a raw EMU ``int`` with no ``.inches``.
    Treating that int as inches parks a photo millions of inches off the slide
    and PowerPoint repairs the file.
    """
    if val is None:
        return 0.0
    if hasattr(val, "inches"):
        return float(val.inches)
    if isinstance(val, int):
        return float(val) / 914400.0
    return float(val)


def _hex_rgb(hex_color: str) -> RGBColor:
    rgb = hex_to_rgb(hex_color or "#14161a") or (0x14, 0x16, 0x1A)
    return RGBColor(*rgb)


def _palette(palette_id: str) -> dict[str, RGBColor]:
    pid = normalize_palette_id(palette_id)
    if pid == "auto":
        pid = "atelier"
    p = _PALETTES.get(pid) or _PALETTES["atelier"]
    primary = str(p["primary"])
    accents = list(p.get("accents") or [primary])
    accent = str(accents[0] if accents else primary)
    muted = str(p.get("muted") or "#6a6f64")
    return {
        "primary": _hex_rgb(primary),
        "accent": _hex_rgb(accent),
        "muted": _hex_rgb(muted),
        "ink": _hex_rgb("#14161a"),
        "ink2": _hex_rgb("#2c3028"),
        "paper": _hex_rgb("#f0ede4"),
        "sheet": _hex_rgb("#fffcf7"),
        "rule": _hex_rgb("#e6e2d8"),
        "panel": _hex_rgb("#f0ede4"),
    }


def _office_font_name(name: str, default: str) -> str:
    """Map Liber/web face names to Office-safe families for PPTX latin typeface."""
    if not name:
        return default
    part = name.split(",")[0].strip().strip("\"'")
    low = part.lower()
    # Serif / display → Georgia (Liber twin woff2 stays on HTML side).
    if low in {
        "liber serif",
        "fraunces",
        "iowan old style",
        "libre baskerville",
        "playfair display",
        "playfair",
        "crimson pro",
        "crimson text",
    }:
        return "Georgia"
    # Aptos Display is not always installed; Aptos is the Office family.
    if low in {"aptos display", "aptos"}:
        return "Aptos"
    if low in {"arial black"}:
        return "Arial Black"
    # Sans / UI → Calibri (consistent Office body).
    if low in {
        "liber sans",
        "source sans 3",
        "source sans pro",
        "inter",
        "dm sans",
        "manrope",
        "system-ui",
        "sans-serif",
    }:
        return "Calibri"
    return part or default


def _fonts_from_style(deck: dict[str, Any]) -> tuple[str, str]:
    """Return (title_font, body_font) for PPTX.

    Role priority: title ← fonts.title; body ← fonts.body then fallback_pptx.
    Never prefer fallback_pptx over an explicit body face.
    """
    style = deck.get("style") if isinstance(deck.get("style"), dict) else None
    title, body = "Georgia", "Calibri"
    if not style:
        return title, body
    fonts = style.get("fonts") if isinstance(style.get("fonts"), dict) else {}
    raw_title = str(fonts.get("title") or fonts.get("display") or "").strip()
    raw_body = str(
        fonts.get("body") or fonts.get("sans") or fonts.get("fallback_pptx") or ""
    ).strip()
    return _office_font_name(raw_title, title), _office_font_name(raw_body, body)


def _colors_from_style(
    deck: dict[str, Any],
) -> tuple[dict[str, RGBColor], str, str]:
    """ThemeTokens from deck.style when present; else chart palette. Fonts = title, body."""
    style = deck.get("style") if isinstance(deck.get("style"), dict) else None
    title_font, body_font = _fonts_from_style(deck)
    if style and isinstance(style.get("colors"), dict):
        c = style["colors"]
        return {
            "primary": _hex_rgb(str(c.get("primary") or "#2E4208")),
            "accent": _hex_rgb(str(c.get("accent") or "#4F6B14")),
            "muted": _hex_rgb(str(c.get("muted") or "#6A7160")),
            "ink": _hex_rgb(str(c.get("ink") or c.get("text") or "#14161a")),
            "ink2": _hex_rgb(str(c.get("ink2") or "#2c3028")),
            "paper": _hex_rgb(str(c.get("paper") or "#f0ede4")),
            "sheet": _hex_rgb(
                str(c.get("sheet") or c.get("background") or "#fffcf7")
            ),
            "rule": _hex_rgb(str(c.get("rule") or "#e6e2d8")),
            "panel": _hex_rgb(
                str(c.get("panel") or c.get("paper") or "#f0ede4")
            ),
        }, title_font, body_font
    return _palette(str(deck.get("palette") or "atelier")), title_font, body_font


_PPTX_FONT = "Calibri"
_PPTX_TITLE_FONT = "Georgia"
_BRAND_MARK = ""
_CTX_PPTX_FONT: ContextVar[str | None] = ContextVar("_CTX_PPTX_FONT", default=None)
_CTX_PPTX_TITLE_FONT: ContextVar[str | None] = ContextVar("_CTX_PPTX_TITLE_FONT", default=None)
_CTX_BRAND_MARK: ContextVar[str | None] = ContextVar("_CTX_BRAND_MARK", default=None)


def active_pptx_font() -> str:
    return _CTX_PPTX_FONT.get() or _PPTX_FONT


def active_pptx_title_font() -> str:
    return _CTX_PPTX_TITLE_FONT.get() or _PPTX_TITLE_FONT


def active_brand_mark() -> str:
    val = _CTX_BRAND_MARK.get()
    return _BRAND_MARK if val is None else val


@contextmanager
def use_pptx_theme(
    *,
    font: str | None = None,
    title_font: str | None = None,
    brand_mark: str | None = None,
) -> Iterator[None]:
    """Scope font & brand mark per thread/render without mutating module globals."""
    t_font = _CTX_PPTX_FONT.set((font or _PPTX_FONT).strip() or "Calibri")
    t_title = _CTX_PPTX_TITLE_FONT.set((title_font or _PPTX_TITLE_FONT).strip() or "Georgia")
    t_brand = _CTX_BRAND_MARK.set((brand_mark if brand_mark is not None else _BRAND_MARK).strip())
    try:
        yield
    finally:
        _CTX_BRAND_MARK.reset(t_brand)
        _CTX_PPTX_TITLE_FONT.reset(t_title)
        _CTX_PPTX_FONT.reset(t_font)


def _plain(text: str) -> str:
    """TeX decimal grouping ``2{,}68`` is a comma on a slide, not braces."""
    return (
        (text or "")
        .replace(r"{\,}", ",")
        .replace("{,}", ",")
        .replace("{.}", ".")
    )


def _set_run(
    run,
    *,
    size_pt: float,
    bold: bool = False,
    color: RGBColor | None = None,
    title: bool = False,
) -> None:
    """Set face via python-pptx name (also writes a:latin/@typeface)."""
    face = active_pptx_title_font() if title else active_pptx_font()
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.name = face
    if color is not None:
        run.font.color.rgb = color
    # Ensure DrawingML latin typeface matches (PowerPoint quirk / east-asia defaults).
    try:
        rPr = run._r.get_or_add_rPr()
        latin = rPr.find(qn("a:latin"))
        if latin is None:
            latin = parse_xml(f'<a:latin {nsdecls("a")} typeface="{face}"/>')
            rPr.insert(0, latin)
        else:
            latin.set("typeface", face)
    except Exception:  # noqa: BLE001 — non-fatal; name alone is usually enough
        pass


def _add_textbox(
    slide,
    left,
    top,
    width,
    height,
    text: str,
    *,
    size_pt: float,
    bold: bool = False,
    color: RGBColor | None = None,
    align=PP_ALIGN.LEFT,
    title: bool | None = None,
) -> None:
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = _plain(text)
    # Titles / display sizes use title face; kickers stay body.
    use_title = bool(title) if title is not None else (bold and size_pt >= 24)
    _set_run(run, size_pt=size_pt, bold=bold, color=color, title=use_title)


def _add_bullets(
    slide,
    left,
    top,
    width,
    height,
    bullets: list[str],
    *,
    size_pt: float,
    color: RGBColor,
) -> None:
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = 0
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = _plain(f"• {item}")
        _set_run(run, size_pt=size_pt, color=color)
        p.space_after = Pt(8)


def _wants_top_bar(style: dict[str, Any] | None) -> bool:
    """Accent hairline: signal/ink/board/atelier. Not relay split or botanical fern."""
    pack = str((style or {}).get("pack_id") or "") if style else ""
    if pack in ("relay", "pastel", "botanical"):
        return False
    return True


def _top_bar(
    slide,
    colors: dict[str, RGBColor],
    style: dict[str, Any] | None = None,
) -> None:
    pack = str((style or {}).get("pack_id") or "") if style else ""
    # Julius DNA: signal orange; ink/cobalt blue; voltage lime; else primary.
    if pack == "signal":
        bar_color = colors.get("foil", colors["accent"])
        height = Inches(0.055)
    elif pack in ("ink", "voltage"):
        bar_color = colors["accent"] if pack == "ink" else colors.get("foil", colors["accent"])
        height = Inches(0.04)
    elif pack == "board":
        bar_color = colors["accent"]
        height = Inches(0.05)
    else:
        bar_color = colors["primary"]
        height = Inches(0.08)
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), _SLIDE_W, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = bar_color
    shape.line.fill.background()


def _brand(slide, colors: dict[str, RGBColor]) -> None:
    mark = active_brand_mark().strip()
    if not mark:
        return
    _add_textbox(
        slide,
        _MARGIN_X,
        Inches(0.22),
        Inches(5.5),
        Inches(0.3),
        mark,
        size_pt=9,
        bold=True,
        color=colors["muted"],
    )


def _kicker_title(
    slide,
    colors: dict[str, RGBColor],
    *,
    kicker: str,
    title: str,
    top=_MARGIN_TOP,
    takeaway: str = "",
    chapter: int | None = None,
) -> float:
    """Paint brand kicker + title (+ optional takeaway). Returns next Y in inches."""
    y = _as_inches(top)
    top_in = _as_inches(top)
    margin_top_in = _as_inches(_MARGIN_TOP)
    if chapter is not None:
        _add_textbox(
            slide,
            _MARGIN_X,
            Inches(y),
            Inches(1.2),
            Inches(0.28),
            f"{int(chapter):02d}",
            size_pt=12,
            bold=True,
            color=colors["accent"],
        )
    if kicker:
        _add_textbox(
            slide,
            _MARGIN_X + (Inches(0.7) if chapter is not None else Inches(0)),
            Inches(y),
            Inches(11),
            Inches(0.28),
            kicker.upper(),
            size_pt=11,
            bold=True,
            color=colors["accent"],
        )
        y = 0.85 if abs(top_in - margin_top_in) < 1e-6 else y + 0.32
    _add_textbox(
        slide,
        _MARGIN_X,
        Inches(y),
        Inches(12),
        Inches(0.7),
        title,
        size_pt=28 if kicker else 32,
        bold=True,
        color=colors["ink"],
    )
    y2 = y + 0.85
    if takeaway:
        _add_textbox(
            slide,
            _MARGIN_X,
            Inches(y2),
            Inches(11.5),
            Inches(0.45),
            takeaway,
            size_pt=14,
            color=colors["ink2"],
        )
        y2 += 0.5
    return y2


def _is_dark_pack(style: dict[str, Any] | None) -> bool:
    from case3.deck_theme import is_dark_pack

    return is_dark_pack(style)


def _motif_dict(style: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(style, dict):
        return {}
    motif = style.get("motif")
    return motif if isinstance(motif, dict) else {}


def _foil_cards(style: dict[str, Any] | None) -> bool:
    """Gold/accent card borders — botanical bar; any pack with motif.foil_cards."""
    motif = _motif_dict(style)
    if "foil_cards" in motif:
        return bool(motif.get("foil_cards"))
    pack = str((style or {}).get("pack_id") or "")
    return pack == "botanical"


def _botanical_texture_path() -> Path:
    return Path(__file__).resolve().parent / "deck_themes" / "botanical_bg.png"


def _apply_pack_bg(
    slide,
    colors: dict[str, RGBColor],
    style: dict[str, Any] | None,
    *,
    prefer_texture: bool = True,
) -> None:
    """Dark Botanical: fern texture bg (Julius image2) when available."""
    if (
        prefer_texture
        and isinstance(style, dict)
        and str(style.get("pack_id") or "") == "botanical"
    ):
        tex = _botanical_texture_path()
        if tex.is_file() and _set_slide_bg_picture(slide, tex):
            return
    _fill_bg(slide, colors)


def _fill_bg(slide, colors: dict[str, RGBColor]) -> None:
    # Blank layout has no fill control easily; add full-slide rect behind
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), _SLIDE_W, _SLIDE_H
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = colors["sheet"]
    bg.line.fill.background()
    # send to back
    spTree = slide.shapes._spTree
    sp = bg._element
    spTree.remove(sp)
    spTree.insert(2, sp)


def _set_fill_alpha(shape, alpha: float) -> None:
    """Set solid fill transparency (0=opaque, 1=invisible)."""
    try:
        solid = shape.fill._xPr.solidFill
        srgb = solid.find(qn("a:srgbClr"))
        if srgb is None:
            return
        # remove existing alpha
        for child in list(srgb):
            if "alpha" in child.tag:
                srgb.remove(child)
        alpha_el = parse_xml(
            f'<a:alpha {nsdecls("a")} val="{int(max(0, min(1, alpha)) * 100000)}"/>'
        )
        srgb.append(alpha_el)
    except Exception:
        pass


def _set_slide_bg_picture(slide, path: Path) -> bool:
    """Julius-style: full-slide image as OOXML slide background (editable PPTX)."""
    p = Path(path) if path else None
    if p is None or not p.is_file():
        return False
    try:
        _, rid = slide.part.get_or_add_image_part(str(p))
        el = parse_xml(
            f'<p:bg {nsdecls("a", "p", "r")}>'
            f"<p:bgPr>"
            f'<a:blipFill dpi="0" rotWithShape="1">'
            f'<a:blip r:embed="{rid}"/>'
            f"<a:stretch><a:fillRect/></a:stretch>"
            f"</a:blipFill>"
            f"<a:effectLst/>"
            f"</p:bgPr>"
            f"</p:bg>"
        )
        slide._element.cSld.insert(0, el)
        return True
    except Exception:
        return False


def _picture_fit(
    slide,
    path: Path,
    left,
    top,
    box_w,
    box_h,
) -> None:
    """Place image inside box preserving aspect ratio (contain, centered)."""
    if path is None:
        return
    p = Path(path)
    if not p.is_file():
        return
    try:
        with Image.open(p) as im:
            iw, ih = im.size
    except Exception:
        slide.shapes.add_picture(str(p), left, top, width=box_w)
        return
    if iw <= 0 or ih <= 0:
        slide.shapes.add_picture(str(p), left, top, width=box_w)
        return

    bw = _as_inches(box_w)
    bh = _as_inches(box_h)
    l0 = _as_inches(left)
    t0 = _as_inches(top)
    img_r = iw / ih
    box_r = bw / bh if bh > 0 else img_r
    if img_r >= box_r:
        pic_w = bw
        pic_h = bw / img_r
    else:
        pic_h = bh
        pic_w = pic_h * img_r
    off_x = l0 + max(0.0, (bw - pic_w) / 2.0)
    off_y = t0 + max(0.0, (bh - pic_h) / 2.0)
    # Only width — python-pptx keeps aspect ratio (both w+h = stretch/squash).
    slide.shapes.add_picture(
        str(p),
        Inches(off_x),
        Inches(off_y),
        width=Inches(pic_w),
    )


def _split_ratio(style: dict[str, Any] | None) -> float | None:
    if not isinstance(style, dict):
        return None
    motif = style.get("motif") if isinstance(style.get("motif"), dict) else {}
    if "split" not in motif:
        # Panel color alone implies Julius split-pastel title.
        colors = style.get("colors") if isinstance(style.get("colors"), dict) else {}
        if colors.get("panel") and style.get("pack_id") in ("relay", "pastel"):
            return 0.55
        return None
    try:
        return max(0.35, min(0.8, float(motif["split"])))
    except (TypeError, ValueError):
        return 0.55



def _panel_rgb(
    colors: dict[str, RGBColor],
    style: dict[str, Any] | None,
    *,
    slide_index: int = 0,
) -> RGBColor:
    """Rotate Split Pastel panels (lilac/green/peach/blue) like Julius QBR."""
    if isinstance(style, dict):
        motif = style.get("motif") if isinstance(style.get("motif"), dict) else {}
        panels = motif.get("panels") if isinstance(motif.get("panels"), list) else []
        if panels:
            hx = str(panels[slide_index % len(panels)])
            try:
                return _hex_rgb(hx)
            except Exception:
                pass
    return colors.get("panel", colors["accent"])


