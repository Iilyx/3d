# Codebase audit — 2026-10-29

Full Liber/case-3 pass after Deep cleanup (`cleanup-2026-10-29.md`).  
Sources: 3 explore agents (`src/case3`, `web/src`, `scripts`+`tests`+`prompt`+`workers`) + code-review-graph rebuild (206 files / 1602 nodes) + hub/large-function scan.

**Scope:** improve / simplify / reuse / fix / delete. Not new product features (see parked `backlog-deferred-2026-10-25.md`).

**Unified next plan:** [`docs/superpowers/plans/2026-10-29-liber-simplify-for-agents.md`](../superpowers/plans/2026-10-29-liber-simplify-for-agents.md) (Wave 0 hygiene + tracks A/B/C).

---

## Do first (P0) — status 2026-10-29 evening

| # | Action | Status |
|---|--------|--------|
| 1 | Track full `tests/test_*.py` + fixtures | **done** (`8bfd303`) |
| 2 | Archive `ROOT = parents[2]` | **done** |
| 3 | Gallery import from `scripts/archive` | **done** (+ `run_structure_matrix8` path) |
| 4 | Extract App hooks (`useLiberRun` …) | **done** |
| 5 | Split `api_edits` / `api_slides` | **done** |
| 6 | Dead helpers + orphan CSS (thinking-bar/export-menu) | **done** (wave 8) |

---

## Safe deletes / hygiene (P1) — applied in this pass where noted

| Path | Action | Status |
|------|--------|--------|
| `web/src/DeckMakeSplit.tsx` + split/gear CSS | Delete (0 imports; CTA in `ArtifactCard`) | **done** |
| `src/case3/kandinsky.py` | Delete shim (0 importers). Keep health key `kandinsky_configured` | **done** |
| `web/src/icons.tsx` `IconHistory` | Delete unused export | **done** |
| `web/src/diagramMetrics.smoke.ts` | Delete (unit `.test.ts` covers) | **done** |
| Root Week-1 shims (`liberTypes.ts`, … ×7) | Retarget ~12 files → `domain/`, then delete | **done** |
| `domain/liberModes.ts` `showDeckMake` | Remove flag + test assertion | **done** |
| Local junk `__pycache__`, worker `node_modules`/`.wrangler` | Optional local wipe (gitignored) | n/a |

---

## Reuse / simplify (P1)

### Backend (`src/case3`)

| Item | Action |
|------|--------|
| `*_edit.py` (chart/figure/table/paragraph) | Shared `rebuild_run_docs` (**done**); figures load soft-path via `slides_media` |
| Edit routes in `api.py` | `parse_formats_form` + `_resolve_run_dir` + downloads/bust helpers (**done**) |
| `_is_dark_pack` | `deck_theme.is_dark_pack` (**done**) |
| `_norm_hex` / hex expand | Scattered (`deck_theme`, `diagrams`, `docx_charts`) → small `color_util` if touch area |
| `pipeline.py` (~1270) + `resume_pipeline` | Extract stage runners; keep public API stable |
| `slides_pptx_native.py` (~1500) | **done** 2026-11-02 — split → `slides_pptx_draw` + `slides_pptx_layouts` |

### Frontend (`web/src`)

| Item | Action |
|------|--------|
| `editFigure` / `editImage` / `editTable` / `editParagraph` in App | One `postRunEdit({ url, body, toast })` (~280 lines shared) |
| Lazy-load `DiagramVisualEditor` / `@xyflow` | Eager today via `DiagramPane` on rail mount |
| Dynamic `import("mermaid")` in `MermaidView` | Static import pulls into main chunk |
| Gate `ChartsQa` + `useLiberDevPreviews` | Dev-only; keep out of default App chunk |
| `ReportView.tsx` (~970) | **done** 2026-11-02 — extract → `ReportBody.tsx` + `ReportPending.tsx` |
| `PdfFirstPage` lazy | Share one lazy import (`ArtifactRail` + `ReportView` duplicate) |
| `photoMode` always `"document"` | Collapse branches in `canSend`/`send` |
| Split `styles/chat.css` (~5821) | thinking / diagrams / charts-qa / pipeline |

---

## Hub nodes (blast radius)

| Hub | Degree signal |
|-----|---------------|
| `App` / `send` | Largest FE hub — touch last without extract |
| `run_pipeline` / `resume_pipeline` | Pipeline spine |
| `api_run` | HTTP entry |
| `resolve_deck_theme` | Deck colors/packs |
| `_parse_slide` / slides HTML+PPTX layouts | Deck IR → render |

---

## Scripts / prompt / workers

| Finding | Note |
|---------|------|
| Archive ROOT `parents[1]` | **Bug from cleanup** — fix P0 |
| Overlapping matrices in archive | Keep one desk + one slides matrix after ROOT fix; rest optional |
| `prompt/gold/*` + themes | All referenced — **do not delete** |
| `workers/case3-image` | Health OK; `negative_prompt` ignored by design; `/edit` may fall back to text generate |
| KI-liber-deck paths | Still cite pre-archive script paths — doc drift |

---

## Do **not** do (parked / rejected)

- New product from deferred backlog B/C3/C5/F/G library/I queue/J brand kit/K brainstorm
- Angular rewrite / chart whitelist changes / inventing pipeline stages
- Deleting `cli.py` (entry: `pyproject` + `scripts/run.cmd`)
- Deleting health alias `kandinsky_configured` (UI still reads it)

---

## Suggested order of work

1. Tests into git + archive ROOT + gallery import (hygiene, ~30 min)
2. Dead FE deletes + shim retarget (half day)
3. `useLiberRun` extract from App — **done**
4. `api.py` route modules + shared edit helpers — **done** (`api_edits` / `api_slides`)
5. Bundle lazy-loads (mermaid / xyflow / ChartsQa) — **done**
6. Larger splits (`slides_pptx_native`, `pipeline`, `chat.css`) — **done** 2026-11-02 (pptx draw/layouts; ReportBody; buildRunFormData)

---

## Backend detail (from [case3 backend audit](d0309e97-71a9-4f70-a006-4d0625bd3d8c))

Still open after safe deletes:

| # | Item | Pri | Status |
|---|------|-----|--------|
| 4 | Edit routes → `parse_formats_form` (4× copy) | P1 | **done** |
| 5 | `edit_run_figure` → `_resolve_run_dir` | P1 | **done** |
| 6–7 | Shared `_edit_response` + `rebuild_run_docs` | P1 | **done** |
| 8–10 | Share `load_figures_json` / `_is_dark_pack` / hex parsers | P1 | dark_pack done; hex → color_util (deck/docx/charts/diagrams/pptx) |
| 11–13 | Split `api.py` / pipeline media path / pptx layouts | P1 | routers done; pipeline media shared; **pptx layouts done** 2026-11-02 |
| 16 | Документация: label counters disagree (`chart_style` vs coerce) | P1 | **wontfix docs** — `_count_chart_labels` is heuristic in `chart_style` only; coerce uses `CHART_TYPES` whitelist, not label counts |
| 17 | Bare `except` in `slides_pptx_charts` → log | P1 | **done** (`log.debug`) |

## Applied this session

- Audit doc (this file)
- Deleted `DeckMakeSplit.tsx`, `kandinsky.py`, `IconHistory`, `generate_tex`, `inject_figures`, `KandinskyConfig`, `ensure_deck_has_chart_slide`
- Pruned split/gear CSS; kept `.deck-make-primary.is-ghost` for `ArtifactCard`
- Fixed archive `ROOT` → `parents[2]` + gallery import
- KI-liber-deck paths → `scripts/archive/…`
- Wave continue: `run_rebuild.py`; edit routes → `parse_formats_form` / `_resolve_run_dir`; `deck_theme.is_dark_pack`; FE Week-1 shims deleted; `showDeckMake` removed
- Wave 3: dynamic `mermaid` import; lazy `DiagramVisualEditor`/`ChartsQa`; `postJsonEdit` shared edits; pdfFindPage → node:test; drop `diagramMetrics.smoke.ts`
- Wave 4: `api_edits.py` + `api_slides.py` routers; `useLiberEdits` extracted from App
- Wave 5: `useMakePresentation` + `useResumeFailedRun`; App ~2840→2076 lines
- Wave 6: `useLiberRun` (`send`); App ~1273 + `useLiberRun.ts` ~1002
- Wave 7: `slides_pptx_charts` bare except → `log.debug`; audit backend table synced
- Verify (post–Wave 6): **438 pytest**, **54 web helpers**, `tsc` + `npm run build` OK, `/api/health` all green
- Wave 8: dead helpers (`_kick_pipeline_thread`, `default_*_box`, `_align`, …); orphan CSS; unused api imports; `modeNudge`/`loadLastReport`; matrix8 archive path
- Functional (Wave 7): UI dry-run via Liber desk → `status=ok`, PDF/DOCX, artifact rail + history (`source_20261029T195115Z`, ~3s)
