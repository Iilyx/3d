"""LLM often leaks \\includegraphics{fig_XX.png} without figures/ — harden must fix."""

from __future__ import annotations

from case3.inject import inject_media


def test_rewrites_bare_fig_path_when_ok() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\begin{figure}[H]
\centering
\includegraphics[width=\linewidth]{fig_02.png}
\caption{Photo}
\end{figure}
\end{document}
"""
    status = {"fig_02": {"ok": True, "kind": "figure"}}
    figures = [{"id": "fig_02", "caption": "Photo", "width": r"0.85\textwidth"}]
    out = inject_media(tex, figures, [], status)
    assert r"\includegraphics[width=\linewidth]{figures/fig_02.png}" in out
    assert "{fig_02.png}" not in out


def test_strips_failed_chart_includegraphics_and_empty_figure() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\begin{figure}[H]
\centering
\includegraphics[width=0.85\textwidth]{cht_01.png}
\caption{Bad chart}
\end{figure}
Prose stays.
\end{document}
"""
    status = {"cht_01": {"ok": False, "error": "timeout", "kind": "chart"}}
    charts = [{"id": "cht_01", "caption": "Bad chart", "width": r"0.85\textwidth"}]
    out = inject_media(tex, [], charts, status)
    assert r"\includegraphics" not in out
    assert r"\begin{figure}" not in out
    assert "Prose stays." in out


def test_leaves_correct_figures_path_unchanged() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\includegraphics[width=0.85\textwidth]{figures/fig_01.png}
\end{document}
"""
    status = {"fig_01": {"ok": True, "kind": "figure"}}
    figures = [{"id": "fig_01", "caption": "A", "width": r"0.85\textwidth"}]
    out = inject_media(tex, figures, [], status)
    assert out.count(r"\includegraphics[width=0.85\textwidth]{figures/fig_01.png}") == 1


def test_strips_diagram_includegraphics_never_in_pdf() -> None:
    """Diagrams are Liber UI-only (ADR-0007); model still leaks dia_*.png into TeX."""
    tex = r"""\documentclass{article}
\begin{document}
See flow.
\begin{figure}[H]
\centering
\includegraphics[width=0.85\textwidth]{dia_0.png}
\caption{Schema}
\end{figure}
Done.
\end{document}
"""
    out = inject_media(tex, [], [], {})
    assert "dia_0" not in out
    assert r"\includegraphics" not in out
    assert r"\begin{figure}" not in out
    assert "See flow." in out
    assert "Done." in out
