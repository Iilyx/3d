"""Structured TeX table patch for Liber Preview edit."""

from __future__ import annotations

import pytest

from case3.table_edit import (
    TableEditError,
    find_table_spans,
    patch_table_in_tex,
    validate_table_payload,
)
from case3.tex_preview import tex_to_preview_blocks

SAMPLE = r"""
\documentclass{article}
\begin{document}
\title{T}
\section{S}

\begin{table}[H]
  \centering
  \caption{Ключевые показатели}
  \begin{tabularx}{\textwidth}{lXX}
    \toprule
    Показатель & Значение & Комментарий \\
    \midrule
    Население & 9330 & Конец периода \\
    Рождения & 72\,000 & Зарегистрировано \\
    \bottomrule
  \end{tabularx}
\end{table}

\begin{table}[H]
  \centering
  \caption{Вторая}
  \begin{tabular}{ll}
    \toprule
    A & B \\
    \midrule
    1 & 2 \\
    \bottomrule
  \end{tabular}
\end{table}

\end{document}
"""


def test_find_table_spans_counts_two() -> None:
    spans = find_table_spans(SAMPLE)
    assert len(spans) == 2
    assert "Ключевые показатели" in SAMPLE[spans[0][0] : spans[0][1]]
    assert "Вторая" in SAMPLE[spans[1][0] : spans[1][1]]


def test_validate_rejects_mismatched_row() -> None:
    with pytest.raises(TableEditError):
        validate_table_payload(
            caption="x",
            headers=["a", "b"],
            rows=[["1"]],
        )


def test_validate_rejects_empty_headers() -> None:
    with pytest.raises(TableEditError):
        validate_table_payload(caption="", headers=[], rows=[])


def test_validate_rejects_too_large() -> None:
    headers = [f"c{i}" for i in range(41)]
    with pytest.raises(TableEditError):
        validate_table_payload(caption="", headers=headers, rows=[])


def test_patch_round_trip_caption_and_cell() -> None:
    patched = patch_table_in_tex(
        SAMPLE,
        1,
        caption="Новая подпись",
        headers=["Показатель", "Значение", "Комментарий"],
        rows=[
            ["Население", "9400", "Обновлено"],
            ["Рождения", "72000", "Зарегистрировано"],
        ],
    )
    blocks = tex_to_preview_blocks(patched)["blocks"]
    tables = [b for b in blocks if b["type"] == "table"]
    assert tables[0]["caption"] == "Новая подпись"
    assert tables[0]["rows"][0][1] == "9400"
    assert tables[0]["rows"][0][2] == "Обновлено"
    # second table untouched
    assert tables[1]["caption"] == "Вторая"


def test_patch_add_and_delete_column() -> None:
    patched = patch_table_in_tex(
        SAMPLE,
        2,
        caption="Вторая",
        headers=["A", "B", "C"],
        rows=[["1", "2", "3"]],
    )
    tables = [
        b
        for b in tex_to_preview_blocks(patched)["blocks"]
        if b["type"] == "table"
    ]
    assert tables[1]["headers"] == ["A", "B", "C"]
    assert tables[1]["rows"] == [["1", "2", "3"]]

    patched2 = patch_table_in_tex(
        patched,
        2,
        caption="Вторая",
        headers=["A", "C"],
        rows=[["1", "3"]],
    )
    tables2 = [
        b
        for b in tex_to_preview_blocks(patched2)["blocks"]
        if b["type"] == "table"
    ]
    assert tables2[1]["headers"] == ["A", "C"]
    assert tables2[1]["rows"] == [["1", "3"]]


def test_patch_empty_cell_becomes_tilde_round_trips_empty() -> None:
    patched = patch_table_in_tex(
        SAMPLE,
        2,
        caption="Вторая",
        headers=["A", "B"],
        rows=[["", "2"]],
    )
    span = find_table_spans(patched)[1]
    chunk = patched[span[0] : span[1]]
    assert "~" in chunk
    tables = [
        b
        for b in tex_to_preview_blocks(patched)["blocks"]
        if b["type"] == "table"
    ]
    assert tables[1]["rows"][0][0] == ""


def test_patch_escapes_specials() -> None:
    patched = patch_table_in_tex(
        SAMPLE,
        2,
        caption="100% & more",
        headers=["A_1", "B"],
        rows=[["x & y", "50%"]],
    )
    span = find_table_spans(patched)[1]
    chunk = patched[span[0] : span[1]]
    assert r"\%" in chunk
    assert r"\&" in chunk
    assert r"\_" in chunk
    tables = [
        b
        for b in tex_to_preview_blocks(patched)["blocks"]
        if b["type"] == "table"
    ]
    assert tables[1]["caption"] == "100% & more"
    assert tables[1]["headers"][0] == "A_1"
    assert tables[1]["rows"][0][0] == "x & y"


def test_long_region_table_can_be_saved() -> None:
    rows = [[f"Район {i:02d}", str(1000 + i)] for i in range(1, 31)]
    validate_table_payload(caption="", headers=["Район", "Сумма"], rows=rows)


def test_patch_oob_raises() -> None:
    with pytest.raises(TableEditError):
        patch_table_in_tex(
            SAMPLE,
            9,
            caption="x",
            headers=["A"],
            rows=[["1"]],
        )


def test_patch_xltabular_preserves_caption_and_chart_caption_edit() -> None:
    from case3.figure_edit import patch_figure_caption_in_tex
    from case3.parse_output import parse_model_output

    xlt_tex = r"""
\documentclass{article}
\begin{document}
\begin{landscape}
{\small
\setlength{\tabcolsep}{4pt}
\begin{xltabular}{\linewidth}{rYrr}
\caption{Поступления по инспекциям, январь 2025} \\
\toprule
Код & Инспекция & План & Факт \\
\midrule
\endhead
\bottomrule
\endfoot
101 & Центральный р-н & 62 000,0 & 65 420,5 \\
\end{xltabular}
}
\end{landscape}
\begin{figure}[H]
 \centering
 \includegraphics[width=0.82\textwidth]{figures/cht_01.png}
 \caption{Старая подпись графика}
 \label{chart:cht_01}
\end{figure}
\end{document}
"""
    patched = patch_table_in_tex(
        xlt_tex,
        1,
        caption="Поступления по инспекциям (обновлено)",
        headers=["Код", "Инспекция", "План", "Факт"],
        rows=[["101", "г. Минск", "62 000,0", "65 420,5"]],
    )
    assert r"\caption{Поступления по инспекциям (обновлено)} \\" in patched
    blocks = tex_to_preview_blocks(patched)["blocks"]
    tables = [b for b in blocks if b["type"] == "table"]
    assert tables[0]["caption"] == "Поступления по инспекциям (обновлено)"

    # Also verify chart caption edit with \label{chart:cht_01}
    cap_patched = patch_figure_caption_in_tex(patched, "cht_01", "Новая подпись графика")
    assert r"\caption{Новая подпись графика}" in cap_patched

    # And verify user photo (usr_01) vision caption is preserved when max_images=0
    raw_model = (
        "```json\n"
        '{"figures":[{"id":"usr_01","caption":"Скриншот дашборда поступлений ИМНС"}],'
        '"charts":[],"diagrams":[]}\n'
        "```\n"
        "```latex\n"
        "\\documentclass{article}\n\\begin{document}\nТекст.\n%CASE3_FIG:usr_01%\n\\end{document}\n"
        "```\n"
    )
    _tex, figs, _charts, _diags, _drops = parse_model_output(
        raw_model, max_images=0, max_charts=0, max_diagrams=0
    )
    assert len(figs) == 1
    assert figs[0]["id"] == "usr_01"
    assert figs[0]["caption"] == "Скриншот дашборда поступлений ИМНС"

