# ADR-0002: Charts via Chart.js HTML + Playwright PNG

## Status
Accepted

## Date
2026-10-21

## Context
Модели плохо рисуют «нативные» графики в TeX. Нужны красивые, палитровые диаграммы, которые вставляются в PDF как PNG и правятся из Liber.

## Decision
LLM выдаёт `charts[].html` (Chart.js). Санитизация → offline Chart.js в `chart_frame.html` → Playwright screenshot `#mount` → `%CASE3_CHART:id%` → `\includegraphics`. Правка: `chart_edit` (local palette / LLM rewrite) + coerce/harden типов.

## Alternatives Considered

### matplotlib / plotly server-side
- Pros: детерминизм
- Cons: хуже «editorial» look, другой стек на винде
- Rejected for primary path

### Native PPTX/Excel charts
- Pros: editable in Office
- Cons: вне текущего PDF-first продукта
- Parked (см. parked-pptx)

### SVG in TeX
- Pros: вектор
- Cons: сложный LLM output, шрифты
- Rejected

## Consequences
- Soft-fail отдельного графика не валит весь PDF.
- Палитра enforce post-gen (`polish_charts` / `apply_palette_to_html`).
- Edit часто = полный rebuild PDF/DOCX (дорого) — кандидат на «PNG-first» в UX roadmap.
