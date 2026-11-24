"""Harden Chart.js HTML (fills, gaps, legend, canvas)."""

from __future__ import annotations

import logging
import re
from typing import Any

from case3.chart_style import normalize_palette_id

log = logging.getLogger("case3.charts")

_JS_TYPE = {
    "bar": "bar",
    "grouped_bar": "bar",
    "stacked_bar": "bar",
    "line": "line",
    "horizontal_bar": "bar",
    "donut": "doughnut",
    "area": "line",
    "scatter": "scatter",
    "kpi": "kpi",
}

_SCATTER_RADIUS = 10
_SCATTER_HOVER = 14
_MAX_CANVAS_H = 560  # D7: tall canvases waste A4 vertical space

def _is_kpi_html(html: str) -> bool:
    return bool(re.search(r"""class\s*=\s*['"]kpi['"]""", html or "", flags=re.I))

def html_matches_type(html: str, want: str) -> bool:
    """True when fragment already looks like the catalog type."""
    h = html or ""
    if want == "kpi":
        return _is_kpi_html(h)
    if want == "donut":
        return bool(re.search(r"""type\s*:\s*['"]doughnut['"]""", h, flags=re.I))
    if want == "scatter":
        return bool(re.search(r"""type\s*:\s*['"]scatter['"]""", h, flags=re.I))
    if want == "line":
        # area is also type:line — require no fill:true for plain line
        if not re.search(r"""type\s*:\s*['"]line['"]""", h, flags=re.I):
            return False
        return not re.search(r"""fill\s*:\s*true""", h, flags=re.I)
    if want == "area":
        return bool(re.search(r"""type\s*:\s*['"]line['"]""", h, flags=re.I)) and bool(
            re.search(r"""fill\s*:\s*true""", h, flags=re.I)
        )
    if want == "horizontal_bar":
        return bool(re.search(r"""type\s*:\s*['"]bar['"]""", h, flags=re.I)) and (
            "indexAxis" in h
        )
    if want == "stacked_bar":
        return bool(re.search(r"""type\s*:\s*['"]bar['"]""", h, flags=re.I)) and (
            "stacked" in h
        )
    if want in {"bar", "grouped_bar"}:
        return bool(re.search(r"""type\s*:\s*['"]bar['"]""", h, flags=re.I))
    return True

def _skip_js_comment(text: str, i: int) -> int | None:
    """If ``text[i:]`` starts a JS ``//`` or ``/* ... */`` comment, return index after it."""
    if text.startswith("//", i):
        nl = text.find("\n", i + 2)
        return len(text) if nl < 0 else nl + 1
    if text.startswith("/*", i):
        end = text.find("*/", i + 2)
        return len(text) if end < 0 else end + 2
    return None


def _bracket_span(text: str, open_idx: int, open_ch: str, close_ch: str) -> tuple[int, int] | None:
    """Return [start, end) of balanced open/close starting at open_idx."""
    if open_idx < 0 or open_idx >= len(text) or text[open_idx] != open_ch:
        return None
    depth = 0
    i = open_idx
    n = len(text)
    in_str: str | None = None
    escape = False
    while i < n:
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        after_comment = _skip_js_comment(text, i)
        if after_comment is not None:
            i = after_comment
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            i += 1
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return open_idx, i + 1
        i += 1
    return None


def _numeric_data_arrays(html: str) -> list[list[float]]:
    """Collect scalar ``data:[…]`` arrays (skip scatter ``{x,y}`` points)."""
    arrays: list[list[float]] = []
    for m in re.finditer(r"data\s*:\s*\[", html or "", flags=re.I):
        span = _bracket_span(html, m.end() - 1, chr(91), chr(93))
        if not span:
            continue
        raw = html[span[0] + 1 : span[1] - 1]
        if re.search(r"\{\s*x\s*:", raw):
            continue
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", raw)]
        if nums:
            arrays.append(nums)
    return arrays


def _sum_series(arrays: list[list[float]]) -> list[float]:
    if not arrays:
        return []
    if len(arrays) == 1:
        return list(arrays[0])
    n = max(len(a) for a in arrays)
    out: list[float] = []
    for i in range(n):
        out.append(sum(a[i] if i < len(a) else 0.0 for a in arrays))
    return out


def _fmt_num(n: float) -> str:
    """Plain digits. ``.4g`` turned 105865.2 into ``1.059e+05``."""
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    return f"{n:.4f}".rstrip("0").rstrip(".")


_DONUT_FALLBACK_COLORS = (
    "#1A4A4B",
    "#5A6E28",
    "#8B5A2B",
    "#3D5A80",
    "#A63D2F",
    "#6A7160",
    "#2E4208",
    "#7A9A28",
)


def _scatter_points_xy(html: str) -> list[tuple[str, str]]:
    """Extract ``{x,y}`` pairs as strings."""
    return re.findall(
        r"\{\s*x\s*:\s*(-?[\d.]+)\s*,\s*y\s*:\s*(-?[\d.]+)\s*\}",
        html or "",
        flags=re.I,
    )


def _scatter_to_scalar_series(html: str) -> str:
    """Turn scatter ``data:[{x,y},…]`` into categorical labels + scalar data."""
    src = html or ""
    pts = _scatter_points_xy(src)
    if not pts:
        return src
    labels = ",".join(f"'{x}'" for x, _y in pts)
    values = ",".join(y for _x, y in pts)
    colors = ",".join(
        f"'{_DONUT_FALLBACK_COLORS[i % len(_DONUT_FALLBACK_COLORS)]}'"
        for i in range(len(pts))
    )
    single = (
        "{label:'Значение',data:["
        + values
        + "],backgroundColor:["
        + colors
        + "],borderColor:'#1A4A4B',borderWidth:2,pointRadius:0}"
    )
    out = src
    ds_m = re.search(r"datasets\s*:\s*\[", out, flags=re.I)
    if ds_m:
        span = _bracket_span(out, ds_m.end() - 1, chr(91), chr(93))
        if span:
            out = out[: span[0]] + "[" + single + "]" + out[span[1] :]
    # Ensure labels exist for bar/line/donut.
    if re.search(r"labels\s*:\s*\[", out, flags=re.I):
        out = re.sub(
            r"labels\s*:\s*\[[^\]]*\]",
            f"labels:[{labels}]",
            out,
            count=1,
            flags=re.I,
        )
    else:
        out = re.sub(
            r"data\s*:\s*\{",
            f"data:{{labels:[{labels}],",
            out,
            count=1,
            flags=re.I,
        )
    return out


def _parse_kpi_value_label(html: str) -> tuple[str, str]:
    vm = re.search(
        r"""class\s*=\s*['"]value['"]\s*>\s*([^<]+)\s*<""",
        html or "",
        flags=re.I,
    )
    lm = re.search(
        r"""class\s*=\s*['"]label['"]\s*>\s*([^<]+)\s*<""",
        html or "",
        flags=re.I,
    )
    value = (vm.group(1) if vm else "0").strip()
    label = (lm.group(1) if lm else "Показатель").strip() or "Показатель"
    return value, label


def chart_html_from_kpi(html: str, want: str) -> str:
    """Build a minimal Chart.js fragment from a KPI card (leaving KPI type)."""
    raw_val, label = _parse_kpi_value_label(html)
    nums = re.findall(r"-?\d+(?:[.,]\d+)?", raw_val.replace(" ", ""))
    num = (nums[0].replace(",", ".") if nums else "0")
    safe_lab = label.replace("\\", "").replace("'", "")
    color = _DONUT_FALLBACK_COLORS[0]
    if want == "scatter":
        body = (
            f"datasets:[{{label:'{safe_lab}',data:[{{x:1,y:{num}}}],"
            f"backgroundColor:'{color}',pointRadius:10,pointHoverRadius:14}}]"
        )
        opts = "scales:{x:{},y:{}},animation:false,responsive:false,maintainAspectRatio:false"
        js_type = "scatter"
    elif want == "donut":
        # One slice: the KPI number. A second slice would be a share that is not in the data.
        try:
            v = abs(float(num))
        except ValueError:
            v = 0.0
        body = (
            f"labels:['{safe_lab}'],datasets:[{{label:'{safe_lab}',"
            f"data:[{_fmt_num(v)}],"
            f"backgroundColor:['{color}'],borderWidth:0}}]"
        )
        opts = (
            "cutout:'58%',plugins:{legend:{display:false}},"
            "animation:false,responsive:false,maintainAspectRatio:false"
        )
        js_type = "doughnut"
    else:
        fill = ",fill:true" if want == "area" else ""
        body = (
            f"labels:['{safe_lab}'],datasets:[{{label:'{safe_lab}',data:[{num}],"
            f"backgroundColor:['{color}'],borderColor:'{color}',borderWidth:2{fill}}}]"
        )
        opts = "scales:{x:{},y:{}},animation:false,responsive:false,maintainAspectRatio:false"
        if want == "horizontal_bar":
            opts = "indexAxis:'y'," + opts
        if want == "stacked_bar":
            opts = "scales:{x:{stacked:true},y:{stacked:true}}," + opts.replace(
                "scales:{x:{},y:{}},", ""
            )
        js_type = "line" if want in {"line", "area"} else "bar"
    return (
        '<canvas id="c1" width="1100" height="560"></canvas>'
        "<script>new Chart(document.getElementById('c1'),"
        f"{{type:'{js_type}',data:{{{body}}},options:{{{opts}}}}});"
        "window.__CASE3_CHART_READY=true;</script>"
    )


def _coerce_html_to_donut(html: str) -> str:
    """Force a single-ring doughnut: collapse multi-series (no concentric «мишень»).

    Grouped/stacked/line → one dataset with per-category sums (or the sole series).
    Strips cartesian scales / indexAxis that confuse doughnut layout.
    """
    src = _scatter_to_scalar_series(html or "")
    out = re.sub(
        r"""type\s*:\s*['"](?:bar|line|doughnut|pie|scatter|radar)['"]""",
        "type:'doughnut'",
        src,
        count=1,
        flags=re.I,
    )
    arrays = _numeric_data_arrays(out)
    values = _sum_series(arrays)
    if not values:
        return out

    # Prefer existing per-category colors from the first backgroundColor array.
    colors: list[str] = []
    bg_m = re.search(r"backgroundColor\s*:\s*\[", out, flags=re.I)
    if bg_m:
        span = _bracket_span(out, bg_m.end() - 1, chr(91), chr(93))
        if span:
            colors = re.findall(
                r"""['"](#[0-9a-fA-F]{3,8}|rgba?\([^)'"]+\))['"]""",
                out[span[0] : span[1]],
                flags=re.I,
            )
    while len(colors) < len(values):
        colors.append(_DONUT_FALLBACK_COLORS[len(colors) % len(_DONUT_FALLBACK_COLORS)])
    colors = colors[: len(values)]

    data_js = ",".join(_fmt_num(v) for v in values)
    colors_js = ",".join(f"'{c}'" for c in colors)
    single = (
        "{label:'Доля',data:["
        + data_js
        + "],backgroundColor:["
        + colors_js
        + "],borderWidth:0}"
    )

    ds_m = re.search(r"datasets\s*:\s*\[", out, flags=re.I)
    if ds_m:
        span = _bracket_span(out, ds_m.end() - 1, chr(91), chr(93))
        if span:
            out = out[: span[0]] + "[" + single + "]" + out[span[1] :]

    # Doughnut ignores cartesian axes — drop leftover bar/line chrome.
    out = re.sub(r"indexAxis\s*:\s*['\"][^'\"]*['\"]\s*,?", "", out, flags=re.I)
    # Chart.js v4: top-level scales.display is ignored — kill x/y (and stacked).
    if re.search(r"scales\s*:\s*\{", out, flags=re.I):
        out = re.sub(
            r"scales\s*:\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
            "scales:{x:{display:false},y:{display:false}}",
            out,
            count=1,
            flags=re.I,
        )
    else:
        out = re.sub(
            r"options\s*:\s*\{",
            "options:{scales:{x:{display:false},y:{display:false}},",
            out,
            count=1,
            flags=re.I,
        )
    # Soften fill/tension left from line/area
    out = re.sub(r"""fill\s*:\s*true\s*,?""", "", out, flags=re.I)
    out = re.sub(r"""tension\s*:\s*[\d.]+\s*,?""", "", out, flags=re.I)
    if "cutout" not in out.lower():
        out = re.sub(
            r"options\s*:\s*\{",
            "options:{cutout:'58%',",
            out,
            count=1,
            flags=re.I,
        )
    return out


def _rewrite_js_type(html: str, preferred: str) -> str:
    if preferred == "donut":
        return _coerce_html_to_donut(html or "")

    src = html or ""
    # Scatter points are not valid bar/line/area data — flatten first.
    if preferred != "scatter" and _scatter_points_xy(src):
        src = _scatter_to_scalar_series(src)

    js = _JS_TYPE.get(preferred, preferred)
    out = re.sub(
        r"""type\s*:\s*['"](?:bar|line|doughnut|pie|scatter|radar)['"]""",
        f"type:'{js}'",
        src,
        count=1,
        flags=re.I,
    )
    if preferred == "horizontal_bar":
        if "indexAxis" not in out:
            out = re.sub(
                r"options\s*:\s*\{",
                "options:{indexAxis:'y',",
                out,
                count=1,
            )
    else:
        # Leaving horizontal_bar (or leftover indexAxis) → vertical cartesian.
        out = re.sub(r"indexAxis\s*:\s*['\"][^'\"]*['\"]\s*,?", "", out, flags=re.I)

    if preferred == "area":
        if re.search(r"fill\s*:", out) is None:
            out = re.sub(
                r"(datasets\s*:\s*\[\s*\{)",
                r"\1fill:true,",
                out,
                count=1,
            )
        else:
            out = re.sub(r"""fill\s*:\s*false""", "fill:true", out, count=1, flags=re.I)
    elif preferred == "line":
        # drop fill:true if model emitted an area-like line
        out = re.sub(r"""fill\s*:\s*true\s*,?""", "", out, count=1, flags=re.I)
    elif preferred == "stacked_bar":
        if "stacked" not in out:
            out = re.sub(
                r"options\s*:\s*\{",
                "options:{scales:{x:{stacked:true},y:{stacked:true}},",
                out,
                count=1,
            )
    if preferred != "stacked_bar":
        # Drop stacked flags when leaving stacked_bar → plain bar/line/…
        out = re.sub(r"stacked\s*:\s*true\s*,?", "", out, flags=re.I)
    if preferred == "scatter":
        out = _scalar_series_to_scatter_points(out)
        out = _ensure_scatter_point_size(out)
    # Restore visible axes when leaving donut (display:false leftovers).
    if preferred != "donut":
        out = re.sub(
            r"scales\s*:\s*\{\s*x\s*:\s*\{\s*display\s*:\s*false\s*\}\s*,\s*"
            r"y\s*:\s*\{\s*display\s*:\s*false\s*\}\s*\}",
            "scales:{x:{},y:{}}",
            out,
            count=1,
            flags=re.I,
        )
        out = re.sub(r"cutout\s*:\s*['\"][^'\"]*['\"]\s*,?", "", out, flags=re.I)
    return out

def _scatter_radius_for(html: str) -> tuple[int, int]:
    """A two-point cloud stays large. A dense cloud shrinks so points do not merge."""
    count = len(re.findall(r"\{\s*x\s*:", html or ""))
    if count >= 36:
        return 4, 7
    if count >= 16:
        return 6, 9
    return _SCATTER_RADIUS, _SCATTER_HOVER


def _relax_vertical_bar_labels(html: str) -> str:
    """Turn crowded category labels so a vertical bar chart stays readable."""
    out = html or ""
    if _count_labels(out) < 8 or "maxRotation" in out:
        return out
    tick_cfg = "ticks:{maxRotation:45,minRotation:35,autoSkip:true,font:{size:12}}"
    if re.search(r"\bscales\s*:\s*\{", out):
        if re.search(r"\bscales\s*:\s*\{[\s\S]*?\bx\s*:\s*\{", out):
            out = re.sub(
                r"(\bscales\s*:\s*\{[\s\S]*?\bx\s*:\s*\{)",
                rf"\1{tick_cfg},",
                out,
                count=1,
            )
        else:
            out = re.sub(
                r"(\bscales\s*:\s*\{)",
                rf"\1x:{{{tick_cfg}}},",
                out,
                count=1,
            )
    elif re.search(r"options\s*:\s*\{", out):
        out = re.sub(
            r"(options\s*:\s*\{)",
            rf"\1scales:{{x:{{{tick_cfg}}}}},",
            out,
            count=1,
        )
    if re.search(r"options\s*:\s*\{", out) and not re.search(r"\blayout\s*:\s*\{", out):
        out = re.sub(
            r"(options\s*:\s*\{)",
            r"\1layout:{padding:{bottom:20}},",
            out,
            count=1,
        )
    return out


def _ensure_scatter_point_size(html: str) -> str:
    """Scatter defaults are tiny (r≈3) — bump for print. A large cloud stays smaller."""
    radius, hover = _scatter_radius_for(html)
    out = html or ""

    def _set(key: str, target: int) -> None:
        nonlocal out
        out = re.sub(
            rf"({key}\s*:\s*)([\d.]+)",
            rf"\g<1>{target}",
            out,
            flags=re.I,
        )

    _set("pointRadius", radius)
    _set("pointHoverRadius", hover)
    if not re.search(r"pointRadius\s*:", out, flags=re.I):
        out = re.sub(
            r"(datasets\s*:\s*\[\s*\{)",
            rf"\1pointRadius:{radius},pointHoverRadius:{hover},borderWidth:2,",
            out,
            count=1,
            flags=re.I,
        )
    elif not re.search(r"pointHoverRadius\s*:", out, flags=re.I):
        out = re.sub(
            r"(pointRadius\s*:\s*[\d.]+)",
            rf"\1,pointHoverRadius:{hover}",
            out,
            count=1,
            flags=re.I,
        )
    return out

def _scalar_series_to_scatter_points(html: str) -> str:
    """Chart.js scatter needs ``data:[{x,y},…]`` — coerce categorical scalars."""

    def _points(m: re.Match[str]) -> str:
        raw = m.group(1)
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", raw)]
        if not nums:
            return m.group(0)
        # Already point objects?
        if re.search(r"\{\s*x\s*:", raw):
            return m.group(0)
        pts = ",".join(f"{{x:{i},y:{v}}}" for i, v in enumerate(nums))
        return f"data:[{pts}]"

    out = re.sub(
        r"data\s*:\s*\[([^\]]*)\]",
        _points,
        html or "",
        flags=re.I,
    )
    # Scatter ignores category labels; drop to avoid Chart.js axis confusion.
    out = re.sub(r"labels\s*:\s*\[[^\]]*\]\s*,?", "", out, count=1, flags=re.I)
    return out

def _kpi_html_from_chart(chart: dict[str, Any]) -> str:
    """Build Liber-style KPI block from caption / dataset numbers."""
    caption = str(chart.get("caption") or "").strip() or "Показатель"
    html = str(chart.get("html") or "")
    value = None
    m = re.search(
        r"(\d+(?:[.,]\d+)?)\s*%?",
        caption,
    )
    if m:
        value = m.group(1).replace(",", ".")
    if value is None:
        m = re.search(r"data\s*:\s*\[\s*([\d.]+)", html)
        if m:
            value = m.group(1)
    if value is None:
        # several KPI numbers in caption: "выручка 152, рост 12"
        nums = re.findall(r"\d+(?:[.,]\d+)?", caption)
        if nums:
            value = nums[0].replace(",", ".")
    if value is None:
        value = "—"
    label = re.sub(r"\s*\d+(?:[.,]\d+)?\s*%?\s*", " ", caption).strip(" —–-") or caption
    return (
        f'<div class="kpi"><div class="value">{value}</div>'
        f'<div class="label">{label}</div></div>'
        "<script>requestAnimationFrame(function(){"
        "requestAnimationFrame(function(){"
        "window.__CASE3_CHART_READY=true;});});</script>"
    )

def _count_labels(html: str) -> int:
    m = re.search(r"labels\s*:\s*\[([^\]]*)\]", html or "")
    if not m:
        return 4
    n = len(re.findall(r"""['"]([^'"]+)['"]""", m.group(1)))
    return max(1, n)

def _solidify_pale_bar_fill(html: str) -> str:
    """Turn ghostly rgba(…,0.18) bar fills into readable solid / mid-alpha ink."""

    def _bump(m: re.Match[str]) -> str:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            alpha = float(m.group(4))
        except ValueError:
            alpha = 1.0
        if alpha >= 0.45:
            return m.group(0)
        return f"backgroundColor:'#{r:02X}{g:02X}{b:02X}'"

    # Only touch scalar backgroundColor (not arrays of segment colors).
    # All datasets — grouped/stacked often ship N pale fills.
    return re.sub(
        r"backgroundColor\s*:\s*'rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([0-9.]+)\s*\)'",
        _bump,
        html or "",
        flags=re.I,
    )

def _clamp_canvas_height(html: str, *, max_h: int = _MAX_CANVAS_H) -> str:
    def _cap(m: re.Match[str]) -> str:
        try:
            h = int(m.group(2))
        except ValueError:
            return m.group(0)
        if h <= max_h:
            return m.group(0)
        return f'{m.group(1)}{max_h}{m.group(3)}'

    return re.sub(
        r'(<canvas\b[^>]*\bheight=")(\d+)(")',
        _cap,
        html or "",
        count=1,
        flags=re.I,
    )

def _ensure_stack_segment_gaps(html: str) -> str:
    """White borders between stacked segments so multi-hue series stay separable."""
    out = html or ""
    stacked = bool(
        re.search(r"stack\s*:", out, flags=re.I)
        or re.search(r"stacked\s*:\s*true", out, flags=re.I)
    )
    if not stacked:
        return out
    if re.search(r"borderColor\s*:\s*['\"]#fff", out, flags=re.I):
        return out

    def _inject_open(m: re.Match[str]) -> str:
        return m.group(1) + "borderWidth:1,borderColor:'#ffffff',"

    out = re.sub(r"(datasets\s*:\s*\[\s*\{)", _inject_open, out, count=1, flags=re.I)
    out = re.sub(
        r"(\}\s*,\s*\{)(?=[^\}]{0,200}stack\s*:)",
        r"\1borderWidth:1,borderColor:'#ffffff',",
        out,
        flags=re.I,
    )
    return out

def _count_datasets(html: str) -> int:
    """Count top-level objects in ``datasets:[...]`` (ignore scatter ``{x,y}`` points)."""
    m = re.search(r"datasets\s*:\s*\[", html or "", flags=re.I)
    if not m:
        return 0
    i = m.end()
    n = 0
    depth = 0  # brace depth relative to array contents
    in_str: str | None = None
    escape = False
    while i < len(html):
        ch = html[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            i += 1
            continue
        if ch == "]" and depth == 0:
            break
        if ch == "{":
            if depth == 0:
                n += 1
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == "[":
            # nested array (e.g. data:[{x,y},…]) — track via braces only;
            # entering `[` at depth>0 is inside a dataset object already.
            pass
        i += 1
    return n

def _set_plugin_bool(html: str, plugin: str, key: str, value: str) -> str:
    """Set ``plugins.{plugin}.{key}`` to ``value`` (true/false), creating nests if needed."""
    src = html or ""
    # plugin:{ ... key: X → replace
    pat_key = re.compile(
        rf"({plugin}\s*:\s*\{{[^}}]*?\b{key}\s*:\s*)([^,}}\s]+)",
        flags=re.I | re.S,
    )
    if pat_key.search(src):
        return pat_key.sub(rf"\g<1>{value}", src, count=1)
    # plugin:{ → inject key
    pat_obj = re.compile(rf"({plugin}\s*:\s*\{{)", flags=re.I)
    if pat_obj.search(src):
        return pat_obj.sub(rf"\1{key}:{value},", src, count=1)
    # plugins:{ → inject plugin:{key:value}
    if re.search(r"plugins\s*:\s*\{", src, flags=re.I):
        return re.sub(
            r"plugins\s*:\s*\{",
            f"plugins:{{{plugin}:{{{key}:{value}}},",
            src,
            count=1,
            flags=re.I,
        )
    # options:{ → inject plugins
    if re.search(r"options\s*:\s*\{", src, flags=re.I):
        return re.sub(
            r"options\s*:\s*\{",
            f"options:{{plugins:{{{plugin}:{{{key}:{value}}}}},",
            src,
            count=1,
            flags=re.I,
        )
    return src

def ensure_legend_and_tooltips(html: str, chart_type: str) -> str:
    """Turn on tooltips always; Chart.js legend for multi-series (HTML valued-legend wins for donut)."""
    want = (chart_type or "").strip()
    out = html or ""
    if not out or want == "kpi":
        return out

    out = _set_plugin_bool(out, "tooltip", "enabled", "true")

    has_valued = bool(re.search(r"valued-legend", out, flags=re.I))
    n_ds = _count_datasets(out)
    want_js_legend = False
    if want == "donut" or has_valued:
        want_js_legend = False
    elif want in {"grouped_bar", "stacked_bar", "line", "area"}:
        want_js_legend = True
    elif n_ds >= 2:
        want_js_legend = True

    if want_js_legend:
        out = _set_plugin_bool(out, "legend", "display", "true")
        # Prefer bottom so it doesn't steal plot height on print.
        if not re.search(r"legend\s*:\s*\{[^}]*position\s*:", out, flags=re.I | re.S):
            out = re.sub(
                r"(legend\s*:\s*\{)",
                r"\1position:'bottom',",
                out,
                count=1,
                flags=re.I,
            )
    else:
        # Frame defaults legend:true — hide for single-series / valued-legend / scatter.
        out = _set_plugin_bool(out, "legend", "display", "false")

    return out

def _ensure_line_point_size(html: str) -> str:
    """Line/area markers readable in print (default Chart.js r≈3 is tiny)."""
    out = html or ""

    def _bump(m: re.Match[str]) -> str:
        try:
            v = float(m.group(2))
        except ValueError:
            return f"{m.group(1)}5"
        if v >= 5:
            return m.group(0)
        return f"{m.group(1)}5"

    out = re.sub(r"(pointRadius\s*:\s*)([\d.]+)", _bump, out, flags=re.I)
    if not re.search(r"pointRadius\s*:", out, flags=re.I):
        out = re.sub(
            r"(datasets\s*:\s*\[\s*\{)",
            r"\1pointRadius:5,pointHoverRadius:8,",
            out,
            count=1,
            flags=re.I,
        )
    return out

def _colorize_hbar_categories(html: str, palette_id: str = "atelier") -> str:
    """Single-series hbar: one accent per category bar (not one flat wash)."""
    out = html or ""
    if _count_datasets(out) > 1:
        return out
    if re.search(r"backgroundColor\s*:\s*\[", out, flags=re.I):
        return out
    n = _count_labels(out)
    if n < 2:
        return out
    from case3.chart_style import _PALETTES

    pid = normalize_palette_id(palette_id)
    if pid == "auto" or pid not in _PALETTES:
        pid = "atelier"
    p = _PALETTES[pid]
    ladder = [str(p["primary"]).upper(), *[str(a).upper() for a in p["accents"]]]
    colors_list = [ladder[i % len(ladder)] for i in range(n)]
    colors = ",".join(f"'{c}'" for c in colors_list)
    out = re.sub(
        r"backgroundColor\s*:\s*'[^']+'",
        f"backgroundColor:[{colors}]",
        out,
        count=1,
        flags=re.I,
    )
    out = re.sub(r"borderWidth\s*:\s*\d+\s*,?", "", out, count=1, flags=re.I)
    out = re.sub(r"borderColor\s*:\s*'[^']+'\s*,?", "", out, count=1, flags=re.I)
    return out

def _find_top_level_key_brace(obj_text: str, key: str) -> int | None:
    """Inside a JS object body (without outer `{}`), return index of `{` for top-level `key: {`."""
    pat = re.compile(
        rf"""(?:(?P<q>['"]){re.escape(key)}(?P=q)|\b{re.escape(key)})\s*:\s*\{{"""
    )
    depth = 0
    i = 0
    n = len(obj_text)
    in_str: str | None = None
    escape = False
    while i < n:
        ch = obj_text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        after_comment = _skip_js_comment(obj_text, i)
        if after_comment is not None:
            i = after_comment
            continue
        if depth == 0:
            m = pat.match(obj_text, i)
            if m and (
                ch in ("'", '"')
                or i == 0
                or not (obj_text[i - 1].isalnum() or obj_text[i - 1] == "_")
            ):
                return m.end() - 1
        if ch in ("'", '"', "`"):
            in_str = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        i += 1
    return None


def _ensure_hbar_y_ticks(html: str) -> str:
    """Disable Chart.js Y-axis label autoSkip on horizontal bars so all row labels appear."""
    out = html or ""
    if re.search(r"autoSkip\s*:\s*false", out, flags=re.I):
        return out
    y_ticks = "ticks:{autoSkip:false,font:{size:12}}"
    m_scales = re.search(r"\bscales\s*:\s*\{", out)
    if m_scales:
        scales_open = m_scales.end() - 1
        scales_span = _bracket_span(out, scales_open, "{", "}")
        if scales_span is not None:
            s_start, s_end = scales_span
            scales_body = out[s_start + 1 : s_end - 1]
            y_rel = _find_top_level_key_brace(scales_body, "y")
            if y_rel is not None:
                y_open = s_start + 1 + y_rel
                y_span = _bracket_span(out, y_open, "{", "}")
                if y_span is not None:
                    y_start, y_end = y_span
                    y_body = out[y_start + 1 : y_end - 1]
                    t_rel = _find_top_level_key_brace(y_body, "ticks")
                    if t_rel is not None:
                        t_open = y_start + 1 + t_rel
                        return out[: t_open + 1] + "autoSkip:false," + out[t_open + 1 :]
                    return out[: y_open + 1] + f"{y_ticks}," + out[y_open + 1 :]
            return out[: scales_open + 1] + f"y:{{{y_ticks}}}," + out[scales_open + 1 :]
    if re.search(r"options\s*:\s*\{", out):
        return re.sub(
            r"(options\s*:\s*\{)",
            rf"\1scales:{{y:{{{y_ticks}}}}},",
            out,
            count=1,
        )
    return out


_SCALES_PLUGIN_CHILDREN = frozenset(
    {"title", "subtitle", "legend", "tooltip", "datalabels"}
)
_SCALES_MISPLACED_SUBKEYS = frozenset(
    {"ticks", "grid", "border", "font", "anglelines", "pointlabels"}
)
_SCALES_OPTION_KEYS = frozenset(
    {
        "animation",
        "responsive",
        "maintainAspectRatio",
        "layout",
        "indexAxis",
        "cutout",
        "interaction",
        "elements",
        "hover",
        "aspectRatio",
        "devicePixelRatio",
    }
)
_AXIS_KEYS = frozenset({"x", "y", "r", "x0", "x1", "y0", "y1", "y2", "x2"})
_OPTIONS_KEY_RE = re.compile(r"""(?:(?P<q>['"])options(?P=q)|\boptions)\s*:\s*\{""")
_SCALES_KEY_RE = re.compile(r"""(?:(?P<q>['"])scales(?P=q)|\bscales)\s*:\s*\{""")


def _split_js_entries(obj_body: str) -> list[tuple[str, str, str]]:
    """Split top-level `key: value` entries inside `{...}` body, respecting strings/comments/brackets."""
    entries: list[tuple[str, str, str]] = []
    n = len(obj_body)
    i = 0
    start = 0
    brace = 0
    bracket = 0
    paren = 0
    in_str: str | None = None
    escape = False

    def _push(end_idx: int) -> None:
        chunk = obj_body[start:end_idx].strip()
        if not chunk:
            return
        head = re.sub(
            r"^(?:\s*(?://[^\n]*(?:\n|$)|/\*[\s\S]*?\*/))+",
            "",
            chunk,
        ).strip()
        if not head:
            return
        m = re.match(r"^(['\"]?)([A-Za-z_$][A-Za-z0-9_$]*)\1\s*:\s*([\s\S]+)$", head)
        if m:
            entries.append((m.group(2), m.group(3).strip(), chunk))
        else:
            entries.append(("", chunk, chunk))

    while i < n:
        ch = obj_body[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        after_comment = _skip_js_comment(obj_body, i)
        if after_comment is not None:
            i = after_comment
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            i += 1
            continue
        if ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "," and brace == 0 and bracket == 0 and paren == 0:
            _push(i)
            start = i + 1
        i += 1
    _push(n)
    return entries


def _insert_into_object(html: str, obj_open_idx: int, prefix: str) -> str:
    if not prefix:
        return html
    return html[: obj_open_idx + 1] + prefix + html[obj_open_idx + 1 :]


def _relocate_to_options(
    html: str,
    *,
    plugin_entries: list[tuple[str, str]],
    plugins_wrapper_val: str | None,
    option_entries: list[tuple[str, str]],
) -> str:
    """Safely relocate misplaced scales children into `options` / `options.plugins`."""
    if not plugin_entries and not plugins_wrapper_val and not option_entries:
        return html
    m_opt = _OPTIONS_KEY_RE.search(html)
    if not m_opt:
        return html
    opt_open = m_opt.end() - 1
    opt_span = _bracket_span(html, opt_open, "{", "}")
    if not opt_span:
        return html
    opt_body = html[opt_span[0] + 1 : opt_span[1] - 1]

    # Collect existing top-level option keys and plugins children.
    existing_opt = {k.lower() for k, _v, _raw in _split_js_entries(opt_body) if k}

    # Build plugin additions from misplaced `plugins:{...}` wrapper + direct children.
    merged_plugins: list[tuple[str, str]] = []
    if plugins_wrapper_val and plugins_wrapper_val.startswith("{") and plugins_wrapper_val.endswith("}"):
        for pk, pv, _praw in _split_js_entries(plugins_wrapper_val[1:-1]):
            if pk:
                merged_plugins.append((pk, pv))
    merged_plugins.extend(plugin_entries)

    out = html
    if merged_plugins:
        p_rel = _find_top_level_key_brace(opt_body, "plugins")
        if p_rel is not None:
            p_open = opt_open + 1 + p_rel
            p_span = _bracket_span(out, p_open, "{", "}")
            if p_span:
                p_body = out[p_span[0] + 1 : p_span[1] - 1]
                existing_p = {k.lower() for k, _v, _raw in _split_js_entries(p_body) if k}
                add_parts: list[str] = []
                for k, v in merged_plugins:
                    kl = k.lower()
                    if kl not in existing_p:
                        existing_p.add(kl)
                        add_parts.append(f"{k}:{v},")
                out = _insert_into_object(out, p_open, "".join(add_parts))
        else:
            seen_p: set[str] = set()
            uniq_p: list[str] = []
            for k, v in merged_plugins:
                if k.lower() not in seen_p:
                    seen_p.add(k.lower())
                    uniq_p.append(f"{k}:{v}")
            if uniq_p:
                out = _insert_into_object(out, opt_open, f"plugins:{{{','.join(uniq_p)}}},")

    # Re-locate `options:{` after possible insertion above.
    m_opt2 = _OPTIONS_KEY_RE.search(out)
    if m_opt2 and option_entries:
        opt_open2 = m_opt2.end() - 1
        add_opt_parts: list[str] = []
        for k, v in option_entries:
            kl = k.lower()
            if kl not in existing_opt:
                existing_opt.add(kl)
                add_opt_parts.append(f"{k}:{v},")
        out = _insert_into_object(out, opt_open2, "".join(add_opt_parts))
    return out


def repair_misplaced_scales_keys(html: str) -> str:
    """Strip/relocate misplaced `plugins`/`title`/`legend`/`tooltip`/option keys out of `scales:{...}`.

    Chart.js v4 treats every direct key in `options.scales` as a scale ID; misplaced
    keys like `scales: {x: {...}, y: {...}, title: {...}}` throw
    `TypeError: Cannot read properties of undefined (reading 'axis')`.
    """
    src = html or ""
    if not src or "scales" not in src:
        return src
    m_scales = _SCALES_KEY_RE.search(src)
    if not m_scales:
        return src
    s_open = m_scales.end() - 1
    s_span = _bracket_span(src, s_open, "{", "}")
    if not s_span:
        return src

    s_body = src[s_open + 1 : s_span[1] - 1]
    entries = _split_js_entries(s_body)
    if not entries:
        return src

    axis_entries = [k for k, _v, _raw in entries if k.lower() in _AXIS_KEYS]
    kept: list[tuple[str, str, str]] = []
    plugin_entries: list[tuple[str, str]] = []
    plugins_wrapper_val: str | None = None
    option_entries: list[tuple[str, str]] = []
    single_axis_title: str | None = None

    changed = False
    for k, v, raw in entries:
        kl = k.lower()
        if kl == "plugins":
            changed = True
            if plugins_wrapper_val is None:
                plugins_wrapper_val = v
            continue
        if kl in _SCALES_PLUGIN_CHILDREN:
            changed = True
            if kl == "title" and len(axis_entries) == 1 and v.startswith("{"):
                single_axis_title = v
            else:
                plugin_entries.append((k, v))
            continue
        if kl in {opt.lower() for opt in _SCALES_OPTION_KEYS}:
            changed = True
            option_entries.append((k, v))
            continue
        if kl in _SCALES_MISPLACED_SUBKEYS:
            changed = True
            continue
        kept.append((k, v, raw))

    if not changed:
        return src

    if single_axis_title and len(axis_entries) == 1:
        sole_axis = axis_entries[0]
        rebuilt_kept: list[str] = []
        for k, v, raw in kept:
            if k == sole_axis and v.startswith("{") and v.endswith("}"):
                inner = v[1:-1].strip()
                if re.search(r"\btitle\s*:", inner):
                    rebuilt_kept.append(raw)
                elif inner:
                    rebuilt_kept.append(f"{k}:{{{inner},title:{single_axis_title}}}")
                else:
                    rebuilt_kept.append(f"{k}:{{title:{single_axis_title}}}")
            else:
                rebuilt_kept.append(raw)
        new_scales_body = ", ".join(rebuilt_kept)
    else:
        new_scales_body = ", ".join(raw for _k, _v, raw in kept)

    out = src[: s_open + 1] + new_scales_body + src[s_span[1] - 1 :]
    return _relocate_to_options(
        out,
        plugin_entries=plugin_entries,
        plugins_wrapper_val=plugins_wrapper_val,
        option_entries=option_entries,
    )


def harden_chart_html(
    html: str,
    chart_type: str,
    *,
    palette_id: str = "auto",
) -> str:
    """Fix sparse / washed-out Chart.js HTML for known types (esp. horizontal_bar)."""
    want = (chart_type or "").strip()
    out = repair_misplaced_scales_keys(html or "")
    # D7: clamp over-tall print canvases (hbar has its own denser height).
    if want != "horizontal_bar" and out:
        out = _clamp_canvas_height(out)
    if want == "horizontal_bar" and out:
        n = _count_labels(out)
        # 40px per region so a 15-row ranking stays readable without auto-skipping labels.
        h = max(320, min(960, 90 + n * 40))
        out = re.sub(
            r'(<canvas\b[^>]*\bheight=")(\d+)(")',
            rf"\g<1>{h}\3",
            out,
            count=1,
            flags=re.I,
        )
        if re.search(r"barPercentage\s*:", out):
            out = re.sub(r"barPercentage\s*:\s*[\d.]+", "barPercentage:0.78", out, count=1)
        else:
            out = re.sub(
                r"(datasets\s*:\s*\[\s*\{)",
                r"\1barPercentage:0.78,categoryPercentage:0.88,",
                out,
                count=1,
            )
        if re.search(r"categoryPercentage\s*:", out):
            out = re.sub(
                r"categoryPercentage\s*:\s*[\d.]+",
                "categoryPercentage:0.88",
                out,
                count=1,
            )
        if "borderRadius" not in out:
            out = re.sub(
                r"(datasets\s*:\s*\[\s*\{)",
                r"\1borderRadius:6,",
                out,
                count=1,
            )
        out = _solidify_pale_bar_fill(out)
        out = _colorize_hbar_categories(out, palette_id)
        out = _ensure_hbar_y_ticks(out)
    elif want in {"bar", "grouped_bar", "stacked_bar"} and out:
        out = _solidify_pale_bar_fill(out)
        out = _relax_vertical_bar_labels(out)
        if want == "stacked_bar":
            out = _ensure_stack_segment_gaps(out)
    elif want == "scatter" and out:
        out = _ensure_scatter_point_size(out)
    elif want in {"line", "area"} and out:
        out = _ensure_line_point_size(out)
    return out


def _datasets_array_body(src: str) -> str | None:
    """Return balanced substring inside ``datasets: [...]`` (nested data arrays intact)."""
    m = re.search(r"\bdatasets\s*:\s*\[", src, flags=re.I)
    if not m:
        return None
    start = m.end()
    depth = 1
    i = start
    n = len(src)
    in_sq = False
    in_dq = False
    esc = False
    while i < n:
        ch = src[i]
        if esc:
            esc = False
        elif ch == "\\":
            esc = True
        elif in_sq:
            if ch == "'":
                in_sq = False
        elif in_dq:
            if ch == '"':
                in_dq = False
        elif ch == "'":
            in_sq = True
        elif ch == '"':
            in_dq = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return src[start:i]
        i += 1
    return None


def _hide_legend_if_unnamed_dataset(html: str) -> str:
    """Donut→bar leaves datasets without ``label`` → Chart.js legend shows «undefined»."""
    src = html or ""
    body = _datasets_array_body(src)
    if body is None:
        return src
    # Multiple labeled series keep the legend; unlabeled single series → hide.
    labeled = len(re.findall(r"""\blabel\s*:\s*['"][^'"]+['"]""", body))
    series = len(re.findall(r"\{", body))
    if series >= 2 and labeled >= 1:
        return src
    if re.search(r"legend\s*:\s*\{[^}]*display\s*:", src, flags=re.I):
        return re.sub(
            r"(legend\s*:\s*\{[^}]*?display\s*:\s*)[^,}\s]+",
            r"\1false",
            src,
            count=1,
        )
    if re.search(r"legend\s*:\s*\{", src, flags=re.I):
        return re.sub(r"legend\s*:\s*\{", "legend:{display:false,", src, count=1)
    if re.search(r"plugins\s*:\s*\{", src, flags=re.I):
        return re.sub(
            r"plugins\s*:\s*\{",
            "plugins:{legend:{display:false},",
            src,
            count=1,
        )
    if re.search(r"options\s*:\s*\{", src, flags=re.I):
        return re.sub(
            r"options\s*:\s*\{",
            "options:{plugins:{legend:{display:false}},",
            src,
            count=1,
        )
    return src

def full_chat_canvas(
    html: str,
    *,
    width: int = 1100,
    height: int = 560,
    chart_type: str = "",
) -> str:
    """Chat charts fill one frame without squashing donuts, hbars, or pure CSS KPIs."""
    raw = html or ""
    kind = (chart_type or "").strip().lower()
    if kind == "kpi" or _is_kpi_html(raw):
        return raw
    if not re.search(r"<canvas\b", raw, flags=re.I) and "new Chart" not in raw:
        return raw

    is_donut = (
        kind == "donut"
        or "donut-layout" in raw
        or bool(re.search(r"""type\s*:\s*['"]doughnut['"]""", raw, flags=re.I))
    )
    if is_donut:
        # Donuts require a 520x520 square canvas alongside their valued HTML legend.
        from case3.chart_donut import _force_square_canvas

        return _force_square_canvas(raw, size=520)

    is_hbar = (
        kind == "horizontal_bar"
        or bool(re.search(r"""indexAxis\s*:\s*['"]y['"]""", raw, flags=re.I))
    )

    def _repl(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        target_h = height
        if is_hbar:
            hm = re.search(r"""\bheight\s*=\s*["']?(\d+)""", attrs, flags=re.I)
            if hm:
                try:
                    existing_h = int(hm.group(1))
                    if existing_h >= 300:
                        target_h = existing_h
                except ValueError:
                    pass
        attrs = re.sub(r"\s*width\s*=\s*(\"[^\"]*\"|'[^']*'|\S+)", "", attrs, flags=re.I)
        attrs = re.sub(r"\s*height\s*=\s*(\"[^\"]*\"|'[^']*'|\S+)", "", attrs, flags=re.I)
        attrs = re.sub(r"\s*style\s*=\s*(\"[^\"]*\"|'[^']*')", "", attrs, flags=re.I)
        return f'<canvas{attrs} width="{width}" height="{target_h}">'

    if re.search(r"<canvas\b", raw, flags=re.I):
        return re.sub(r"<canvas(\s[^>]*)?>", _repl, raw, count=1, flags=re.I)
    return f'<canvas id="c" width="{width}" height="{height}"></canvas>\n{raw}'


def _landscape_canvas_if_square(html: str, *, width: int = 1100, height: int = 560) -> str:
    """Donut print uses 520×520 — after leaving donut, restore a landscape bitmap."""

    def _repl(m: re.Match[str]) -> str:
        attrs = m.group(1) or ""
        wm = re.search(r"\bwidth\s*=\s*[\"']?(\d+)", attrs, flags=re.I)
        hm = re.search(r"\bheight\s*=\s*[\"']?(\d+)", attrs, flags=re.I)
        if not wm or not hm:
            return m.group(0)
        try:
            w, h = int(wm.group(1)), int(hm.group(1))
        except ValueError:
            return m.group(0)
        if w != h or w > 640:
            return m.group(0)
        attrs = re.sub(r"\s*width\s*=\s*(\"[^\"]*\"|'[^']*'|\S+)", "", attrs, flags=re.I)
        attrs = re.sub(r"\s*height\s*=\s*(\"[^\"]*\"|'[^']*'|\S+)", "", attrs, flags=re.I)
        attrs = attrs.rstrip()
        return f'<canvas{attrs} width="{width}" height="{height}">'

    return re.sub(r"<canvas(\s[^>]*)?>", _repl, html or "", count=1, flags=re.I)
