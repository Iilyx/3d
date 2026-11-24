# Deferred backlog — 2026-10-25

Owner decisions after the Oct-24 Liber feature audit.  
**Do not implement** these until the owner unparks them (often after LLM chat-memory / multi-turn Intent is set up).

Active now: [`../superpowers/plans/2026-10-25-liber-polish-batch-a-handoff.md`](../superpowers/plans/2026-10-25-liber-polish-batch-a-handoff.md)  
(G3 local type · G9 live preview · sticky TOC · section collapse · PPTX fonts · gallery→Slide).

## C — Report depth (owner approved 2026-10-25)

| # | Feature | Status |
|---|---------|--------|
| C1 | Paragraph edit in Preview (like tables → patch TeX → re-render) | **done** 2026-10-25 |
| C2 | Citations / footnotes from Source only (no invented refs) | **done** 2026-10-25 |
| C4 | Landscape page for wide tables (smart) | **done** 2026-10-25 |
| C3 TOC+LoF, C5 1-pager, C6 academic skin | parked / C6≈D9 rejected | — |
| C7 DOCX lists (List Bullet / List Number post-pandoc) | **done** 2026-10-29 | `docx_lists.py` · spec `2026-10-29-liber-docx-lists-c7-design` |

Mirror of table edit: `table_edit.py` + Preview UI. Landscape: today prompt says avoid landscape — change to allow `pdflscape` / landscape float when table is too wide.

## D — Presentations craft (owner 2026-10-25)

| Feature | Status |
|---------|--------|
| Present mode polish (click-to-advance, idle chrome hide) | **done** 2026-10-25 |
| Reorder / duplicate / delete slides without full regen | **done** 2026-10-25 |
| Speaker notes, layout insert picker, pack motif parity, photo+veil parity, deck-from-report section picker, Google/Keynote export, aspect ratios | **rejected** — не надо |

IR patch + rebuild twin/PPTX only for structural slide ops; no full LLM slides job.

## E — Diagrams (owner 2026-10-25)

| Feature | Status |
|---------|--------|
| Схема → SVG export (not only PNG) | **done** 2026-10-25 |
| media_hero one-click, Sequence/ER/Gantt whitelist, legend sync, diagram version diff | **rejected** — не надо |

## F — Data / number honesty (owner 2026-10-25)

| Feature | Status |
|---------|--------|
| CSV/XLSX attach → structured Source | **future** — «можно подумать», записать; не сейчас |
| Source lint panel, number heatmap, unit/currency normalize | **parked**. Разбор PDF-таблицы уже в коде: `source_ingest` и `dashboard_source` |

## G — Photos / media (owner 2026-10-25)

| Feature | Status |
|---------|--------|
| Image worker health chip in UI | **done** 2026-10-25 |
| Style-lock photos to pack | **done** 2026-10-25 |
| Stock-ban / brand-safe filter in Image prompt | **done** 2026-10-25 — design: [`image-brand-safe-and-pack-lock.md`](image-brand-safe-and-pack-lock.md) |
| Photo library per thread, remove/replace/caption without full regen | **parked** |

## I — Platform / Win desk (owner 2026-10-25)

| Feature | Status |
|---------|--------|
| Desk health dashboard (Qwen / Image / Docker / soffice / Playwright) | **rejected** 2026-10-26 — owner: не надо вообще |
| SSE/WebSocket stages instead of poll — richer user-facing craft progress | **done** (v1 + 2A/2B) — UX note: [`desk-live-progress-and-health.md`](desk-live-progress-and-health.md) |
| **SSE phase 2** — cooler & smarter (ETA, per-cht/fig substeps, skip awareness, artifact film, mode scripts, post-run recap, `meta.steps[]`) | **done** 2026-10-26 (2A+2B+finish); sound **rejected** |
| Resume failed stage (same run_id, missing media only, UI «Продолжить») | **done** 2026-10-29 | `resume_pipeline` · `POST /resume` · spec `2026-10-29-liber-resume-failed-stage-design` |
| Queue: one run executing, one waiting | **done** — ADR-0010, `runs/pipeline_queue.json` |
| Run retention UI, Win installer/doctor | **parked** |

## J — Differentiation (owner 2026-10-25)

| Feature | Status |
|---------|--------|
| **Atelier critique** — second LLM pass: layout/clarity advice only, **no** rewriting facts/numbers | **later** — remember; not now |
| Brand kit as product story, Source-grounded-only mode UX, Triptych export, Client-ready pack | **rejected** 2026-10-26 — owner: убрать |

## K — «Новое» (артефакты / входы / взаимодействия / продукт) — owner 2026-10-25

После разбора длинного списка новых идей владелец оставил только:

| Idea | Status |
|------|--------|
| **Infographic poster** (вертикальный 1080×1920 / A3) | **maybe later** — «потом подумать»; не проектировать и не кодить |
| **PDF/DOCX ingest** (старый отчёт → Source) | **done** 2026-11-13 — `POST /api/source/ingest`, `source_ingest.py`. Дашборд: `parse_dashboard` |
| **Ask the document** (чат по готовому run: «где маржа?», цитаты TeX/Source) | **do after LLM chat memory** — тот же gate, что блок B |

**Всё остальное из того brainstorm (one-pager, email/memo, fact cards, data appendix, audio, handout, URL scrape, voice, OCR screenshot, multi-file, what-if, compare Sources, marketplace, client ZIP, brand kit workspace, project workspace, review loop, gallery, CLI, claim ledger, contradiction, coverage, redact, audit JSON, visual genres, integrations, Liber Studio, multi-audience, live board, HITL outline, plugin charts, eval harness UI, и т.д.) — owner: «больше ничего не нравится».**

Не предлагать агентам эти пункты как next work. Не открывать specs. Excel/CSV Source остаётся отдельно как **F future** (раньше уже «можно подумать»).

Когда memory готова → Ask the document: brainstorm → spec, не прыгать в код.

---

## Gate: LLM chat memory

Several items need **new messages into the model conversation** (follow-up Intent on an existing run / section), not only one-shot Source+Intent.

**Owner:** «правки / цикл правок — когда настрою память, чтобы новые сообщения в чат модели писать.»

Until that gate is open:

- Do **not** start section B (edit cycle) below.
- Do **not** start deferred A item **G5** (style chips) if it still assumes richer multi-turn style memory — owner tied G5 to the same memory setup.

---

## A — from «Доработать старое» (not in active handoff)

| # | Item | Status | Note |
|---|------|--------|------|
| 2 | G5 Style chips → deterministic HTML patches | **deferred** | After LLM memory setup |
| 3 | G6 Edit → PNG first, PDF/DOCX async | **rejected** | Owner: не надо |
| 7 | C9 Print-mode preview ≈ PDF sheet | **rejected** 2026-10-26 — owner: не надо вообще |
| 8 | C10 Click figure → PDF page | **done** 2026-10-26 | Caption→PDF search; needles Рис/Рисунок/Fig; soft-hyphen; longest-match page |
| 9 | D9 Two report styles (Liber / строгий) | **rejected** | Один стиль отчёта только |
| 11 | ≥1 native OOXML chart when Source has series | **done** 2026-10-26 | Every deck `cht_*` → native OOXML + pack colors; Series IR on figures.json; inject chart_hero if IR skipped charts |
| 12 | Save/timeout toast on IR patch | **rejected** 2026-10-26 — owner: убрать |
| 14 | Surface `deck_pdf_mode` (lo vs png_stitch) in rail | **rejected** 2026-10-26 — owner: убрать |
| 15 | D11 Visual regression PDF fixtures | **parked** | Explained to owner 2026-10-26; not selected |

Still useful later (no owner veto): **15** (D11).  
Hard no: **3, 7, 9, 12, 14** + Brand kit/Triptych/Client-ready.  
C10 **done**. SSE finish (mode scripts + `meta.steps[]`) **done** 2026-10-26; sound rejected. Resume **done**. Queue **done** (ADR-0010). Retention UI and the Win installer stay parked.  
A11 native charts **done** — see spec `2026-10-26-liber-pptx-native-charts-design`.

Roadmap origin: [`../superpowers/plans/2026-10-20-liber-ux-polish-roadmap.md`](../superpowers/plans/2026-10-20-liber-ux-polish-roadmap.md).  
Julius font/chart gaps: [`../superpowers/specs/2026-10-22-liber-vs-julius-gap-audit.md`](../superpowers/specs/2026-10-22-liber-vs-julius-gap-audit.md).

---

## B — Цикл правок (слабее генерации)

**Status:** parked behind **LLM chat memory** gate.  
Idea: generation is strong; iterative rewrite/compare/partial regen is weak. Fix after the model can take follow-up turns on an existing run.

| # | Feature | One-liner |
|---|---------|-----------|
| 15 | «Перепиши раздел» | Intent на одну `\section` без полного re-run |
| 16 | Версии артефакта | v1/v2 в history; diff «что изменилось» |
| 17 | Compare runs | два PDF side-by-side / film |
| 18 | Pinned Source + сменный Intent | один файл Source, много брифов |
| 19 | Batch chart recolor | **done** 2026-11-07 — отказ 2026-10-26 перекрыт кодом: `POST /api/runs/{id}/charts/recolor`, `RecolorChartsModal` |
| 20 | Partial pipeline regen | only photos / only charts / only prose |
| 21 | Undo last edit | **done** 2026-10-26 — chart/figure/table/paragraph/diagram · `POST /api/runs/{id}/undo` · toast «Отменить» |

### Suggested unlock order (when gate opens)

1. **21 Undo** — **unparked** — local history of last edit payloads.  
2. ~~**19 Batch recolor**~~ — shipped 2026-11-07.  
3. **15 Section rewrite** — needs chat memory + scoped TeX patch.  
4. **18 Pinned Source** — UX + API for Intent-only re-run.  
5. **20 Partial regen** — pipeline stage flags.  
6. **16 Versions + 17 Compare** — product/history surface.

**B21** may ship without LLM memory. Default for other B items: wait for the gate unless explicitly unparked.

---

## L — Owner queue 2026-11-03 («сделать потом»)

**Status:** parked — do not start until owner unparks. Recorded from owner voice notes (typos normalized).

| # | Item | Kind | Note |
|---|------|------|------|
| L1 | Редактирование презентаций — доработать | polish | **done 2026-11-04**: deck Edit → chart/photo sheets + shared undo; overflow-safe media |
| L2 | Редактирование графиков — доработать | polish | Chart edit flow (preview → patch → re-render); Preview desk chrome improved 2026-11-04 (click-to-edit + on-demand sheets) — remaining = regen weirdness L4 |
| L3 | Source edit — переделать | redesign | Source draft click-to-edit shipped 2026-11-02; owner wants a redo |
| L4 | Перегенерация графиков — странное поведение | bug/QA | **done 2026-11-04** Liber 9×9 `c9f505b` + Series IR refresh so DOCX/PPTX match type edits |
| L5 | Перегенерация фото — проверить | QA | **done 2026-11-04**: generate+img2img + deck refresh after edit |
| L6 | Прикрепить фото в Source — проверить | QA | **done 2026-11-04**: usr_* → report (+ first-section slot) + deck media |
| L7 | Отказоустойчивость LLM — попробовать | experiment | После ошибки stage — второй прогон LLM (retry / fallback); не проектировать сразу, сначала spike |

Unlock order when unparked: **L4 → L5 → L6** (bugs/QA first) → **L2 → L1** (edit polish) → **L3** (Source redesign = brainstorm → spec first) → **L7** (LLM retry spike after pipeline KI/ADR check).

---

## Agent rules

1. If a task looks like B15–B21 or deferred A rows → stop; point here.  
2. Do not add a second report style (A9 rejected). Do not implement C9 print-mode (A7 rejected).  
3. Do not sneak G6 async docs into chart edit (A3 rejected).  
4. Item A11 native charts **done** 2026-10-26 (every deck `cht_*` + Series IR).  
5. When memory is ready: brainstorm → spec in `docs/superpowers/specs/` before coding B.  
6. Atelier critique (J): do not implement until owner asks; keep as parked product idea.  
7. Desk health strip: **rejected** — do not implement. SSE craft progress already shipped (v1+2A+2B).  
8. SSE craft theatre **done** (incl. meta.steps + mode scripts). Sound rejected — do not add.  
9. Section **K**: Ask-the-doc still waits on a follow-up design. The poster stays maybe-later. PDF/DOCX ingest is **done** — do not pitch it as future work. Do not pitch rejected K ideas.
10. Section **L** (2026-11-03): L1–L2 and L4–L6 were continued in the 5–10 Nov deck/photo work. Still parked: **L3** Source redesign (brainstorm→spec) and **L7** LLM retry spike. Do not start those until the owner unparks them.
