"""Sanitize untrusted LLM fields before they touch TeX."""

from __future__ import annotations

import re

# Only fractional textwidth / linewidth — no free-form TeX.
_WIDTH_OK = re.compile(r"^(?:0?\.\d+|1(?:\.0+)?|0)\\(?:text|line)width$")
# D7: keep figures inside A4 text block (margin for caption).
_MAX_WIDTH_FRAC = 0.92
# Multi-chart docs: slightly narrower so two figures fit a page rhythm.
_MAX_MULTI_CHART_FRAC = 0.82


def sanitize_width(
    raw: str | None,
    *,
    default: str = r"0.85\textwidth",
    max_frac: float | None = None,
) -> str:
    value = (raw or default).strip().replace(" ", "")
    # JSON often double-escapes: 0.85\\textwidth
    while "\\\\" in value:
        value = value.replace("\\\\", "\\")
    if not _WIDTH_OK.match(value):
        return default
    m = re.match(r"^(0?\.\d+|1(?:\.0+)?|0)\\(text|line)width$", value)
    if not m:
        return default
    try:
        frac = float(m.group(1))
    except ValueError:
        return default
    unit = m.group(2)
    cap = _MAX_WIDTH_FRAC if max_frac is None else float(max_frac)
    if frac > cap:
        cap_s = f"{cap:.2f}"
        return rf"{cap_s}\{unit}width"
    return value


def multi_chart_max_frac() -> float:
    return _MAX_MULTI_CHART_FRAC


def escape_tex_text(text: str) -> str:
    """Escape LaTeX specials in captions / short prose from the model."""
    out: list[str] = []
    for ch in text or "":
        if ch == "\\":
            out.append(r"\textbackslash{}")
        elif ch == "{":
            out.append(r"\{")
        elif ch == "}":
            out.append(r"\}")
        elif ch == "$":
            out.append(r"\$")
        elif ch == "&":
            out.append(r"\&")
        elif ch == "%":
            out.append(r"\%")
        elif ch == "#":
            out.append(r"\#")
        elif ch == "_":
            out.append(r"\_")
        elif ch == "^":
            out.append(r"\^{}")
        elif ch == "~":
            out.append(r"\textasciitilde{}")
        else:
            out.append(ch)
    return "".join(out)
