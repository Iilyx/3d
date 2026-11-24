"""Named chart palettes for UI → Intent → Chart.js HTML."""

from __future__ import annotations

from case3.color_util import hex_to_rgb

import re
from typing import Any

# Preset ids used in Form/UI. ``auto`` = model picks one preset for the doc.
PALETTE_IDS = ("auto", "editorial", "ocean", "sunset", "mono", "atelier")

_HEX = re.compile(r"#([0-9a-fA-F]{6})\b")
_RGBA = re.compile(
    r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*([0-9.]+))?\s*\)",
    re.I,
)


def _lum(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _parse_hex(h: str) -> tuple[int, int, int]:
    rgb = hex_to_rgb(h)
    if rgb is None:
        raise ValueError(f"bad hex: {h!r}")
    return rgb


def apply_hex_series_to_html(
    html: str,
    series_hexes: list[str],
    *,
    muted: str | None = None,
    area: str = "",
    grid: str = "",
) -> str:
    """Remap #hex / rgb(a) chart colors onto an ordered hex series (deck packs).

    First hex ≈ primary; remaining ≈ accents. Keeps alpha. Near-white unchanged.
    """
    targets = [
        f"#{h.lstrip('#').upper()}"
        for h in series_hexes
        if h and re.match(r"^#?[0-9A-Fa-f]{6}$", str(h).strip())
    ]
    if not targets or not (html or "").strip():
        return html
    muted_u = (muted or "").upper()
    if muted_u and not muted_u.startswith("#"):
        muted_u = f"#{muted_u}"
    src = html or ""

    def _is_near_white(hx: str) -> bool:
        r, g, b = _parse_hex(hx)
        return min(r, g, b) >= 245

    def _is_ink_grey(hx: str) -> bool:
        r, g, b = _parse_hex(hx)
        if max(r, g, b) - min(r, g, b) > 28:
            return False
        return 40 <= _lum(r, g, b) <= 190

    _PROP_NEAR = re.compile(
        r"(backgroundcolor|bordercolor|pointbackgroundcolor|pointbordercolor|"
        r"fillcolor|(?<![a-z])color)\s*[:=]",
        re.I,
    )
    _SERIES_PROPS = frozenset(
        {
            "backgroundcolor",
            "bordercolor",
            "pointbackgroundcolor",
            "pointbordercolor",
            "fillcolor",
        }
    )

    def _series_context(start: int) -> bool:
        ctx = src[max(0, start - 72) : start]
        matches = list(_PROP_NEAR.finditer(ctx))
        if not matches:
            return False
        return matches[-1].group(1).lower() in _SERIES_PROPS

    seen: list[str] = []
    series: set[str] = set()
    for m in _HEX.finditer(src):
        hx = f"#{m.group(1).upper()}"
        if _is_near_white(hx):
            continue
        if hx not in seen:
            seen.append(hx)
        if _series_context(m.start()):
            series.add(hx)
    if not seen:
        return html

    ranked = sorted(seen, key=lambda h: _lum(*_parse_hex(h)))
    mapping: dict[str, str] = {}
    if ranked:
        mapping[ranked[0]] = targets[0]
        accent_i = 1
        for hx in seen:
            if hx in mapping:
                continue
            if muted_u and _is_ink_grey(hx) and hx not in series:
                mapping[hx] = muted_u
                continue
            mapping[hx] = targets[min(accent_i, len(targets) - 1)]
            accent_i += 1

    def _sub_hex(m: re.Match[str]) -> str:
        key = f"#{m.group(1).upper()}"
        return mapping.get(key, m.group(0))

    out = _HEX.sub(_sub_hex, html)

    def _sub_rgba(m: re.Match[str]) -> str:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a = m.group(4)
        nearest = min(
            mapping.keys(),
            key=lambda h: abs(_lum(*_parse_hex(h)) - _lum(r, g, b)),
            default=None,
        )
        if nearest is None:
            return m.group(0)
        nr, ng, nb = _parse_hex(mapping[nearest])
        try:
            alpha = float(a) if a is not None else 1.0
        except ValueError:
            alpha = 1.0
        ctx = (m.string[max(0, m.start() - 20) : m.start()] or "").lower()
        if alpha < 0.35:
            if "grid" in ctx and grid.startswith("rgba"):
                return grid
            if area.startswith("rgba"):
                return area
        if a is None:
            return f"rgb({nr},{ng},{nb})"
        return f"rgba({nr},{ng},{nb},{a})"

    return _RGBA.sub(_sub_rgba, out)


_LABELS_ARR = re.compile(r"labels\s*:\s*\[([^\]]*)\]", re.I | re.S)
_DATASET_BLOCK = re.compile(r"datasets\s*:\s*\[", re.I)


def _count_chart_labels(html: str) -> int:
    m = _LABELS_ARR.search(html or "")
    if not m:
        return 0
    return len(re.findall(r"""['"]([^'"]*)['"]""", m.group(1)))


def _count_chart_datasets(html: str) -> int:
    """Rough dataset object count inside datasets:[...]."""
    m = _DATASET_BLOCK.search(html or "")
    if not m:
        return 0
    # Count `{label:` or `{data:` at dataset depth — prefer label markers.
    tail = (html or "")[m.end() :]
    # Stop at matching ] is hard; count dataset-like objects with data:
    return len(re.findall(r"\{\s*(?:label|data)\s*:", tail[:8000], flags=re.I))


def apply_pack_category_colors_to_html(
    html: str,
    series_hexes: list[str],
    *,
    chart_type: str | None = None,
) -> str:
    """Force per-category pack colors on single-series bar/donut (twin ≈ native).

    Multi-series (grouped/stacked) left unchanged — those color by series.
    """
    ctype = (chart_type or "").strip().lower()
    if ctype in ("line", "area", "kpi", "scatter", "grouped_bar", "stacked_bar"):
        return html
    targets = [
        f"#{h.lstrip('#').upper()}"
        for h in series_hexes
        if h and re.match(r"^#?[0-9A-Fa-f]{6}$", str(h).strip())
    ]
    if not targets or not (html or "").strip():
        return html
    n_ds = _count_chart_datasets(html)
    if n_ds > 1:
        return html
    n = _count_chart_labels(html)
    if n < 2:
        return html
    # Donut / bar / horizontal_bar / plain bar — one color per category.
    if ctype and ctype not in (
        "bar",
        "donut",
        "doughnut",
        "horizontal_bar",
        "",
    ):
        # Unknown single-series types: still expand (matches native point colors).
        pass
    colors = ",".join(f"'{targets[i % len(targets)]}'" for i in range(n))
    out = html or ""
    if re.search(r"backgroundColor\s*:\s*\[", out, flags=re.I):
        out = re.sub(
            r"backgroundColor\s*:\s*\[[^\]]*\]",
            f"backgroundColor:[{colors}]",
            out,
            count=1,
            flags=re.I,
        )
    else:
        out = re.sub(
            r"backgroundColor\s*:\s*'[^']+'",
            f"backgroundColor:[{colors}]",
            out,
            count=1,
            flags=re.I,
        )
        # Also handle "..." quotes
        if f"backgroundColor:[{colors}]" not in out.replace(" ", ""):
            out = re.sub(
                r'backgroundColor\s*:\s*"[^"]+"',
                f"backgroundColor:[{colors}]",
                out,
                count=1,
                flags=re.I,
            )
    # Drop conflicting single borderColor so Chart.js uses segment fills cleanly.
    if "backgroundColor:[" in out.replace(" ", ""):
        out = re.sub(r"borderWidth\s*:\s*\d+\s*,?", "", out, count=1, flags=re.I)
        out = re.sub(
            r"borderColor\s*:\s*'[^']+'\s*,?",
            "",
            out,
            count=1,
            flags=re.I,
        )
    return out


def apply_palette_to_html(html: str, palette_id: str) -> str:
    """Remap #hex / rgb(a) colors in chart HTML onto a named palette.

    Keeps alpha channels. ``auto`` leaves HTML unchanged. Data arrays are
    untouched because only color tokens are rewritten.
    """
    pid = normalize_palette_id(palette_id)
    if pid == "auto" or pid not in _PALETTES:
        return html
    p = _PALETTES[pid]
    targets: list[str] = [p["primary"], *list(p["accents"])]
    return apply_hex_series_to_html(
        html,
        targets,
        muted=str(p.get("muted") or "") or None,
        area=str(p.get("area") or ""),
        grid=str(p.get("grid") or ""),
    )


# Four chromatic presets from published datavis schemes (no purple/indigo).
# Sources: Okabe–Ito CUD · Paul Tol vibrant/bright · Tableau 10 categorical.
# mono kept as greyscale print option. Same-hue ladders rejected (Mary-blue mush).
_PALETTES: dict[str, dict[str, Any]] = {
    # Tableau 10 categorical (soft multi-hue) — skip pink/purple #B07AA1 / #FF9DA7.
    "editorial": {
        "label": "Editorial",
        "primary": "#4E79A7",
        "accents": ["#F28E2B", "#76B7B2", "#E15759", "#59A14F", "#EDC948", "#9C755F"],
        "muted": "#8A9AAB",
        "area": "rgba(118,183,178,0.34)",
        "grid": "rgba(78,121,167,0.12)",
    },
    # Okabe–Ito (Nature Methods / CUD) — skip reddish-purple #CC79A7.
    "ocean": {
        "label": "Ocean",
        "primary": "#0072B2",
        "accents": ["#56B4E9", "#009E73", "#E69F00", "#D55E00", "#F0E442"],
        "muted": "#7A90A8",
        "area": "rgba(86,180,233,0.34)",
        "grid": "rgba(0,114,178,0.12)",
    },
    # Paul Tol bright (warm-first) — skip purple #AA3377.
    "sunset": {
        "label": "Sunset",
        "primary": "#EE6677",
        "accents": ["#CCBB44", "#4477AA", "#228833", "#66CCEE", "#BBBBBB"],
        "muted": "#A09090",
        "area": "rgba(238,102,119,0.34)",
        "grid": "rgba(68,119,170,0.12)",
    },
    "mono": {
        "label": "Mono",
        "primary": "#1A1F28",
        "accents": ["#2C3340", "#5C6570", "#8B7355", "#A8B0BA", "#6B7280"],
        "muted": "#9CA3AF",
        "area": "rgba(26,31,40,0.18)",
        "grid": "rgba(26,31,40,0.09)",
    },
    # Paul Tol vibrant (TensorBoard-family) — skip magenta #EE3377; Liber ink = dark teal.
    "atelier": {
        "label": "Atelier",
        "primary": "#004D47",
        "accents": ["#0077BB", "#EE7733", "#009988", "#CC3311", "#33BBEE"],
        "muted": "#5A706C",
        "area": "rgba(0,153,136,0.34)",
        "grid": "rgba(0,77,71,0.12)",
    },
}


def normalize_palette_id(raw: str | None) -> str:
    key = (raw or "editorial").strip().lower()
    if key in PALETTE_IDS:
        return key
    return "editorial"


def palette_color_list(palette_id: str | None) -> list[str]:
    """Named palette as ink then accents. Empty when the id is not a real palette."""
    pid = normalize_palette_id(palette_id)
    if pid == "auto" or pid not in _PALETTES:
        return []
    p = _PALETTES[pid]
    return [str(p["primary"]), *[str(a) for a in p["accents"]]]


def palette_css_vars(palette_id: str) -> str:
    """CSS custom properties for frame KPI / card chrome (inject into fragment)."""
    pid = normalize_palette_id(palette_id)
    if pid == "auto" or pid not in _PALETTES:
        return ""
    p = _PALETTES[pid]
    primary = str(p["primary"])
    accents = list(p["accents"])
    value = accents[0] if accents else primary
    label = str(p.get("muted") or primary)
    ink = primary
    muted = str(p.get("muted") or "#94A3B8")
    return (
        f"--chart-ink:{ink};--chart-accent:{value};--chart-muted:{muted};"
        f"--kpi-value:{value};--kpi-label:{label};--kpi-ink:{ink};"
    )


def apply_kpi_palette_vars(html: str, palette_id: str) -> str:
    """Inject palette CSS vars so host ``.kpi`` / cards pick soft ink (not fixed orange)."""
    pid = normalize_palette_id(palette_id)
    vars_decl = palette_css_vars(pid)
    if not vars_decl or not (html or "").strip():
        return html
    # Replace prior inject; keep one block.
    cleaned = re.sub(
        r'<style\s+id=["\']case3-palette["\'][^>]*>.*?</style>\s*',
        "",
        html,
        count=1,
        flags=re.I | re.S,
    )
    block = f'<style id="case3-palette">#mount{{{vars_decl}}}</style>'
    return block + cleaned


# Intent line: "- палитра графиков: Atelier (atelier) — …" or "… AUTO — …"
_PALETTE_INTENT_RE = re.compile(
    r"палитра графиков:\s*(?:AUTO\b|[^(]*\((\w+)\))",
    re.I,
)


# Same-family ramps for a named hue. Presets stay multi-hue; a named color does not.
_HUE_RAMPS: dict[str, tuple[str, ...]] = {
    "green": ("#146C36", "#1F8A45", "#2EAA58", "#5CC47A", "#0E4F28", "#8ED9A4"),
    "blue": ("#0B4F8C", "#1D6FBF", "#3D8FD4", "#7EB6E6", "#08386A", "#B7D7F2"),
    "orange": ("#C45C12", "#E07A2F", "#F0A05A", "#F6C48A", "#8C3E0A", "#F8D7B0"),
    "red": ("#B42318", "#D6453D", "#E56B63", "#F0A09A", "#7A1610", "#F6C9C6"),
    "yellow": ("#A67C00", "#C99A12", "#E0B84A", "#F0D48A", "#7A5A00", "#F6E7B8"),
    "gray": ("#2C3340", "#4B5563", "#6B7280", "#9CA3AF", "#1A1F28", "#D1D5DB"),
}
_HUE_WORDS: tuple[tuple[str, str], ...] = (
    ("green", r"зел[её]н"),
    ("orange", r"оранж"),
    ("yellow", r"ж[её]лт"),
    ("red", r"(?<![а-яё])красн"),
    ("blue", r"голуб|\bсин(?:ий|яя|ее|ие|им|его|юю|еньк)"),
    ("gray", r"сер(?:ый|ая|ое|ые|ого|ым)|ч[её]рн(?:ый|ая|ое|ые|ого|ым)"),
)
HUE_SAY = {
    "green": "зелёный",
    "blue": "синий",
    "orange": "оранжевый",
    "red": "красный",
    "yellow": "жёлтый",
    "gray": "серый",
}


def hue_from_text(text: str | None) -> str:
    """Named hue in the user line. Empty when they named a preset, not a color."""
    raw = (text or "").replace("ё", "е").replace("Ё", "Е")
    if re.search(r"editorial|ocean|sunset|\bmono\b|atelier|закат|океан|редакц|ателье|монохром", raw, re.I):
        return ""
    for key, pattern in _HUE_WORDS:
        if re.search(pattern, raw, re.I):
            return key
    return ""


def hue_prompt_line(text: str | None) -> str:
    """One instruction for the chart model. Empty when the line names no hue."""
    hue = hue_from_text(text)
    ramp = _HUE_RAMPS.get(hue or "")
    if not hue or not ramp:
        return ""
    hexes = ", ".join(ramp)
    return (
        f"ЦВЕТ: пользователь просит {HUE_SAY[hue]}. "
        f"В каждом dataset задай backgroundColor массивом этих hex по числу категорий: {hexes}. "
        "Не используй синий цвет Chart.js по умолчанию. "
        "Если есть текущий график и просят только цвет — подписи, числа и type не меняй."
    )


def paint_hue_on_html(html: str, hue: str) -> str:
    """Force a named hue onto Chart.js series. Injects color when the model left the default."""
    ramp = _HUE_RAMPS.get((hue or "").strip().lower())
    if not ramp or not (html or "").strip():
        return html
    n = _count_chart_labels(html) or 1
    colors = ",".join(f"'{ramp[i % len(ramp)]}'" for i in range(max(n, 1)))
    ink = ramp[0]
    out = html
    if re.search(r"backgroundColor\s*:\s*\[", out, flags=re.I):
        out = re.sub(
            r"backgroundColor\s*:\s*\[[^\]]*\]",
            f"backgroundColor:[{colors}]",
            out,
            count=1,
            flags=re.I,
        )
    elif re.search(r"backgroundColor\s*:", out, flags=re.I):
        out = re.sub(
            r"backgroundColor\s*:\s*(?:'[^']*'|\"[^\"]*\"|rgba?\([^)]*\))",
            f"backgroundColor:[{colors}]",
            out,
            count=1,
            flags=re.I,
        )
    else:
        out = re.sub(
            r"(datasets\s*:\s*\[\s*\{)",
            rf"\1backgroundColor:[{colors}],",
            out,
            count=1,
            flags=re.I,
        )
    if re.search(r"borderColor\s*:", out, flags=re.I):
        out = re.sub(
            r"borderColor\s*:\s*(?:'[^']*'|\"[^\"]*\"|\[[^\]]*\]|rgba?\([^)]*\))",
            f"borderColor:'{ink}'",
            out,
            count=1,
            flags=re.I,
        )
    elif "backgroundColor:[" in out:
        out = out.replace("backgroundColor:[", f"borderColor:'{ink}',backgroundColor:[", 1)
    return out


def palette_from_intent(intent: str) -> str:
    """Parse UI palette id from Intent block; ``auto`` when missing/AUTO."""
    m = _PALETTE_INTENT_RE.search(intent or "")
    if not m or m.group(1) is None:
        return "auto"
    return normalize_palette_id(m.group(1))


def palette_public() -> list[dict[str, Any]]:
    """Catalog for /api/health and the React sidebar."""
    out: list[dict[str, Any]] = [
        {
            "id": "auto",
            "label": "Auto",
            "swatches": ["#2E4208", "#F07A3A", "#0B4F8C", "#FF8C2A"],
        }
    ]
    for pid in ("editorial", "ocean", "sunset", "mono", "atelier"):
        p = _PALETTES[pid]
        out.append(
            {
                "id": pid,
                "label": p["label"],
                "swatches": [p["primary"], *p["accents"][:3]],
            }
        )
    return out


def palette_fallback_table() -> str:
    """D10: one markdown/prompt table sourced from ``_PALETTES`` (not hand-copied hex)."""
    lines = [
        "**Fallback palette hex** (Intent AUTO or unnamed → pick one; print ≈ Liber):",
        "",
    ]
    for pid in ("editorial", "ocean", "sunset", "mono", "atelier"):
        p = _PALETTES[pid]
        accents = "/".join(str(a) for a in p["accents"][:4])
        lines.append(
            f"- **{pid}** ({p['label']}): ink `{p['primary']}`; accents `{accents}`"
        )
    return "\n".join(lines)


def intent_palette_lines(palette_id: str, style_notes: str = "") -> list[str]:
    """Lines appended to UI Intent for chart colors / look."""
    pid = normalize_palette_id(palette_id)
    lines: list[str] = []
    if pid == "auto":
        lines.append(
            "- палитра графиков: AUTO — выбери одну из editorial/ocean/sunset/mono/atelier "
            "на весь документ; не смешивай пресеты и не используй фиолетовый нейрослоп"
        )
    else:
        p = _PALETTES[pid]
        accents = "/".join(p["accents"])
        lines.append(
            f"- палитра графиков: {p['label']} ({pid}) — ink {p['primary']}, "
            f"accents {accents}, area {p['area']}, grid {p['grid']}; "
            "в charts[].html используй ТОЛЬКО эти hex/rgba"
        )
    notes = (style_notes or "").strip()
    if notes:
        lines.append(
            f"- стиль графиков (нюансы UI): {notes} "
            "(легенда/сетка/толщина линий — по желанию; цвета — из палитры выше)"
        )
    return lines
