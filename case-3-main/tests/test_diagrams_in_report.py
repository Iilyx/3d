"""Tests for diagram slots, parsing, and preview in reports."""

from __future__ import annotations

from case3.parse_output import parse_model_output
from case3.tex_preview import build_report_preview


def test_parse_model_output_extracts_diagram_slots() -> None:
    raw = r"""```json
{
  "diagrams": [
    {
      "id": "dia_01",
      "title": "Схема бизнес-процесса",
      "type": "flowchart",
      "mermaid": "flowchart TD\n  A --> B"
    }
  ]
}
```

```latex
\documentclass{article}
\begin{document}
\section{Процесс}
Описание процесса:
%CASE3_DIAG:dia_01%
\section{Итоги}
\end{document}
```"""
    tex, figures, charts, diagrams, drops = parse_model_output(
        raw, max_images=0, max_charts=0, max_diagrams=1
    )
    assert len(diagrams) == 1
    assert diagrams[0]["id"] == "dia_01"
    assert "%CASE3_DIAG:dia_01%" in tex


def test_parse_model_output_appends_missing_diagram_slots() -> None:
    raw = r"""```json
{
  "diagrams": [
    {
      "id": "dia_01",
      "title": "Архитектура решения",
      "type": "flowchart",
      "mermaid": "flowchart LR\n  A --> B"
    }
  ]
}
```

```latex
\documentclass{article}
\begin{document}
\section{Обзор}
Текст без слота диаграммы.
\end{document}
```"""
    tex, figures, charts, diagrams, drops = parse_model_output(
        raw, max_images=0, max_charts=0, max_diagrams=1
    )
    assert len(diagrams) == 1
    assert diagrams[0]["id"] == "dia_01"
    # Should have appended missing slot before \end{document}
    assert "%CASE3_DIAG:dia_01%" in tex


def test_tex_preview_assigns_diagram_kind_and_caption() -> None:
    tex = r"""\documentclass{article}
\title{Тестовый Отчёт}
\begin{document}
\maketitle
\section{Раздел}
Текст.
\begin{figure}[H]
\centering
\includegraphics[width=0.92\linewidth]{figures/dia_01.png}
\caption{Схема процесса продаж}
\label{dia:dia_01}
\end{figure}
\end{document}
"""
    media_status = {"dia_01": {"ok": True, "kind": "diagram"}}
    figures_json = {
        "diagrams": [
            {
                "id": "dia_01",
                "title": "Схема процесса продаж",
                "type": "flowchart",
                "mermaid": "flowchart TD\n  A --> B",
            }
        ]
    }
    preview = build_report_preview(
        tex, run_id="run_123", media_status=media_status, figures_json=figures_json
    )
    blocks = preview["blocks"]
    diag_blocks = [b for b in blocks if b.get("type") == "figure" and b.get("id") == "dia_01"]
    assert len(diag_blocks) == 1
    b = diag_blocks[0]
    assert b["kind"] == "diagram"
    assert b["caption"] == "Схема процесса продаж"
    assert b["url"] == "/api/runs/run_123/figures/dia_01.png"


def test_parse_model_output_strips_unknown_diagram_slots() -> None:
    raw = r"""```json
{
  "diagrams": [
    {
      "id": "dia_01",
      "title": "Схема 1",
      "type": "flowchart",
      "mermaid": "flowchart TD\n  A --> B"
    }
  ]
}
```

```latex
\documentclass{article}
\begin{document}
%CASE3_DIAG:dia_01%
%CASE3_DIAG:dia_02%
Текст.
\end{document}
```"""
    tex, figures, charts, diagrams, drops = parse_model_output(
        raw, max_images=0, max_charts=0, max_diagrams=2
    )
    assert len(diagrams) == 1
    assert "%CASE3_DIAG:dia_01%" in tex
    assert "%CASE3_DIAG:dia_02%" not in tex


def test_parse_model_output_strips_all_diagram_slots_when_max_diagrams_zero() -> None:
    raw = r"""```latex
\documentclass{article}
\begin{document}
%CASE3_DIAG:dia_01%
Текст.
\end{document}
```"""
    tex, figures, charts, diagrams, drops = parse_model_output(
        raw, max_images=0, max_charts=0, max_diagrams=0
    )
    assert len(diagrams) == 0
    assert "%CASE3_DIAG:dia_01%" not in tex

