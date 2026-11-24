"""Markdown ** leaked into TeX breaks microtype (MT@prot runaway)."""

from case3.tex_prose import fix_markdown_bold_leaks
from case3.tex_preamble import ensure_document_preamble


def test_textbf_closed_with_markdown_stars() -> None:
    raw = (
        r"\item \textbf{Что из любимого ты почти никогда не включаешь?**"
        "\n  Далее текст.\n"
    )
    fixed = fix_markdown_bold_leaks(raw)
    assert r"\textbf{Что из любимого ты почти никогда не включаешь?}" in fixed
    assert "**" not in fixed


def test_standalone_markdown_bold() -> None:
    raw = "Текст с **жирным** словом."
    assert r"\textbf{жирным}" in fix_markdown_bold_leaks(raw)


def test_ensure_document_preamble_applies_fix() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\item \textbf{Вопрос?**
\end{document}
"""
    out = ensure_document_preamble(tex)
    assert r"\textbf{Вопрос?}" in out
    assert "**" not in out


def test_unclosed_textbf_before_next_item() -> None:
    from case3.tex_prose import fix_unclosed_textbf

    raw = (
        "\\begin{enumerate}\n"
        "  \\item \\textbf{Есть ли артисты или альбомы, которые вы слушаете из "
        "ностальгии, личной истории\n"
        "        или принципиально не обсуждаете?\n"
        "  \\item \\textbf{Что вы хотите получить от этого разбора:} точное "
        "самозеркало?\n"
        "\\end{enumerate}\n"
    )
    fixed = fix_unclosed_textbf(raw)
    # First textbf must close before the second \item
    first = fixed.split(r"\item")[1]
    assert first.count("{") == first.count("}")
    assert r"не обсуждаете?}" in fixed
    assert r"\textbf{Что вы хотите" in fixed


def test_ensure_closes_unclosed_textbf() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\begin{enumerate}
\item \textbf{Вопрос без закрытия
\item \textbf{Второй:} ок
\end{enumerate}
\end{document}
"""
    out = ensure_document_preamble(tex)
    assert r"закрытия}" in out
