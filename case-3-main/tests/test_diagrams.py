"""Mermaid diagram sanitize + parse (UI-only, no TeX slots)."""

from __future__ import annotations

import pytest

from case3.diagrams import DIAGRAM_TYPES, parse_diagrams, sanitize_mermaid
from case3.parse_output import parse_model_output


def test_sanitize_strips_mermaid_fence() -> None:
    raw = "```mermaid\nflowchart TD\n  A-->B\n```"
    out = sanitize_mermaid(raw)
    assert out.startswith("flowchart")
    assert "```" not in out


def test_sanitize_keeps_classdef_colors() -> None:
    raw = (
        "flowchart TD\n"
        "  A[Старт]:::start --> B{Ок?}:::decision\n"
        "  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22\n"
        "  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22\n"
    )
    out = sanitize_mermaid(raw)
    assert ":::start" in out
    assert "classDef start" in out
    assert "#dce8df" in out
    assert "#f3e6c8" in out


def test_sanitize_repairs_multi_classname_class_line() -> None:
    """LLM emits `class A,B,C start decision process` — invalid; zip 1:1."""
    raw = (
        "flowchart TD\n"
        "  A[Старт]:::start --> B{Ок?}:::decision\n"
        "  B --> C[Шаг]\n"
        "  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22\n"
        "  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22\n"
        "  classDef process fill:#eef3ef,stroke:#5a7a64,color:#1a2e22\n"
        "  class A,B,C start decision process\n"
    )
    out = sanitize_mermaid(raw)
    assert "class A,B,C start decision process" not in out
    assert "class A start" in out
    assert "class B decision" in out
    assert "class C process" in out
    assert "classDef start" in out


def test_sanitize_drops_unmappable_multi_class_line() -> None:
    raw = (
        "flowchart TD\n"
        "  A-->B\n"
        "  class A,B start decision process process process\n"
    )
    out = sanitize_mermaid(raw)
    assert "class A,B" not in out
    assert "A-->B" in out


def test_sanitize_repairs_space_separated_class_nodes() -> None:
    """LLM emits ``class A B C process`` (spaces, one class) — keep as class A,B,C process."""
    raw = (
        "flowchart TD\n"
        "  A-->B-->C\n"
        "  classDef process fill:#eef3ef,stroke:#5a7a64,color:#1a2e22\n"
        "  class A B C process\n"
    )
    out = sanitize_mermaid(raw)
    assert "class A B C process" not in out
    assert "class A,B,C process" in out or (
        "class A process" in out and "class B process" in out and "class C process" in out
    )


def test_sanitize_repairs_two_colon_role_suffix() -> None:
    """LLM writes ``]::start``; Mermaid needs ``]:::start``."""
    raw = (
        "flowchart TD\n"
        '  A["Клиент<br/>Заявка"]::start --> B["Склад"]::process\n'
        "  B --> C{Товар годен}::decision\n"
        "  C -->|годен| D[Деньги]::ok\n"
        "  classDef start fill:#D4EBE8,stroke:#1F6F66,color:#1a2e22\n"
        "  classDef process fill:#E7F0D8,stroke:#6B7F45,color:#1a2e22\n"
        "  classDef decision fill:#F8E6D8,stroke:#C47A3A,color:#1a2e22\n"
        "  classDef ok fill:#D7EDD9,stroke:#2F7D4A,color:#1a2e22\n"
    )
    out = sanitize_mermaid(raw)
    assert 'A["Клиент<br/>Заявка"]:::start' in out
    assert 'B["Склад"]:::process' in out
    assert "C{Товар годен}:::decision" in out
    assert "D[Деньги]:::ok" in out
    assert "]::start" not in out
    assert 'classDef start fill:#D4EBE8' in out


def test_sanitize_repairs_class_with_leading_colons() -> None:
    """LLM emits ``class A :::start`` — invalid style separator; fix to ``class A start``."""
    raw = (
        "flowchart TD\n"
        "  A-->B\n"
        "  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22\n"
        "  classDef process fill:#eef3ef,stroke:#5a7a64,color:#1a2e22\n"
        "  class A :::start\n"
        "  class B :::process\n"
    )
    out = sanitize_mermaid(raw)
    assert "class A :::start" not in out
    assert "class A start" in out
    assert "class B process" in out


def test_sanitize_repairs_sequence_diagram_participant_alias() -> None:
    """LLM emits ``Alias as Label`` without participant keyword in sequence diagrams."""
    raw = (
        "sequenceDiagram\n"
        "  АОН as Оператор\n"
        "  Менеджер по продажам as Менеджер\n"
        "  Менеджер по логистике as Логист\n"
        "  АОН->>Менеджер: заявка на продажу\n"
        "  Менеджер->>Логист: отгрузка\n"
        "  Логист-->>АОН: подтверждение отгрузки\n"
    )
    out = sanitize_mermaid(raw)
    assert "participant АОН as Оператор" in out
    assert 'participant "Менеджер по продажам" as Менеджер' in out
    assert 'participant "Менеджер по логистике" as Логист' in out
    assert "АОН->>Менеджер: заявка на продажу" in out


def test_sanitize_rewrites_class_style_as_classdef() -> None:
    """LLM writes ``class start fill:#…`` instead of classDef — rewrite."""
    raw = (
        "flowchart TD\n"
        "  A[X]:::start --> B[Y]\n"
        "  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22\n"
        "  class A start\n"
        "  class start fill:#d4ebe8,stroke:#004D47,color:#1a2e22\n"
        "  class process fill:#eef6f5,stroke:#009988,color:#1a2e22\n"
    )
    out = sanitize_mermaid(raw)
    assert "class start fill:" not in out
    assert "class process fill:" not in out
    assert "classDef start fill:" in out
    assert "classDef process fill:" in out
    assert "class A start" in out


def test_sanitize_rewrites_purple_and_strips_click() -> None:
    raw = (
        "flowchart TD\n"
        "  A[X]:::x\n"
        "  click A \"https://evil.example\"\n"
        "  classDef x fill:#7c3aed,stroke:#a855f7,color:#fff\n"
    )
    out = sanitize_mermaid(raw)
    assert "click" not in out.lower()
    assert "#7c3aed" not in out.lower()
    assert "#a855f7" not in out.lower()
    assert "#dce8df" in out or "#6b8f76" in out


def test_sanitize_rejects_empty() -> None:
    with pytest.raises(ValueError):
        sanitize_mermaid("   ")


def test_parse_diagrams_accepts_flowchart() -> None:
    items = parse_diagrams(
        [
            {
                "id": "dia_01",
                "title": "Процесс",
                "type": "flowchart",
                "mermaid": "flowchart TD\n  A[Start] --> B[End]",
            }
        ],
        max_diagrams=2,
    )
    assert len(items) == 1
    assert items[0]["id"] == "dia_01"
    assert items[0]["type"] == "flowchart"
    assert "flowchart TD" in items[0]["mermaid"]


def test_parse_diagrams_drops_unknown_type() -> None:
    items = parse_diagrams(
        [{"id": "dia_01", "title": "X", "type": "pie", "mermaid": "pie\n  \"A\": 1"}],
        max_diagrams=2,
    )
    assert items == []


def test_parse_diagrams_respects_cap() -> None:
    raw = [
        {
            "id": f"dia_0{i}",
            "title": f"T{i}",
            "type": "flowchart",
            "mermaid": f"flowchart TD\n  A{i}-->B{i}",
        }
        for i in range(1, 5)
    ]
    items = parse_diagrams(raw, max_diagrams=2)
    assert len(items) == 2
    assert {d["id"] for d in items} == {"dia_01", "dia_02"}


def test_parse_diagrams_zero_cap() -> None:
    assert (
        parse_diagrams(
            [
                {
                    "id": "dia_01",
                    "title": "X",
                    "type": "flowchart",
                    "mermaid": "flowchart TD\nA-->B",
                }
            ],
            max_diagrams=0,
        )
        == []
    )


def test_parse_diagrams_drops_bad_id() -> None:
    items = parse_diagrams(
        [
            {
                "id": "DIA-01",
                "title": "X",
                "type": "flowchart",
                "mermaid": "flowchart TD\nA-->B",
            }
        ],
        max_diagrams=2,
    )
    assert items == []


def test_diagram_types_whitelist() -> None:
    assert "flowchart" in DIAGRAM_TYPES
    assert "pie" not in DIAGRAM_TYPES


def test_parse_normalizes_graph_header_to_flowchart() -> None:
    items = parse_diagrams(
        [
            {
                "id": "dia_01",
                "title": "Поток",
                "type": "flowchart",
                "mermaid": "graph TD\n  A[Шаг1] --> B[Шаг2]",
            }
        ],
        max_diagrams=2,
    )
    assert len(items) == 1
    assert items[0]["mermaid"].startswith("flowchart")


def test_parse_drops_type_header_mismatch() -> None:
    items = parse_diagrams(
        [
            {
                "id": "dia_01",
                "title": "X",
                "type": "flowchart",
                "mermaid": "sequenceDiagram\n  A->>B: hi",
            }
        ],
        max_diagrams=2,
    )
    assert items == []


def test_parse_accepts_sequence_with_sequenceDiagram_header() -> None:
    items = parse_diagrams(
        [
            {
                "id": "dia_02",
                "title": "Диалог",
                "type": "sequence",
                "mermaid": "sequenceDiagram\n  Alice->>Bob: ping",
            }
        ],
        max_diagrams=2,
    )
    assert len(items) == 1
    assert items[0]["type"] == "sequence"


def test_parse_diagrams_reports_drops() -> None:
    kept, drops = parse_diagrams(
        [
            {
                "id": "dia_01",
                "title": "Ok",
                "type": "flowchart",
                "mermaid": "flowchart TD\nA-->B",
            },
            {
                "id": "dia_02",
                "title": "Bad",
                "type": "flowchart",
                "mermaid": "sequenceDiagram\nA->>B: x",
            },
        ],
        max_diagrams=3,
        with_drops=True,
    )
    assert len(kept) == 1
    assert len(drops) == 1
    assert drops[0]["id"] == "dia_02"
    assert "header" in drops[0]["reason"].lower() or "mismatch" in drops[0]["reason"].lower()


def test_intent_nudges_diagrams_when_budget() -> None:
    from case3.api import build_intent_from_ui

    intent = build_intent_from_ui(
        chat="отчёт",
        chart_types=[],
        max_charts=0,
        max_images=0,
        max_diagrams=2,
        forbid_charts=True,
        forbid_images=True,
    )
    low = intent.lower()
    assert "mermaid" in low or "схем" in low
    # Forbidding charts must NOT forbid Liber Mermaid schemas
    assert "без графиков и диаграмм" not in low
    assert "charts" in low or "html-график" in low or "график" in low


def test_parse_model_output_returns_diagrams() -> None:
    raw = r'''```json
{
  "figures": [],
  "charts": [],
  "diagrams": [
    {
      "id": "dia_01",
      "title": "Согласование",
      "type": "flowchart",
      "mermaid": "flowchart TD\n  A[Заявка] --> B[Готово]"
    }
  ]
}
```
```latex
\documentclass{article}
\begin{document}
Hello.
\end{document}
```
'''
    tex, figs, charts, diagrams, _drops = parse_model_output(
        raw, max_images=0, max_charts=0, max_diagrams=2
    )
    assert figs == []
    assert charts == []
    assert len(diagrams) == 1
    assert diagrams[0]["id"] == "dia_01"
    assert "%CASE3_DIAG:dia_01%" in tex
    assert r"\documentclass" in tex


def test_parse_model_output_diagram_id_collision_with_chart() -> None:
    raw = r'''```json
{
  "figures": [],
  "charts": [
    {
      "id": "cht_01",
      "type": "bar",
      "caption": "C",
      "html": "<canvas id=\"c1\" width=\"1100\" height=\"560\"></canvas><script>new Chart(document.getElementById('c1'),{type:'bar',data:{labels:['a'],datasets:[{data:[1],backgroundColor:'#D62828'}]},options:{animation:false}});window.__CASE3_CHART_READY=true;</script>"
    }
  ],
  "diagrams": [
    {
      "id": "cht_01",
      "title": "Clash",
      "type": "flowchart",
      "mermaid": "flowchart TD\nA-->B"
    }
  ]
}
```
```latex
\documentclass{article}
\begin{document}
%CASE3_CHART:cht_01%
\end{document}
```
'''
    from case3.parse_output import ParseError

    with pytest.raises(ParseError, match="collision"):
        parse_model_output(raw, max_images=0, max_charts=1, max_diagrams=2)


def test_sanitize_mermaid_sequence_diagram_quotes_spaced_participants() -> None:
    raw = """sequenceDiagram
  АОН as Оператор
  Менеджер по продажам as Менеджер
  participant Менеджер по логистике as Логист
  АОН->>Менеджер: заявка на продажу"""
    out = sanitize_mermaid(raw)
    assert 'participant "Менеджер по продажам" as Менеджер' in out
    assert 'participant "Менеджер по логистике" as Логист' in out
    assert 'participant АОН as Оператор' in out


def test_parse_diagrams_preserves_diagram_with_leading_comment() -> None:
    raw = "%% комментарий перед диаграммой\nflowchart TD\n  A[Начало] --> B[Конец]"
    parsed = parse_diagrams([{"id": "dia_01", "type": "flowchart", "mermaid": raw}], max_diagrams=1)
    assert len(parsed) == 1
    assert parsed[0]["id"] == "dia_01"


def test_parse_diagrams_preserves_diagram_with_frontmatter() -> None:
    raw = "---\ntitle: Тест\n---\nflowchart LR\n  A --> B"
    parsed = parse_diagrams([{"id": "dia_01", "type": "flowchart", "mermaid": raw}], max_diagrams=1)
    assert len(parsed) == 1
    assert parsed[0]["id"] == "dia_01"


def test_parse_diagrams_preserves_diagram_with_init_directive() -> None:
    raw = "%%{init: {'theme': 'base'}}%%\nsequenceDiagram\n  Alice->>Bob: Hello"
    parsed = parse_diagrams([{"id": "dia_01", "type": "sequence", "mermaid": raw}], max_diagrams=1)
    assert len(parsed) == 1
    assert parsed[0]["id"] == "dia_01"


def test_ensure_role_classdefs_with_leading_comment() -> None:
    from case3.diagram_style import ensure_role_classdefs

    raw = "%% Comment\nflowchart TD\n  A[Старт]:::start --> B[Шаг]:::process"
    out = ensure_role_classdefs(raw, palette="ocean")
    assert "classDef start" in out
    assert "classDef process" in out


def test_pptx_parsers_support_leading_comments() -> None:
    from case3.slides_pptx_diagrams import parse_mermaid_flowchart, parse_mermaid_timeline

    fc = "%% comment\nflowchart TD\n  A[Заявка] --> B[Одобрено]"
    graph = parse_mermaid_flowchart(fc)
    assert graph is not None
    assert "A" in graph.nodes

    tl = "%% timeline comment\ntimeline\n  title Хронология\n  2024 : Старт : Релиз"
    spec = parse_mermaid_timeline(tl)
    assert spec is not None
    assert len(spec.periods) >= 1


def test_sanitize_mermaid_quotes_node_labels_with_parens_colons_quotes() -> None:
    raw = (
        "flowchart TD\n"
        '  A[Выручка (2025): 120 "план"] --> B{Итог (100%): да?}\n'
        '  B -->|Резерв: +450| C(Рост (Гомель))\n'
    )
    out = sanitize_mermaid(raw)
    assert 'A["Выручка (2025): 120' in out
    assert 'B{"Итог (100%): да?"}' in out
    assert 'C("Рост (Гомель)")' in out


def test_sanitize_mermaid_unescapes_double_escaped_newlines() -> None:
    raw = r"flowchart TD\n  A[Старт]:::start --> B[Финиш]:::ok\n  classDef start fill:#DCE6F0"
    out = sanitize_mermaid(raw)
    lines = out.splitlines()
    assert lines[0] == "flowchart TD"
    assert "A[Старт]:::start --> B[Финиш]:::ok" in lines[1]
    assert "classDef start" in lines[2]


def test_render_mermaid_png_rejects_bomb_svg(tmp_path: Path) -> None:
    import pytest
    from case3.slides_media import render_mermaid_png

    dest = tmp_path / "dia_bomb.png"
    with pytest.raises(RuntimeError, match="mermaid syntax error"):
        render_mermaid_png(
            mermaid=r"flowchart TD\n  A --> B",
            dest=dest,
            palette="editorial",
        )
    assert not dest.exists()



