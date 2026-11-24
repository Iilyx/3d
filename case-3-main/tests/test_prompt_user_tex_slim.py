"""user_tex stays a short checklist — hard rules live in system_tex."""

from __future__ import annotations

from case3.generate import SOURCE_BEGIN, build_user_prompt
from case3.prompts import prompt_dir

# Echo of system hard rules that should not bloat the user message.
_ECHO_FORBIDDEN = (
    r"\begin{landscape}",
    "Footnotes",
    "case-3/case3",
    "setspace/fancyhdr",
    "tabularx{\\textwidth}",
)


def test_user_tex_md_is_slim_scaffold() -> None:
    md = (prompt_dir() / "user_tex.md").read_text(encoding="utf-8")
    assert "{{INTENT_BLOCK}}" in md
    assert "{{SOURCE}}" in md
    assert "{{DIAGRAM_COLOR_TABLE}}" in md
    assert "## Limits" in md
    assert "charts → diagrams → figures" in md or "charts" in md
    for needle in _ECHO_FORBIDDEN:
        assert needle not in md, f"echo hard-rule still in user_tex: {needle}"
    # Target: roughly half of the pre-slim ~2.2k body (scaffold alone).
    assert len(md) < 1600, f"user_tex.md still too long: {len(md)} chars"


def test_build_user_prompt_keeps_essentials() -> None:
    text = build_user_prompt(
        intent="Сделай отчёт",
        source="Выручка 10",
        max_images=0,
        max_charts=2,
        max_diagrams=1,
    )
    assert "## Intent" in text
    assert "Сделай отчёт" in text
    assert SOURCE_BEGIN in text
    assert "Выручка 10" in text
    assert "max_charts" in text.lower() or "CASE3_MAX_CHARTS" in text
    assert "Liber diagram colors" in text
