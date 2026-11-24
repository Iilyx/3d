# ADR-0003: Liber chat-first UI

## Status
Accepted

## Date
2026-10-21

## Context
Старый UI «форма + сайдбар» выглядел как дашборд и плохо подходил к сценарию «написал текст → получил отчёт». Нужен atelier-look и понятный прогресс сборки.

## Decision
React Liber — **chat-first**: composer + сообщения; advanced controls в `SettingsModal`; прогресс `PipelineFlow`; отчёт в `ReportView`; PDF pages через `pdfjs` (`PdfFirstPage`). API: `POST /api/run` → poll `/status`.

## Alternatives Considered

### Keep multi-panel form
- Pros: все knobs видны
- Cons: перегруз, слабый brand
- Rejected

### Stream LLM tokens into chat
- Pros: «живой» ответ
- Cons: артефакт — PDF, не чат-текст; сложнее
- Deferred

## Consequences
- Source из чата = тот же текст, что Intent, если нет файла — риск тонкого Source.
- Preview ≠ PDF (нужен PDF slider / фаза UX roadmap).
- Sticky download buttons убраны — actions в конце сообщения.

## Amendment (2026-10-21)
Chat-first сохраняется; тяжёлые артефакты (TeX preview, PDF, Source) открываются в правом **Artifact rail** (Julius-style), а не раздувают тред. См. `docs/superpowers/specs/2026-10-21-liber-artifact-rail-design.md`.

## Amendment (2026-10-21 · diagrams)
Artifact rail hosts Mermaid diagrams (Diagram strip + fullscreen + PNG download). See ADR-0007.

## Amendment (2026-11-07)
Тот же rail остаётся. Печать схем больше не UI-only: ADR-0009 кладёт `dia_*.png` в PDF и DOCX. Предложение выше про «не injected» историческое.
