"""Diagram-only model output: JSON diagrams without \\documentclass still parses."""

from __future__ import annotations

from case3.parse_output import parse_model_output

RAW = '''
Let me analyze the request carefully.
I will emit diagrams only.

```json
{
  "figures": [],
  "charts": [],
  "diagrams": [
    {
      "id": "dia_01",
      "title": "Пайплайн",
      "type": "flowchart",
      "mermaid": "flowchart TD\\n  A[Start]:::start --> B[Done]:::ok\\n  classDef start fill:#dce8df,stroke:#6b8f76\\n  classDef ok fill:#cfe6d4,stroke:#3d7a4a"
    }
  ]
}
```
'''


def test_parse_diagrams_without_documentclass() -> None:
    tex, figs, charts, diagrams, drops = parse_model_output(
        RAW, max_images=0, max_charts=0, max_diagrams=2
    )
    assert r"\documentclass" in tex
    assert figs == []
    assert charts == []
    assert len(diagrams) == 1
    assert diagrams[0]["id"] == "dia_01"
    assert "flowchart" in diagrams[0]["mermaid"]
