# PPTX / Liber presentation deck

**Status:** **implemented (v1)** — image PPTX + deck PDF + Liber tab.  
**Design:** [`docs/superpowers/specs/2026-10-22-liber-pptx-deck-design.md`](../superpowers/specs/2026-10-22-liber-pptx-deck-design.md)  
**ADR:** [`docs/adr/0008-liber-deck-image-pptx.md`](../adr/0008-liber-deck-image-pptx.md)  
**KI:** [`.agents/knowledge/KI-liber-deck.md`](../../.agents/knowledge/KI-liber-deck.md)

## v1 summary

- On-demand `POST /api/runs/{id}/slides` (not every report run).
- Deck IR → Liber static HTML → Playwright PNG → `{stem}_slides.pptx` + `{stem}_deck.pdf`.
- Layouts: title, kpi_row, chart_*, media_* (photos + Mermaid→PNG), bullets, closing; optional `kicker`.
- Live LLM path validated on 10 real `runs/out` (2026-10-22); numbers from Source + chart captions.
- Freeform (no structure template): beat planner + number scrub heal; live 3/3 QA `runs/freeform_slides_live/` (2026-10-24).
- **PPTX is native editable** (`slides_pptx_native.py`); Liber preview = token twin; **deck PDF = LO-convert PPTX** (PNG stitch fallback).
- **Formats:** PPTX rail = twin/edit; PDF rail = vertical film (`DeckSlidesFilm`). «Скачать» on chat cards **and** rail (same `deck-slides-film-dl` pattern). No Export sheet.
- **After deck ok:** pulse cards in chat; **do not** auto-open artifact rail.
- **Stop:** `POST /api/runs/{id}/cancel` + UI «Останавливаю…» until `cancelled`; cooperative checks in LLM / slides stages.
- Extra theme skins / richer native layouts — later.
