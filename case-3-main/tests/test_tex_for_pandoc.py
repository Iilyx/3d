"""Pandoc must not see Liber Y wrap columns."""

from case3.tex_preamble import tex_for_pandoc


def test_tex_for_pandoc_rewrites_y_to_x() -> None:
    src = r"""
\newcolumntype{Y}{>{\hspace{0pt}\raggedright\arraybackslash}X}
\begin{tabularx}{\textwidth}{YYYYY}
\toprule
A & B & C & D & E \\
\bottomrule
\end{tabularx}
"""
    out = tex_for_pandoc(src)
    assert r"\newcolumntype{Y}" not in out
    assert "{XXXXX}" in out.replace(" ", "")
    assert "YYYYY" not in out.replace(" ", "")
