"""Tests for Russian typography hardening (non-breaking spaces ~ for prepositions and units)."""

from __future__ import annotations

from case3.tex_prose import harden_russian_typography


def test_harden_prepositions() -> None:
    tex = (
        r"\documentclass{article}" "\n"
        r"\begin{document}" "\n"
        r"В первом квартале выручка выросла на 15 процентов и достигла максимума к концу года." "\n"
        r"\end{document}"
    )
    res = harden_russian_typography(tex)
    assert "В~первом" in res
    assert "на~15" in res
    assert "и~достигла" in res
    assert "к~концу" in res


def test_harden_numbers_and_units() -> None:
    tex = (
        r"\documentclass{article}" "\n"
        r"\begin{document}" "\n"
        r"Объём рынка составил 100 млн руб., а чистая прибыль за 2026 г. превысила 5 млрд руб." "\n"
        r"\end{document}"
    )
    res = harden_russian_typography(tex)
    assert "100~млн~руб." in res
    assert "2026~г." in res
    assert "5~млрд~руб." in res
    assert "за~2026" in res
    assert "а~чистая" in res


def test_protects_tex_macros_and_math() -> None:
    tex = (
        r"\documentclass{article}" "\n"
        r"\usepackage{amsmath}" "\n"
        r"\begin{document}" "\n"
        r"\section{Введение в анализ данных}" "\n"
        r"\includegraphics[width=0.8\textwidth]{figures/fig_01.png}" "\n"
        r"Формула $x \in A$ и $E = mc^2$ не должна меняться." "\n"
        r"\label{sec:vvedenie}" "\n"
        r"\end{document}"
    )
    res = harden_russian_typography(tex)
    assert r"\usepackage{amsmath}" in res
    assert r"\includegraphics[width=0.8\textwidth]{figures/fig_01.png}" in res
    assert "$x \\in A$" in res
    assert "$E = mc^2$" in res
    assert r"\label{sec:vvedenie}" in res
    assert "Введение в~анализ" in res or "Введение в анализ" in res


def test_table_cells_avoid_nonbreaking_unit_chains_and_double_periods() -> None:
    tex = (
        r"\documentclass{article}" "\n"
        r"\begin{document}" "\n"
        r"Выручка составила 412 850,4 тыс. руб.. Итог по региону." "\n"
        r"\begin{tabularx}{\textwidth}{lY}" "\n"
        r"Показатель & \textbf{412 850,4 тыс. руб.} \\" "\n"
        r"\end{tabularx}" "\n"
        r"\end{document}"
    )
    res = harden_russian_typography(tex)
    # Table cell must NOT glue 412 850,4~тыс.~руб. with ~ inside narrow table columns
    assert r"\textbf{412 850,4 тыс. руб.}" in res
    # Accidental double period after руб.. must collapse to single period
    assert ".." not in res
