"""system_tex omits diagram/figure/usr parts when budgets are off."""

from __future__ import annotations

from case3.generate import load_system_prompt
from case3.prompts import load, system_tex_part_rels

_DIAG_NEEDLE = "Mermaid `diagrams` (Liber UI & PDF/DOCX)"
_FIG_NEEDLE = "Image API `figures` (photos / illustrations)"
_USR_NEEDLE = "Пользовательские фото (`usr_01`"


def test_system_tex_part_rels_omits_diagrams_and_figures() -> None:
    rels = system_tex_part_rels(max_images=0, max_diagrams=0, has_user_photos=False)
    joined = "\n".join(rels)
    assert "04_diagrams.md" not in joined
    assert "03b_figures.md" not in joined
    assert "03c_user_photos.md" not in joined
    assert "03_when_media.md" in joined
    assert "05_hard_rules.md" in joined


def test_system_tex_part_rels_includes_when_budgets_on() -> None:
    rels = system_tex_part_rels(max_images=2, max_diagrams=1, has_user_photos=True)
    joined = "\n".join(rels)
    assert "04_diagrams.md" in joined
    assert "03b_figures.md" in joined
    assert "03c_user_photos.md" in joined


def test_load_omits_diagram_and_figure_sections() -> None:
    text = load(
        "system_tex",
        MAX_IMAGES=0,
        MAX_CHARTS=3,
        MAX_DIAGRAMS=0,
        PALETTE_TABLE="| p |",
        has_user_photos=False,
    )
    assert _DIAG_NEEDLE not in text
    assert _FIG_NEEDLE not in text
    assert _USR_NEEDLE not in text
    assert "# Chart types" in text
    assert "# When to add charts" in text
    assert "# Hard rules" in text


def test_load_includes_diagrams_figures_usr_when_on() -> None:
    text = load(
        "system_tex",
        MAX_IMAGES=2,
        MAX_CHARTS=2,
        MAX_DIAGRAMS=2,
        PALETTE_TABLE="| p |",
        has_user_photos=True,
    )
    assert _DIAG_NEEDLE in text
    assert _FIG_NEEDLE in text
    assert _USR_NEEDLE in text


def test_usr_section_without_generated_images() -> None:
    text = load(
        "system_tex",
        MAX_IMAGES=0,
        MAX_CHARTS=1,
        MAX_DIAGRAMS=0,
        PALETTE_TABLE="| p |",
        has_user_photos=True,
    )
    assert _FIG_NEEDLE not in text
    assert _USR_NEEDLE in text


def test_load_system_prompt_passes_user_photos_flag() -> None:
    bare = load_system_prompt(max_images=0, max_charts=2, max_diagrams=0)
    with_usr = load_system_prompt(
        max_images=0, max_charts=2, max_diagrams=0, has_user_photos=True
    )
    assert _USR_NEEDLE not in bare
    assert _USR_NEEDLE in with_usr
