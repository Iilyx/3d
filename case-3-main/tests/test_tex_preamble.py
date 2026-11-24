"""Tests for tex_preamble table wrapping, landscape detection, and Pandoc cleanup."""

from case3.tex_preamble import (
    ensure_document_preamble,
    fix_tabularx_colspec_junk,
    harden_tabularx_wrap_cols,
    maybe_landscape_wide_tables,
    tex_for_pandoc,
)


def test_fix_tabularx_colspec_junk_preserves_nested_braces_in_colspec() -> None:
    tex = (
        r"\begin{tabularx}{\textwidth}{@{}l >{\raggedright\arraybackslash}X p{2.4cm} r@{}}"
        "X r}garbage"
        "\n"
        r"\toprule"
        "\nA & B & C & D \\\\\n"
        r"\bottomrule"
        "\n"
        r"\end{tabularx}"
    )
    out = fix_tabularx_colspec_junk(tex)
    assert r"{@{}l >{\raggedright\arraybackslash}X p{2.4cm} r@{}}" in out
    assert "garbage" not in out
    assert "X r}" not in out


def test_six_column_tabularx_gets_landscape_after_y_wrap_rewrite() -> None:
    tex = r"""
\documentclass{article}
\usepackage{tabularx}
\usepackage{booktabs}
\usepackage{pdflscape}
\begin{document}
\begin{table}[htbp]
\begin{tabularx}{\textwidth}{lrrrrr}
\toprule
Регион & Факт & План & Доля & Рост & Итог \\
\midrule
Москва & 10 & 9 & 50 & 11 & 100 \\
\bottomrule
\end{tabularx}
\end{table}
\end{document}
"""
    wrapped = harden_tabularx_wrap_cols(tex)
    assert "{YYYYYY}" in wrapped
    landscaped = maybe_landscape_wide_tables(wrapped)
    assert r"\begin{landscape}" in landscaped
    assert r"\end{landscape}" in landscaped

    full = ensure_document_preamble(tex)
    assert r"\begin{landscape}" in full


def test_tex_for_pandoc_handles_xltabular_and_y_columns() -> None:
    src = r"""
\newcolumntype{Y}{>{\hspace{0pt}\raggedright\arraybackslash}X}
\begin{xltabular}{\textwidth}{YYY}
\toprule
A & B & C \\
\bottomrule
\end{xltabular}
"""
    out = tex_for_pandoc(src)
    assert r"\newcolumntype{Y}" not in out
    assert "YYY" not in out
    assert "xltabular" not in out
    assert r"\begin{tabularx}{\textwidth}{XXX}" in out
    assert r"\end{tabularx}" in out
