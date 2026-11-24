# KI: Liber presentation deck

## Entry points

- API: `POST /api/runs/{id}/slides`, `GET …/slides`, `PATCH …/slides/ir` (text), `POST …/slides/structure` (reorder|duplicate|delete → IR + rebuild twin/PPTX, no LLM), `POST …/cancel`, `GET …/slides/png|media/{name}`
- Job: `src/case3/slides_job.py` (`rebuild_slides_from_deck` after edit/structure)
- Structure: `slides_patch.apply_deck_structure` · UI filmstrip/gallery DnD + Дублировать/Удалить (confirm)
- Cancel: `src/case3/run_cancel.py` — cooperative `cancel_requested` between stages + `LLMClient.complete(cancel_check=…)`
- IR: `src/case3/slides_ir.py` + `slides_patch.py` (text-only) + `prompt/system_slides.md`
- Capture: `slides_html.py` / `slides_render.py` / `templates/slide_frame.html`
- Export: `slides_pptx_native.build_native_pptx` (facade) + `slides_pptx_draw` (fonts/shapes/bg) + `slides_pptx_layouts` (layout painters) + `slides_lo.py` (LO PPTX→PDF, Julius) + `slides_export.build_deck_pdf` (PNG fallback)
- UI: `PresentationPane.tsx` (PPTX twin) + `DeckSlidesFilm.tsx` (PDF vertical film) + `DeckCanvas.tsx` + `DeckFileCard.tsx`

## Invariants

- Not part of `formats` / Docker TeX. Composer **Презентация** → `formats=[]` (no report PDF/DOCX). Diagram budget stays at least 1 so `dia_*` can be placed on the deck.
- **One presentation, two formats:** PPTX tab = live twin + edit; PDF tab = vertical slide film. Same deck IR.
- **Download contract:** «Скачать» on **both** `DeckFileCard` (chat) **and** rail head (`deck-slides-film-dl` next to slide count). No Export sheet / `is-export` chrome.
- **After slides ok:** pulse cards in chat; **do not** auto-open artifact rail.
- Layouts: `title` | `section` | `kpi_row` | `scorecard` | `card_row` | `chart_hero` | `chart_split` | `media_hero` | `media_split` | `table_hero` | `callout` | `bullets` | `closing` | `stat_hero` | `timeline` | `compare` | `quote`. Cross-fields: `chapter?`, `takeaway?`.
- `table_hero` keeps 14 rows (header included) and 8 columns. A longer grid is the report table, not the slide. More than 8 data rows uses the dense table style.
- Prompt: `system_slides.md` + `prompt/themes/slides_{pack}.md` + `structure_{id}.md`.
- **Long Source:** `slides_source_text` replaces a spec longer than 8000 characters with a map (size, headings, sentences that contain numbers, at most 4 code signatures). The number gate still uses the full Source. Shorter text is passed through; listings get a CODE HIGHLIGHTS tail.
- **Code listings:** `code_highlights` keeps one signature per fence (`def` / `function` / method). `ensure_code_callouts` adds a `callout` (kicker КОД, term = name, definition = that line) if the model skipped it. The rest of the listing is not a slide.
- **Slide wish:** Settings «Слайдов в презе» (6–24, default 12, `localStorage liber.slidesTarget.v1`) → `POST /api/run` field `target_slides` → `meta.slides_target`. Beat planner keeps the template arc and **repeats its narrative layouts** up to that count (charts/photos are not cloned). Model may emit fewer if Source is thin. IR hard max **24**. A kicker that is only `01` or `1`…`24` is chrome. A table cell `07` or `12` needs Source.
- **Anti-monotony:** ≥5 distinct layouts when ≥8 slides; vary beat 2; cap consecutive scorecards; title takeaway hero KPIs on split packs.
- **Premium twin craft:** `card_row` leading `%` → `narr-meter` (HTML+PPTX); chart caption=`caption--insight`; closing `takeaway` → `closing-hero`; grain on `signal`/`ink`/`voltage`/`botanical`; pack charts via `scripts/archive/render_premium_gallery_charts.py`.
- Media ids only from run: `cht_*` PNG, `fig_*`/`usr_*` PNG, `dia_*` Mermaid→PNG (`slides_media.py`).
- **Photos:** API keeps up to 5 uploads (`clip_photo_files`). A numbered list in the intent (`1. логотип…` / `3. 4. 5. интерфейс` / `1. схема…`) becomes captions when the form sends none. Presentation with uploads sets the generated-image budget to 0 (`split_image_budget`) so leftover slots are not `fig_*`. `ensure_deck_photos`: «лог» → `media_hero` right after the title; word overlap → `media_split` beside that slide; no overlap → spread through the body, not a stack before closing. Cap 24: a filler layout is replaced.
- **Edit a schema on a slide:** edit mode → click the `dia_*` picture → same visual Mermaid editor. Save writes `figures.json`, copies the title onto that slide, then `POST /slides/rebuild` re-rasters the PNG and PPTX.
- **Schema photos:** caption with «схема»/«диаграмма», or every upload unlabeled while the intent says «перерисуй схемы», becomes Mermaid (`schema_redraw.py`, max 3) before the deck LLM. The source `usr_*` is not placed. `ensure_deck_diagrams` inserts a `media_hero` for each unused `dia_*`. Logos and UI screenshots stay photos.
- Numbers ⊆ Source. Whole-token match; spaced thousands `9 330` ≡ `9330`.
- **Freeform (no `structure_id`):** `slides_beat_planner.plan_beats` → skeleton. Live QA: `scripts/archive/run_freeform_slides_live.py`.
- **Number heal:** `scrub_invented_numbers` on IR reject. Meta: `slides_number_scrub=true`.
- **Chrome nums:** zero-padded `01`…`099` anywhere, and a field that is only `1`…`24`. A sentence that contains `1`…`24` (`3 фокуса`, `Блок 24`) still needs Source. A sentence that mixes a source number with an invented one is dropped whole, so a title does not stay as «в раза». After `bind_deck_numbers`, a slide with no remaining text is dropped. If that would empty the deck, one title slide «Итоги» remains.
- **Single kick:** UI must not `POST /slides` twice (SSE `pipeline_ok` + `makePresentation`). `slidesJobNeedsKick` / in-flight → attach only.
- **LLM 402 credit clamp:** `llm_client` re-clamps `afford` max_tokens (up to 4 shrinks).
- Downloads: `pptx` + `deck_pdf` (`deck_pdf_mode`: `lo` | `png_stitch`). Report `pdf` untouched.
- **PPTX = visual truth**; Liber twin ≈ tokens (ADR-0008). Deck style ≠ report palette.
- Soft-fail: `slides_status=error|cancelled` does not flip report `status`.
- **Stop:** UI shows «Останавливаю…» until meta `cancelled` (or timeout); `POST /cancel` sets `cancel_requested`. Checkpoints: pipeline `bump`, LLM `cancel_check`, slides `_set_slides` / render / pptx / PDF. `PresentationPane` has explicit `cancelled` state (not error).

## Theme / style

- Packs: `atelier` · `board` · `signal` · `relay` · `ink` · `voltage` · `studio` · `botanical`.
- Structures: **eleven** (`board_update`, `performance`, `qbr`, `survey`, `council`, `campaign`, `quarter`, `investor`, `launch`, `workshop`, `hire`). Gallery shows **8** unique visual packs. `launch` / `workshop` / `hire` attach by brief keywords. Arc: question, compare only when Source has two sides, one decision.
- UI: `DeckStyleSheet` + `DeckTemplateGallery`; `localStorage liber.deckStyle.v1`.
- Presentation UX: Preview → Slide → Edit; Present = click-advance + idle chrome hide + Space/←/→; Esc exits; concurrent IR PATCH coalesces (no 409).
- API: `POST /api/run` stamps `deck_pack` + `deck_structure_id` + `deck_style_json` → `meta.slides_style` (survives pipeline rewrite via `merge_desk_slides_fields`). Auto-kick slides uses that style (`slides_kick_source=api_auto`). `POST …/slides` may still send `theme_pack` + `style_settings` as backup.
- Roadmap: [`docs/superpowers/specs/2026-10-22-julius-live-ux-parity-design.md`](../../docs/superpowers/specs/2026-10-22-julius-live-ux-parity-design.md).

## Fonts (PPTX)

- Roles: `fonts.title` → title runs; `fonts.body` → body (then `fallback_pptx` only if body missing).
- Liber/web faces map in `slides_pptx_draw._office_font_name`: Liber Serif/Fraunces/… → Georgia; Liber Sans/Inter/… → Calibri; Aptos Display → Aptos.
- Twin HTML may still use woff2; PPTX must not look “all Calibri” when pack declares serif titles (atelier/botanical → Georgia titles).

## Native diagrams (PPTX)

- `slides_pptx_diagrams.add_native_diagram` from layout painters. Returns `True` → shapes; `False` → existing PNG (`_picture_fit`).
- Native: `flowchart` (≤10 nodes; more → PNG), `timeline`, `mindmap`. `sequenceDiagram` and `stateDiagram` stay PNG.
- Colors from `diagram_style.role_colors_for_palette`. Spec `2026-11-07-pptx-native-diagrams-design` (out-of-scope line about timeline/mindmap is stale; code draws both).
- Slide UI: zoom overlay + bullet↔node highlight (`diagramSlideSync.ts`, `bullet_node_map`). Edit schema on a slide still writes Mermaid, then rebuilds PNG and PPTX.

## Batch render

- Deck chart PNGs share one Chromium via `charts.render_charts_batch` (`slides_job.py`). Same helper serves `POST /api/runs/{id}/charts/recolor`.

## Native charts (PPTX)

- Every deck slide with eligible `cht_*` embeds OOXML (`ppt/charts/…`); Liber twin stays PNG.
- Series IR on `figures.json` charts (`series` field) via `attach_series_ir`; PPTX prefers it over HTML regex (`slides_chart_data`).
- Whitelist: bar / grouped_bar / stacked_bar / horizontal_bar / line / area / donut. KPI/scatter → PNG.
- Colors from pack `chart_series` (per-point for single-series bar/donut).
- Every eligible `cht_*` in run must appear in deck: `ensure_deck_charts` injects missing `chart_hero`s (meta `slides_chart_injected` = list of ids).
- Twin recolor: pack `chart_series` + per-category colors for single-series bar/donut (`apply_pack_category_colors_to_html`) so twin ≈ native.
- Donut native: % data labels + series name from caption (not anonymous `Series`).
- Spec: `docs/superpowers/specs/2026-10-26-liber-pptx-native-charts-design.md`.

## Gotchas

- Slides job = **daemon thread**; meta `running`/`starting` before kick. Crash → `slides_error` (never forever-`queued`).
- Report `/api/run` = daemon thread (not BackgroundTasks — Windows stall).
- Capture: home Playwright browsers if sandbox path broken.
- Mermaid: `web/node_modules/mermaid/dist/mermaid.min.js`.
- Stem: `{stem}_slides.pptx`, `{stem}_deck.pdf`.
- **deck_pdf:** LO-convert native PPTX; fallback PNG stitch. Env `CASE3_SOFFICE`.
- **No-JSON retry:** `slides_job._retry_user` prepends the original user text. A retry must not drop Source.
- **Diagram roles:** `ensure_role_classdefs` uses the run palette (`role_colors_for_palette`), not pack `chart_series`. Canvas legend strokes live in `web/src/deckStyle.ts` `diagramLegendStrokes` and must match `_ROLE_MAP`.
