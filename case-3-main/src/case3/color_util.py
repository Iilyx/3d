"""Shared hex helpers for decks / charts / DOCX (no purple invent)."""

from __future__ import annotations

import re

_HEX6 = re.compile(r"^[0-9a-fA-F]{6}$")
_HEX3 = re.compile(r"^[0-9a-fA-F]{3}$")


def expand_hex(hx: str) -> str:
    """``#abc`` → ``#AABBCC``; already-6 stays upper with leading ``#``."""
    raw = (hx or "").strip().lstrip("#")
    if _HEX3.fullmatch(raw):
        raw = "".join(c * 2 for c in raw)
    if _HEX6.fullmatch(raw):
        return f"#{raw.upper()}"
    return f"#{raw}"


def norm_hex(value: str | None, fallback: str = "#000000") -> str:
    """Normalize to ``#RRGGBB`` or return normalized ``fallback`` if invalid/empty."""
    raw = (value or "").strip()
    if raw:
        if not raw.startswith("#"):
            raw = f"#{raw}"
        body = raw.lstrip("#")
        if _HEX3.fullmatch(body) or _HEX6.fullmatch(body):
            return expand_hex(raw)
    fb = (fallback or "#000000").strip()
    if not fb.startswith("#"):
        fb = f"#{fb}"
    body = fb.lstrip("#")
    if _HEX3.fullmatch(body) or _HEX6.fullmatch(body):
        return expand_hex(fb)
    return "#000000"


def hex_to_rgb(hx: str) -> tuple[int, int, int] | None:
    """Parse ``#RGB`` / ``#RRGGBB`` → (r, g, b) or None."""
    raw = (hx or "").strip().lstrip("#")
    if _HEX3.fullmatch(raw):
        raw = "".join(c * 2 for c in raw)
    if not _HEX6.fullmatch(raw):
        return None
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _linear_channel(c: int) -> float:
    x = c / 255
    if x <= 0.04045:
        return x / 12.92
    return ((x + 0.055) / 1.055) ** 2.4


def relative_luminance(hx: str) -> float:
    rgb = hex_to_rgb(hx)
    if rgb is None:
        return 0.0
    r, g, b = (_linear_channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def accent_fields(colors: dict | None) -> dict[str, str]:
    """Ink that stays readable on the accent, plus the opposite column.

    Large poster type: dark ink once the field is brighter than deep olive.
    The second column is the pack color farthest from the accent.
    """
    src = colors if isinstance(colors, dict) else {}
    accent = norm_hex(str(src.get("accent") or "#4F6B14"))
    sheet = norm_hex(str(src.get("sheet") or src.get("background") or "#FFFCF7"))
    paper = norm_hex(str(src.get("paper") or sheet))
    ink = norm_hex(str(src.get("ink") or "#14161A"))
    primary = norm_hex(str(src.get("primary") or accent))
    options = [sheet, paper, ink]
    dark = min(options, key=relative_luminance)
    light = max(options, key=relative_luminance)

    def ink_for(bg: str) -> str:
        choice = dark if relative_luminance(bg) >= 0.22 else light
        if abs(relative_luminance(choice) - relative_luminance(bg)) < 0.12:
            choice = light if choice == dark else dark
        return choice

    field_b = max(options, key=lambda c: abs(relative_luminance(c) - relative_luminance(accent)))
    if field_b.upper() == accent.upper():
        field_b = dark if relative_luminance(accent) >= 0.22 else light
    return {
        "on_accent": ink_for(accent),
        "field_b": field_b,
        "on_field_b": ink_for(field_b),
        "rail": primary,
        "on_rail": ink_for(primary),
    }
