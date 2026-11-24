"""Wide tabular → tabularx rewriting + rule cleanup."""

from __future__ import annotations

from case3.tex_preamble import (
    ensure_document_preamble,
    ensure_font_aliases,
    harden_tabularx_colcount,
    harden_tabularx_wrap_cols,
    harden_wide_tables,
)
from case3.tex_tables import harden_table_rules


def test_three_l_columns_become_tabularx() -> None:
    src = r"""
\begin{table}[H]
\begin{tabular}{l l l}
\toprule
A & B & C \\
\bottomrule
\end{tabular}
\end{table}
"""
    out = harden_wide_tables(src)
    assert r"\begin{tabularx}{\textwidth}{YYY}" in out.replace(" ", "")
    assert r"\end{tabularx}" in out
    assert r"\begin{tabular}{l l l}" not in out


def test_two_column_tabular_unchanged() -> None:
    src = r"\begin{tabular}{lr} a & 1 \\ \end{tabular}"
    assert harden_wide_tables(src) == src


def test_already_p_column_unchanged() -> None:
    src = r"\begin{tabular}{lp{0.4\textwidth}r} a & b & c \\ \end{tabular}"
    assert harden_wide_tables(src) == src


def test_tabularx_already_ok() -> None:
    src = r"\begin{tabularx}{\textwidth}{YYY} a & b & c \\ \end{tabularx}"
    assert harden_wide_tables(src) == src


def test_tabularx_with_thinspace_numbers_stays_aligned() -> None:
    """Numbers like 85\\,000 must not break colcount harden."""
    tex = r"""
\begin{tabularx}{\textwidth}{lrrrr}
\toprule
Показатель & 2019 & 2020 & 2021 & 2022 & 2023 \\
\midrule
Рождения & 85\,000 & 82\,000 & 78\,000 & 74\,000 & 72\,000 \\
\bottomrule
\end{tabularx}
"""
    out = harden_tabularx_colcount(tex)
    assert r"{YYYYYY}" in out.replace(" ", "")
    assert r"85\,000" in out


def test_tabularx_colcount_mismatch_fixed() -> None:
    src = (
        r"\begin{tabularx}{\textwidth}{lrrrr}"
        r"\toprule Показатель & 2019 & 2020 & 2021 & 2022 & 2023 \\"
        r"\midrule A & 1 & 2 & 3 & 4 & 5 \\"
        r"\bottomrule\end{tabularx}"
    )
    out = harden_tabularx_colcount(src)
    assert r"{YYYYYY}" in out.replace(" ", "")


def test_dejavu_mono_aliased() -> None:
    assert r"DejaVu Sans Mono" in ensure_font_aliases(
        r"\setmonofont{DejaVu Mono}"
    )


def test_harden_table_rules_collapses_double_hline() -> None:
    src = r"""
\begin{tabular}{ll}
\hline\hline
A & B \\
\hline\hline
1 & 2 \\
\hline\hline
\end{tabular}
"""
    out = harden_table_rules(src)
    assert r"\hline\hline" not in out.replace(" ", "")
    assert out.count(r"\hline") >= 2
    assert "A & B" in out


def test_harden_table_rules_strips_hline_after_toprule() -> None:
    src = r"\toprule\hline A & B \\\bottomrule"
    out = harden_table_rules(src)
    assert r"\toprule\hline" not in out.replace("\n", "")
    assert r"\toprule" in out


def test_ensure_document_preamble_runs_table_rule_harden() -> None:
    raw = r"""\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\begin{document}
\begin{tabular}{ll}
\hline\hline
A & 1 \\
\hline\hline
\end{tabular}
\end{document}
"""
    out = ensure_document_preamble(raw)
    assert r"\hline\hline" not in out.replace(" ", "")


def test_tabularx_wrap_cols_all_y() -> None:
    """lXXXX squeezes text cols — rewrite to wrapping Y columns."""
    src = r"""
\begin{tabularx}{\textwidth}{lXXXX}
\toprule
Инструмент & Лицензия & Язык / API & Типичный объём & Ограничения экспорта \\
\midrule
Excel & проприетарная & VBA / Office Scripts & до миллионов строк & xlsx, csv \\
\bottomrule
\end{tabularx}
"""
    out = harden_tabularx_wrap_cols(src)
    assert "{YYYYY}" in out.replace(" ", "")
    assert "{lXXXX}" not in out.replace(" ", "")


def test_ensure_preamble_injects_y_columntype() -> None:
    raw = r"""\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\begin{document}
\begin{tabularx}{\textwidth}{lXXXX}
\toprule
A & проприетарная & C & D & E \\
\bottomrule
\end{tabularx}
\end{document}
"""
    out = ensure_document_preamble(raw)
    assert r"\usepackage{array}" in out
    assert r"\newcolumntype{Y}" in out
    assert "{YYYYY}" in out.replace(" ", "")
    assert "hspace{0pt}" in out
