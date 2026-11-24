"""Sanitize LLM HTML chart fragments and wrap in offline Chart.js frame."""

from __future__ import annotations

from case3.paths import repo_root

import re
from pathlib import Path

# Only types Chart.js 4.x (+ HTML kpi) can render without extra plugins.
# heatmap/treemap/waterfall live in prototip (Plotly) — not here.
CHART_TYPES = frozenset(
    {
        "bar",
        "grouped_bar",
        "stacked_bar",
        "line",
        "horizontal_bar",
        "donut",
        "kpi",
        "area",
        "scatter",
    }
)

_MAX_HTML_BYTES = 80 * 1024
_FORBIDDEN_TAGS = re.compile(
    r"<(?:iframe|object|embed|link|base|meta|form)\b[^>]*>.*?</(?:iframe|object|embed|link|base|meta|form)>\s*"
    r"|<(?:iframe|object|embed|link|base|meta|form)\b[^>]*/?>"
    r"|<script\b[^>]+src\s*=[^>]*>.*?</script>",
    re.I | re.S,
)
_ON_ATTR = re.compile(r"\son[a-z]+\s*=\s*(['\"]).*?\1", re.I | re.S)
_ON_ATTR_UQ = re.compile(r"\son[a-z]+\s*=\s*[^\s>]+", re.I)
_REMOTE_URL = re.compile(
    r"""(?i)(?:src|href|action|data-src)\s*=\s*(['"])\s*(?:https?:|//|javascript:)[^'"]*\1"""
)
_REMOTE_URL_UQ = re.compile(
    r"""(?i)(?:src|href|action|data-src)\s*=\s*(?:https?:|//|javascript:)[^\s>]+"""
)


class ChartHtmlError(ValueError):
    """HTML chart fragment rejected."""


_DEFER_READY = (
    "requestAnimationFrame(function(){"
    "requestAnimationFrame(function(){"
    "window.__CASE3_CHART_READY=true;});});"
)

# LLM often nests READY in double rAF; stripping only the assignment leaves `function(){}`.
_READY_RAF_SHELL = re.compile(
    r"requestAnimationFrame\s*\(\s*function\s*\(\s*\)\s*\{\s*"
    r"requestAnimationFrame\s*\(\s*function\s*\(\s*\)\s*\{\s*"
    r"(?:window\s*\.\s*)?__CASE3_CHART_READY\s*=\s*true\s*;?\s*"
    r"\}\s*\)\s*;?\s*"
    r"\}\s*\)\s*;?",
    re.I,
)
_READY_ASSIGN = re.compile(
    r"(?:window\s*\.\s*)?__CASE3_CHART_READY\s*=\s*true\s*;?",
    re.I,
)
_EMPTY_RAF_SHELL = re.compile(
    r"requestAnimationFrame\s*\(\s*function\s*\(\s*\)\s*\{\s*"
    r"requestAnimationFrame\s*\(\s*function\s*\(\s*\)\s*\{\s*"
    r"\}\s*\)\s*;?\s*"
    r"\}\s*\)\s*;?",
    re.I,
)


def _skip_js_comment(text: str, i: int) -> int | None:
    if text.startswith("//", i):
        nl = text.find("\n", i + 2)
        return len(text) if nl < 0 else nl + 1
    if text.startswith("/*", i):
        end = text.find("*/", i + 2)
        return len(text) if end < 0 else end + 2
    return None


def _brace_object_span(text: str, open_idx: int) -> tuple[int, int] | None:
    """Return [start, end) of `{...}` starting at open_idx, respecting strings and comments."""
    if open_idx < 0 or open_idx >= len(text) or text[open_idx] != "{":
        return None
    depth = 0
    i = open_idx
    in_str: str | None = None
    escape = False
    while i < len(text):
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
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return open_idx, i + 1
        i += 1
    return None


def _strip_keyed_objects(text: str, key: str) -> str:
    """Remove `key:{...}` (and a preceding comma) via brace matching."""
    pattern = re.compile(rf"(,?)\s*{re.escape(key)}\s*:\s*\{{", re.I)
    while True:
        m = pattern.search(text)
        if not m:
            break
        brace_at = text.find("{", m.start())
        span = _brace_object_span(text, brace_at)
        if not span:
            break
        start = m.start()
        end = span[1]
        # Drop leading comma when present; keep trailing comma ownership simple.
        text = text[:start] + text[end:]
        text = re.sub(r",\s*,", ",", text)
        text = re.sub(r"\{\s*,", "{", text)
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _strip_function_props(text: str, prop: str) -> str:
    """Remove `prop:function(...){...}` (tick/tooltip callbacks)."""
    pattern = re.compile(rf"(,?)\s*{re.escape(prop)}\s*:\s*function\b", re.I)
    while True:
        m = pattern.search(text)
        if not m:
            break
        # Find the `{` that opens the function body.
        i = m.end()
        while i < len(text) and text[i] != "{":
            # Skip (...) args
            i += 1
        if i >= len(text):
            break
        span = _brace_object_span(text, i)
        if not span:
            break
        text = text[: m.start()] + text[span[1] :]
        text = re.sub(r",\s*,", ",", text)
        text = re.sub(r"\{\s*,", "{", text)
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _balance_chart_call(script: str) -> str:
    """Drop extra `}` / insert missing `}` and `)` inside `new Chart(...)` args."""
    m = re.search(r"new\s+Chart\s*\(", script, re.I)
    if not m:
        return script
    start = m.end() - 1  # '('
    out: list[str] = [script[: start + 1]]
    i = start + 1
    paren = 1
    brace = 0
    bracket = 0
    in_str: str | None = None
    escape = False
    while i < len(script):
        ch = script[i]
        if in_str:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        after_comment = _skip_js_comment(script, i)
        if after_comment is not None:
            out.append(script[i:after_comment])
            i = after_comment
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            out.append(ch)
            i += 1
            continue
        if ch == "{":
            brace += 1
            out.append(ch)
        elif ch == "}":
            if brace == 0:
                # Extra closer from LLM — skip.
                i += 1
                continue
            brace -= 1
            out.append(ch)
        elif ch == "[":
            bracket += 1
            out.append(ch)
        elif ch == "]":
            if bracket > 0:
                bracket -= 1
            out.append(ch)
        elif ch == "(":
            paren += 1
            out.append(ch)
        elif ch == ")":
            if paren == 1:
                if bracket > 0:
                    out.append("]" * bracket)
                    bracket = 0
                if brace > 0:
                    out.append("}" * brace)
                    brace = 0
                out.append(ch)
                out.append(script[i + 1 :])
                return "".join(out)
            paren -= 1
            out.append(ch)
        elif ch == ";" and paren == 1 and brace == 0 and bracket == 0:
            # Missing closing ')' before statement semicolon: `new Chart(ctx, {...};`
            out.append(")")
            out.append(script[i:])
            return "".join(out)
        else:
            out.append(ch)
        i += 1
    if bracket > 0:
        out.append("]" * bracket)
    if brace > 0:
        out.append("}" * brace)
    if paren > 0:
        out.append(")" * paren)
    return "".join(out)


def _clean_script_body(body: str) -> str:
    body = _READY_RAF_SHELL.sub("", body)
    body = _READY_ASSIGN.sub("", body)
    body = _EMPTY_RAF_SHELL.sub("", body)
    body = _strip_keyed_objects(body, "tooltip")
    body = _strip_function_props(body, "callback")
    body = _balance_chart_call(body)
    body = body.strip()
    if body and not body.endswith(";"):
        body += ";"
    return body


def _repair_scripts(text: str) -> str:
    """Strip fragile LLM callbacks, orphan </script> READY tails, and rebalance Chart() args."""
    # Remove malformed duplicate tail `</script>window.__CASE3_CHART_READY=true;</script>`
    cleaned = re.sub(
        r"(?is)</script>\s*(?:window\s*\.\s*)?__CASE3_CHART_READY\s*=\s*true\s*;?\s*</script>",
        "</script>",
        text,
    )

    if re.search(r"(?is)<script\b", cleaned):
        # Close an unclosed <script> if no </script> follows it
        last_open = max(
            (m.start() for m in re.finditer(r"(?is)<script\b[^>]*>", cleaned)),
            default=-1,
        )
        last_close = max(
            (m.start() for m in re.finditer(r"(?is)</script>", cleaned)),
            default=-1,
        )
        if last_open > last_close:
            cleaned += "</script>"

        parts: list[str] = []
        pos = 0
        for m in re.finditer(r"(?is)<script(?:\s[^>]*)?>(.*?)</script>", cleaned):
            outside = cleaned[pos : m.start()]
            outside = re.sub(r"(?is)</script>", "", outside)
            outside = _READY_RAF_SHELL.sub("", outside)
            outside = _READY_ASSIGN.sub("", outside)
            parts.append(outside)
            body = _clean_script_body(m.group(1))
            parts.append(f"<script>{body}{_DEFER_READY}</script>")
            pos = m.end()
        tail = cleaned[pos:]
        tail = re.sub(r"(?is)</script>", "", tail)
        tail = _READY_RAF_SHELL.sub("", tail)
        tail = _READY_ASSIGN.sub("", tail)
        parts.append(tail)
        return "".join(parts)

    repaired = _clean_script_body(cleaned)
    return repaired + f"<script>{_DEFER_READY}</script>"


def nest_orphan_scale_titles(html: str) -> str:
    """``scales:{y:{…},title:{…}}`` → nest title under y (Chart.js throws otherwise).

    Win desk 091728: cht_02/cht_04 hung on wait_for_READY — Chart constructor threw
    on an orphan ``title`` scale id beside ``y``/``x``.
    """
    if not html or "scales" not in html:
        return html
    out = html
    for axis in ("y", "x"):
        out = re.sub(
            rf"(scales\s*:\s*\{{\s*{axis}\s*:\s*\{{)([^}}]*)(\}})\s*,\s*title\s*:\s*(\{{[^{{}}]*\}})",
            rf"\1\2,title:\4\3",
            out,
            flags=re.I,
        )
    # ``scales:{x:{…},animation:false}`` — animation is not a scale.
    out = re.sub(
        r"(scales\s*:\s*\{(?:[^{}]|\{[^{}]*\})*?),\s*animation\s*:\s*false(\s*\})",
        r"\1\2",
        out,
        flags=re.I,
    )
    return out


def sanitize_chart_html(html: str) -> str:
    text = (html or "").strip()
    if not text:
        raise ChartHtmlError("empty chart html")
    text = (
        text.replace(r"{\,}", ",")
        .replace("{,}", ",")
        .replace("{.}", ".")
    )
    if len(text.encode("utf-8")) > _MAX_HTML_BYTES:
        raise ChartHtmlError(f"chart html exceeds {_MAX_HTML_BYTES} bytes")
    text = re.sub(r"(?is)<!DOCTYPE[^>]*>", "", text)
    text = re.sub(r"(?is)</?(?:html|head|body)\b[^>]*>", "", text)
    text = _FORBIDDEN_TAGS.sub("", text)
    text = _ON_ATTR.sub("", text)
    text = _ON_ATTR_UQ.sub("", text)
    text = _REMOTE_URL.sub("", text)
    text = _REMOTE_URL_UQ.sub("", text)
    text = text.strip()
    if not text:
        raise ChartHtmlError("chart html empty after sanitize")
    # Frame sets responsive:false; model often overrides → blank / tiny canvas.
    text = re.sub(r"responsive\s*:\s*true", "responsive:false", text, flags=re.I)
    text = re.sub(
        r"maintainAspectRatio\s*:\s*true",
        "maintainAspectRatio:false",
        text,
        flags=re.I,
    )
    text = nest_orphan_scale_titles(text)
    from case3.chart_harden import repair_misplaced_scales_keys

    text = repair_misplaced_scales_keys(text)
    # Drop broken tooltip/tick callbacks; defer READY via a single double-rAF.
    text = _repair_scripts(text)
    return text

def assets_charts_dir() -> Path:
    return repo_root() / "assets" / "charts"


def frame_template_path() -> Path:
    return Path(__file__).resolve().parent / "templates" / "chart_frame.html"


def wrap_chart_page(*, fragment: str, chart_js_href: str = "./chart.umd.min.js") -> str:
    tpl = frame_template_path().read_text(encoding="utf-8")
    return tpl.replace("{{CHART_JS}}", chart_js_href).replace("{{FRAGMENT}}", fragment or "")
