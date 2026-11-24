"""Donut / doughnut Chart.js HTML enhance + square canvas."""

from __future__ import annotations

import html as _html
import logging
import re
from typing import Any

log = logging.getLogger("case3.charts")

def _fmt_slice_num(n: float) -> str:
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    return f"{n:.1f}".rstrip("0").rstrip(".")

def _parse_donut_slices(
    html: str,
) -> list[tuple[str, float, str]] | None:
    """Pull labels / values / colors from a doughnut Chart.js fragment."""
    if not re.search(r"""type\s*:\s*['"]doughnut['"]""", html or "", flags=re.I):
        return None
    labels_m = re.search(r"labels\s*:\s*\[([^\]]*)\]", html or "")
    data_m = re.search(r"data\s*:\s*\[([^\]]*)\]", html or "")
    colors_m = re.search(r"backgroundColor\s*:\s*\[([^\]]*)\]", html or "", flags=re.I)
    if not labels_m or not data_m:
        return None
    labels = re.findall(r"""['"]([^'"]+)['"]""", labels_m.group(1))
    values: list[float] = []
    for raw_item in re.findall(r"'[^']*'|\"[^\"]*\"|[^,\s]+", data_m.group(1)):
        cleaned = re.sub(r"[\s\u00a0\u202f'\"]+", "", raw_item).replace(",", ".")
        if not cleaned or cleaned.lower() == "null":
            continue
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    colors: list[str] = []
    if colors_m:
        colors = re.findall(
            r"""['"](#[0-9a-fA-F]{3,8}|rgba?\([^)'"]+\))['"]""",
            colors_m.group(1),
            flags=re.I,
        )
    n = min(len(labels), len(values))
    if n < 2:
        return None
    while len(colors) < n:
        colors.append("#6A7160")
    return list(zip(labels[:n], values[:n], colors[:n]))

def _unwrap_donut_layout(html: str) -> str:
    """Strip a prior enhance wrap so palette/LLM edits can rebuild layout."""
    src = html or ""
    if not re.search(r"donut-layout", src, flags=re.I):
        return src
    # Nested .pct/.lbl — non-greedy </div> would stop at the first child.
    src = re.sub(
        r'<div\s+class=["\']donut-center["\']\s*>\s*'
        r'<div\s+class=["\']pct["\']\s*>[\s\S]*?</div>\s*'
        r'<div\s+class=["\']lbl["\']\s*>[\s\S]*?</div>\s*'
        r"</div>",
        "",
        src,
        flags=re.I,
    )
    # Orphan leftovers from older broken unwraps
    src = re.sub(
        r'<div\s+class=["\']lbl["\']\s*>[\s\S]*?</div>\s*',
        "",
        src,
        flags=re.I,
    )
    src = re.sub(
        r'<ul\s+class=["\']valued-legend["\'][\s\S]*?</ul>',
        "",
        src,
        flags=re.I,
    )
    src = re.sub(r"</?div[^>]*\bdonut-viz\b[^>]*>", "", src, flags=re.I)
    src = re.sub(r"</?div[^>]*\bdonut-layout\b[^>]*>", "", src, flags=re.I)
    # Only unwrap outer chart-card when it was the donut shell (avoid nested cards).
    src = re.sub(
        r'<div\s+class=["\'][^"\']*\bchart-card\b[^"\']*["\']\s*>',
        "",
        src,
        count=1,
        flags=re.I,
    )
    src = re.sub(r"</div>\s*$", "", src.strip(), count=1)
    return src.strip()

def _clean_slice_label(label: str) -> str:
    """Strip embedded % / absolutes so valued-legend columns stay single-purpose."""
    s = (label or "").strip()
    if not s:
        return s
    # "Retail 42% (210)" / "Food (140)" / "Pharma — 18%"
    s = re.sub(r"\s*[\(（]\s*[\d\s.,]+\s*[\)）]\s*$", "", s)
    s = re.sub(r"\s*[-–—·|:]\s*\d+(?:[.,]\d+)?\s*%\s*$", "", s)
    s = re.sub(r"\s+\d+(?:[.,]\d+)?\s*%\s*$", "", s)
    s = re.sub(r"\s+\d+(?:[.,]\d+)?\s*%", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ·—-|:")
    return s or (label or "").strip()

def _rewrite_chart_labels_array(html: str, labels: list[str]) -> str:
    if not labels:
        return html or ""
    quoted = ",".join("'" + lab.replace("\\", "\\\\").replace("'", "\\'") + "'" for lab in labels)
    return re.sub(
        r"labels\s*:\s*\[[^\]]*\]",
        f"labels:[{quoted}]",
        html or "",
        count=1,
        flags=re.I,
    )


def _rewrite_chart_data_array(html: str, values: list[float]) -> str:
    """Emit plain numeric JS values so Chart.js draws slices from '18 400,5' too."""
    if not values:
        return html or ""
    nums = ",".join(_fmt_slice_num(v) for v in values)
    return re.sub(
        r"\bdata\s*:\s*\[[^\]]*\]",
        f"data:[{nums}]",
        html or "",
        count=1,
        flags=re.I,
    )

def _fmt_slice_pct(val: float, total: float) -> str:
    """A positive slice never prints as 0%. Tiny shares keep one decimal."""
    raw = 100.0 * val / total if total else 0.0
    whole = int(round(raw))
    if val > 0 and whole == 0:
        tenth = round(raw, 1)
        if tenth <= 0:
            tenth = 0.1
        return f"{tenth:.1f}".replace(".", ",") + "%"
    return f"{whole}%"


def enhance_donut_html(html: str) -> str:
    """Wrap doughnut fragment with center % + valued HTML legend when parseable.

    No Chart.js plugins — CSS overlay + list. Rebuilds after unwrap so palette /
    LLM edits keep Mary layout. If JS is too exotic to parse, returns html
    unchanged (prompt recipes still emit the structure).
    """
    src = _unwrap_donut_layout(html or "")
    if not src.strip():
        return src
    slices = _parse_donut_slices(src)
    if not slices:
        return src

    clean_slices = [
        (_clean_slice_label(lab), val, color) for lab, val, color in slices
    ]
    src = _rewrite_chart_labels_array(src, [lab for lab, _, _ in clean_slices])
    src = _rewrite_chart_data_array(src, [val for _, val, _ in clean_slices])

    total = sum(v for _, v, _ in clean_slices) or 1.0
    focus_i = max(range(len(clean_slices)), key=lambda i: clean_slices[i][1])
    focus_label, focus_val, _ = clean_slices[focus_i]
    focus_pct = int(round(100.0 * focus_val / total))

    rows: list[str] = []
    for label, val, color in clean_slices:
        pct = _fmt_slice_pct(val, total)
        safe_label = _html.escape(label, quote=True)
        rows.append(
            '<li class="valued-legend__row">'
            f'<span class="valued-legend__swatch" style="background:{color}"></span>'
            f'<span class="valued-legend__label">{safe_label}</span>'
            f'<span class="valued-legend__pct">{pct}</span>'
            f'<span class="valued-legend__abs">{_fmt_slice_num(val)}</span>'
            "</li>"
        )
    legend_class = "valued-legend is-dense" if len(clean_slices) >= 8 else "valued-legend"
    legend = f'<ul class="{legend_class}">' + "".join(rows) + "</ul>"
    safe_focus = _html.escape(focus_label, quote=True)
    center = (
        '<div class="donut-center">'
        f'<div class="pct">{focus_pct}%</div>'
        f'<div class="lbl">{safe_focus}</div>'
        "</div>"
    )

    # Canvas + scripts only — ignore leftover unwrap junk around them.
    script_m = re.search(r"(<script\b)", src, flags=re.I)
    tail = src[script_m.start() :] if script_m else ""
    canvas_m = re.search(
        r"<canvas\b[^>]*>\s*</canvas>|<canvas\b[^>]*/?>",
        src,
        flags=re.I,
    )
    if not canvas_m:
        return html or src
    head = canvas_m.group(0)

    # Prefer HTML legend over Chart.js legend to avoid double keys.
    if re.search(r"legend\s*:\s*\{[^}]*display\s*:", tail):
        # Already has display — force false without duplicating the key.
        tail = re.sub(
            r"(legend\s*:\s*\{[^}]*?display\s*:\s*)[^,}\s]+",
            r"\1false",
            tail,
            count=1,
        )
    elif re.search(r"legend\s*:\s*\{", tail):
        tail = re.sub(
            r"legend\s*:\s*\{",
            "legend:{display:false,",
            tail,
            count=1,
        )
    else:
        tail = re.sub(
            r"plugins\s*:\s*\{",
            "plugins:{legend:{display:false},",
            tail,
            count=1,
        )

    # Print frame uses responsive:false — canvas width/height attrs ARE the
    # bitmap. LLM often emits 1100×560 → oval donut + empty right gutter.
    head_sq = _force_square_canvas(head.strip(), size=520)

    wrapped = (
        '<div class="chart-card donut-layout">'
        f'<div class="donut-viz">{center}{head_sq}</div>'
        f"{legend}{tail}"
        "</div>"
    )
    return wrapped

def _force_square_canvas(html: str, *, size: int = 520) -> str:
    """Set first <canvas> to a square bitmap (print Chart.js defaults)."""

    def _repl(m: re.Match[str]) -> str:
        attrs = m.group(1) or ""
        attrs = re.sub(r"\s*width\s*=\s*(\"[^\"]*\"|'[^']*'|\S+)", "", attrs, flags=re.I)
        attrs = re.sub(r"\s*height\s*=\s*(\"[^\"]*\"|'[^']*'|\S+)", "", attrs, flags=re.I)
        attrs = attrs.rstrip()
        return f'<canvas{attrs} width="{size}" height="{size}">'

    return re.sub(r"<canvas(\s[^>]*)?>", _repl, html or "", count=1, flags=re.I)
