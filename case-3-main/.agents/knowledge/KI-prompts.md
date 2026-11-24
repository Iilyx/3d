# KI — LLM prompts

**Каталог:** [`prompt/MANIFEST.md`](../../prompt/MANIFEST.md)  
**Код:** `src/case3/prompts.py` → `load(id, **vars)` · `load_theme` · `dump_prompts` · `list_prompt_ids()`

## Invariants

- Prose lives under `prompt/` (md). Python wires vars / calls the model.
- `system_tex` = join of `parts/tex/*.md` (`PROMPT_COMPOSITES`); stub `system_tex.md` is not the body.
- `{{KEY}}` substitution only.
- New core role → file / part + register + MANIFEST + catalog/smoke test.
- Gold = `prompt/gold/` via `gold_select` (appended after `system_tex`).
- Image brand-safe / pack lock = `image_prompt.py` (not catalog prose).
- `CASE3_DUMP_PROMPTS=1` → `out/prompts_used/{system,user,continuation}.md`.

## Gotchas

- Source markers `<<<CASE3_SOURCE_*>>>` must stay in sync with `generate.SOURCE_BEGIN/END`.
- `SUMMARY_SYSTEM` is loaded once at import from `summary_system.md`.
- Themes: `themes/slides_{pack}.md`, `themes/structure_{id}.md` — path-based.
- Do not paste full prose back into `system_tex.md` stub.
- Data gate (2026-11-10): `system_tex` / `system_slides` / `diagram_generate` may answer JSON `{"status":"insufficient_data","message":…}` when Source+Intent have no facts. A short request that contains numbers or a concrete situation must still generate. Photos do not count as Source. Heuristic twin: `input_validation.py`.
- Diagram hex (2026-11-13): only via `format_diagram_color_prompt` → `{{DIAGRAM_COLOR_TABLE}}` (or user_tex for TeX). No hardcoded `#dce8df…` in prompt md. Inject **once** (system for generate/repair/refine; user for TeX). Baseline pre-change: agent store `prompt-wave1-baseline/` @ `2e90a73`.
- Conditional `system_tex` (2026-11-13): `system_tex_part_rels` drops `04_diagrams` when `MAX_DIAGRAMS=0`, `03b_figures` when `MAX_IMAGES=0`, `03c_user_photos` unless `has_user_photos` (from `user_figures` in `generate_document`).
- Prompt optimize wave (2026-11-13): slim `user_tex`, dedupe READY/anti-slop, compact `01`/`02`/`system_slides` examples, gold `full_minimal` without package dump; inline LLM prompts listed in `prompt/MANIFEST.md`.
