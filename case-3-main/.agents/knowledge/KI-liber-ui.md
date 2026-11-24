# KI: Liber UI

## What
Vite React soft-premium chat desk: sidebar + compose → poll run → compact chat card + **Artifact rail** (Preview · PDF · Схема · Source).

## Entry
- Map: `web/ARCHITECTURE.md` · modules spec `2026-10-25-liber-frontend-modules-design` (Week 1: `app/` `api/` `domain/`)
- `web/src/app/App.tsx` — shell: state + `send`/`edit*` + rail wiring (flat UI still at `web/src/*.tsx`)
- `domain/` — types, modes, constants, phrases, history, runHelpers · `api/summaryStream` — SSE (root shims keep old import paths)
- `ChatMessages.tsx` / `ChatComposer.tsx` / `ComposerPhotoChips.tsx` — transcript + composer UI
- `useLiberDevPreviews.ts` — `?preview=artifact|flow` bootstraps
- `Sidebar.tsx` — New / History (sessionStorage) / Settings; collapse
- `EmptyState.tsx` — «Чем займёмся?»; empty desk uses `is-empty-home` (composer centered mid-viewport like Julius)
- `liberModes.ts` + `ChatComposer` pills: Отчёт · Схема · Презентация — **остаются** после первого сообщения; gallery только empty∧presentation; стиль → `DeckStyleSheet`
- Template apply: **только** pack+structure (не DNA-промпт в чат); honesty «пример · 6 кадров / 10–12 в деке». Отправка не режется порогом 48 символов: пустой/бессмысленный запрос ловит `input_validation` и остаётся сообщением в чате (`insufficient_data`), карточка артефакта не открывается
- `output_mode=presentation` → `formats=none` (без PDF/DOCX) + после run сразу `makePresentation`; rail **не** авто-открывается — Julius large `DeckFileCard`s in-chat; rail only on card click
- Mode surfaces (2026-10-23): **report** → rail Превью(+PDF)+Схема if any; **diagram** → **only Схема** (no Preview/PDF/Source; formats=none); in-chat `DiagramChatCard` = live Mermaid + source snippet (Julius); **presentation** → only PPTX+deck PDF. Auto-open primary tab on finish. `output_mode` in meta.
- Deck in-chat: **PPTX** = file card (download + Изменить); **PDF twin** = `DeckPdfGallery` (slide images only, no download, ←/→ + strip)
- Julius in-chat cards (2026-10-23): matte paper stage + file glyph + hover veil + footer «→»; deck = PPTX+PDF twin (+ filmstrip); report = A4 sheet; diagram = sketch hero; `DeckMakeSplit quiet` under cards; empty hero = Crimson serif + segmented mode track; `?preview=deck` QA; history/restore **не** auto-open rail
- Deck gen (2026-10-23): `makePresentation` **closes rail**, keeps progress in chat (`DeckBuildCard` + thinking); presentation tab only when `ok`/`error`; `thinkingMode` pools in `pipelinePhrases.ts` (report/diagram/presentation + slides_*)
- Julius strip (2026-10-23): composer `Working · m:ss` on **any** busy run (report/diagram/deck); chat column session title from `preview.title` (`provisionalSessionTitle` → `reportTitle`) — **scrolls with transcript**, not sticky over cards; sidebar brand unchanged
- Empty-home (2026-10-23): all pills use `is-empty-stage` @ `--deck-stage-max` — composer = starters = templates same width; `ModeStarterGrid` under input for report/diagram/**presentation**; rail-open chat column centered
- `ThinkingFold.tsx` + `pipelinePhrases.ts` — collapsible «Размышления» in bot bubble (Flow above); no ThinkingBar; phrases from large pools, seeded per run (`thinkingStartedAt`) so logs don’t repeat the same sequence
- `icons.tsx` — stroke icon set (no emoji chrome)
- `ChartCard.tsx` — optional insight/highlights around chart figures
- `reportHistory.ts` — local history + last-run payloads
- `ArtifactRail.tsx` — sidecar: tabs (Превью·PDF·Схема·Source), Export, resize, sticky TOC (`RailToc`), figure→PDF, SourcePane
- Source draft click-to-edit (2026-11-02): live `sourceDraft` + artifact `kind=source` → preview click → textarea; Esc/blur back; write-through to draft — spec `2026-11-02-liber-source-draft-edit-design`
- Report collapse (C11): chevron on headings in `ReportView`; body until next same/higher level; `sessionStorage` `liber-report-collapse:{runId}` via `reportSections.ts`
- `DiagramPane.tsx` / `MermaidView.tsx` / `DiagramFullscreen.tsx` / `downloadDiagramPng.ts` — tab «Схема»; PNG + **SVG** download (live DOM; API `GET …/diagrams/{id}/svg` fallback). The same `dia_*` PNG is injected into PDF/DOCX
- `ArtifactCard.tsx` / `ContextPlaque.tsx` / `ExportMenu.tsx` / `PdfThumb.tsx`
- `SettingsModal.tsx` — palette, types, limits, dry-run
- `ReportView.tsx` — TeX blocks + edit; top **Редактировать** / **Готово** (`editMode`) — only then «Изменить» on paragraphs/tables/charts/photos; ChartCard wraps charts; tables → `TableEditSheet`; paragraphs → `ParagraphEditSheet` (`para-N`); leave mode closes sheets (`reportEditMode.ts`)
- `PipelineFlow.tsx` — stage animation while pending

## Invariants
- Proxy `/api` → `:8000` (vite)
- Chart type badge not shown in caption (title= only)
- Full report/PDF live in Artifact rail; chat shows streamed LLM **chat summary** (prose) + card — not bare «Отчёт готов»
- Summary SSE: `GET /api/runs/{id}/summary/stream` while stage `latex`/`docx`; light markdown via `lightMd.tsx`
- Report downloads: **one** chat card (Source → PDF+DOCX twin links) + rail header PDF/DOCX (`reportDownloadLinks`); no Export ▾
- `sessionStorage` last report + history list → opens rail
- Attach `.txt/.md` or intent >400 chars → `ContextPlaque` (eyebrow «Документ», not Source/Текст) + Source tab labeled «Документ»
- A screen capture or a dashboard PNG with no PDF table sets `fromScreen`. The plaque says the model could read the numbers. A document that contains `## Таблица PDF` or «скопированы из ячеек» does not: those digits were copied from the file. Success toast: «Данные прикреплены». The × on the document chip hides the chip. The attached text and file stay, and the open document stays on the rail.
- A finished report card has «Сделать презентацию» until the deck is queued or ready (`reportCanMakeDeck`).
- The photo chip and `max_images` stay off unless a photo is attached or the message asks for one.
- Undo hints use Ctrl+Z on Windows and Linux, ⌘Z on a Mac.
- Attach PDF/DOCX/DOC/RTF → `POST /api/source/ingest` → Source draft (edit before run); photos stay `usr_*`
- Deck build: `ThinkingFold` auto-opens with `live` + «Собираю презентацию» while `slides_*` / slides_status running|queued; `DeckBuildCard` under ArtifactCard; QA `?preview=deck-busy`
- `PdfThumb`: skeleton+shimmer while pdf.js loads (not empty “PDF” stub)
- Rail width persisted in `localStorage` key `liber-rail-width` (dblclick reset)
- Close rail: keep `activeArtifact` until width→0 (`railExiting` + `onClosed`); don’t null early (snaps user bubble). Guard `onAnimationComplete` until width &lt; 32px.
- Quiet Mono tokens in `web/src/styles/tokens.css` (ink/paper editorial; no olive chrome) — split: shell/chat/composer/deck/rail/presentation/modals; PDF = print truth (rail hint). Spec: `2026-10-23-liber-quiet-mono-ui-design.md`
- Premium UI refactor 2026-10-22: empty-home desk scrolls; composer send right; deck style only via `DeckStyleSheet`; template gallery Julius-stage mocks; `useFocusTrap` on modals/FS
- Template preview 2026-10-22: modal = **6-slide vertical scroll**; **PNG-first** Liber twins only (`scripts/render_template_previews.py` → `web/public/deck/previews/{structureId}/01–06.png`); Julius refs = style DNA, not gallery screenshots; CSS mock = fallback
- Craft floor = botanical (wine): board/signal/atelier now have `motif.foil_cards` + `panels` + `table.body_fill` (`deck_theme` passes through); foil chrome via `_foil_cards()` not botanical-only
- Specs: `2026-10-22-liber-template-preview-6slides-design.md` · `2026-10-22-liber-template-parity-botanical-bar-design.md`
- Spec/plan: `docs/superpowers/specs/2026-10-22-liber-premium-ui-refactor-design.md` · `docs/superpowers/plans/2026-10-22-liber-premium-ui-refactor.md`
- Diagrams render in the rail **and** in PDF/DOCX (ADR-0009). Settings «Схем ≤» 0–5 (`DIAGRAMS_HARD_MAX`, default 5). Client PNG/SVG download stays. Primary edit is the visual React Flow pane. `DiagramCodeModal` still edits raw Mermaid (any diagram type) when that modal is opened; the always-on syntax preview in the pane was removed 2026-11-07
- Composer mode **Схема** → `output_mode=diagram` + `formats=none` (no PDF/DOCX); rail opens «Схема» + chat summary as short description
- Spec: `docs/superpowers/specs/2026-10-22-liber-composer-modes-design.md`
- Focused workbench: rail default ~62%; card has no Export (rail only); Presentation CTA primary — `docs/superpowers/specs/2026-10-22-liber-focused-workbench-design.md`
- Schema tab: premium hero (type RU · Liber·PNG + serif title); PNG primary; zoom ± / % / short hint; PNG via viewBox + slug(title); fullscreen has own SVG ref
- Mode **Схема**: after llm, pipeline stage `diagram_repair` (2nd LLM) enriches Mermaid from Source; soft-fail keeps draft; meta `diagrams_repaired` / `diagrams_draft` in figures.json — see `docs/superpowers/specs/2026-10-23-liber-diagram-repair-premium-design.md`
- Diagram colors: **model-owned** Mermaid `:::role` + `classDef` (start/process/decision/ok/warn/data, Liber hex by Settings palette); sanitize strips `click` + purple neon → sage (`diagrams.sanitize_mermaid`)
- Schema pane: legend · **Ещё вариант** (`POST …/diagrams/regenerate` + undo) · **Изменить** → visual React Flow editor (flowchart IR; Mermaid textarea fallback) · `POST …/diagrams/{id}/edit` — specs `diagram-edit-legend` + `diagram-visual-editor`. Empty mode keeps tab + CTA.

## Gotchas
- C8: run error bubble may include `график …` / `TeX: …` from status `failed_charts` + `latex_log_tail`
- Chart type chip hover: portal card `pointer-events:auto` + delayed hide; unknown typeId → GlyphBar fallback (G1)
- Edit sheet palette seeds from `block.palette` then Settings default (G2)
- Chat Source without file = Intent text
- pdfjs chunk lazy-loaded — need `npm install` after pull
- Figure→PDF: **pdf.js text search** by caption (TeX `pdfPage` hints omit natural breaks → badge no longer shows «с.N»; jump must not seed page=1 or it clobbers find)
- Donut print canvas forced square in `enhance_donut_html` (LLM 1100×560 → oval)
- Image edit sheet: no second preview body (figure above stays source of truth); chat summary kept on Apply
- Live Chart.js in Preview + edit sheet (`LiveChart` inline mount — no iframe / `GET…/charts/{id}` + `POST…/preview`); PDF remains print truth. Blur root cause was iframe fractional-px compositor layer, not Chart DPR alone. Retina live DPR → 3. QA all types: `?preview=charts-qa` + `web/public/qa-chart-fixtures.json`.
- After chart Apply, `ChartLivePane` must refetch on URL `?v=` bust (stale HTML otherwise)
- Live frame CSS mirrors `chart_frame.html` (donut legend / KPI); no CSS `scale` (breaks hover hit-testing)
- Live donut canvas must stay **in-flow** (not `absolute; inset:0`) — stretch inverted arc hit-tests; doughnut interaction = `nearest`+`intersect`; `.live-chart` overflow visible so center tooltips show
- User bubble: collapsed Intent + `chips[]` (C6); long text still opens Source
- Global `editingFigureId` locks all edit buttons (`tab:N` = table edit busy id)
- Table / paragraph edit: empty `run_id` → FastAPI `Not Found` on `/runs//…`; guards in `editTable` / `editParagraph`; need fresh run on disk + API process that includes the route (restart uvicorn after pull). Rebuild needs Docker `case-3:tex` (same as table edit).
- ArtifactCard: strip `?v=` from download labels; `source.pdf` → «Отчёт.pdf»
- History payloads are session-only; refresh keeps them until tab close
- `web/public/vendor/chart.umd.min.js` required for live iframes (Vite static)

## See
ADR-0003 · ADR-0006 · `docs/superpowers/specs/2026-10-21-liber-soft-premium-ui-design.md`

## Desk chrome (2026-11-10)

- Confirms: `ConfirmProvider` in `App.tsx`, `useConfirm()` in slide/chart/photo/folder delete and unsaved diagram close. No `window.confirm`.
- Attached photos: click the chip in composer or chat to preview (`ComposerPhotoChips`, `ChatMessages`).
- Chart type badge stays off the live chart (`LiveChart`).
- History sync: `GET /api/history` + `POST /api/history/sync` (`useReportHistory`).

## Chat-first (2026-11-18)

Default send is a chat answer, full width, no bubble. The user message is a right bubble. Plaques Отчёт · Схема · Презентация sit above the composer and only bias the next send. The message wins when it names an artifact: «проанализируй отчёт» stays in chat; «проанализируй регионы» with the report plaque builds a report; «сделай презу» builds a deck even with the plaque off. An artifact turn speaks a short line first (`chat_opening`), then the existing pipeline, then the card and the side rail. Router: `turn_route.resolve_turn`. Spec: `docs/superpowers/specs/2026-11-18-liber-chat-first-design.md`.

## Preview full edit (2026-11-02)

Top «Редактировать» expands all sections and opens inline prose/heading/list editors + media sheets (no per-block «Изменить»). APIs: `/headings/{n}/edit`, `/lists/{n}/edit`. Spec: `docs/superpowers/specs/2026-11-02-liber-preview-full-edit-design.md`.
