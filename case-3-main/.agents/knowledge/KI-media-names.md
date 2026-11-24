# KI — media names (figure / photo / chart / image)

| Term | Meaning | ID prefix | Stage / API |
|------|---------|-----------|-------------|
| **figure** | Photo slot in TeX (`\\includegraphics`) | `fig_`, `usr_` | `images` stage; `/figures/{id}/edit` |
| **photo** | Same as figure in Liber UI copy | — | Image API generate/edit |
| **chart** | Chart.js → PNG | `cht_` | `charts` stage; `/charts/{id}/edit` |
| **diagram** | Mermaid → PNG in the report and on slides; PPTX may draw flowchart/timeline/mindmap as shapes | `dia_` | `%CASE3_DIAG` · `slides_pptx_diagrams` · Liber schema tab |
| **image** | Generic: Image API / PNG file | — | `IMAGE_API_BASE_URL` (health: `kandinsky_configured` alias) |
| **media_status** | per-id `{ok, error, kind}` in meta | — | `meta.json` + `status.json` |

**Gotchas**
- Do not invent chart types — whitelist `chart_html.CHART_TYPES`.
- Preview figure URLs: `/api/runs/{id}/figures/{name}.png?v=`.
- PDF is print truth; chat preview ≈ TeX blocks and may diverge.

See also: `KI-charts.md`, `KI-image-api.md`, `KI-pipeline.md`.
