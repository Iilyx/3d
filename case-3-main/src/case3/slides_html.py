"""Render Liber deck slides to offline static HTML (capture canvas)."""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path
from typing import Any

from case3.chart_style import _PALETTES, normalize_palette_id
from case3.color_util import accent_fields

_SLIDE_W = 1920
_SLIDE_H = 1080
_FRAME: str | None = None
_FONTS_DIR = Path(__file__).resolve().parent / "templates" / "fonts"


def _frame_template() -> str:
    global _FRAME
    if _FRAME is None:
        path = Path(__file__).resolve().parent / "templates" / "slide_frame.html"
        _FRAME = path.read_text(encoding="utf-8")
    return _FRAME


def _palette_colors(palette_id: str) -> tuple[str, str, str]:
    pid = normalize_palette_id(palette_id)
    if pid == "auto":
        pid = "atelier"
    p = _PALETTES.get(pid) or _PALETTES["atelier"]
    primary = str(p["primary"])
    accents = list(p.get("accents") or [primary])
    accent = str(accents[0] if accents else primary)
    muted = str(p.get("muted") or "#6a6f64")
    return primary, accent, muted


def _esc(s: str) -> str:
    plain = (s or "").replace(r"{\,}", ",").replace("{,}", ",").replace("{.}", ".")
    return html.escape(plain, quote=True)


def _brand(mark: str | None = None) -> str:
    text = (mark or "").strip()
    if not text:
        return ""
    # Split on first · / middle dot for Liber span styling when possible.
    if "·" in text:
        left, right = text.split("·", 1)
        return (
            f'<div class="brand"><span>{_esc(left.strip())}</span> · '
            f"{_esc(right.strip())}</div>"
        )
    return f'<div class="brand">{_esc(text)}</div>'


def _bullets_html(items: list[Any], *, bands: bool = False) -> str:
    lis = "".join(f"<li>{_esc(str(b))}</li>" for b in items if str(b).strip())
    if not lis:
        return ""
    cls = "bullets bullets--bands" if bands else "bullets"
    return f'<ul class="{cls}">{lis}</ul>'


def _len_class(text: str) -> str:
    n = len(str(text or "").split())
    if n <= 6:
        return "is-short"
    if n <= 12:
        return "is-mid"
    return "is-long"


def _section_head(slide: dict[str, Any], *, compact: bool = False) -> str:
    raw_title = str(slide.get("title") or "")
    title = _esc(raw_title)
    kicker = str(slide.get("kicker") or "").strip()
    chapter = slide.get("chapter")
    takeaway = str(slide.get("takeaway") or "").strip()
    chapter_html = (
        f'<p class="chapter">{int(chapter):02d}</p>'
        if isinstance(chapter, int)
        else ""
    )
    kicker_html = f'<p class="kicker">{_esc(kicker)}</p>' if kicker else ""
    takeaway_html = (
        f'<p class="takeaway">{_esc(takeaway)}</p>' if takeaway else ""
    )
    cls = "section-head section-head--compact" if compact else "section-head"
    return (
        f'<header class="{cls}">'
        f"{chapter_html}"
        f"{kicker_html}"
        f'<h2 class="section-title {_len_class(raw_title)}">{title}</h2>'
        f"{takeaway_html}"
        f"</header>"
    )


def _media_img(href: str | None, *, kind: str = "chart") -> str:
    if href:
        return f'<img src="{_esc(href)}" alt="" />'
    label = {
        "photo": "Photo unavailable",
        "diagram": "Diagram unavailable",
    }.get(kind, "Chart unavailable")
    return f'<div class="chart-empty">{_esc(label)}</div>'


def _media_kind(media_id: str) -> str:
    if media_id.startswith(("fig_", "usr_")):
        return "photo"
    if media_id.startswith("dia_"):
        return "diagram"
    return "chart"


def _wants_split_title(style: dict[str, Any] | None) -> bool:
    if not isinstance(style, dict):
        return False
    motif = style.get("motif") if isinstance(style.get("motif"), dict) else {}
    if "split" in motif:
        return True
    if _is_dark_pack(style):
        return False
    return str(style.get("pack_id") or "") in ("relay", "pastel")


def _is_dark_pack(style: dict[str, Any] | None) -> bool:
    from case3.deck_theme import is_dark_pack

    return is_dark_pack(style)


def _motif_panels(style: dict[str, Any] | None) -> list[str]:
    if not isinstance(style, dict):
        return []
    motif = style.get("motif") if isinstance(style.get("motif"), dict) else {}
    raw = motif.get("panels") if isinstance(motif.get("panels"), list) else []
    return [str(p) for p in raw if str(p).strip()]


_STATUS_KIND = {
    "масштаб": "is-scale",
    "scale": "is-scale",
    "рост": "is-scale",
    "в плане": "is-scale",
    "норма": "is-scale",
    "готово": "is-scale",
    "высокий": "is-scale",
    "high": "is-scale",
    "пауза": "is-pause",
    "pause": "is-pause",
    "риск": "is-pause",
    "срыв": "is-pause",
    "отставание": "is-pause",
    "держать": "is-hold",
    "дерBим": "is-hold",
    "держим": "is-hold",
    "hold": "is-hold",
    "фокус": "is-hold",
    "тест": "is-hold",
    "средний": "is-hold",
    "med": "is-hold",
}


def _cell_html(text: str, *, header: bool) -> str:
    tag = "th" if header else "td"
    raw = str(text or "")
    kind = None if header else _STATUS_KIND.get(raw.strip().casefold())
    inner = (
        f'<span class="status-chip {kind}">{_esc(raw)}</span>' if kind else _esc(raw)
    )
    return f"<{tag}>{inner}</{tag}>"


def _pct_from_kicker(kicker: str) -> int | None:
    """Parse leading ``68%`` / ``104% NA`` kickers for narr-card meters."""
    m = re.match(r"^(\d{1,3})\s*%", (kicker or "").strip())
    if not m:
        return None
    return max(0, min(100, int(m.group(1))))


def parse_hero_metrics(takeaway: str) -> list[tuple[str, str]]:
    """Julius title-panel KPIs: stacked (value, label) from takeaway.

    Accepts:
    - one ``VALUE — label`` per line (2–4 lines),
    - alternating bare lines ``value\\nlabel\\nvalue\\nlabel``,
    - or ``VALUE — label · VALUE — label`` on one line.
    """
    raw = (takeaway or "").strip()
    if not raw:
        return []

    def _split_pair(ch: str) -> tuple[str, str] | None:
        for sep in (" — ", " – ", " - ", ": "):
            if sep in ch:
                left, right = ch.split(sep, 1)
                if left.strip() and right.strip():
                    return left.strip(), right.strip()
        return None

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    # Prefer per-line VALUE — label (works for 2, 3, or 4 metrics).
    if len(lines) >= 2:
        dashed = [_split_pair(ln) for ln in lines]
        if all(p is not None for p in dashed):
            return [p for p in dashed if p is not None][:4]
        # Alternating bare value / label lines.
        if len(lines) >= 2 and len(lines) % 2 == 0 and all(
            _split_pair(ln) is None for ln in lines
        ):
            return [(lines[i], lines[i + 1]) for i in range(0, len(lines), 2)][:4]

    chunks = [c.strip() for c in raw.replace("|", "·").split("·") if c.strip()]
    out: list[tuple[str, str]] = []
    for ch in chunks:
        pair = _split_pair(ch)
        if pair:
            out.append(pair)
        elif ch:
            out.append((ch, ""))
    if len(out) >= 2:
        return out[:4]
    if len(out) == 1 and out[0][1]:
        return out[:1]
    return []


def _title_panel_inner(
    takeaway: str, *, slide: dict[str, Any] | None = None
) -> str:
    metrics = parse_hero_metrics(takeaway)
    if metrics:
        blocks = []
        for idx, (value, label) in enumerate(metrics, start=1):
            lab = (
                f'<p class="hero-metric__label">{_esc(label)}</p>' if label else ""
            )
            blocks.append(
                f'<div class="hero-metric">'
                f'<span class="hero-metric__idx">{idx:02d}</span>'
                f'<p class="hero-metric__value">{_esc(value)}</p>'
                f"{lab}</div>"
            )
        return f'<div class="hero-metrics">{"".join(blocks)}</div>'
    if takeaway.strip():
        kicker = str((slide or {}).get("kicker") or "КЛЮЧЕВОЙ ФОКУС").strip()
        return (
            f'<div class="hero-metrics">'
            f'<div class="hero-metric hero-metric--statement">'
            f'<span class="hero-metric__idx">{_esc(kicker)}</span>'
            f'<p class="takeaway takeaway--hero">{_esc(takeaway.strip())}</p>'
            f"</div></div>"
        )
    sub = str((slide or {}).get("subtitle") or "").strip()
    kicker = str((slide or {}).get("kicker") or "ОБЗОР").strip()
    title = str((slide or {}).get("title") or "").strip()
    fallback_copy = sub or title
    if fallback_copy:
        return (
            f'<div class="hero-metrics">'
            f'<div class="hero-metric hero-metric--statement">'
            f'<span class="hero-metric__idx">{_esc(kicker)}</span>'
            f'<p class="takeaway takeaway--hero">{_esc(fallback_copy)}</p>'
            f"</div></div>"
        )
    return '<p class="takeaway takeaway--hero"></p>'


def _diagram_legend(
    palette: str,
    *,
    diagram_spec: dict[str, Any] | None = None,
) -> str:
    """Role legend dots under diagram caption — real roles from diagram_spec when provided."""
    from case3.diagram_style import ROLE_LABEL_RU, extract_diagram_legend, role_colors_for_palette

    colors = role_colors_for_palette(palette)
    if diagram_spec is not None:
        dtype = str(diagram_spec.get("type") or "").strip().lower()
        mermaid = str(diagram_spec.get("mermaid") or "")
        if dtype and dtype not in ("flowchart", "graph"):
            return ""
        entries = extract_diagram_legend(mermaid)
        if not entries:
            return ""
        lis = []
        for ent in entries:
            role = str(ent.get("role") or "")
            stroke = (colors.get(role) or {}).get("stroke") or str(ent.get("fill") or "#6b8f76")
            label = str(ent.get("label") or ROLE_LABEL_RU.get(role, role))
            lis.append(f'<li><i style="background:{stroke}"></i>{_esc(label)}</li>')
        return f'<ul class="dia-legend">{"".join(lis)}</ul>'

    items = (
        ("start", "Старт"),
        ("decision", "Решение"),
        ("ok", "Успех"),
        ("warn", "Риск"),
    )
    lis = []
    for role, label in items:
        stroke = colors[role]["stroke"]
        lis.append(
            f'<li><i style="background:{stroke}"></i>{_esc(label)}</li>'
        )
    return f'<ul class="dia-legend">{"".join(lis)}</ul>'


def _body_for_slide(
    slide: dict[str, Any],
    *,
    media_png_href: str | None,
    brand_mark: str | None = None,
    style: dict[str, Any] | None = None,
    slide_index: int = 0,
    palette: str = "atelier",
    diagram_spec: dict[str, Any] | None = None,
) -> str:
    layout = str(slide.get("layout") or "")
    brand = _brand(brand_mark)
    panels = _motif_panels(style)

    if layout == "title":
        title = _esc(str(slide.get("title") or ""))
        sub = str(slide.get("subtitle") or "").strip()
        sub_html = f'<p class="subtitle">{_esc(sub)}</p>' if sub else ""
        kicker = str(slide.get("kicker") or "").strip()
        kicker_html = f'<p class="kicker">{_esc(kicker)}</p>' if kicker else ""
        takeaway = str(slide.get("takeaway") or "").strip()
        takeaway_html = (
            f'<p class="takeaway takeaway--hero">{_esc(takeaway)}</p>'
            if takeaway
            else ""
        )
        raw_bullets = [
            str(b).strip() for b in (slide.get("bullets") or []) if str(b).strip()
        ]
        pills_html = (
            '<div class="title-pills">'
            + "".join(f'<span class="title-pill">{_esc(b)}</span>' for b in raw_bullets[:4])
            + "</div>"
            if raw_bullets
            else ""
        )
        dark = _is_dark_pack(style)
        motif = style.get("motif") if isinstance(style, dict) else {}
        hero_bleed = bool(isinstance(motif, dict) and motif.get("hero_bleed"))
        split = _wants_split_title(style)
        panel_inner = _title_panel_inner(takeaway, slide=slide)
        panel_html = (
            f'<aside class="title-panel">{panel_inner}</aside>' if split else ""
        )
        main_takeaway = "" if split else takeaway_html
        pack = _esc(str((style or {}).get("pack_id") or ""))
        # Dark Botanical: full-bleed media behind left copy (Julius VESPER).
        if dark and hero_bleed and media_png_href:
            bg = ""
            if media_png_href:
                bg = (
                    f'<div class="title-bleed" aria-hidden="true">'
                    f'<img src="{_esc(media_png_href)}" alt="" />'
                    f'<div class="title-bleed__veil"></div></div>'
                )
            bullets_html = _bullets_html(slide.get("bullets") or [])
            return (
                f'<div class="slide-inner title-stage title-stage--bleed" data-pack="{pack}">'
                f"{bg}"
                f'<div class="title-main title-main--bleed">'
                f"{brand}"
                f"{kicker_html}"
                f'<h1 class="{_len_class(str(slide.get("title") or ""))}">{title}</h1>'
                f"{main_takeaway or _title_panel_inner(takeaway, slide=slide)}"
                f"{sub_html}"
                f"{bullets_html}"
                f"</div></div>"
            )
        if not split:
            return (
                f'<div class="slide-inner title-stage title-stage--field" data-pack="{pack}">'
                f'<div class="title-field__copy">'
                f"{brand}"
                f"{kicker_html}"
                f'<h1 class="{_len_class(str(slide.get("title") or ""))}">{title}</h1>'
                f"{main_takeaway}"
                f"{sub_html}"
                f"{pills_html}"
                f"</div>"
                f'<aside class="title-field__rail" aria-hidden="true">'
                f"{panel_inner}"
                f'<span class="rail-watermark">01</span>'
                f"</aside>"
                f"</div>"
            )
        stage_cls = "slide-inner title-stage title-stage--split"
        return (
            f'<div class="{stage_cls}" data-pack="{pack}">'
            f'<div class="title-main">'
            f"{brand}"
            f"{kicker_html}"
            f'<h1 class="{_len_class(str(slide.get("title") or ""))}">{title}</h1>'
            f"{main_takeaway}"
            f"{sub_html}"
            f"{pills_html}"
            f"</div>"
            f"{panel_html}"
            f"</div>"
        )

    if layout == "section":
        # Twin of PPTX _layout_section: title left, accent chapter panel right.
        chapter = slide.get("chapter")
        num_str = f"{int(chapter):02d}" if isinstance(chapter, int) else "01"
        kicker = str(slide.get("kicker") or "").strip()
        kicker_html = (
            f'<p class="kicker">{_esc(kicker)}</p>'
            if kicker
            else f'<p class="kicker">ГЛАВА {num_str}</p>'
        )
        sub = str(slide.get("subtitle") or slide.get("takeaway") or "").strip()
        line = (
            f'<p class="section-splash__line">{_esc(sub)}</p>' if sub else ""
        )
        panel = (
            f'<aside class="section-splash__panel is-sentence">'
            f'<p class="section-splash__num">{num_str}</p>'
            f"{line}</aside>"
        )
        raw_bullets = [
            str(b).strip() for b in (slide.get("bullets") or []) if str(b).strip()
        ]
        pills_html = (
            '<div class="title-pills">'
            + "".join(f'<span class="title-pill">{_esc(b)}</span>' for b in raw_bullets[:4])
            + "</div>"
            if raw_bullets
            else ""
        )
        return (
            f'<div class="slide-inner section-splash">'
            f"{brand}"
            f'<div class="section-splash__main">'
            f"{kicker_html}"
            f'<h1 class="section-splash__title {_len_class(str(slide.get("title") or ""))}">{_esc(str(slide.get("title") or ""))}</h1>'
            f"{pills_html}"
            f"</div>"
            f"{panel}"
            f"</div>"
        )

    if layout == "bullets":
        return (
            f'<div class="slide-inner bullets-stage">'
            f"{brand}"
            f"{_section_head(slide)}"
            f"{_bullets_html(slide.get('bullets') or [], bands=True)}"
            f"</div>"
        )

    if layout == "closing":
        dark = _is_dark_pack(style)
        motif = style.get("motif") if isinstance(style, dict) else {}
        hero_bleed = bool(isinstance(motif, dict) and motif.get("hero_bleed"))
        if dark and hero_bleed and media_png_href:
            # Twin of PPTX closing→title hero bleed (Julius VESPER close).
            return _body_for_slide(
                {
                    **slide,
                    "layout": "title",
                    "kicker": str(slide.get("kicker") or "CLOSE"),
                },
                media_png_href=media_png_href,
                brand_mark=brand_mark,
                style=style,
                slide_index=slide_index,
            )
        takeaway = str(slide.get("takeaway") or "").strip()
        kicker = str(slide.get("kicker") or "").strip()
        kicker_html = (
            f'<p class="closing-plaque__kicker">{_esc(kicker)}</p>' if kicker else ""
        )
        metrics = parse_hero_metrics(takeaway)
        hero_html = ""
        if metrics:
            value, label = metrics[0]
            lab = (
                f'<p class="closing-hero__label">{_esc(label)}</p>' if label else ""
            )
            hero_html = (
                f'<div class="closing-hero">'
                f'<p class="closing-hero__value">{_esc(value)}</p>'
                f"{lab}</div>"
            )
        elif takeaway and len(takeaway) <= 24:
            hero_html = (
                f'<div class="closing-hero">'
                f'<p class="closing-hero__value">{_esc(takeaway)}</p>'
                f"</div>"
            )
        bullets = [
            str(b).strip() for b in (slide.get("bullets") or []) if str(b).strip()
        ]
        decision = " ".join(bullets) or str(slide.get("title") or "")
        title = str(slide.get("title") or "")
        if hero_html:
            left = (
                f"{kicker_html}{hero_html}"
                f'<h2 class="closing-plaque__title is-sub">{_esc(title)}</h2>'
            )
        else:
            left = f"{kicker_html}<h2 class=\"closing-plaque__title\">{_esc(title)}</h2>"
        if bullets:
            right = (
                f'<p class="closing-plaque__kicker">КЛЮЧЕВЫЕ РЕШЕНИЯ И ШАГИ</p>'
                f"{_bullets_html(bullets, bands=True)}"
            )
        else:
            right = f'<p class="closing-plaque__decision">{_esc(decision)}</p>'
        return (
            f'<div class="slide-inner closing-stage closing-stage--split">'
            f'<div class="closing-plaque closing-plaque--a">{brand}{left}</div>'
            f'<div class="closing-plaque closing-plaque--b">{right}</div>'
            f"</div>"
        )

    if layout in ("kpi_row", "scorecard"):
        cards = []
        for i, k in enumerate(slide.get("kpis") or []):
            if not isinstance(k, dict):
                continue
            hint = str(k.get("hint") or "").strip()
            delta = str(k.get("delta") or "").strip()
            status = str(k.get("status") or "").strip()
            hint_html = f'<div class="hint">{_esc(hint)}</div>' if hint else ""
            delta_html = (
                f'<div class="delta status-{_esc(status or "flat")}">'
                f"{_esc(delta)}</div>"
                if delta
                else ""
            )
            # Split Pastel: distinct pastels across KPI cards (Julius scorecard).
            pastel = ""
            if panels:
                hx = panels[i % len(panels)]
                pastel = (
                    f' style="background:{_esc(hx)};border-color:transparent;'
                    f'border-left-color:{_esc(hx)}"'
                )
            bar_html = f'<div class="kpi-bar status-{_esc(status or "flat")}" aria-hidden="true"><i></i></div>'
            foot = (
                f'<div class="kpi-foot">{delta_html}{bar_html}</div>'
                if delta_html
                else f'<div class="kpi-foot">{bar_html}</div>'
            )
            cards.append(
                f'<div class="kpi-card"{pastel}>'
                f'<div class="kpi-main">'
                f'<span class="kpi-idx">{i + 1:02d}</span>'
                f"<div class=\"value\">{_esc(str(k.get('value') or ''))}</div>"
                f"<div class=\"label\">{_esc(str(k.get('label') or ''))}</div>"
                f"{hint_html}"
                f"</div>"
                f"{foot}"
                "</div>"
            )
        cols = max(1, min(4, len(cards) or 1))
        grid_cls = "kpi-grid scorecard-grid" if layout == "scorecard" else "kpi-grid"
        gate = str(slide.get("caption") or "").strip()
        gate_html = f'<p class="narr-gate">{_esc(gate)}</p>' if gate else ""
        return (
            f'<div class="slide-inner">'
            f"{brand}"
            f"{_section_head(slide)}"
            f'<div class="{grid_cls}" style="--kpi-cols:{cols}">'
            f'{"".join(cards)}</div>'
            f"{gate_html}"
            f"</div>"
        )

    if layout == "callout":
        term = _esc(str(slide.get("term") or ""))
        definition = _esc(str(slide.get("definition") or ""))
        body = str(slide.get("body") or "").strip()
        kicker = str(slide.get("kicker") or "").strip()
        raw_title = str(slide.get("title") or "").strip()
        kicker_html = (
            f'<p class="callout__kicker">{_esc(kicker)}</p>' if kicker else ""
        )
        title_html = (
            f'<h2 class="callout__title">{_esc(raw_title)}</h2>'
            if raw_title and raw_title.casefold() != str(slide.get("term") or "").strip().casefold()
            else ""
        )
        body_html = f'<p class="callout__body">{_esc(body)}</p>' if body else ""
        rail_label = kicker or str(slide.get("term") or "ТЕЗИС").strip()
        rail_note = raw_title if raw_title else body
        rail_note_html = (
            f'<p class="rail-card__note">{_esc(rail_note)}</p>'
            if rail_note
            else ""
        )
        return (
            f'<div class="slide-inner callout-stage">'
            f'<div class="callout-stage__copy">'
            f"{brand}"
            f"{kicker_html}"
            f'<p class="callout__term">{term}</p>'
            f'<p class="callout__def">{definition}</p>'
            f"{body_html}"
            f"</div>"
            f'<aside class="title-field__rail" aria-hidden="true">'
            f'<div class="rail-card">'
            f'<span class="rail-watermark">«</span>'
            f'<p class="rail-card__kicker">{_esc(rail_label)}</p>'
            f"{rail_note_html}"
            f"</div>"
            f"</aside>"
            f"</div>"
        )

    if layout == "card_row":
        cards_html: list[str] = []
        for i, c in enumerate(slide.get("cards") or []):
            if not isinstance(c, dict):
                continue
            kicker = str(c.get("kicker") or "").strip()
            pct = _pct_from_kicker(kicker)
            kicker_html = (
                f'<p class="narr-card__kicker">{_esc(kicker)}</p>' if kicker else ""
            )
            meter_html = ""
            if pct is not None:
                m = re.match(r"^\s*([0-9]+(?:[.,][0-9]+)?\s*%)\s+(.*\S)\s*$", kicker)
                if m:
                    pct_val, pct_label = m.group(1), m.group(2)
                    kicker_html = (
                        f'<div class="narr-card__pct-head">'
                        f'<span class="narr-card__kicker is-pct">{_esc(pct_val)}</span>'
                        f'<span class="narr-card__pct-tag">{_esc(pct_label)}</span>'
                        f"</div>"
                    )
                else:
                    kicker_html = (
                        f'<p class="narr-card__kicker is-pct">{_esc(kicker)}</p>'
                    )
                meter_html = (
                    f'<div class="narr-meter" style="--pct:{pct}" aria-hidden="true">'
                    f"<i></i></div>"
                )
            body = str(c.get("body") or "").strip()
            body_html = (
                f'<p class="narr-card__body">{_esc(body)}</p>' if body else ""
            )
            pastel = ""
            if panels:
                hx = panels[i % len(panels)]
                pastel = f' style="background:{_esc(hx)}"'
            card_cls = "narr-card is-metered" if pct is not None else "narr-card"
            cards_html.append(
                f'<article class="{card_cls}"{pastel}>'
                f"{kicker_html}"
                f"{meter_html}"
                f'<p class="narr-card__title">{_esc(str(c.get("title") or ""))}</p>'
                f"{body_html}"
                f"</article>"
            )
        gate = str(slide.get("caption") or "").strip()
        gate_html = (
            f'<p class="narr-gate">{_esc(gate)}</p>' if gate else ""
        )
        # Prefer subtitle over takeaway for the audience hypothesis line.
        head = dict(slide)
        if str(slide.get("subtitle") or "").strip() and not str(
            slide.get("takeaway") or ""
        ).strip():
            head = {**slide, "takeaway": str(slide.get("subtitle") or "")}
        return (
            f'<div class="slide-inner">'
            f"{brand}"
            f"{_section_head(head)}"
            f'<div class="narr-grid" style="--narr-cols:{max(1, min(3, len(cards_html) or 1))}">'
            f'{"".join(cards_html)}</div>'
            f"{gate_html}</div>"
        )

    if layout == "table_hero":
        rows = slide.get("rows") or []
        trs = []
        for i, row in enumerate(rows):
            if not isinstance(row, list):
                continue
            cells = "".join(
                _cell_html(str(c), header=(i == 0)) for c in row
            )
            trs.append(f"<tr>{cells}</tr>")
        cap = str(slide.get("caption") or "").strip()
        cap_html = f'<p class="narr-gate">{_esc(cap)}</p>' if cap else ""
        data_n = max(0, len(trs) - 1)
        if 0 < data_n <= 6:
            roomy = " is-roomy"
        elif data_n > 8:
            roomy = " is-dense"
        else:
            roomy = ""
        return (
            f'<div class="slide-inner">'
            f"{brand}"
            f"{_section_head(slide, compact=True)}"
            f'<div class="table-stage">'
            f'<table class="deck-table{roomy}"><tbody>{"".join(trs)}</tbody></table>'
            f"{cap_html}</div></div>"
        )

    if layout == "chart_hero":
        img = _media_img(media_png_href, kind="chart")
        cap = str(
            slide.get("caption") or slide.get("takeaway") or slide.get("title") or ""
        ).strip()
        line = (
            f'<p class="caption caption--insight chart-hero__line">{_esc(cap)}</p>'
            if cap
            else ""
        )
        head_slide = {**slide, "takeaway": ""}
        head_html = (
            _section_head(head_slide, compact=True)
            if str(slide.get("title") or "").strip() and str(slide.get("title") or "").strip() != cap
            else ""
        )
        return (
            f'<div class="slide-inner chart-hero chart-hero--field">'
            f'<aside class="chart-hero__rail">{brand}{head_html}{line}</aside>'
            f'<div class="chart-hero__plot">{img}</div>'
            f"</div>"
        )

    if layout == "chart_split":
        img = _media_img(media_png_href, kind="chart")
        body = str(slide.get("body") or "").strip()
        body_html = f'<p class="body">{_esc(body)}</p>' if body else ""
        bullets = _bullets_html(slide.get("bullets") or [], bands=True)
        cap = str(slide.get("caption") or "").strip()
        cap_html = (
            f'<p class="caption caption--insight">{_esc(cap)}</p>' if cap and not bullets else ""
        )
        return (
            f'<div class="slide-inner chart-split chart-split--field">'
            f'<div class="chart-split__copy">{brand}{_section_head(slide, compact=True)}{body_html}{bullets}{cap_html}</div>'
            f'<div class="chart-hero__plot">{img}</div>'
            f"</div>"
        )

    if layout == "media_hero":
        mid = str(slide.get("media_id") or "")
        kind = _media_kind(mid)
        img = _media_img(media_png_href, kind=kind)
        pack_key = str((style or {}).get("pack_id") or "").strip() or palette
        cap = str(
            slide.get("caption") or slide.get("takeaway") or slide.get("title") or ""
        ).strip()
        line = (
            f'<p class="caption caption--insight chart-hero__line">{_esc(cap)}</p>'
            if cap
            else ""
        )
        head_slide = {**slide, "takeaway": ""}
        head_html = (
            _section_head(head_slide, compact=True)
            if str(slide.get("title") or "").strip()
            and str(slide.get("title") or "").strip() != cap
            else ""
        )
        if kind == "diagram":
            return (
                f'<div class="slide-inner media-hero media-hero--diagram">'
                f'<aside class="chart-hero__rail">{brand}{head_html}{line}{_diagram_legend(pack_key, diagram_spec=diagram_spec)}</aside>'
                f'<div class="chart-hero__plot"><div class="diagram-stage">{img}</div></div>'
                f"</div>"
            )
        kicker = str(slide.get("kicker") or "").strip()
        kick = f'<p class="kicker">{_esc(kicker)}</p>' if kicker else ""
        return (
            f'<div class="slide-inner media-hero media-hero--bleed">'
            f'<div class="media-hero__photo media-frame">{img}</div>'
            f'<aside class="media-hero__plaque">{kick}{head_html}{line}</aside>'
            f"</div>"
        )

    if layout == "media_split":
        mid = str(slide.get("media_id") or "")
        kind = _media_kind(mid)
        img = _media_img(media_png_href, kind=kind)
        pack_key = str((style or {}).get("pack_id") or "").strip() or palette
        body = str(slide.get("body") or "").strip()
        body_html = (
            f'<p class="media-split__body">{_esc(body)}</p>' if body else ""
        )
        bullets = _bullets_html(slide.get("bullets") or [], bands=True)
        legend_html = _diagram_legend(pack_key, diagram_spec=diagram_spec) if kind == "diagram" else ""
        cap = str(slide.get("caption") or "").strip()
        cap_html = (
            f'<p class="media-aside-caption">{_esc(cap)}</p>' if cap else ""
        )
        frame_mod = " media-frame--diagram" if kind == "diagram" else (
            " media-frame--photo" if kind == "photo" else ""
        )
        grid_mod = " is-diagram" if kind == "diagram" else ""
        return (
            f'<div class="slide-inner media-split">'
            f"{brand}"
            f'<div class="media-split__grid{grid_mod}">'
            f'<div class="media-split__copy">'
            f"{_section_head(slide, compact=True)}"
            f"{body_html}{bullets}{legend_html}"
            f"</div>"
            f'<aside class="media-split__aside">'
            f'<figure class="media-frame media-frame--thumb{frame_mod}">'
            f'<div class="media-frame__inset">{img}</div>'
            f"</figure>"
            f"{cap_html}"
            f"</aside></div></div>"
        )

    if layout == "quote":
        definition = _esc(str(slide.get("definition") or ""))
        term = str(slide.get("term") or "").strip()
        body = str(slide.get("body") or "").strip()
        term_html = f'<p class="pull-quote__who">{_esc(term)}</p>' if term else ""
        body_html = f'<p class="pull-quote__note">{_esc(body)}</p>' if body else ""
        return (
            f'<div class="slide-inner">'
            f"{brand}"
            f"{_section_head(slide)}"
            f'<blockquote class="pull-quote">'
            f'<p class="pull-quote__text">{definition}</p>'
            f"{term_html}{body_html}"
            f"</blockquote></div>"
        )

    if layout == "stat_hero":
        kpi = next(
            (k for k in (slide.get("kpis") or []) if isinstance(k, dict)),
            {},
        )
        kicker = str(slide.get("kicker") or "").strip()
        raw_title = str(slide.get("title") or "").strip()
        kicker_html = f'<p class="kicker">{_esc(kicker)}</p>' if kicker else ""
        title_html = (
            f'<h2 class="stat-hero__headline">{_esc(raw_title)}</h2>'
            if raw_title
            else ""
        )
        delta = str(kpi.get("delta") or "").strip()
        hint = str(kpi.get("hint") or "").strip()
        delta_html = f'<p class="stat-hero__delta">{_esc(delta)}</p>' if delta else ""
        hint_html = f'<p class="stat-hero__hint">{_esc(hint)}</p>' if hint else ""
        return (
            f'<div class="slide-inner stat-hero stat-hero--field">'
            f'<div class="stat-hero__figure">'
            f"{brand}"
            f"{kicker_html}"
            f"{title_html}"
            f'<p class="stat-hero__value">{_esc(str(kpi.get("value") or ""))}</p>'
            f'<p class="stat-hero__label">{_esc(str(kpi.get("label") or ""))}</p>'
            f"{delta_html}{hint_html}"
            f"</div>"
            f'<div class="stat-hero__notes">'
            f'<p class="stat-hero__notes-kicker">КОНТЕКСТ И ДРАЙВЕРЫ</p>'
            f'{_bullets_html(slide.get("bullets") or [], bands=True)}'
            f"</div>"
            f"</div>"
        )

    if layout == "timeline":
        steps = []
        for i, c in enumerate(slide.get("cards") or []):
            if not isinstance(c, dict):
                continue
            kicker = str(c.get("kicker") or "").strip()
            body = str(c.get("body") or "").strip()
            kick = f'<p class="timeline__time">{_esc(kicker)}</p>' if kicker else ""
            body_html = f'<p class="timeline__body">{_esc(body)}</p>' if body else ""
            steps.append(
                f'<li class="timeline__step">'
                f'<span class="timeline__num">{i + 1:02d}</span>'
                f"{kick}"
                f'<p class="timeline__title">{_esc(str(c.get("title") or ""))}</p>'
                f"{body_html}</li>"
            )
        return (
            f'<div class="slide-inner">'
            f"{brand}"
            f"{_section_head(slide)}"
            f'<ol class="timeline">{"".join(steps)}</ol>'
            f"</div>"
        )

    if layout == "compare":
        cols = []
        for i, c in enumerate(slide.get("cards") or []):
            if not isinstance(c, dict):
                continue
            kicker = str(c.get("kicker") or "").strip()
            body = str(c.get("body") or "").strip()
            kick = f'<p class="compare__kicker">{_esc(kicker)}</p>' if kicker else ""
            body_html = f'<p class="compare__body">{_esc(body)}</p>' if body else ""
            side = "is-a" if i == 0 else "is-b"
            cols.append(
                f'<article class="compare__col {side}">{kick}'
                f'<p class="compare__title">{_esc(str(c.get("title") or ""))}</p>'
                f"{body_html}"
                f'<p class="compare__index">{i + 1:02d}</p></article>'
            )
        return (
            f'<div class="slide-inner compare-stage">'
            f"{brand}"
            f"{_section_head(slide)}"
            f'<div class="compare compare--fields">{"".join(cols)}</div>'
            f"</div>"
        )

    raise ValueError(f"unsupported layout: {layout!r}")


def _theme_color_map(
    palette: str, style: dict[str, Any] | None
) -> dict[str, str]:
    """Prefer deck.style.colors (ThemeTokens); fall back to chart palette."""
    colors = (style or {}).get("colors") if isinstance(style, dict) else None
    if isinstance(colors, dict) and colors.get("primary"):
        return {
            "primary": str(colors.get("primary") or "#2E4208"),
            "accent": str(colors.get("accent") or "#4F6B14"),
            "muted": str(colors.get("muted") or "#6A7160"),
            "ink": str(colors.get("ink") or "#14161a"),
            "ink2": str(colors.get("ink2") or "#2c3028"),
            "paper": str(colors.get("paper") or "#f0ede4"),
            "sheet": str(colors.get("sheet") or colors.get("background") or "#fffcf7"),
            "rule": str(colors.get("rule") or "#e6e2d8"),
            "foil": str(colors.get("foil") or "#b8a36a"),
            "panel": str(colors.get("panel") or colors.get("paper") or "#f0ede4"),
        }
    primary, accent, muted = _palette_colors(palette)
    return {
        "primary": primary,
        "accent": accent,
        "muted": muted,
        "ink": "#14161a",
        "ink2": "#2c3028",
        "paper": "#f0ede4",
        "sheet": "#fffcf7",
        "rule": "#e6e2d8",
        "foil": "#b8a36a",
        "panel": "#f0ede4",
    }


def _panel_for_slide(
    style: dict[str, Any] | None, *, slide_index: int = 0, fallback: str = "#E8E0F2"
) -> str:
    if not isinstance(style, dict):
        return fallback
    motif = style.get("motif") if isinstance(style.get("motif"), dict) else {}
    panels = motif.get("panels") if isinstance(motif.get("panels"), list) else []
    if panels:
        return str(panels[slide_index % len(panels)])
    colors = style.get("colors") if isinstance(style.get("colors"), dict) else {}
    return str(colors.get("panel") or fallback)


def render_slide_html(
    slide: dict[str, Any],
    *,
    palette: str,
    chart_png_href: str | None = None,
    media_png_href: str | None = None,
    language: str = "ru",
    style: dict[str, Any] | None = None,
    slide_index: int = 0,
    diagram_spec: dict[str, Any] | None = None,
) -> str:
    """Return a full HTML document for one slide (1920×1080)."""
    cmap = _theme_color_map(palette, style)
    href = media_png_href if media_png_href is not None else chart_png_href
    brand_mark = ""
    if isinstance(style, dict) and style.get("brand_mark"):
        brand_mark = str(style.get("brand_mark")).strip()
    body = _body_for_slide(
        slide,
        media_png_href=href,
        brand_mark=brand_mark,
        style=style,
        slide_index=slide_index,
        palette=palette,
        diagram_spec=diagram_spec,
    )
    layout = str(slide.get("layout") or "")
    footer = _esc(brand_mark)
    panel = _panel_for_slide(
        style, slide_index=slide_index, fallback=cmap.get("panel") or cmap["paper"]
    )
    pack = ""
    if isinstance(style, dict) and style.get("pack_id"):
        pack = str(style.get("pack_id") or "").strip()
    fields = accent_fields(cmap)
    return (
        _frame_template()
        .replace("{{LANG}}", _esc(language or "ru"))
        .replace("{{PRIMARY}}", cmap["primary"])
        .replace("{{ACCENT}}", cmap["accent"])
        .replace("{{MUTED}}", cmap["muted"])
        .replace("{{INK}}", cmap["ink"])
        .replace("{{INK2}}", cmap["ink2"])
        .replace("{{PAPER}}", cmap["paper"])
        .replace("{{SHEET}}", cmap["sheet"])
        .replace("{{RULE}}", cmap["rule"])
        .replace("{{FOIL}}", cmap["foil"])
        .replace("{{PANEL}}", panel)
        .replace("{{ON_ACCENT}}", fields["on_accent"])
        .replace("{{FIELD_B}}", fields["field_b"])
        .replace("{{ON_FIELD_B}}", fields["on_field_b"])
        .replace("{{RAIL}}", fields["rail"])
        .replace("{{ON_RAIL}}", fields["on_rail"])
        .replace("{{LAYOUT}}", _esc(layout))
        .replace("{{PACK}}", _esc(pack))
        .replace("{{BRAND_MARK}}", footer)
        .replace("{{BODY}}", body)
    )


def _copy_fonts(dest_fonts: Path) -> None:
    dest_fonts.mkdir(parents=True, exist_ok=True)
    if not _FONTS_DIR.is_dir():
        return
    for src in _FONTS_DIR.glob("*.woff2"):
        target = dest_fonts / src.name
        if not target.is_file() or target.stat().st_size != src.stat().st_size:
            shutil.copy2(src, target)


def write_slide_work(
    slide: dict[str, Any],
    work_dir: Path,
    *,
    palette: str,
    language: str = "ru",
    chart_png: Path | None = None,
    media_png: Path | None = None,
    style: dict[str, Any] | None = None,
    slide_index: int = 0,
    diagram_spec: dict[str, Any] | None = None,
) -> Path:
    """Write index.html (+ fonts + optional media.png) into work_dir."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    _copy_fonts(work_dir / "fonts")
    # Dark Botanical fern texture (Julius image2 twin) for non-hero slides.
    if isinstance(style, dict) and str(style.get("pack_id") or "") == "botanical":
        tex_src = (
            Path(__file__).resolve().parent / "deck_themes" / "botanical_bg.png"
        )
        if tex_src.is_file():
            shutil.copy2(tex_src, work_dir / "botanical_bg.png")
    src_png = media_png if media_png is not None else chart_png
    href: str | None = None
    if src_png is not None and Path(src_png).is_file():
        dest = work_dir / "media.png"
        if Path(src_png).resolve() != dest.resolve():
            dest.write_bytes(Path(src_png).read_bytes())
        # Keep chart.png alias for older allowlist / tests
        chart_alias = work_dir / "chart.png"
        if not chart_alias.is_file():
            shutil.copy2(dest, chart_alias)
        href = "media.png"
    html_doc = render_slide_html(
        slide,
        palette=palette,
        media_png_href=href,
        language=language,
        style=style,
        slide_index=slide_index,
        diagram_spec=diagram_spec,
    )
    index = work_dir / "index.html"
    index.write_text(html_doc, encoding="utf-8")
    return index


SLIDE_VIEWPORT = (_SLIDE_W, _SLIDE_H)
