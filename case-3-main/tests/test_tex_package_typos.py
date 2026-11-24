"""LLM package typos and broken tabularx markup must be repaired."""

from __future__ import annotations

from case3.tex_preamble import ensure_document_preamble


def test_titlespec_rewritten_to_titlesec() -> None:
    tex = r"""\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\usepackage{titlespec}
\usepackage{titlesec}
\begin{document}
Hi
\end{document}
"""
    out = ensure_document_preamble(tex)
    assert r"\usepackage{titlespec}" not in out
    assert r"\usepackage{titlesec}" in out


def test_tabularx_colspec_junk_after_brace_removed() -> None:
    tex = r"""\documentclass[a4paper,12pt]{article}
\begin{document}
\begin{tabularx}{\textwidth}{YYY}X r X}
\toprule
A & B & C \\
\midrule
1 & 2 & 3 \\
\bottomrule
\end{tabularx}
\end{document}
"""
    out = ensure_document_preamble(tex)
    assert r"{YYY}X r X}" not in out
    assert r"\begin{tabularx}{\textwidth}{YYY}" in out.replace(" ", "") or (
        r"\begin{tabularx}{\textwidth}{YYY}" in out
    )


def test_tabularx_colspec_arraybackslash_junk_stripped() -> None:
    tex = r"""\documentclass[a4paper,12pt]{article}
\begin{document}
\begin{tabularx}{\textwidth}{lXXXX}\raggedright\arraybackslash}p{2.4cm} >{\raggedright\arraybackslash}X}
\toprule
A & B & C & D & E \\
\midrule
1 & 2 & 3 & 4 & 5 \\
\bottomrule
\end{tabularx}
\end{document}
"""
    out = ensure_document_preamble(tex)
    assert r"\raggedright" not in out.split(r"\begin{tabularx}", 1)[1].split(
        r"\toprule", 1
    )[0]
    assert "{YYYYY}" in out.replace(" ", "")


def test_tabularx_closed_with_tabular_fixed() -> None:
    tex = r"""\documentclass[a4paper,12pt]{article}
\begin{document}
\begin{tabularx}{\textwidth}{lX}
\toprule
A & B \\
\bottomrule
\end{tabular}
\end{document}
"""
    out = ensure_document_preamble(tex)
    assert out.count(r"\begin{tabularx}") == out.count(r"\end{tabularx}")
    assert r"\end{tabular}" not in out.split(r"\begin{tabularx}")[1].split(
        r"\end{tabularx}"
    )[0]
