# Liber prompt catalog

**Edit prose here.** Python only assembles vars / calls the model.  
Loader: `case3.prompts.load(id, **VARS)` · `list_prompt_ids()` · themes via `load_theme`.

| id | file / parts | caller | vars |
|----|--------------|--------|------|
| `system_tex` | **`parts/tex/*.md`** (composed; stub `system_tex.md`) | `generate.load_system_prompt` | `MAX_IMAGES` `MAX_CHARTS` `MAX_DIAGRAMS` `PALETTE_TABLE` · kw `has_user_photos` |
| `user_tex` | `user_tex.md` | `generate.build_user_prompt` | `INTENT_BLOCK` `MAX_*` `DIAGRAM_COLOR_TABLE` `SOURCE` |
| `continuation_tex` | `continuation_tex.md` | `generate.build_continuation_prompt` | `MAX_CHARTS` `PARTIAL_TAIL` `SOURCE` |
| `summary_system` | `summary_system.md` | `chat_summary` (system role) | — |
| `chat_opening` | `chat_opening.md` | `chat_turn.try_opening` | — |
| `stage_narration` | `stage_narration.md` | `stage_narration.narrate_stages` | — |
| `chat_answer` | `chat_answer.md` | `chat_turn.try_chat_answer` | — |
| `chat_section` | `chat_section.md` | `chat_turn.draft_section` | — |
| `dashboard_png` | `dashboard_png.md` | `dashboard_source.read_dashboard_png` when a PDF is also present | — |
| `dashboard_png_only` | `dashboard_png_only.md` | `read_dashboard_png` when the screenshot is the only file | — |
| `dashboard_filters` | `dashboard_filters.md` | `POST /api/dashboard/phrase` | — |
| `system_slides` | `system_slides.md` | `slides_job.load_slides_system_prompt` | `PALETTE` `THEME_OVERLAY` `STRUCTURE_OVERLAY` `CHART_IDS` `FIGURE_IDS` `DIAGRAM_IDS` `MEDIA_CATALOG` `INTENT` `SOURCE` |
| `diagram_generate` | `diagram_generate.md` | `diagram_edit` / `diagram_generate` | `MAX_DIAGRAMS` `DIAGRAM_COLOR_TABLE` |
| `diagram_repair` | `diagram_repair.md` | pipeline `diagram_repair` stage | `DIAGRAM_COLOR_TABLE` |
| `diagram_refine` | `diagram_refine.md` | `diagram_edit` refine (AI Copilot) | `DIAGRAM_COLOR_TABLE` |

## `system_tex` parts (edit these)

Runtime compose (`prompts.system_tex_part_rels`): omit `03b` unless `MAX_IMAGES≥1`; omit `03c` unless user photos; omit `04` unless `MAX_DIAGRAMS≥1`.

| part | topic |
|------|--------|
| `parts/tex/00_role.md` | Role + budgets |
| `parts/tex/01_output.md` | JSON + LaTeX fences |
| `parts/tex/02_charts.md` | Chart.js types / HTML rails |
| `parts/tex/03_when_media.md` | When charts (always) |
| `parts/tex/03b_figures.md` | Image API `fig_*` (opt-in budget) |
| `parts/tex/03c_user_photos.md` | Uploaded `usr_*` Vision placement |
| `parts/tex/04_diagrams.md` | Mermaid diagrams |
| `parts/tex/05_hard_rules.md` | TeX hard rules / citations / landscape |

## Themes (path-based)

| pattern | loader | note |
|---------|--------|------|
| `themes/slides_{pack}.md` | `prompts.load_theme("slides", pack, fallback="atelier")` | deck visual tone |
| `themes/structure_{id}.md` | `deck_structure.structure_overlay` | narrative arc |

## Gold exemplars

| path | loader | note |
|------|--------|------|
| `gold/index.yaml` + `*.tex` | `gold_select` → appended after `system_tex` | Intent tag overlap; see `gold/README.md` |

## Debug dump

Set **`CASE3_DUMP_PROMPTS=1`** → after generate, writes `out/prompts_used/system.md` + `user.md` (+ `continuation.md` if truncated). Off by default.

## Not prompt files (code policy)

- `src/case3/image_prompt.py` — brand-safe / pack style-lock / banned n-grams; inline `image_prompt` RU→EN `_TRANSLATE_SYSTEM`.
- `chart_style.palette_fallback_table` / `diagram_style.format_diagram_color_prompt` — injected tables (`DIAGRAM_COLOR_TABLE` / `PALETTE_TABLE`).

## Inline LLM prompts (not catalog md — document here)

| name | where | note |
|------|-------|------|
| `chart_edit` | `chart_edit.py` restyle system string | Chart.js fragment restyle |
| `chat_chart` | `chat_turn.generate_chat_charts` system string | Inline chart; `hue_prompt_line` adds named-color hex |
| `schema_redraw` | `schema_redraw.py` `_SYSTEM` | photo → Mermaid |
| `latex_recovery` | `generate._build_latex_recovery_prompt` | JSON ok, missing ```latex |
| `image_prompt` translate | `image_prompt.py` `_TRANSLATE_SYSTEM` | RU caption → EN photo prompt |

## How to add a prompt

1. Add `prompt/<name>.md` **or** a new part under `parts/…` + `PROMPT_COMPOSITES`.
2. Register in `PROMPT_FILES` or `PROMPT_COMPOSITES` (`src/case3/prompts.py`).
3. Add a row here.
4. Call `prompts.load("<id>", ...)`.
5. Extend `tests/test_prompts_catalog.py` / smoke tests.
