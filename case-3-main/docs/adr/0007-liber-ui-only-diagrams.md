# ADR-0007: Liber UI-only Mermaid diagrams

## Status
Superseded by [ADR-0009](0009-inclusion-of-diagrams-in-pdf-docx-reports.md) (2026-11-07). Историческое решение: схемы только в Liber. В коде слот `%CASE3_DIAG` и PNG в PDF/DOCX.

## Date
2026-10-21

## Context
Нужны смысловые схемы (процесс, структура, ветвления) вместе с отчётом. Chart.js покрывает числа; PDF уже print truth. Пользователь выбрал: схемы **только в Liber**, с скачиванием PNG — без inject в PDF/DOCX.

## Decision
- LLM JSON получает `diagrams[]` (Mermaid) рядом с `figures` / `charts`.
- Нет TeX-слотов `%CASE3_DIAG`, нет Playwright/inject стадии для схем.
- Liber Artifact rail: Document tabs (Preview·PDF·Source) + Diagram strip; fullscreen portal; client PNG.
- Soft-fail: битый Mermaid отбрасывается; pipeline остаётся `ok`.
- Cap: `CASE3_MAX_DIAGRAMS` / Settings 0–3 (default 2).

## Alternatives Considered

### Mermaid → PNG → TeX inject (like charts)
- Pros: единый print path
- Cons: пользователь отказался от PDF; усложняет inject
- Rejected

### Second LLM call after TeX
- Pros: чище system_tex
- Cons: latency/cost
- Rejected for v1

## Consequences
- Preview/PDF/DOCX **не содержат** Mermaid-схем — только Liber Artifact «Схема» + optional PNG download.
- Числа в PDF по-прежнему через Chart.js; схемы ≠ графики.
- Prompt must teach structural vs numeric (diagrams vs charts).
- ADR-0001 print truth unchanged for charts/photos.
- **2026-10-23:** в `output_mode=diagram` после llm всегда `diagram_repair` (2-й LLM, soft-fail) — см. spec repair+premium.
- **2026-10-23 (annotated flow):** числа из Source на labels узлов/рёбер (`Заявка<br/>820`, `|62%|`); Liber chips «Числа на схеме»; prompts short labels (без SDR/SE в тексте узла). Spec: `2026-10-23-annotated-flow-design.md`.
- **2026-10-23 (UX):** legend highlight (prefixed Mermaid ids), PNG via data-URI, fullscreen scroll top.
- **2026-10-30 (UX):** Liber «Ещё вариант» → `POST …/diagrams/regenerate` + undo `diagram_regen`; empty diagram mode — honest chat + empty-pane CTA.

## See
Spec: `docs/superpowers/specs/2026-10-21-liber-semantic-diagrams-design.md`  
Plan: `docs/superpowers/plans/2026-10-21-liber-semantic-diagrams.md`  
Repair+UI: `docs/superpowers/specs/2026-10-23-liber-diagram-repair-premium-design.md`  
Annotated flow: `docs/superpowers/specs/2026-10-23-annotated-flow-design.md`
