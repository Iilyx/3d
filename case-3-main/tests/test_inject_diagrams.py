"""Tests for diagram injection into LaTeX (PDF/DOCX)."""

from __future__ import annotations

from case3.inject import inject_media


def test_inject_diagram_slot_replaces_with_figure_env() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{Процесс}
Ниже приведена карта процесса.
%CASE3_DIAG:dia_01%

\section{Заключение}
Итоги отчёта.
\end{document}
"""
    status = {"dia_01": {"ok": True}}
    diagrams = [{"id": "dia_01", "title": "Путь сделки · KPI"}]
    out = inject_media(tex, [], [], status, diagrams=diagrams)

    assert r"\includegraphics[width=\linewidth,height=0.38\textheight,keepaspectratio]{figures/dia_01.png}" in out
    assert r"\caption{Путь сделки \cdot KPI}" in out or r"\caption{Путь сделки · KPI}" in out
    assert r"\label{dia:dia_01}" in out
    assert r"\begin{figure}" in out
    assert "%CASE3_DIAG" not in out


def test_inject_diagram_slot_inside_figure() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\begin{figure}[H]
\centering
%CASE3_DIAG:dia_01%
\caption{Существующая подпись}
\end{figure}
\end{document}
"""
    status = {"dia_01": {"ok": True}}
    diagrams = [{"id": "dia_01", "title": "Карта"}]
    out = inject_media(tex, [], [], status, diagrams=diagrams)

    assert out.count(r"\begin{figure}") == 1
    assert r"\includegraphics[width=\linewidth,height=0.38\textheight,keepaspectratio]{figures/dia_01.png}" in out
    assert r"\caption{Существующая подпись}" in out


def test_inject_diagram_fallback_before_conclusion() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{Введение}
Текст введения.

\section{Заключение}
Итоги отчёта.
\end{document}
"""
    status = {"dia_01": {"ok": True}}
    diagrams = [{"id": "dia_01", "title": "Архитектура процесса"}]
    out = inject_media(tex, [], [], status, diagrams=diagrams)

    assert r"\includegraphics[width=\linewidth,height=0.38\textheight,keepaspectratio]{figures/dia_01.png}" in out
    # Must appear before \section{Заключение}
    diag_pos = out.find(r"figures/dia_01.png")
    conclusion_pos = out.find(r"\section{Заключение}")
    assert diag_pos != -1
    assert conclusion_pos != -1
    assert diag_pos < conclusion_pos


def test_inject_diagram_strips_when_status_failed() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{Процесс}
%CASE3_DIAG:dia_01%
\section{Заключение}
\end{document}
"""
    status = {"dia_01": {"ok": False, "error": "timeout"}}
    diagrams = [{"id": "dia_01", "title": "Схема"}]
    out = inject_media(tex, [], [], status, diagrams=diagrams)

    assert "dia_01" not in out
    assert r"\includegraphics" not in out
    assert r"\begin{figure}" not in out


def test_rewrites_bare_dia_path_when_ok() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\begin{figure}[H]
\centering
\includegraphics[width=\linewidth]{dia_01.png}
\caption{Diagram}
\end{figure}
\end{document}
"""
    status = {"dia_01": {"ok": True}}
    diagrams = [{"id": "dia_01", "title": "Diagram"}]
    out = inject_media(tex, [], [], status, diagrams=diagrams)
    assert r"\includegraphics[width=\linewidth,height=0.38\textheight,keepaspectratio]{figures/dia_01.png}" in out
    assert "{dia_01.png}" not in out

