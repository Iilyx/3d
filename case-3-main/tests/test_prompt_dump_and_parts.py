"""system_tex parts compose + CASE3_DUMP_PROMPTS + scaffold smoke."""

from __future__ import annotations

from pathlib import Path

import pytest

from case3 import prompts
from case3.generate import (
    SOURCE_BEGIN,
    build_continuation_prompt,
    build_user_prompt,
    generate_document,
    load_system_prompt,
)


def test_system_tex_parts_all_exist() -> None:
    root = prompts.prompt_dir()
    for rel in prompts.PROMPT_COMPOSITES["system_tex"]:
        assert (root / rel).is_file(), rel


def test_system_tex_composed_has_every_part_heading() -> None:
    text = prompts.load(
        "system_tex",
        MAX_IMAGES=1,
        MAX_CHARTS=2,
        MAX_DIAGRAMS=1,
        PALETTE_TABLE="| x |",
    )
    for needle in (
        "# Role",
        "# Output format",
        "# Chart types",
        "# When to add charts",
        "Mermaid",
        "# Hard rules",
        "| x |",
    ):
        assert needle in text
    assert "{{MAX_CHARTS}}" not in text
    assert "{{PALETTE_TABLE}}" not in text


def test_manifest_mentions_parts_tex() -> None:
    man = (prompts.prompt_dir() / "MANIFEST.md").read_text(encoding="utf-8")
    assert "parts/tex" in man
    assert "CASE3_DUMP_PROMPTS" in man


def test_dump_prompts_writes_when_env_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CASE3_DUMP_PROMPTS", raising=False)
    assert prompts.dump_prompts(tmp_path, system="S", user="U") is None
    monkeypatch.setenv("CASE3_DUMP_PROMPTS", "1")
    out = prompts.dump_prompts(
        tmp_path, system="SYS", user="USR", continuation="CONT"
    )
    assert out is not None
    assert (out / "system.md").read_text(encoding="utf-8") == "SYS"
    assert (out / "user.md").read_text(encoding="utf-8") == "USR"
    assert (out / "continuation.md").read_text(encoding="utf-8") == "CONT"


def test_generate_dry_run_dumps_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CASE3_DUMP_PROMPTS", "true")
    src = tmp_path / "src.txt"
    src.write_text("Выручка 10 млн в 2024\n", encoding="utf-8")
    out = tmp_path / "out" / "doc.tex"
    generate_document(src, out_tex=out, intent="Короткий отчёт", dry_run=True)
    used = out.parent / "prompts_used"
    assert (used / "system.md").is_file()
    assert (used / "user.md").is_file()
    assert "LaTeX" in (used / "system.md").read_text(encoding="utf-8")
    assert SOURCE_BEGIN in (used / "user.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "intent,source",
    [
        ("Сделай отчёт с графиком", "Продажи: 2023 — 10, 2024 — 18"),
        ("Презентация без фото", "Шаги: заявка → проверка → отгрузка"),
        ("Только таблицы", "A B\n1 2\n3 4"),
    ],
)
def test_prompt_scaffold_smoke(intent: str, source: str) -> None:
    """No LLM — assert scaffolds stay coherent for typical intents."""
    system = load_system_prompt(max_images=2, max_charts=2, max_diagrams=1)
    user = build_user_prompt(
        intent=intent,
        source=source,
        max_images=2,
        max_charts=2,
        max_diagrams=1,
    )
    cont = build_continuation_prompt(
        partial='{"charts":[{"id":"cht_01"',
        source=source,
        max_charts=2,
    )
    assert "```json" in system or "json" in system.lower()
    assert "bar" in system and "donut" in system
    assert intent.split()[0] in user or intent in user
    assert source[:8] in user
    assert SOURCE_BEGIN in user and SOURCE_BEGIN in cont
    assert "TRUNCATED" in cont
