"""Tests for unfenced JSON parsing, partial slot preservation, and chart_palette."""

from case3.intent_compose import build_intent_from_ui
from case3.parse_output import parse_model_output


def test_parse_model_output_recovers_unfenced_json_before_latex() -> None:
    raw = """
{
  "charts": [
    {
      "id": "cht_01",
      "type": "bar",
      "caption": "Выручка по регионам",
      "html": "<!doctype html><script>new Chart(c,{type:'bar',data:{labels:['Москва'],datasets:[{data:[100]}]}});</script>"
    }
  ],
  "diagrams": [],
  "figures": []
}

```latex
\\documentclass{article}
\\begin{document}
%CASE3_CHART:cht_01%
Москва 100.
\\end{document}
```
"""
    tex, figs, charts, diags, _drops = parse_model_output(
        raw, max_images=0, max_charts=2, max_diagrams=1
    )
    assert len(charts) == 1
    assert charts[0]["id"] == "cht_01"
    assert "%CASE3_CHART:cht_01%" in tex
    assert figs == []
    assert diags == []


def test_parse_model_output_appends_missing_chart_and_diagram_slots_on_partial_tex() -> None:
    raw = """
```json
{
  "charts": [
    {"id": "cht_01", "type": "bar", "caption": "Первый", "html": "data:[1]"},
    {"id": "cht_02", "type": "line", "caption": "Второй", "html": "data:[2]"}
  ],
  "diagrams": [
    {"id": "dia_01", "type": "flowchart", "title": "Схема 1", "caption": "Поток 1", "mermaid": "flowchart TD\\nA[Старт]-->B[Финиш]"},
    {"id": "dia_02", "type": "flowchart", "title": "Схема 2", "caption": "Поток 2", "mermaid": "flowchart TD\\nC[Вход]-->D[Выход]"}
  ],
  "figures": []
}
```

```latex
\\documentclass{article}
\\begin{document}
%CASE3_CHART:cht_01%
%CASE3_DIAG:dia_01%
Текст анализа.
\\end{document}
```
"""
    tex, _figs, charts, diags, _drops = parse_model_output(
        raw, max_images=0, max_charts=2, max_diagrams=2
    )
    assert [c["id"] for c in charts] == ["cht_01", "cht_02"]
    assert [d["id"] for d in diags] == ["dia_01", "dia_02"]
    assert "%CASE3_CHART:cht_02%" in tex
    assert "%CASE3_DIAG:dia_02%" in tex


def test_run_pipeline_persists_chart_palette_in_meta(tmp_path) -> None:
    from case3.pipeline import run_pipeline

    src = tmp_path / "source.md"
    src.write_text("| Регион | Сумма |\n| --- | --- |\n| Москва | 100 |\n", encoding="utf-8")
    intent = build_intent_from_ui(
        chat="Сделай отчёт",
        chart_types=[],
        max_charts=2,
        max_images=0,
        forbid_charts=False,
        forbid_images=True,
        chart_palette="ocean",
    )
    out = run_pipeline(
        src,
        project_root=tmp_path,
        formats={"tex"},
        dry_run=True,
        intent=intent,
        output_mode="report",
    )
    import json

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("chart_palette") == "ocean"
