"""Gold skeleton skips full preamble; MANIFEST lists inline LLM prompts."""

from __future__ import annotations

from case3.prompts import prompt_dir


def test_full_minimal_gold_skips_full_preamble_list() -> None:
    tex = (prompt_dir() / "gold" / "full_minimal.tex").read_text(encoding="utf-8")
    assert r"\documentclass" in tex
    assert r"\begin{document}" in tex
    assert r"\section{Введение}" in tex
    # Shared package list lives in Hard rules — don't re-dump it in gold.
    assert r"\usepackage{fontspec}" not in tex
    assert r"\usepackage{booktabs}" not in tex
    assert len(tex) < 500


def test_manifest_documents_inline_llm_prompts() -> None:
    man = (prompt_dir() / "MANIFEST.md").read_text(encoding="utf-8")
    for needle in (
        "chart_edit",
        "schema_redraw",
        "latex_recovery",
        "image_prompt",
        "DIAGRAM_COLOR_TABLE",
    ):
        assert needle in man, f"MANIFEST missing orphan note: {needle}"
