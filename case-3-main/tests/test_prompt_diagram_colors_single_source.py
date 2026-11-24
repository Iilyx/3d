"""Diagram colors: one live table from format_diagram_color_prompt — no stale hex."""

from __future__ import annotations

from pathlib import Path

from case3.diagram_generate import diagram_prompts
from case3.diagram_repair import load_repair_system
from case3.diagram_style import format_diagram_color_prompt, role_colors_for_palette
from case3.prompts import load, prompt_dir

# Stale "Liber prefer these" hex that contradicted live atelier/editorial tables.
_STALE_HEX = (
    "#dce8df",
    "#eef3ef",
    "#f3e6c8",
    "#cfe6d4",
    "#f0ddd8",
    "#d9e6f0",
    "#6b8f76",
    "#5a7a64",
    "#b8893a",
    "#3d7a4a",
    "#a85a4a",
    "#4a6f8c",
)

_PROMPT_FILES = (
    "parts/tex/04_diagrams.md",
    "parts/tex/01_output.md",
    "diagram_repair.md",
    "diagram_refine.md",
)


def _assert_no_stale_hex(text: str, *, where: str) -> None:
    lower = text.lower()
    for hx in _STALE_HEX:
        assert hx not in lower, f"stale hex {hx} still in {where}"


def test_prompt_files_have_no_stale_diagram_hex() -> None:
    root = prompt_dir()
    for rel in _PROMPT_FILES:
        body = (root / rel).read_text(encoding="utf-8")
        _assert_no_stale_hex(body, where=rel)


def test_system_tex_has_no_stale_diagram_hex() -> None:
    text = load(
        "system_tex",
        MAX_IMAGES=0,
        MAX_CHARTS=2,
        MAX_DIAGRAMS=2,
        PALETTE_TABLE="(table)",
    )
    _assert_no_stale_hex(text, where="system_tex")


def test_diagram_prompts_color_table_only_in_system() -> None:
    table = format_diagram_color_prompt("atelier")
    atelier_fill = role_colors_for_palette("atelier")["start"]["fill"]
    system, user = diagram_prompts(
        intent="схема",
        source_text="Шаг A затем шаг B",
        max_diagrams=1,
        palette="atelier",
    )
    assert atelier_fill in system
    assert table in system
    assert table not in user
    assert "Liber diagram colors" not in user
    _assert_no_stale_hex(system, where="diagram_generate system")
    _assert_no_stale_hex(user, where="diagram_generate user")


def test_load_repair_system_uses_live_table_once() -> None:
    table = format_diagram_color_prompt("atelier")
    text = load_repair_system("atelier")
    assert table in text
    assert text.count("### Liber diagram colors") == 1
    _assert_no_stale_hex(text, where="diagram_repair system")


def test_diagram_refine_loads_live_color_table() -> None:
    table = format_diagram_color_prompt("ocean")
    text = load("diagram_refine", DIAGRAM_COLOR_TABLE=table)
    assert table in text
    _assert_no_stale_hex(text, where="diagram_refine")
