"""C4: wide tables → landscape wrap; normal tabularx stays portrait."""

from __future__ import annotations

from case3.tex_preamble import ensure_preamble, maybe_landscape_wide_tables, table_needs_landscape


def test_narrow_table_no_landscape() -> None:
    block = r"""
\begin{table}[ht]
\caption{KPI}
\begin{tabularx}{\textwidth}{lXr}
Метрика & Q2 & Q3 \\
Выручка & 1 & 2 \\
\end{tabularx}
\end{table}
"""
    assert table_needs_landscape(block) is False
    out = maybe_landscape_wide_tables(block)
    assert r"\begin{landscape}" not in out


def test_wide_many_cols_needs_landscape() -> None:
    cols = " & ".join(f"C{i}" for i in range(8))
    spec = "l" + "X" * 7
    block = rf"""
\begin{{table}}[ht]
\caption{{Wide}}
\begin{{tabularx}}{{\textwidth}}{{{spec}}}
{cols} \\
\end{{tabularx}}
\end{{table}}
"""
    assert table_needs_landscape(block) is True
    out = maybe_landscape_wide_tables(block)
    assert r"\begin{landscape}" in out
    assert r"\end{landscape}" in out
    # idempotent
    out2 = maybe_landscape_wide_tables(out)
    assert out2.count(r"\begin{landscape}") == 1


def test_ensure_preamble_adds_pdflscape() -> None:
    tex = r"""\documentclass{article}
\begin{document}
Hi
\end{document}
"""
    out = ensure_preamble(tex)
    assert r"\usepackage{pdflscape}" in out


def test_landscape_long_wide_table_promotes_to_xltabular_with_proportional_cols() -> None:
    rows_tex = "\n".join(
        f"{300 + i} & ИМНС по району {i} & 10\\,000 & 11\\,000 & +1\\,000 & 110\\% \\\\"
        for i in range(18)
    )
    tex = rf"""\documentclass{{article}}
\begin{{document}}
\begin{{landscape}}
\begin{{table}}[H]
\caption{{Широкая таблица по инспекциям}}
\begin{{tabularx}}{{\textwidth}}{{YYYYYY}}
\toprule
Код & Инспекция & План & Факт & Откл. & Вып. \\
\midrule
{rows_tex}
Итого & Всего & 180\,000 & 198\,000 & +18\,000 & 110\% \\
\bottomrule
\end{{tabularx}}
\end{{table}}
\end{{landscape}}
\end{{document}}"""
    out = ensure_preamble(tex)
    # Long wide landscape table must NOT stay trapped inside non-breakable table[H] + equal YYYYYY
    assert r"\begin{table}[H]" not in out
    assert r"\begin{xltabular}" in out
    assert r"{YYYYYY}" not in out
    assert r"\endhead" in out
    assert r"\captionof{table}" in out or r"\caption{" in out


def test_landscape_long_numeric_headers_use_z_and_clean_for_pandoc() -> None:
    from case3.tex_preamble import tex_for_pandoc

    tex = r"""\documentclass{article}
\begin{document}
\begin{landscape}
\begin{table}[H]
\caption{Показатели инспекций}
\begin{tabularx}{\textwidth}{YYYYYY}
\toprule
Код & Наименование инспекции & Фактические поступления, тыс. руб. & Плановые назначения, тыс. руб. & Отклонение от плана, тыс. руб. & Процент выполнения, \% \\
\midrule
101 & ИМНС по Центральному району & 65 420,5 & 60 000,0 & +5 420,5 & 109,0\% \\
102 & ИМНС по Советскому району & 52 100,0 & 50 000,0 & +2 100,0 & 104,2\% \\
\bottomrule
\end{tabularx}
\end{table}
\end{landscape}
\end{document}"""
    out = ensure_preamble(tex)
    assert r"\newcolumntype{Z}" in out
    assert "{lYZZZZ}" in out or "{rYZZZZ}" in out
    pdoc = tex_for_pandoc(out)
    assert r"\newcolumntype{Z}" not in pdoc
    assert r"\newcolumntype{Y}" not in pdoc
    assert "{lXrrrr}" in pdoc or "{rXrrrr}" in pdoc
