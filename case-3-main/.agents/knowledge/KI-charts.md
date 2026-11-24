# KI: Charts

## What
LLM HTML (Chart.js) → sanitize → Playwright PNG → inject; Liber edit restyles.

## Entry
- Gen: `charts.generate_all_charts` after coerce/`polish_charts`
- Edit: `POST /api/runs/{id}/charts/{cid}/edit` → `chart_edit.edit_chart_in_run`
- Recolor every chart in the run (no LLM): `POST /api/runs/{id}/charts/recolor` · UI `RecolorChartsModal` (shipped 2026-11-07; backlog B19 rejection is obsolete)
- PNG batch: `charts.render_charts_batch` — one Chromium for the deck and for recolor
- Types: `chart_html.CHART_TYPES`; coerce: `chart_types_coerce.py`
- Palette: `chart_style.apply_palette_to_html` + `palette_from_intent` — 4 chromatic presets from Okabe–Ito / Paul Tol / Tableau 10 (+ mono greys); no purple; D10 `palette_fallback_table` → `{{PALETTE_TABLE}}`
- Prompt: freer HTML (layout/cutout/radius); gold `chart_slot.tex` = TeX slot only
- G2: `charts[].palette` stamped in polish/edit → preview `palette` seeds ChartEditSheet
- Print legend: `.valued-legend` ≥18px + first-row emphasis in `chart_frame.html`; D7 width ≤0.92`\textwidth`, canvas h≤560
- Stacked: harden injects white segment borders if missing
- Legend+tooltip: `ensure_legend_and_tooltips` in polish — Chart.js legend on for multi-series; donut keeps HTML `.valued-legend`; Liber hover tooltips always on (`LiveChart`)
- `_count_datasets` must ignore scatter `{x,y}` points (else false multi-series legend)
- Scatter: a small cloud stays at `pointRadius` 10. 16–35 points use 6, 36 or more use 4. Line/area stay ≥5. Hbar gets a per-category color array from the palette.
- Vertical bar with 8 or more categories gets `maxRotation:45` and `autoSkip`. Horizontal bar does not.
- Donut legend: 8 or more slices use `.valued-legend.is-dense` (two columns, names wrap). A positive slice never prints as `0%`; a share under 0.5% keeps one decimal (`0,4%`).
- Word native charts: `extract_chart_series` walks every top-level dataset, including `data` before `label` and nested objects. A second series must reach DOCX.
- A category label that names one table row may keep only that row's numbers (`fact_ground._row_norms_for_label`). A label that names no row, such as a month, keeps any Source number. The point becomes `null` when it belongs to another row.
- `chart_number.take_chart_number`: `12,5` and `105 865,2` are one point and are rewritten with a dot before Chart.js runs. `100,40` stays two points. Word reads the same rule.
- Offline matrix: `python3 scripts/archive/chart_visual_pack.py` → `runs/chart_visual_pack/` (all types × 4 palettes)
- Multi-chart (≥2): polish clamps width to 0.82; donut legend col `minmax(320px,1fr)`
- Visual pack: `scripts/archive/chart_visual_pack.py` → `runs/chart_visual_pack/`

## Invariants
- Whitelist types only; donut = Chart.js `doughnut`; hbar = `indexAxis:'y'`
- KPI = HTML cards, not canvas
- Frame CSP + abort non-file routes in Playwright
- After gen: polish palette + harden hbar geometry/fill (+ stack gaps)

## Gotchas
- Type/palette-only edit is **local** (`apply_type_to_chart` + palette); modes include `local_type` / `local_palette`. LLM only when «Как изменить» (style notes) non-empty — never for type-only. Live `POST …/preview` is the same local path (`preview_chart_html`); style notes deferred until Apply.
- A named hue («зелёный», «столбцы зелёные», «сделай в зелёных цветах») is `recolor_hue`: paint the existing chart HTML and re-render PNG. It is not a chart-type question and not a new data brief. Preset names (ocean, закат) stay `recolor_charts`. `paint_hue_on_html` injects `backgroundColor` when Chart.js would otherwise stay default blue. `chat_answer.md` answers such a line in one sentence.
- Leaving donut: `_unwrap_donut_layout` + landscape canvas + hide unnamed Chart.js legend (else «undefined»)
- G8: model picks concrete `charts[].type` + matching HTML; coerce only safety net — **do not** paste gold HTML
- KPI palette via CSS vars (`apply_kpi_palette_vars`) — frame `.kpi` uses `--kpi-value`, not hardcoded orange; palette-only edit on KPI skips Chart.js remap
- Donut premium: `enhance_donut_html` after polish when labels/data parseable
- Tall `#mount` min-height removed — don't bring back 600px empty band
- Edit rebuilds full PDF/DOCX by default

## See
ADR-0002 · `prompt/parts/tex/` (system_tex) · tests `test_palette_hue_spread`, `test_harden_stack_gaps`, `test_harden_horizontal_bar`
