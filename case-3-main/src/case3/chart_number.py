"""One number inside a Chart.js data array.

``12,5`` and ``105 865,2`` are one point. ``100,40`` is two points: a comma
plus two digits is a decimal only after four digits of the integer part.
"""

from __future__ import annotations

import re

_THOUSANDS_GAP = re.compile(r"(?<=\d)[\s\u00a0\u202f]+(?=\d{3}(?:\D|$))")


def compact_chart_number_text(text: str) -> str:
    """Join a thousands gap. ``105 865,2`` becomes ``105865,2``."""
    return _THOUSANDS_GAP.sub("", text or "")


def take_chart_number(text: str, index: int) -> tuple[str, int] | None:
    """Read one number starting at index. A decimal comma is returned with a dot."""
    if index < 0 or index >= len(text):
        return None
    if index > 0 and text[index - 1].isdigit():
        return None
    match = re.match(r"-?\d+", text[index:])
    if not match:
        return None
    num = match.group(0)
    cursor = index + len(num)
    if cursor < len(text) and text[cursor] == ".":
        frac = re.match(r"\.\d+", text[cursor:])
        if frac:
            num += frac.group(0)
            cursor += len(frac.group(0))
    elif cursor < len(text) and text[cursor] == ",":
        one = re.match(r",(\d)(?!\d)", text[cursor:])
        if one:
            num += "." + one.group(1)
            cursor += 2
        elif len(num.lstrip("-")) >= 4:
            two = re.match(r",(\d{2})(?!\d)", text[cursor:])
            if two:
                num += "." + two.group(1)
                cursor += 3
    if cursor < len(text) and text[cursor] in "eE":
        exp = re.match(r"[eE][+-]?\d+", text[cursor:])
        if exp:
            num += exp.group(0)
            cursor += len(exp.group(0))
    return num, cursor
