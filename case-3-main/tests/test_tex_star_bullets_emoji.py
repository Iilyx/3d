"""Win desk 070133: Markdown ``* `` outlines + emoji section titles."""

from case3.tex_preamble import ensure_document_preamble
from case3.tex_prose import harden_prose_lists, scrub_emoji_from_headings


def test_star_bullets_become_itemize() -> None:
    raw = (
        "Текст.\n"
        "* 1.1. Глобальный тренд.\n"
        "* 1.2. Специфика Беларуси.\n"
        "\nПосле.\n"
    )
    fixed = harden_prose_lists(raw)
    assert r"\begin{itemize}" in fixed
    assert r"\item 1.1. Глобальный тренд." in fixed
    assert r"\item 1.2. Специфика Беларуси." in fixed
    assert "* 1.1." not in fixed


def test_scrub_emoji_from_subsection() -> None:
    raw = r"\subsection{📂 БЛОК 1: СТРУКТУРА ОТЧЕТА}"
    assert scrub_emoji_from_headings(raw) == r"\subsection{БЛОК 1: СТРУКТУРА ОТЧЕТА}"


def test_ensure_heals_070133_signature() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\subsection{📂 БЛОК 1: СТРУКТУРА}
* 1.1. Тренд.
* 1.2. Специфика.
\end{document}
""".replace("###", r"\subsection")
    out = ensure_document_preamble(tex)
    assert "📂" not in out
    assert r"\subsection{БЛОК 1: СТРУКТУРА}" in out
    assert r"\begin{itemize}" in out
    assert r"\item 1.1. Тренд." in out
