"""Deck/report TeX must use numbered \\section, not \\section*."""

from case3.tex_preamble import ensure_document_preamble
from case3.tex_prose import unstar_headings


def test_unstar_section_and_subsection() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section*{Стратегия}
Текст.
\subsection*{Промышленность}
Ещё.
\end{document}
"""
    out = unstar_headings(tex)
    assert r"\section*{Стратегия}" not in out
    assert r"\section{Стратегия}" in out
    assert r"\subsection*{Промышленность}" not in out
    assert r"\subsection{Промышленность}" in out


def test_ensure_preamble_unstars() -> None:
    tex = r"""\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\begin{document}
\section*{Титул}
Ok.
\end{document}
"""
    out = ensure_document_preamble(tex)
    assert r"\section*{Титул}" not in out
    assert r"\section{Титул}" in out
