"""D12: orphan & / booktabs rules outside tabular must not reach latexmk."""

from __future__ import annotations

from case3.tex_preamble import (
    ensure_document_preamble,
    repair_tabularx_row_breaks,
    strip_orphan_table_markup,
)


def test_ampersand_outside_tabular_escaped() -> None:
    src = "Сравнение A & B в тексте.\n"
    out = strip_orphan_table_markup(src)
    assert r"A \& B" in out
    assert "A & B" not in out


def test_midrule_outside_tabular_removed() -> None:
    src = "Проза.\n\\midrule\nЕщё проза.\n"
    out = strip_orphan_table_markup(src)
    assert r"\midrule" not in out
    assert "Проза." in out
    assert "Ещё проза." in out


def test_inside_tabularx_untouched() -> None:
    src = (
        r"\begin{tabularx}{\textwidth}{lX}" + "\n"
        r"A & B \\" + "\n"
        r"\midrule" + "\n"
        r"1 & 2 \\" + "\n"
        r"\end{tabularx}" + "\n"
    )
    assert strip_orphan_table_markup(src) == src


def test_cell_per_line_two_amp_ends_still_repairs() -> None:
    """Two-column cell-per-line (amp_ends=2) must still join into rows."""
    broken = r"""
\begin{tabularx}{\textwidth}{lX}
\toprule
A &
B \\
\midrule
1 &
2 \\
\bottomrule
\end{tabularx}
"""
    out = repair_tabularx_row_breaks(broken)
    assert "A &\nB" not in out
    assert r"A & B \\" in out or "A & B" in out.split(r"\midrule", 1)[0]


def test_ensure_preamble_strips_orphan_and_repairs() -> None:
    tex = (
        r"\documentclass{article}"
        r"\usepackage{tabularx,booktabs,polyglossia,fontspec}"
        r"\begin{document}"
        "Факт A & B.\n"
        r"\midrule" + "\n"
        r"\begin{tabularx}{\textwidth}{lXX}" + "\n"
        r"\toprule" + "\n"
        "X &\nY &\nZ \\\\\n"
        r"\bottomrule" + "\n"
        r"\end{tabularx}" + "\n"
        r"\end{document}"
    )
    out = ensure_document_preamble(tex)
    assert r"A \& B" in out
    # orphan midrule before table gone
    pre = out.split(r"\begin{tabularx}", 1)[0]
    assert r"\midrule" not in pre
    assert "X &\nY" not in out
