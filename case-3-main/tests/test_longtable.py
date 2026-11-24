"""Tests for longtable support in tex_preview and table_edit."""

from __future__ import annotations

import pytest

from case3.table_edit import find_table_spans, patch_table_in_tex
from case3.tex_preview import build_report_preview, find_paragraph_spans

_SAMPLE_LONGTABLE = r"""\documentclass{article}
\usepackage{longtable}
\usepackage{booktabs}
\title{Отчёт с таблицей}
\begin{document}
\section{Данные}
Вводный абзац перед большой таблицей.

\begin{longtable}{lrr}
\caption{Финансовые показатели 2024-2025}\label{tab:fin}\\
\toprule
Показатель & 2024 & 2025 \\
\midrule
Выручка & 120 & 250 \\
Прибыль & 30 & 85 \\
\bottomrule
\end{longtable}

Заключительный абзац после таблицы.
\end{document}
"""


def test_find_paragraph_spans_skips_longtable() -> None:
    spans = find_paragraph_spans(_SAMPLE_LONGTABLE)
    # Only 2 paragraphs: "Вводный абзац..." and "Заключительный абзац..."
    assert len(spans) == 2
    p1 = _SAMPLE_LONGTABLE[spans[0][0] : spans[0][1]]
    p2 = _SAMPLE_LONGTABLE[spans[1][0] : spans[1][1]]
    assert "Вводный абзац" in p1
    assert "Заключительный абзац" in p2
    assert "Выручка" not in p1
    assert "Выручка" not in p2


def test_build_report_preview_parses_longtable() -> None:
    preview = build_report_preview(_SAMPLE_LONGTABLE, run_id="test_run")
    blocks = preview["blocks"]
    tables = [b for b in blocks if b.get("type") == "table"]
    assert len(tables) == 1
    t = tables[0]
    assert "Финансовые показатели" in t["caption"]
    assert t["headers"] == ["Показатель", "2024", "2025"]
    assert len(t["rows"]) == 2
    assert t["rows"][0] == ["Выручка", "120", "250"]
    assert t["rows"][1] == ["Прибыль", "30", "85"]


def test_find_table_spans_detects_longtable() -> None:
    spans = find_table_spans(_SAMPLE_LONGTABLE)
    assert len(spans) == 1
    chunk = _SAMPLE_LONGTABLE[spans[0][0] : spans[0][1]]
    assert r"\begin{longtable}" in chunk
    assert r"\end{longtable}" in chunk


def test_patch_table_in_tex_patches_longtable() -> None:
    patched = patch_table_in_tex(
        _SAMPLE_LONGTABLE,
        1,
        caption="Новая подпись",
        headers=["Метрика", "Факт"],
        rows=[["План", "100%"], ["Факт", "110%"]],
    )
    assert "Новая подпись" in patched
    assert "Метрика" in patched
    assert "Факт" in patched
    assert r"\begin{longtable}" in patched or r"\begin{tabularx}" in patched
    # Verify preview can parse the patched table
    preview = build_report_preview(patched, run_id="test_run")
    tables = [b for b in preview["blocks"] if b.get("type") == "table"]
    assert len(tables) == 1
    assert tables[0]["caption"] == "Новая подпись"
    assert tables[0]["headers"] == ["Метрика", "Факт"]
