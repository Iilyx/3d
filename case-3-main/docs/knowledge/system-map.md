# System map

```text
┌──────────── Liber (web :5173) ────────────┐
│  App · Settings · ReportView · PdfSlider  │
└───────────────┬───────────────────────────┘
                │ /api/*
┌───────────────▼───────────────────────────┐
│           FastAPI (api.py :8000)          │
│  run · status · chart/figure edit · health│
└───────────────┬───────────────────────────┘
                │
┌───────────────▼───────────────────────────┐
│              run_pipeline                 │
│  llm → images → charts+diagrams → inject → render │
│  slides job (separate): IR → PNG → PPTX    │
└───┬─────────┬──────────┬──────────┬───────┘
    │         │          │          │
 Qwen      Image API  Playwright  Docker
 VISION_*  IMAGE_*    Chart.js    case-3:tex
                                  PDF + DOCX
```

## Artifacts per run

```text
runs/out/<run_id>/
  *.tex  figures.json  figures/*.png  *.pdf  *.docx  meta.json
runs/logs/<run_id>/   pipeline + latex logs
runs/work/<run_id>/   scratch
```

## Key modules

| Concern | Module |
|---------|--------|
| Orchestration | `pipeline.py` |
| LLM + parse | `generate.py`, `parse_output.py` |
| Charts | `charts.py`, `chart_*` |
| Photos | `image_api.py`, `user_photos.py`, `figure_edit.py`, `schema_redraw.py` |
| Empty request | `input_validation.py` → `meta.insufficient_data` |
| Diagrams | `inject.py` (`%CASE3_DIAG`), `slides_pptx_diagrams.py` |
| TeX | `tex_preamble.py`, `inject.py`, `render.py` |
| Deck | `slides_job.py`, `slides_ir.py`, `source_brief.py` |
| Preview JSON | `tex_preview.py` |
