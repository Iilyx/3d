"""Unclosed \\section{…} → Runaway argument / \\@xdblarg (latexmk exit 12)."""

from case3.tex_preamble import ensure_document_preamble
from case3.tex_prose import fix_unclosed_heading_args


def test_unclosed_subsection_before_figure() -> None:
    """Windows desk failure signature: title then \\begin{figure} swallowed into arg."""
    raw = (
        r"\subsection{4.3. Сельское хозяйство и AI"
        "\n"
        r"\begin{figure}[H]"
        "\n"
        r"\includegraphics{figures/cht_01.png}"
        "\n"
        r"\end{figure}"
        "\n"
    )
    fixed = fix_unclosed_heading_args(raw)
    assert r"\subsection{4.3. Сельское хозяйство и AI}" in fixed
    assert r"\begin{figure}[H]" in fixed
    # Closing brace must sit before the float, not at EOF.
    title_end = fixed.index(r"AI}")
    fig = fixed.index(r"\begin{figure}")
    assert title_end < fig


def test_unclosed_section_at_eof() -> None:
    fixed = fix_unclosed_heading_args(r"\section{Введение")
    assert fixed == r"\section{Введение}"


def test_balanced_heading_untouched() -> None:
    raw = r"\subsection{4.3. Сельское хозяйство и AI}" + "\n" + r"Текст."
    assert fix_unclosed_heading_args(raw) == raw


def test_section_with_optional_short_title() -> None:
    raw = r"\section[Кратко]{Полный заголовок}" + "\n" + "ok\n"
    assert fix_unclosed_heading_args(raw) == raw


def test_ensure_document_preamble_closes_heading() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\subsection{4.3. Сельское хозяйство и AI
\begin{figure}[H]
\end{figure}
\end{document}
""".replace("###", r"\subsection")
    out = ensure_document_preamble(tex)
    assert (
        r"\subsection{4.3. Сельское хозяйство и~AI}" in out
        or r"\subsection{4.3. Сельское хозяйство и AI}" in out
    )
    assert out.index(r"AI}") < out.index(r"\begin{figure}")
