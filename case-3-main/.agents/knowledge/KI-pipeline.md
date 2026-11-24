# KI: Pipeline

## What
`run_pipeline` в `src/case3/pipeline.py`: llm → images → charts → diagrams PNG → inject → **latex/docx ∥ chat summary** → meta ok/error.  
Mermaid `diagrams[]` пишутся в `figures.json` и **растеризуются** в `figures/dia_NN.png`. Слот `%CASE3_DIAG:dia_NN%` инжектится в TeX (ADR-0009, снимает UI-only ADR-0007). Нет слота — fallback перед «Заключение» / «Выводы» или перед `\end{document}`. Битый Mermaid: слот снимается, прогон не падает. `strip_diagram_includegraphics` оставляет include только при `media_status.ok`.  
**Default-on:** при `max_diagrams≥1` модель должна дать ≥1 схему, если в Source есть структура (шаги/роли/ветки/≥3 раздела). Soft-drop → `diagrams_dropped`.  
**Режим Схема** (`output_mode=diagram`): после llm stage `diagram_repair` (`prompt/diagram_repair.md`); soft-fail → draft; meta `diagrams_repaired` / `diagrams_draft`. Форматы пустые — PDF/DOCX отчёта нет.  
**Annotated flow:** числа из Source на labels. Liber chips «Числа на схеме». Не дублировать chart series. Без живой БД.  
Палитра Settings → `format_diagram_color_prompt`. API: `POST …/diagrams/{id}/edit` перерисовывает PNG; `…/regenerate`.  
**Пустой запрос (2026-11-10):** сразу после подготовки каталога `validate_input_heuristics` (`input_validation.py`). Отказ → `meta.insufficient_data`, `status=ok`, `artifacts={}`, `chat_summary` = текст отказа, без LLM и без Docker. Если модель вернула JSON `status: insufficient_data` — тот же ранний выход (`InsufficientDataError`). Фото не заменяют факты: `has_attachments` гейт не обходит. Цифра, список, таблица или блок кода проходят эвристику.  
**Свои фото:** до 5 (`user_photos._MAX_COUNT`). В промпт уходят как vision (`user_photos_to_vision_images`). В TeX каждый `%CASE3_FIG|CHART|DIAG%` один раз (`deduplicate_slots_in_tex`).  
**Вход:** `source_text` режется на 2 МиБ до слота (как файл). Фото: 16 Мп до decode (`user_photos._MAX_PIXELS`). **Born-digital ingest (2026-11-13):** `POST /api/source/ingest` → PDF/DOCX/DOC/RTF/TXT → Markdown в Source draft (`python-docx` + `pdfplumber` tables + `pypdfium2` triage; без OCR/Docling/torch); скан-PDF → 422. OCR/TTN не в контуре. **Health `ok`:** Docker и живой Vision (`vision_ok`), не просто ключ в `.env`. URL Image API в health не отдаётся. Мягкий пропуск графика/рисунка виден в `warnings` статуса. Resume, упавший до записи meta, не остаётся в `running`.
**Слот:** один прогон, один ожидающий. Третий запрос получает 409: «Сейчас собирается один документ, и ещё один уже ждёт. Этот запрос не поставлен.» В тексте нет id и нет слова про перезапуск. Ожидающий пишется в `runs/pipeline_queue.json` и поднимается при старте API, если meta всё ещё `queued` и нет `cancel_requested`. Мёртвый lock снимает `api._reclaim_stale_slot_if_dead`. Ручной сброс: `POST /api/pipeline/slot/reset`. Прогресс SSE: префикс из `meta.steps[]`, RAM только хвост.

## Entry
- CLI: `case3` / `scripts/run.cmd`
- API: `POST /api/run` → background → `GET /api/runs/{id}/status`

## Invariants
- `run_id` = `{stem}_{UTC stamp}`; артефакты в `runs/{work,out,logs}/`
- Uploads: 5 фото (`clip_photo_files`); `max_images` cap 8. Презентация с фото: бюджет `fig_*` = 0 (`split_image_budget`)
- Dry-run: без media render; `summary_status=skipped`; `diagrams: []`
- `CASE3_MAX_DIAGRAMS`: env default 5, hard max 5 (`diagrams.DIAGRAMS_HARD_MAX`, `clamp_diagram_budget`). Meta `diagrams_planned` / `diagrams_ok`
- After inject: ThreadPool — `render_tex` + `try_generate_chat_summary`. The summary is published with `BUS.finish` only after render returns. A TeX failure does not leave «Готов» in the chat. A missing chart is named in the summary. Summary fail ≠ PDF fail
- After render returns → `bump("summary")` so UI leaves «Собираю DOCX…»
- Summary LLM uses ≤90s timeout + local outline blurb fallback on fail/timeout
- `meta.chat_summary` / `summary_status`; SSE fan-out for Liber
- `PipelineError` несёт run_id для debug upload

## Gotchas
- `--reload` на uvicorn рвёт длинные job → `api.cmd` без reload
- Chart soft-fail ≠ pipeline fail
- Intent palette/types парсятся из UI block strings
- Long «Собираю DOCX» with PDF already on disk = hung chat-summary LLM (not pandoc)
- On hard fail: `meta.failed_stage` preserved (`llm|images|charts|inject|latex|docx`). Resume: `POST /api/runs/{id}/resume` → `resume_pipeline` when `can_resume_run`. `llm` replays non-empty `work/*.raw_model.txt` (written before the next model call and before parse) and does not call the model. Other stages regen only missing PNG. Slot is claimed before `meta.status=running`. A stale pipeline `finally` releases only its own generation. Liber button «Продолжить». The run queue is shipped (ADR-0010). Retention UI and the Win installer stay parked. Network failure before any model text has no raw file and stays ineligible. A process restart does not resume a `running` run: `settle_orphaned_runs` writes `error` (or `cancelled` if the user had already stopped it) and keeps `failed_stage`, so «Продолжить» appears when the stage can resume. A deck left `slides_status=running` becomes `slides_status=error`. A live thread is not touched. `queued` is still started by `recover_persisted_pipeline`.

## See
ADR-0001 · ADR-0009 · `api.py` · `generate.py` · `inject.py` · `input_validation.py` · `user_photos.py` · `source_ingest.py`
