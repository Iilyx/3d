"""Sparse (charts-only) TeX must be filled with Source prose."""

from __future__ import annotations

from case3.generate import fill_sparse_tex_with_source, tex_body_is_sparse
from case3.tex_preamble import ensure_document_preamble


def test_sparse_detection() -> None:
    sparse = r"""\documentclass{article}
\begin{document}
\maketitle
%CASE3_CHART:cht_01%
\end{document}
"""
    assert tex_body_is_sparse(sparse)
    rich = sparse.replace(
        "%CASE3_CHART:cht_01%",
        r"\section{Введение} Население республики составило девять миллионов человек.",
    )
    assert not tex_body_is_sparse(rich)
    headings_only = r"""\documentclass{article}
\begin{document}
\maketitle
\section{Демографический сдвиг в Республике Беларусь за пять лет}
\section{Естественное движение и миграционный обмен населения}
%CASE3_CHART:cht_01%
\end{document}
"""
    assert tex_body_is_sparse(headings_only)


def test_fill_inserts_source_and_keeps_slots() -> None:
    sparse = r"""\documentclass{article}
\begin{document}
\maketitle
%CASE3_CHART:cht_01%
%CASE3_CHART:cht_02%
\end{document}
"""
    source = (
        "Население республики в две тысячи девятнадцатом году "
        "составило девять тысяч четыреста семьдесят тысяч человек.\n\n"
        "Рождаемость снизилась до девяти промилле."
    )
    out = fill_sparse_tex_with_source(
        sparse,
        source,
        chart_ids=["cht_01", "cht_02"],
        figure_ids=[],
    )
    assert "Население" in out
    assert "%CASE3_CHART:cht_01%" in out
    assert "%CASE3_CHART:cht_02%" in out
    assert r"\end{document}" in out
    assert not tex_body_is_sparse(out)


def test_fill_converts_markdown_tables_with_blank_lines() -> None:
    """Regression: Source fill left raw `| col |` pipes in PDF (091453Z)."""
    sparse = r"""\documentclass{article}
\begin{document}
\maketitle
%CASE3_CHART:cht_01%
\end{document}
"""
    source = (
        "## Данные\n\n"
        "| Год | Численность |\n\n"
        "| :--- | :--- |\n\n"
        "| 2019 | 9470 |\n\n"
        "| 2020 | 9446 |\n"
    )
    out = fill_sparse_tex_with_source(
        sparse, source, chart_ids=["cht_01"], figure_ids=[]
    )
    assert r"\begin{tabularx}" in out
    assert "| 2019 |" not in out
    assert "9470" in out
    # charts not inserted mid-table
    tx = out.find(r"\begin{tabularx}")
    te = out.find(r"\end{tabularx}")
    slot = out.find("%CASE3_CHART:cht_01%")
    assert tx < te
    assert slot < tx or slot > te


def test_fill_converts_markdown_and_fonts_survive_preamble() -> None:
    sparse = r"""\documentclass[a4paper,12pt]{article}
\usepackage{graphicx}
\begin{document}
\maketitle
%CASE3_CHART:cht_01%
\end{document}
"""
    source = (
        "Понял вас. Ниже представлен текст.\n\n"
        "# Демография Беларуси\n\n"
        "## Введение\n\n"
        "Население снизилось до **9,33** млн.\n\n"
        "| Год | Численность |\n"
        "| :--- | :--- |\n"
        "| 2019 | 9470 |\n"
        "| 2020 | 9446 |\n"
    )
    out = fill_sparse_tex_with_source(
        sparse, source, chart_ids=["cht_01"], figure_ids=[]
    )
    out = ensure_document_preamble(out)
    assert "Понял вас" not in out
    assert r"\section{Введение}" in out
    assert r"\begin{tabularx}" in out
    assert r"\setmainfont{DejaVu Serif}" in out
    assert "Демография" in out  # title
    assert "%CASE3_CHART:cht_01%" in out
