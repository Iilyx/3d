"""Chart slots inside figures must not nest another figure env."""

from __future__ import annotations

from case3.inject import inject_media


def test_chart_inside_figure_after_fig_expand() -> None:
    # Expanding fig_01 grows the string; chart offset must use post-fig text.
    tex = r"""\documentclass{article}
\begin{document}
\begin{figure}[H]
\centering
%CASE3_FIG:fig_01%
\caption{A}
\end{figure}
\begin{figure}[H]
\centering
%CASE3_CHART:cht_01%
\caption{B}
\end{figure}
\end{document}
"""
    status = {
        "fig_01": {"ok": True},
        "cht_01": {"ok": True},
    }
    figures = [{"id": "fig_01", "caption": "A", "width": r"0.85\textwidth"}]
    charts = [{"id": "cht_01", "caption": "B", "width": r"0.85\textwidth"}]
    out = inject_media(tex, figures, charts, status)
    # One includegraphics for the chart, not a nested \begin{figure} inside figure
    assert out.count(r"\begin{figure}") == 2
    assert r"\includegraphics[width=0.85\textwidth,height=0.45\textheight,keepaspectratio]{figures/cht_01.png}" in out
    assert out.count(r"\begin{figure}") == out.count(r"\end{figure}")
    # LLM already had \caption{B} — do not duplicate from meta
    assert out.count(r"\caption{B}") == 1


def test_chart_inside_figure_gets_caption_when_missing() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\begin{figure}[H]
\centering
%CASE3_CHART:cht_01%
\end{figure}
\end{document}
"""
    status = {"cht_01": {"ok": True}}
    charts = [{"id": "cht_01", "caption": "Доли по категориям", "width": r"0.85\textwidth"}]
    out = inject_media(tex, [], charts, status)
    assert r"\includegraphics" in out
    assert (
        r"\caption{Доли по~категориям}" in out
        or r"\caption{Доли по категориям}" in out
    )
    assert r"\label{chart:cht_01}" in out
    assert out.count(r"\begin{figure}") == 1
