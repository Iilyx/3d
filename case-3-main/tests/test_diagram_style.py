"""Diagram role colors + legend extract + palette prompt table."""

from __future__ import annotations

from case3.diagram_style import (
    DIAGRAM_ROLES,
    ensure_role_classdefs,
    extract_diagram_legend,
    format_diagram_color_prompt,
    role_colors_for_palette,
)


def test_role_colors_atelier_has_all_roles() -> None:
    colors = role_colors_for_palette("atelier")
    assert set(colors) >= set(DIAGRAM_ROLES)
    assert colors["start"]["fill"].startswith("#")
    assert colors["decision"]["fill"] != colors["ok"]["fill"]
    assert colors["process"]["stroke"] != colors["ok"]["stroke"]
    for pid in ("atelier", "editorial", "ocean", "sunset", "mono"):
        strokes = [role_colors_for_palette(pid)[role]["stroke"].lower() for role in DIAGRAM_ROLES]
        assert len(set(strokes)) == len(DIAGRAM_ROLES), pid


def test_role_colors_ocean_differs_from_atelier() -> None:
    a = role_colors_for_palette("atelier")
    o = role_colors_for_palette("ocean")
    assert a["start"]["fill"] != o["start"]["fill"] or a["data"]["fill"] != o["data"]["fill"]


def test_format_diagram_color_prompt_mentions_roles() -> None:
    text = format_diagram_color_prompt("atelier")
    assert "classDef" in text
    assert "start" in text
    assert "#d" in text.lower() or "#" in text


def test_extract_legend_from_classdef() -> None:
    src = (
        "flowchart TD\n"
        "  A[Старт]:::start --> B{Ок?}:::decision\n"
        "  B -->|да| C[Готово]:::ok\n"
        "  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22\n"
        "  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22\n"
        "  classDef ok fill:#cfe6d4,stroke:#3d7a4a,color:#1a2e22\n"
    )
    legend = extract_diagram_legend(src)
    roles = [x["role"] for x in legend]
    assert roles == ["start", "decision", "ok"]
    assert legend[0]["fill"].lower() == "#dce8df"
    assert legend[0]["label"]  # RU label


def test_missing_role_classdef_is_filled() -> None:
    src = "flowchart TD\n  A[Заявка]:::start --> B{Проверка}:::decision\n"
    out = ensure_role_classdefs(src, "atelier")
    assert "classDef start" in out
    assert "classDef decision" in out
    assert "classDef ok" not in out
