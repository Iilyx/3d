# Architecture Decision Records

Нумерация: `NNNN-slug.md`. Статусы: Proposed → Accepted → Superseded / Deprecated.

| ID | Title | Status |
|----|-------|--------|
| [0001](0001-pipeline-qwen-latex-docker.md) | Pipeline: Qwen → TeX → Docker PDF/DOCX | Accepted |
| [0002](0002-charts-chartjs-playwright.md) | Charts: Chart.js HTML + Playwright PNG | Accepted |
| [0003](0003-liber-chat-first-ui.md) | Liber: chat-first UI over form desk | Accepted |
| [0004](0004-office-image-api.md) | Photos via office Image API (not Kandinsky-only) | Accepted |
| [0005](0005-tex-harden-over-perfect-model.md) | Harden TeX post-LLM instead of trusting model | Accepted |
| [0006](0006-liber-soft-premium-ui.md) | Liber soft-premium shell (Mary + Julius) | Accepted |
| [0007](0007-liber-ui-only-diagrams.md) | Liber UI-only Mermaid diagrams (+ PNG download) | Superseded by 0009 |
| [0008](0008-liber-deck-image-pptx.md) | Liber deck IR → native PPTX + deck PDF | Accepted, amended 2026-11-05 |
| [0009](0009-inclusion-of-diagrams-in-pdf-docx-reports.md) | Diagrams rasterized into PDF/DOCX | Accepted |
| [0010](0010-one-executing-run-one-waiter.md) | One executing pipeline, one queued run | Accepted, amended 2026-11-22 |
| [0011](0011-prior-turn-and-live-desk-signals.md) | Idle SSE, cancel flag, diagram ceiling. Prior turn superseded by 0013 | Accepted, amended 2026-11-19 |
| [0012](0012-image-opt-in.md) | Generated photos are opt-in | Accepted |
| [0013](0013-chat-memory-chain.md) | Chat memory is a 48-turn chain, not Source | Accepted |
| [0014](0014-dashboard-source-markdown.md) | Dashboard PDF cells + Qwen screen → markdown | Accepted |
| [0015](0015-user-stated-numbers.md) | User-stated numbers join the allow-list | Accepted, amended by 0016 |
| [0016](0016-number-beside-its-word.md) | A historical user number stays beside its word | Accepted |
| [0017](0017-plaque-wins-over-bare-analyze.md) | A plaque wins over a bare analyze line | Accepted |
| [0018](0018-p0-analytics-grounding-and-chat-charts.md) | P0 analytics grounding, derivatives, and inline chat charts | Accepted |
| [0019](0019-dashboard-filter-closes-previous-month.md) | A February filter is the January receipts | Accepted |
| [0020](0020-dashboard-landing-is-a-short-note.md) | Closing a dashboard writes a short note, not an essay | Accepted |
| [0021](0021-chat-screens-are-the-later-source.md) | Later turns and files use the chat's screens | Accepted |
| [0022](0022-concurrent-multiuser-runs.md) | Multi-user concurrent execution & per-browser workspace isolation | Accepted |

Новый ADR: скопируй [`0000-template.md`](0000-template.md), обнови таблицу выше.
