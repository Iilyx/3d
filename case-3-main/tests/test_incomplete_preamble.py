"""Recover when model outputs JSON + truncated preamble (no \\begin{document})."""

from __future__ import annotations

from case3.parse_output import parse_model_output


def test_json_plus_preamble_only_recovers_document() -> None:
    raw = r"""```json
{
  "figures": [],
  "charts": [
    {
      "id": "cht_01",
      "type": "line",
      "caption": "Население",
      "html": "<canvas id=\"c1\" width=\"1100\" height=\"560\"></canvas><script>window.__CASE3_CHART_READY=true;</script>"
    }
  ]
}
```

```latex
\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\usepackage{polyglossia}
\usepackage{geometry}
\setdefaultlanguage{russian}
\setmainfont{DejaVu Serif}
\geometry{a4paper,margin=2.2cm}
\setotherlanguage{engl
```
"""
    tex, figs, charts, _dias, _drops = parse_model_output(raw, max_images=0, max_charts=2)
    assert r"\begin{document}" in tex
    assert r"\end{document}" in tex
    assert "%CASE3_CHART:cht_01%" in tex
    assert len(charts) == 1
    assert charts[0]["id"] == "cht_01"
