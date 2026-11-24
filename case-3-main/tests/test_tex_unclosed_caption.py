"""Unclosed \\caption{…} / figure → Gin@iii + figure ended by \\end{document}."""

from case3.tex_preamble import ensure_document_preamble
from case3.tex_prose import fix_unclosed_caption_args, fix_unclosed_float_envs


def test_unclosed_caption_before_end_figure() -> None:
    raw = (
        "\\begin{figure}[H]\n"
        "  \\includegraphics[width=0.9\\textwidth]{figures/fig_01.png}\n"
        "  \\caption{Современный завод с роботизированной линией\n"
        "\\end{figure}\n"
    )
    fixed = fix_unclosed_caption_args(raw)
    assert r"\caption{Современный завод с роботизированной линией}" in fixed
    assert fixed.index("линией}") < fixed.index(r"\end{figure}")


def test_unclosed_caption_blank_line_then_eof() -> None:
    """Blank line inside caption → Paragraph ended / Gin@iii cascade."""
    raw = (
        "\\begin{figure}[H]\n"
        "  \\includegraphics{figures/fig_01.png}\n"
        "  \\caption{Современный завод с роботизиров\n"
        "\n"
        "\\end{document}\n"
    )
    fixed = fix_unclosed_caption_args(raw)
    assert "роботизиров}" in fixed
    assert fixed.index("роботизиров}") < fixed.index("\n\n")


def test_missing_end_figure_before_end_document() -> None:
    raw = (
        "\\begin{document}\n"
        "\\begin{figure}[H]\n"
        "  \\includegraphics{figures/fig_01.png}\n"
        "  \\caption{Завод}\n"
        "\\end{document}\n"
    )
    fixed = fix_unclosed_float_envs(raw)
    assert r"\end{figure}" in fixed
    assert fixed.index(r"\end{figure}") < fixed.index(r"\end{document}")


def test_ensure_heals_caption_and_figure_desk_signature() -> None:
    """Desk log: runaway \\caption + figure ended by \\end{document}."""
    tex = r"""\documentclass{article}
\begin{document}
\begin{figure}[H]
  \includegraphics[width=0.9\textwidth]{figures/fig_01.png}
  \caption{Современный завод с роботизированной линией
\end{document}
"""
    out = ensure_document_preamble(tex)
    assert (
        r"\caption{Современный завод с~роботизированной линией}" in out
        or r"\caption{Современный завод с роботизированной линией}" in out
    )
    assert r"\end{figure}" in out
    assert out.index(r"\end{figure}") < out.index(r"\end{document}")
