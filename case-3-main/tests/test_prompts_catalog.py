"""Prompt catalog: one loader, manifest, extracted md templates."""

from __future__ import annotations

import pytest

from case3 import prompts
from case3.chat_summary import SUMMARY_SYSTEM
from case3.generate import (
    SOURCE_BEGIN,
    SOURCE_END,
    build_continuation_prompt,
    build_user_prompt,
    load_system_prompt,
)


def test_list_prompt_ids_covers_core_roles() -> None:
    ids = prompts.list_prompt_ids()
    for need in (
        "system_tex",
        "system_slides",
        "user_tex",
        "continuation_tex",
        "summary_system",
        "diagram_generate",
        "diagram_repair",
    ):
        assert need in ids


def test_load_system_tex_replaces_budget_vars() -> None:
    text = prompts.load(
        "system_tex",
        MAX_IMAGES=3,
        MAX_CHARTS=2,
        MAX_DIAGRAMS=1,
        PALETTE_TABLE="| p |",
    )
    assert "{{MAX_IMAGES}}" not in text
    assert "3" in text
    assert "{{PALETTE_TABLE}}" not in text
    assert "| p |" in text


def test_load_unknown_id_raises() -> None:
    with pytest.raises(KeyError, match="unknown prompt"):
        prompts.load("no_such_prompt_id")


def test_manifest_lists_every_registered_id() -> None:
    root = prompts.prompt_dir()
    man = (root / "MANIFEST.md").read_text(encoding="utf-8")
    for pid in prompts.list_prompt_ids():
        assert pid in man, f"{pid} missing from MANIFEST.md"


def test_user_prompt_comes_from_md_scaffold() -> None:
    text = build_user_prompt(
        intent="Сделай отчёт",
        source="Выручка 10",
        max_images=1,
        max_charts=2,
        max_diagrams=0,
    )
    assert "## Intent" in text
    assert "Сделай отчёт" in text
    assert SOURCE_BEGIN in text and SOURCE_END in text
    assert "Выручка 10" in text
    assert "max_images" in text and "1" in text
    # Scaffold lives on disk (not only Python f-strings).
    md = (prompts.prompt_dir() / "user_tex.md").read_text(encoding="utf-8")
    assert "{{INTENT_BLOCK}}" in md
    assert "{{SOURCE}}" in md


def test_user_prompt_includes_user_figures_vision_guidance() -> None:
    text = build_user_prompt(
        intent="Сделай отчёт",
        source="Данные",
        max_images=1,
        max_charts=2,
        user_figures=[{"id": "usr_01", "caption": "Мой файл"}],
    )
    assert "usr_01" in text
    assert "Vision" in text
    assert "%CASE3_FIG:id%" in text


def test_continuation_prompt_from_md() -> None:
    text = build_continuation_prompt(
        partial="x" * 100,
        source="data",
        max_charts=2,
    )
    assert "TRUNCATED" in text
    assert "<<<PARTIAL>>>" in text
    assert SOURCE_BEGIN in text
    md = (prompts.prompt_dir() / "continuation_tex.md").read_text(encoding="utf-8")
    assert "{{PARTIAL_TAIL}}" in md
    assert "{{MAX_CHARTS}}" in md


def test_summary_system_from_md_file() -> None:
    assert "Liber Atelier" in SUMMARY_SYSTEM
    path = prompts.prompt_dir() / "summary_system.md"
    assert path.is_file()
    assert "MEDIA_DELIVERED" in path.read_text(encoding="utf-8")
    # Module constant matches loader (no drift).
    assert SUMMARY_SYSTEM.strip() == prompts.load("summary_system").strip()


def test_load_system_prompt_delegates_to_catalog() -> None:
    from case3.chart_style import palette_fallback_table

    a = load_system_prompt(max_images=0, max_charts=1, max_diagrams=0)
    b = prompts.load(
        "system_tex",
        MAX_IMAGES=0,
        MAX_CHARTS=1,
        MAX_DIAGRAMS=0,
        PALETTE_TABLE=palette_fallback_table(),
    )
    assert a == b
