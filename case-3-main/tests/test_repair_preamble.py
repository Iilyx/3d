"""Truncated / broken preambles must be replaced before latexmk."""

from __future__ import annotations

from case3.tex_preamble import ensure_document_preamble, preamble_looks_broken
from case3.tex_utils import finish_preamble_only_tex


def test_preamble_looks_broken_mid_usepackage() -> None:
    tex = r"""\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\usepackage{geom
\begin{document}
Hi
\end{document}
"""
    assert preamble_looks_broken(tex)


def test_ensure_rewrites_truncated_preamble_fonts() -> None:
    tex = r"""\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\usepackage{geometry}
\setmainfont{DejaVu Serif}
\setmonofont{DejaVu Mono}
\setotherlanguage{engl
\begin{document}
Текст
\end{document}
"""
    out = ensure_document_preamble(tex)
    assert r"\begin{document}" in out
    assert r"\setmonofont{DejaVu Sans Mono}" in out
    assert "DejaVu Mono}" not in out.replace("DejaVu Sans Mono", "")
    assert r"\usepackage{booktabs}" in out
    assert not preamble_looks_broken(out)


def test_finish_preamble_only_uses_clean_min_when_truncated() -> None:
    broken = r"""\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\usepackage{geom"""
    out = finish_preamble_only_tex(broken, chart_ids=["cht_01"])
    assert r"\begin{document}" in out
    assert "%CASE3_CHART:cht_01%" in out
    assert r"\usepackage{geometry}" in out
    assert "usepackage{geom\n" not in out
    assert not preamble_looks_broken(out)
