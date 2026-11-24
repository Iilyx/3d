"""JSON charts must survive even when LaTeX forgot %CASE3_CHART slots."""

from __future__ import annotations

from case3.parse_output import parse_model_output


def test_json_charts_appended_when_tex_has_no_slots() -> None:
    raw = r'''```json
{
  "figures": [],
  "charts": [
    {
      "id": "cht_01",
      "type": "line",
      "caption": "Население",
      "width": "0.9\\textwidth",
      "html": "<canvas id=\"c1\" width=\"1100\" height=\"560\"></canvas><script>new Chart(document.getElementById('c1'),{type:'line',data:{labels:['2019'],datasets:[{data:[9470],borderColor:'#D62828'}]},options:{animation:false}});window.__CASE3_CHART_READY=true;</script>"
    }
  ]
}
```

```latex
\documentclass[a4paper,12pt]{article}
\usepackage{graphicx}
\begin{document}
\maketitle
\section{Введение}
Население республики составило девять миллионов четыреста семьдесят тысяч человек в две тысячи девятнадцатом году.
\end{document}
```
'''
    tex, figures, charts, _dias, _drops = parse_model_output(raw, max_images=0, max_charts=3)
    assert figures == []
    assert len(charts) == 1
    assert charts[0]["id"] == "cht_01"
    assert "%CASE3_CHART:cht_01%" in tex
    assert "девять миллионов" in tex
