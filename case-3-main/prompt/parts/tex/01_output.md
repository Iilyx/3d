# Output format (mandatory)

Return **exactly two** fenced blocks, in this order:

1. ` ```json ` … metadata **in this key order**: `charts` (full Chart.js `html`) → `diagrams` (Mermaid) → `figures` (short photo prompts) … ` ``` `  ← **FIRST**; charts/diagrams before figures so heavy HTML survives length limits
2. ` ```latex ` … **complete** XeLaTeX `\documentclass` … `\end{document}` … ` ``` `

Never put only a fragment (`\section` without `\documentclass`). Never omit `\documentclass`.
Always finish the closing ``` of **both** fences — do not stop mid-table.
Prefer a compact body (short sections) over a truncated draft. **Aim for up to {{MAX_CHARTS}} charts** when Source has numbers — shorten prose / fewer photos before dropping charts. Never soft-cap at 2 when the budget is higher.

JSON schema (key order mandatory). Chart `html` is a **full** Chart.js fragment (rails in Chart types); example uses a stub:

```json
{
  "charts": [
    {
      "id": "cht_01",
      "type": "bar",
      "caption": "Клиенты по годам, 2024–2025",
      "width": "0.85\\textwidth",
      "html": "<canvas id=\"c1\" width=\"1100\" height=\"560\"></canvas><script>/* full Chart.js: type matches charts[].type; Source numbers; palette; animation:false */ window.__CASE3_CHART_READY=true;</script>"
    }
  ],
  "diagrams": [
    {
      "id": "dia_01",
      "title": "Процесс согласования",
      "type": "flowchart",
      "mermaid": "flowchart TD\\n  A[Заявка]:::start --> B{ОК?}:::decision\\n  classDef start fill:…,stroke:…,color:#1a2e22"
    }
  ],
  "figures": [
    {
      "id": "fig_01",
      "caption": "Подпись на русском",
      "prompt": "English photo prompt: sharp detailed photograph, natural light, no text overlays",
      "width": "0.85\\textwidth"
    }
  ]
}
```

Figure/chart `width`: prefer `0.85\\textwidth`; if **2+ charts** use `0.82\\textwidth` (pipeline clamps above `0.92`, and to `0.82` when several charts). Canvas height ≤ 560.

If {{MAX_IMAGES}} is 0 → `"figures": []`. If {{MAX_CHARTS}} is 0 → `"charts": []`. If {{MAX_DIAGRAMS}} is 0 → `"diagrams": []`.

**Diagrams in TeX:** `%CASE3_DIAG:dia_NN%` on its own line (or auto-slot). Slot / no-includegraphics rules → Hard rules.
