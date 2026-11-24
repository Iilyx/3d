# KI: TeX harden + Docker render

## What
Post-LLM TeX repair then `latexmk -xelatex` / pandoc in Docker `case-3:tex`.

## Entry
- Harden: `tex_preamble.ensure_document_preamble` (called from `render.prepare_tex_source`)
- Row repair: `repair_tabularx_row_breaks` (trigger: ≥1 trailing-`&` line)
- Orphan table chrome: `strip_orphan_table_markup` (bare `&` → `\&`, drop midrule outside tabular)
- Prose lists: `tex_prose.harden_prose_lists` (`- `/`• ` → itemize)
- Render: `render.render_tex` (`--net=none`, optional `reference.docx`)
- C8 errors: `pipeline._attach_error_diagnostics` → `failed_charts` + `latex_log_tail` on status

## Invariants
- Cyrillic via DejaVu + polyglossia/fontspec
- Required packages injected if missing
- Brand `case-3` scrubbed from title/author
- Orphan `%CASE3_*` slots stripped before latexmk

## Report depth (C1/C2/C4)
- C1 paragraph edit: `paragraph_edit.py` + Preview `para-N` (`tex_preview.find_paragraph_spans`)
- C2 citations: prompt + `citations.citation_intent_hint`; harden `strip_invented_cites` drops `\cite{…}` without allowed keys; footnotes with URLs kept
- C4 landscape: `pdflscape` in preamble; `maybe_landscape_wide_tables` wraps wide `table` envs; prompt allows per-table landscape only

## Gotchas
- Unclosed `\section{…` / `\subsection{…` (LLM drops `}`) → `File ended while scanning use of \@xdblarg` / latexmk exit 12. Not a Windows/Docker fault — harden via `tex_prose.fix_unclosed_heading_args` in `ensure_document_preamble` (titles close at first newline).
- Unclosed `\caption{…` → runaway + `Paragraph ended before \Gin@iii` + `\begin{figure} … ended by \end{document}`. Harden: `fix_unclosed_caption_args` + `fix_unclosed_float_envs` (close caption before float/doc end; insert missing `\end{figure|table}`).
- `\includegraphics{…%CASE3_FIG:id%}` (slot inside path): TeX `%` comments out `}` → Gin@ii. Line-anchored inject misses it — `inject.rewrite_inline_slot_includegraphics` → `figures/id.png`.
- Markdown `* ` outlines + emoji in `\subsection{📂 …}` (skeleton-echo runs): `harden_prose_lists` accepts `*`; `scrub_emoji_from_headings`. Sparse-fill (`_source_lines_to_tex`) also drops meta-skeleton framing («полный комплект»/«скелет»/«БЛОК N»), converts `* ` → itemize, scrubs emoji in MD headings — Win desk 070133.
- Win desk 073916: `FileNotFoundError` writing `source.raw_model.txt` — `work/` vanished during long LLM call. Remkdir `out_tex.parent` immediately before that write (and keep the early mkdir for dump_prompts).
- Win desk 080546: `VISION_MAX_TOKENS=4096` + 8 charts → `finish_reason=length` twice; JSON ok, LaTeX ~1 paragraph; parse appends all slots → media pile, «no text». `tex_body_needs_source_fill` (media≥4 + ≤1 section + thin prose) forces Source fill; generate bumps max_tokens floor to 12288 when charts/images ≥4.
- Win desk 081536: tokens OK, full prose, but **0** inline slots — model dumped all `%CASE3_*` under `\section{Визуализация данных}` / `\section{Иллюстрации}`. `tex_media_place.redistribute_gallery_slots` strips those galleries and reinserts slots into matching earlier sections (caption/title token overlap + synonym groups). Sparse-fill no longer creates `\section{Иллюстрации}` either.
- Win desk 082722: gallery was `\section{Приложение: … визуализации}` + `\subsection{Графики}` with slots **inside** `\begin{figure}` — redistribute must match keyword-anywhere titles (not only prefix «Визуализация»), peel figure envs, and force-scatter when ≥50% of slots sit in the last 20% of the body (`media_slots_pile_at_eof`).
- Win desk 083615: deck TeX used `\section*` / `\subsection*` — `tex_prose.unstar_headings` in `ensure_document_preamble` forces numbered headings for print twin.
- Mermaid: LLM often emits `class start fill:#…` (meant `classDef`) and `class A B C process` (space-separated nodes). `diagrams._repair_class_assign_lines` rewrites both.
- Debug upload: `scripts\push-debug.cmd` drops PDF/DOCX/PNG/slides by default (slim ~few MB). `KEEP_PDF=1` / `KEEP_MEDIA=1` opt-in. Huge bundles → GitHub `Internal Server Error` on push.
- LLM may leak `\includegraphics{fig_02.png}` (no `figures/`). `rewrite_media_includegraphics_paths` + `strip_failed_media_includes`. Diagrams **are** print media (ADR-0009): `%CASE3_DIAG` → `figures/dia_NN.png`. `strip_diagram_includegraphics` drops a diagram include only when that id is not `ok`. Render also `strip_missing_media_includes` before latexmk. Summary still generates beside latex, but `BUS.finish` waits until render returns. A TeX failure publishes `PDF не собрался` plus the `!` line, not «Готов». `_latex_log_tail` starts at the `!` line when one exists.
- A wide table (6+ columns) gets its own Word landscape page (`orient_wide_tables`, A4 16838×11906, table width 14400). Text before and after stays portrait. The caption «Таблица N» stays on the landscape page. The chat preview says «альбомная страница» only when the TeX itself is inside `\begin{landscape}`. Pandoc drops that environment.
- A foreign number in `\title{…}` is scrubbed before print. An empty title becomes «Отчёт». The rest of the preamble is left alone.
- A column header shorter than four letters (`Май`) still keeps its cells on that row. One invented number drops the whole sentence, including a TeX share `71{,}4\%`. Cutting only the digits left `в раза` and a `}` that broke `tabularx`.
- Slot lines with trailing notes (`%CASE3_CHART:cht_01%  (SLA)`) must still count as slots — strict `$` missed them → `_append_missing_slots` dumped duplicates before `\end{document}` (fix 2026-11-02, `tests/test_slot_trailing_junk.py`).
- Text schemas `\item [узел] $\rightarrow$ …` (Win desk 090626): LaTeX uses `[узел]` as the item label and clips it past the left edge. `tex_prose.brace_schema_item_labels` rewrites to `\item {[узел]}`.
- Empty `\begin{itemize}\end{itemize}` is `missing \item` and latexmk exit 12 even after a PDF was written. `drop_empty_lists` removes it. A `.png` whose bytes are BMP (`BM…`) is the same failure (`Graphic file (type bmp)`); `strip_missing_media_includes` drops any include that is not PNG, JPEG, or PDF.
- Wide tables: cell-per-line `&` → Misplaced `&` without repair
- Markdown source tables longer than 24 rows (header included) become `xltabular`: every row stays, the header repeats, Y columns wrap. Shorter ones stay `tabularx`. Both are preview tables. Table edit allows 200 rows and preserves `\caption{...} \\` inside `xltabular`. Wide tables with `>= 8` columns avoid fixed `2.5cm` `Z` columns, and `>= 10` columns use `\footnotesize` and `\tabcolsep=2.5pt`.
- `titlespec` typo stripped; real package is `titlesec`
- DOCX `reference.docx` = Liberation Serif, margins 2.2cm, footer PAGE (D8); rebuild via `scripts/build_reference_docx.py`
- After pandoc: `docx_polish.try_polish_docx` (D5: mist header fill, booktabs borders, pad, bold header, numeric right-align; soft-fail)
- Then `docx_lists.try_fix_docx_lists` (C7: plain `- `/`1.` + pandoc lists → Liber `List Bullet` / `List Number` + numPr; soft-fail)
- Then `docx_charts.try_replace_docx_native_charts`: each eligible `cht_*` PNG → native `word/charts/` (Series IR + pack colors); KPI/scatter/photos stay images. Soft-fail. Drops replaced PNG media+rels; suppresses OOXML auto-title (pandoc caption only). Spec `2026-10-26-liber-docx-native-charts-design`.
- Captions: `\captionsetup[figure]{name={Рис.}}` / table `Таблица` (D2)
- DOCX media: `docx_polish.polish_media_captions` centers drawings/charts + next short caption as `Рис. N. …` (11pt ink); soft-fail; after tables, before lists/native charts. Spec `2026-11-03-liber-docx-media-captions-design`.
- DOCX batch-2: `polish_table_captions` (pandoc title *before* table → `Таблица N.`); `clamp_drawing_widths` (≤0.92 text width); `polish_paragraph_rhythm` (body space_after 8pt, caption/media air).
- D4: title `\rule` under `\maketitle` + floatsep/captionskip (`ensure_liber_print_chrome`)
- Chrome 2.0: section titlespacing + `\parskip`/`\itemsep`; table rules via `tex_tables.harden_table_rules`
- PDF quality smoke: `tests/test_pdf_quality_smoke.py` (needs Docker `case-3:tex`)
- Chat preview ≠ PDF numbering/chrome

## See
ADR-0005 · `tests/test_repair_tabularx_rows.py` · `tests/test_harden_tables.py` · `tests/test_orphan_table_markup.py` · `tests/test_tex_prose_lists.py` · `tests/test_inject_rogue_includegraphics.py` · `tests/test_strip_missing_includegraphics.py`
