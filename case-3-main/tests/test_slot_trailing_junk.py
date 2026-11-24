"""LLM often annotates slots on the same line — must not dump media at \\end{document}."""

from __future__ import annotations

import re

from case3.inject import inject_media
from case3.parse_output import parse_model_output


def test_trailing_junk_on_slot_line_does_not_append_duplicates() -> None:
    raw = r'''```json
{
  "figures": [
    {
      "id": "fig_01",
      "caption": "Склад",
      "width": "0.85\\textwidth",
      "prompt": "warehouse night loading dock sharp documentary photo"
    }
  ],
  "charts": [
    {
      "id": "cht_01",
      "type": "line",
      "caption": "SLA",
      "width": "0.82\\textwidth",
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
\section{KPI}
Текст про SLA.
%CASE3_CHART:cht_01%  (line - SLA weeks)
\section{Склад}
Про склад.
%CASE3_FIG:fig_01%  (склад Брест)
\section{Заключение}
Итог.
\end{document}
```
'''
    tex, figures, charts, _dias, _drops = parse_model_output(
        raw, max_images=2, max_charts=2
    )
    assert [f["id"] for f in figures] == ["fig_01"]
    assert [c["id"] for c in charts] == ["cht_01"]
    # Detected inline — no second clean copy before \end{document}
    assert tex.count("%CASE3_CHART:cht_01%") == 1
    assert tex.count("%CASE3_FIG:fig_01%") == 1
    assert not re.search(
        r"%CASE3_(?:FIG|CHART):[^\n]+\n\\end\{document\}",
        tex,
    )

    status = {"fig_01": {"ok": True}, "cht_01": {"ok": True}}
    out = inject_media(tex, figures, charts, status)
    assert out.count(r"\includegraphics") == 2
    assert "(line - SLA weeks)" not in out
    assert "(склад Брест)" not in out
    # Figures sit before Заключение, not dumped after it.
    concl = out.index(r"\section{Заключение}")
    assert out.index("figures/cht_01.png") < concl
    assert out.index("figures/fig_01.png") < concl
