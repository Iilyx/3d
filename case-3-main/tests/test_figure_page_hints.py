"""C10: estimate PDF page for each figure from TeX breaks."""

from case3.tex_preview import estimate_figure_pdf_pages


def test_figure_pages_follow_newpage() -> None:
    tex = r"""
\begin{document}
Intro text.
\includegraphics{figures/cht_01.png}
\clearpage
More.
\includegraphics{figures/fig_01.png}
\newpage
Last.
\includegraphics{figures/cht_02.png}
\end{document}
"""
    pages = estimate_figure_pdf_pages(tex)
    assert pages["cht_01"] == 1
    assert pages["fig_01"] == 2
    assert pages["cht_02"] == 3


def test_figures_on_same_page_share_number() -> None:
    tex = r"""
\includegraphics{figures/cht_01.png}
\includegraphics{figures/cht_02.png}
"""
    pages = estimate_figure_pdf_pages(tex)
    assert pages["cht_01"] == pages["cht_02"] == 1
