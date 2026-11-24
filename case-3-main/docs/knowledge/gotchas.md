# Gotchas (living list)

1. **Preview ≠ PDF** — Liber shows TeX blocks; trust PDF slider / download.  
2. **Sticky downloads** — must stay `position: static` at end of report.  
3. **horizontal_bar + pale rgba** — harden solidifies; don't regress canvas height.  
4. **tabularx cell-per-line** — without `repair_tabularx_row_breaks` → Misplaced `&`.  
5. **Orphan `&` / `\midrule` outside tabular** — `strip_orphan_table_markup` escapes/drops before latexmk.  
6. **api --reload** — kills long pipelines; prod desk off.  
7. **KPI type + bar canvas** — coerce rebuilds KPI HTML.  
8. **Chart type badge** — hidden from users; keep in `title=` / edit sheet only.  
9. **Image edit fallback** — worker may regenerate without ref photo.  
10. **Fonts** — PDF DejaVu; DOCX Liberation via `reference.docx` (D1).  
11. **PPTX / deck** — on-demand slides job; keys `pptx` + `deck_pdf` (not report `pdf`). `deck_pdf` prefers LibreOffice convert of PPTX (`CASE3_SOFFICE`); else PNG stitch. See ADR-0008 / KI-liber-deck.  
    If `slides_status` stuck at **`queued`** with null slides — job never started (old BackgroundTasks path). Fixed: daemon thread + `running/starting` before kick; crashes write `slides_error`. Restart `api.cmd`, retry Make presentation.  
    Same Windows stall for **report** `/api/run`: meta `running`/`queued`, polls 200, no LLM logs — fixed `_kick_pipeline_thread`.  
    If still `running`/`queued` after 202: thread never left setup — API+pipeline now heartbeats `stage=llm` before kick/FileHandler; console should show `[case3] pipeline thread start run_id=…`. No such line → kill extra python/uvicorn and restart `api.cmd`.  
    **One run at a time on Win LAN:** 2nd Liber send while 1st still on Qwen → desk feels stuck; Cancel first (or wait), don’t stack jobs on a single llama-server slot.  
    **«Собираю фото» at max_images=0:** was craft map `inject→photos` (debug `20261029T102411`). Fixed: `inject→pdf`. Real photo hang = `stage=images` + `max_images≥1` + Image API timeout.  
12. **`\textbf{…**` / unclosed `\textbf{`** — LLM closes bold with Markdown or drops `}`; microtype → `Runaway argument` / `MT@prot@check@F@` / fake `enumerate ended by end{document}`. Fixed by `fix_markdown_bold_leaks` + `fix_unclosed_textbf` in `tex_prose.py`.  
13. **`figures failed/skipped: fig_*`** — Image worker (`IMAGE_API_BASE_URL`, usually `:8787`) was down during the run; slots strip from TeX. Start `workers/case3-image` before local runs; load `.env` so `KANDINSKY_MAX_IMAGES≥1`. Deck can still show `cht_*` / `dia_*`.  
14. **Tiny `dia_*` on 16:9** — Prefer `flowchart LR` + multiline labels (`<br/>`); capture crops to ink (see `slides_media.render_mermaid_png`). TD flows look like a thin column on `media_hero`.  
15. **PPTX Y ≈ 777240"** — `float(Inches(x))` is EMUs, not inches. Always `_as_inches` / `.inches` before arithmetic; PowerPoint then piles text top-left / “[Repaired]”.  
16. **Dark deck tables white body** — never hardcode `#FFFFFF` body fill; use theme `table.body_fill` / panel (botanical `#243D32`) or light ink vanishes.  
17. **Composer «Схема»** — `output_mode=diagram` + `formats=none` skips Docker TeX; only Mermaid + chat summary. Don’t expect PDF/DOCX keys.  
18. **Presentation / diagram send** — do **not** gate on Source length or «≥48 chars». Template «Взять» fills composer with `starterPrompt` **only if chat is empty**; otherwise keep user text. Empty chat still needs any non-empty brief or file.
19. **Deck photos and schemas** — API keeps 5 uploads, not 2. A numbered line in the intent is the caption (`1. логотип`, `2. схема`). «Схема» becomes Mermaid on the slide; the source PNG is not placed. Logos and UI screenshots stay photos. See `docs/knowledge/deck.md`.
20. **Debug push** — `scripts/push-debug.cmd` drops PNG, slides, and PPTX unless `KEEP_MEDIA=1`. Do not put user logos on a debug branch.
21. **Photos are not Source** — a keyboard-smash plus a JPEG still returns `insufficient_data`. Do not bypass `validate_input_heuristics` when `has_attachments` is true (the argument is ignored on purpose, 2026-11-10).
22. **One slot per media id** — `deduplicate_slots_in_tex` drops a second `%CASE3_FIG|CHART|DIAG%`. A user photo belongs in the report once.
23. **Stuck pipeline slot** — a dead run can hold the lock. Recovery is automatic (`_reclaim_stale_slot_if_dead`) or `POST /api/pipeline/slot/reset`. Do not start a second uvicorn to “clear” it.
24. **Diagrams are in the PDF** — ADR-0007 is superseded. Do not strip every `dia_*` include. `strip_diagram_includegraphics` keeps ids marked ok.
25. **Native PPTX diagrams** — flowchart over 10 nodes, sequence, and state fall back to PNG. Timeline and mindmap are shapes, not PNG-only.
