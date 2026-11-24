"""Liber Mermaid role colors — palette-aware classDef cookbook for the LLM."""

from __future__ import annotations

import re
from typing import Any

from case3.chart_style import _PALETTES, normalize_palette_id

DIAGRAM_ROLES = ("start", "process", "decision", "ok", "warn", "data")

ROLE_LABEL_RU: dict[str, str] = {
    "start": "Старт",
    "process": "Процесс",
    "decision": "Решение",
    "ok": "Успех",
    "warn": "Риск / возврат",
    "data": "Данные / система",
}

_TEXT = "#1a2e22"

# Soft role fills derived from each chart palette & deck theme pack (no purple).
_ROLE_MAP: dict[str, dict[str, tuple[str, str]]] = {
    # Soft fills aligned with chart_style presets (Okabe–Ito / Tol / Tableau 10).
    "atelier": {
        "start": ("#D4EBE8", "#1F6F66"),
        "process": ("#E7F0D8", "#6B7F45"),
        "decision": ("#F8E6D8", "#C47A3A"),
        "ok": ("#D7EDD9", "#2F7D4A"),
        "warn": ("#F6DDD6", "#C45A48"),
        "data": ("#D6E4F2", "#3E6F99"),
    },
    "editorial": {
        "start": ("#DCE6F0", "#4E79A7"),
        "process": ("#E4F2EF", "#76B7B2"),
        "decision": ("#F8E8D4", "#F28E2B"),
        "ok": ("#D8EBE4", "#59A14F"),
        "warn": ("#F5D8D4", "#E15759"),
        "data": ("#E4EEF6", "#3D6490"),
    },
    "ocean": {
        "start": ("#D6EAF5", "#0072B2"),
        "process": ("#E7F3EA", "#2E8B6A"),
        "decision": ("#F5ECD4", "#E69F00"),
        "ok": ("#D4EBE4", "#009E73"),
        "warn": ("#F5DDD0", "#D55E00"),
        "data": ("#DCEEF8", "#3A6F9A"),
    },
    "sunset": {
        "start": ("#F8E0E4", "#9A4A58"),
        "process": ("#EEF2F6", "#4477AA"),
        "decision": ("#F5EFD4", "#A89830"),
        "ok": ("#DCE8DC", "#228833"),
        "warn": ("#F5D4D8", "#EE6677"),
        "data": ("#E0F0F5", "#3A9AAD"),
    },
    "mono": {
        "start": ("#E8EAED", "#1A1F28"),
        "process": ("#F1F2F4", "#3A4250"),
        "decision": ("#ECE8E0", "#8B7355"),
        "ok": ("#E4E8E4", "#2F4A38"),
        "warn": ("#EBE4E4", "#6B4038"),
        "data": ("#E8EAED", "#5C6570"),
    },
    # ——— Deck theme packs (8 presentation templates) ———
    "board": {
        "start": ("#E6F0F8", "#226496"),
        "process": ("#EDF3F8", "#172D40"),
        "decision": ("#FAEDE6", "#D96B43"),
        "ok": ("#E3F3EE", "#2A8C72"),
        "warn": ("#FBE8DF", "#C9522B"),
        "data": ("#E4EEF7", "#2B6A99"),
    },
    "signal": {
        "start": ("#35231B", "#E86A33"),
        "process": ("#2C2621", "#D8CFC4"),
        "decision": ("#382B1B", "#F2A93B"),
        "ok": ("#1D312B", "#38A889"),
        "warn": ("#3B211C", "#FF7B47"),
        "data": ("#2E2822", "#E5C697"),
    },
    "relay": {
        "start": ("#FADFD8", "#C45B46"),
        "process": ("#F5EFE6", "#6B4F49"),
        "decision": ("#F9EAE0", "#D4884E"),
        "ok": ("#E2F0EB", "#3B7A6B"),
        "warn": ("#FCE2DC", "#B83B2A"),
        "data": ("#F3E6DF", "#5C2A24"),
    },
    "pastel": {
        "start": ("#FADFD8", "#C45B46"),
        "process": ("#F5EFE6", "#6B4F49"),
        "decision": ("#F9EAE0", "#D4884E"),
        "ok": ("#E2F0EB", "#3B7A6B"),
        "warn": ("#FCE2DC", "#B83B2A"),
        "data": ("#F3E6DF", "#5C2A24"),
    },
    "voltage": {
        "start": ("#162A3E", "#38BDF8"),
        "process": ("#1E2B3E", "#94A3B8"),
        "decision": ("#2C2E1A", "#E4E869"),
        "ok": ("#16332B", "#34D399"),
        "warn": ("#382124", "#FB7185"),
        "data": ("#1B2E47", "#60A5FA"),
    },
    "studio": {
        "start": ("#E4EEF7", "#2D5A88"),
        "process": ("#F3E9DA", "#5C5346"),
        "decision": ("#F9E8D2", "#D47A3E"),
        "ok": ("#E2F0E8", "#3B7A57"),
        "warn": ("#F7DFD8", "#C25944"),
        "data": ("#EAE4DA", "#4A6F8A"),
    },
    "botanical": {
        "start": ("#1E352B", "#52B788"),
        "process": ("#22332B", "#A3B899"),
        "decision": ("#312C1F", "#D4B475"),
        "ok": ("#1B3B2E", "#40916C"),
        "warn": ("#382520", "#E07A5F"),
        "data": ("#1E3133", "#64A6BD"),
    },
    "ink": {
        "start": ("#1D2938", "#58A6FF"),
        "process": ("#202834", "#94A3B8"),
        "decision": ("#2D281E", "#E3B341"),
        "ok": ("#1A3129", "#3FB950"),
        "warn": ("#362222", "#F85149"),
        "data": ("#1E2C3A", "#79C0FF"),
    },
}

_DARK_TEXT_MAP: dict[str, str] = {
    "signal": "#F7F2EB",
    "voltage": "#F4F0E6",
    "botanical": "#E8E2D4",
    "ink": "#E6E4DC",
}

_CLASSDEF_FILL = re.compile(
    r"classDef\s+([a-zA-Z][\w-]*)\s+[^;\n]*fill:\s*(#[0-9a-fA-F]{3,8})",
    re.I,
)
_NODE_CLASS = re.compile(r":::\s*([a-zA-Z][\w-]*)")


def role_colors_for_palette(palette_id: str | None) -> dict[str, dict[str, str]]:
    """Return {role: {fill, stroke, color}} for Liber Mermaid classDef."""
    raw_key = (palette_id or "").strip().lower()
    if raw_key in _ROLE_MAP:
        pid = raw_key
    else:
        pid = normalize_palette_id(palette_id)
        if pid == "auto":
            pid = "atelier"
    table = _ROLE_MAP.get(pid) or _ROLE_MAP["atelier"]
    txt = _DARK_TEXT_MAP.get(pid, _TEXT)
    out: dict[str, dict[str, str]] = {}
    for role in DIAGRAM_ROLES:
        fill, stroke = table.get(role, _ROLE_MAP["atelier"][role])
        out[role] = {"fill": fill, "stroke": stroke, "color": txt}
    return out


def format_diagram_color_prompt(palette_id: str | None) -> str:
    """Markdown block injected into system/repair prompts."""
    pid = normalize_palette_id(palette_id)
    if pid == "auto":
        pid = "atelier"
    label = (_PALETTES.get(pid) or {}).get("label") or pid
    colors = role_colors_for_palette(pid)
    lines = [
        f"### Liber diagram colors (palette: {label} / {pid})",
        "Assign every flowchart node a role via `:::role` + matching `classDef`.",
        "Use **these hex values** (no purple/neon):",
        "",
        "| role | fill | stroke | when |",
        "|------|------|--------|------|",
    ]
    for role in DIAGRAM_ROLES:
        c = colors[role]
        lines.append(
            f"| `{role}` | `{c['fill']}` | `{c['stroke']}` | {ROLE_LABEL_RU[role]} |"
        )
    lines.append("")
    lines.append("Every classDef must include `color:#1a2e22`.")
    lines.append("Example classDef line:")
    s = colors["start"]
    lines.append(
        f"  classDef start fill:{s['fill']},stroke:{s['stroke']},color:#1a2e22"
    )
    return "\n".join(lines)


_CLASSDEF_NAME = re.compile(r"classDef\s+([A-Za-z][\w-]*)", re.I)


def ensure_role_classdefs(
    mermaid: str, palette: str | None = None, *, overwrite: bool = False
) -> str:
    """Add or retheme role classDefs so a flowchart matches the target palette/pack."""
    text = mermaid or ""
    from case3.diagrams import first_meaningful_line

    first = first_meaningful_line(text).lower()
    if not first.startswith("flowchart") and not first.startswith("graph"):
        return text
    colors = role_colors_for_palette(palette)
    if overwrite:
        cleaned_lines = [
            ln
            for ln in text.splitlines()
            if not (
                _CLASSDEF_NAME.search(ln)
                and _CLASSDEF_NAME.search(ln).group(1).lower() in DIAGRAM_ROLES  # type: ignore[union-attr]
            )
        ]
        text = "\n".join(cleaned_lines)
    used = {m.group(1).lower() for m in _NODE_CLASS.finditer(text)}
    defined = {m.group(1).lower() for m in _CLASSDEF_NAME.finditer(text)}
    missing = [
        role for role in DIAGRAM_ROLES if (role in used or overwrite) and role not in defined
    ]
    if not missing:
        return text
    lines = [
        (
            f"    classDef {role} fill:{colors[role]['fill']},"
            f"stroke:{colors[role]['stroke']},color:{colors[role]['color']}"
        )
        for role in missing
    ]
    return text.rstrip() + "\n" + "\n".join(lines) + "\n"


def extract_diagram_legend(mermaid: str) -> list[dict[str, Any]]:
    """Ordered legend entries from classDef fills for roles used (or defined)."""
    text = mermaid or ""
    fills: dict[str, str] = {}
    for m in _CLASSDEF_FILL.finditer(text):
        role = m.group(1).lower()
        fills[role] = m.group(2)
    used = {m.group(1).lower() for m in _NODE_CLASS.finditer(text)}
    # Prefer roles that appear on nodes; else all classDefs in DIAGRAM_ROLES order.
    order: list[str] = []
    for role in DIAGRAM_ROLES:
        if role in used or role in fills:
            if role not in order:
                order.append(role)
    for role in fills:
        if role not in order:
            order.append(role)
    # If nodes used roles without classDef, still show with palette default atelier.
    defaults = role_colors_for_palette("atelier")
    out: list[dict[str, Any]] = []
    for role in order:
        if role not in DIAGRAM_ROLES and role not in fills:
            continue
        fill = fills.get(role) or defaults.get(role, {}).get("fill") or "#dce8df"
        out.append(
            {
                "role": role,
                "fill": fill,
                "label": ROLE_LABEL_RU.get(role, role),
            }
        )
    return out
