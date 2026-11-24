"""PDF task 4: obvious bullet lines → itemize (outside existing envs)."""

from __future__ import annotations

from case3.tex_preamble import ensure_document_preamble
from case3.tex_prose import (
    brace_schema_item_labels,
    drop_empty_lists,
    harden_prose_lists,
    normalize_includegraphics_aspect,
)


def test_dash_bullets_become_itemize() -> None:
    body = (
        "Введение.\n"
        "- первый пункт\n"
        "- второй пункт\n"
        "Заключение.\n"
    )
    out = harden_prose_lists(body)
    assert r"\begin{itemize}" in out
    assert r"\item первый пункт" in out
    assert r"\item второй пункт" in out
    assert r"\end{itemize}" in out
    assert "Введение." in out
    assert "Заключение." in out


def test_bullet_char_and_idempotent() -> None:
    body = "• альфа\n• бета\n"
    once = harden_prose_lists(body)
    twice = harden_prose_lists(once)
    assert once == twice
    assert once.count(r"\begin{itemize}") == 1


def test_skips_inside_itemize_and_tabular() -> None:
    body = (
        r"\begin{itemize}" + "\n"
        r"\item уже список" + "\n"
        r"\end{itemize}" + "\n"
        r"\begin{tabular}{ll}" + "\n"
        "- не трогать & x \\\\\n"
        r"\end{tabular}" + "\n"
        "- снаружи да\n"
        "- и это\n"
    )
    out = harden_prose_lists(body)
    assert "- не трогать" in out
    assert r"\item снаружи да" in out
    assert out.count(r"\begin{itemize}") == 2  # original + new


def test_schema_item_brackets_stay_in_the_line() -> None:
    """Win desk 090626: ``\\item [Узел] $\\rightarrow$`` is a diagram node.

    LaTeX treats ``[…]`` as the item label and paints it in the margin,
    so the first node is clipped off the page.
    """
    src = (
        r"\begin{itemize}" + "\n"
        r" \item [Датчики станков] $\rightarrow$ [Поток данных 5G]" + "\n"
        r" \item [Дроны] + [Спутники] $\rightarrow$ [Сервер обработки]" + "\n"
        r" \item \textbf{Да:} [Создание двойника] $\rightarrow$ [Прогноз]" + "\n"
        r" \item обычный пункт" + "\n"
        r"\end{itemize}" + "\n"
    )
    out = brace_schema_item_labels(src)
    assert r"\item {[Датчики станков]}" in out
    assert r"\item {[Дроны]}" in out
    assert r"$\rightarrow$ [Поток данных 5G]" in out
    assert r"\item \textbf{Да:}" in out
    assert r"\item обычный пункт" in out
    assert brace_schema_item_labels(out) == out


def test_ensure_preamble_braces_schema_nodes() -> None:
    tex = (
        r"\documentclass{article}" + "\n"
        r"\begin{document}" + "\n"
        r"\item [Датчики станков] $\rightarrow$ [Кластер]" + "\n"
        r"\end{document}" + "\n"
    )
    out = ensure_document_preamble(tex)
    assert r"\item {[Датчики станков]}" in out


def test_strip_includegraphics_height_keeps_width() -> None:
    raw = (
        r"\includegraphics[width=0.85\textwidth,height=0.4\textheight]"
        r"{figures/fig_01.png}"
    )
    out = normalize_includegraphics_aspect(raw)
    assert "height=" not in out
    assert r"width=0.85\textwidth" in out


def test_ensure_preamble_runs_prose_harden() -> None:
    tex = (
        r"\documentclass{article}"
        r"\usepackage{tabularx,booktabs,polyglossia,fontspec,enumitem}"
        r"\begin{document}"
        "Текст.\n- пункт A\n- пункт B\n"
        r"\end{document}"
    )
    out = ensure_document_preamble(tex)
    assert r"\item пункт A" in out


def test_empty_itemize_is_removed_before_compile() -> None:
    tex = (
        "Текст.\n"
        "\\begin{itemize}\n\\end{itemize}\n"
        "\\begin{enumerate}\n\\item один\n\\end{enumerate}\n"
    )
    out = drop_empty_lists(tex)
    assert r"\begin{itemize}" not in out
    assert r"\item один" in out
