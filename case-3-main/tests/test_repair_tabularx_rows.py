"""LLM wide tables: cell-per-line bodies must become real \\\\ rows."""

from __future__ import annotations

from case3.tex_preamble import ensure_document_preamble, repair_tabularx_row_breaks


_BROKEN = r"""
\begin{tabularx}{\textwidth}{lXXXX}\raggedright\arraybackslash}p{2.4cm} >{\raggedright\arraybackslash}X}
\toprule
Инструмент & Лицензия & Язык / API & Типичный объём & Ограничения экспорта \\
\midrule
Excel &
Проприетарная &
VBA / Office Scripts &
До миллионов строк &
\texttt{xlsx}, \texttt{csv} \\

Python pandas &
BSD &
Python &
Память машины &
\texttt{csv}, \texttt{parquet} \\
\bottomrule
\end{tabularx}
"""


def test_repair_joins_cell_per_line_into_rows() -> None:
    out = repair_tabularx_row_breaks(_BROKEN)
    assert "Excel &\nПроприетарная" not in out
    assert r"Excel & Проприетарная & VBA / Office Scripts & До миллионов строк &" in out
    assert out.count(r"\\") >= 3  # header + 2 data rows
    assert r"Python pandas & BSD & Python &" in out


def test_repair_idempotent_on_healthy_table() -> None:
    good = r"""
\begin{tabularx}{\textwidth}{lXX}
\toprule
A & B & C \\
\midrule
1 & 2 & 3 \\
\bottomrule
\end{tabularx}
"""
    assert repair_tabularx_row_breaks(good).replace(" ", "") == good.replace(" ", "")


def test_ensure_preamble_strips_colspec_junk_and_repairs_rows() -> None:
    tex = (
        r"\documentclass{article}"
        r"\usepackage{tabularx,booktabs,polyglossia,fontspec}"
        r"\begin{document}"
        + _BROKEN
        + r"\end{document}"
    )
    out = ensure_document_preamble(tex)
    # Wrapping Y columntype in preamble is OK; junk after colspec must stay gone.
    between = out.split(r"\begin{tabularx}", 1)[1].split(r"\toprule", 1)[0]
    assert r"\raggedright" not in between
    assert r"p{2.4cm}" not in out.split(r"\begin{tabularx}", 1)[-1].split(r"\toprule", 1)[0]
    assert "Excel &\nПроприетарная" not in out
    assert r"Excel & Проприетарная &" in out
