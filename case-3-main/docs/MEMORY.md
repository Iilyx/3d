# case-3 — карта памяти (3 уровня)

Единая точка входа для людей и агентов. Читай это **до** крупных правок.

```text
L1  Рабочий контекст     AGENTS.md · .cursor/rules · этот файл · открытый чат
L2  Граф кода            codebase-memory-mcp / code-review-graph (проект case-3)
L3  Долгосрочная память  docs/adr · .agents/knowledge · docs/knowledge · docs/superpowers
```

---

## L1 — Рабочий контекст (сессия)

| Артефакт | Зачем |
|----------|--------|
| [`AGENTS.md`](../AGENTS.md) | Контракт для агента: стек, запреты, куда смотреть |
| [`.cursor/rules/case3-memory.mdc`](../.cursor/rules/case3-memory.mdc) | Always-on: «сначала MEMORY» |
| [`README.md`](../README.md) | Запуск Windows / Qwen / Image API |
| [`docs/knowledge/repo-map.md`](knowledge/repo-map.md) | Что за папка / куда смотреть |
| [`docs/knowledge/windows-final-run.md`](knowledge/windows-final-run.md) | Win readiness + 3 промпта финал-прогона |
| Текущий чат | Задача «сейчас»; не считается источником истины без коммита в L3 |

**Правило:** если решение переживает один чат — запиши в ADR или KI, не оставляй только в диалоге.

---

## L2 — Граф кода

После индексации:

```bash
# через MCP codebase-memory: index_repository
# repo_path = /Users/borisserzhanovich/Projects/case-3
# name = case-3, mode = fast|full
```

Использовать для: «где pipeline stage», impact radius, поиск символов.  
Не дублировать длинные выдержки кода в markdown — ссылайся на пути.

Статус (2026-10-21): проект **`case-3`** проиндексирован (`mode=fast`, ~2.8k nodes).  
Примечание: папка `docs/` часто исключается из графа — ADR/KI живут в git как L3-файлы; граф — для кода.  
Если `list_projects` не показывает `case-3` — `index_repository` снова.

---

## L3 — Долгосрочная память (в репо)

### ADRs — *почему так*

[`docs/adr/`](adr/) — нумерованные решения. Шаблон: [`0000-template.md`](adr/0000-template.md).

### KI-карточки — *как устроена подсистема*

[`.agents/knowledge/`](../.agents/knowledge/) — короткие карточки (входные точки, инварианты, gotchas).

### Knowledge — *операционка и карта*

[`docs/knowledge/`](knowledge/) — глоссарий, system map, Windows desk, parked ideas.

### Superpowers — *спеки и планы фич*

[`docs/superpowers/`](superpowers/) — design + implementation plans (не ADR).

| Тип | Папка |
|-----|--------|
| Spec | `docs/superpowers/specs/` |
| Plan | `docs/superpowers/plans/` |

Активный UX: soft-premium shell — [`specs/2026-10-21-liber-soft-premium-ui-design.md`](superpowers/specs/2026-10-21-liber-soft-premium-ui-design.md) · ADR-0006.  
Chrome palette: Quiet Mono — [`specs/2026-10-23-liber-quiet-mono-ui-design.md`](superpowers/specs/2026-10-23-liber-quiet-mono-ui-design.md) (olive/cream chrome заменён).  
Premium refactor (полный desk): [`specs/2026-10-22-liber-premium-ui-refactor-design.md`](superpowers/specs/2026-10-22-liber-premium-ui-refactor-design.md) · [`plans/2026-10-22-liber-premium-ui-refactor.md`](superpowers/plans/2026-10-22-liber-premium-ui-refactor.md).  
Frontend modules (pre-Angular): [`specs/2026-10-25-liber-frontend-modules-design.md`](superpowers/specs/2026-10-25-liber-frontend-modules-design.md) · plan Week1 [`plans/2026-10-25-liber-frontend-modules-week1.md`](superpowers/plans/2026-10-25-liber-frontend-modules-week1.md) · map [`web/ARCHITECTURE.md`](../web/ARCHITECTURE.md).  
Parked backlog: [`plans/2026-10-20-liber-ux-polish-roadmap.md`](superpowers/plans/2026-10-20-liber-ux-polish-roadmap.md).  
Simplify-for-agents (hygiene + tracks A/B/C): [`plans/2026-10-29-liber-simplify-for-agents.md`](superpowers/plans/2026-10-29-liber-simplify-for-agents.md).
Active polish handoff (G3/G9/TOC/collapse/PPTX fonts/gallery→Slide): [`plans/2026-10-25-liber-polish-batch-a-handoff.md`](superpowers/plans/2026-10-25-liber-polish-batch-a-handoff.md).  
Deferred (A leftovers + B edit cycle; gate = LLM chat memory): [`knowledge/backlog-deferred-2026-10-25.md`](knowledge/backlog-deferred-2026-10-25.md). **B21 Undo shipped** 2026-10-26 (`run_undo.py` · `POST /undo` · toast «Отменить»). **B19 batch recolor shipped** 2026-11-07 (`POST /api/runs/{id}/charts/recolor` · `RecolorChartsModal`) — отказ от 2026-10-26 перекрыт кодом. **L3** Source redesign и **L7** LLM retry spike всё ещё parked. Остальное из L (дек/графики/фото) дорабатывалось 5–10 ноября, см. снимок ниже.  
Report Preview edit redesign (document prose + session undo/redo): [`specs/2026-11-04-liber-report-preview-edit-redesign-design.md`](superpowers/specs/2026-11-04-liber-report-preview-edit-redesign-design.md) — supersedes full-open desk UX of 2026-11-02.  
A11 native PPTX charts **done** — [`specs/2026-10-26-liber-pptx-native-charts-design.md`](superpowers/specs/2026-10-26-liber-pptx-native-charts-design.md).  
DOCX native charts **done** — [`specs/2026-10-26-liber-docx-native-charts-design.md`](superpowers/specs/2026-10-26-liber-docx-native-charts-design.md) (`docx_charts.py` post-pandoc).  
Report depth C1/C2/C4 **done** (paragraph edit · Source citations · landscape tables) — KI-liber-ui / KI-tex-render · spec `2026-10-25-liber-report-depth-c1-c2-c4`. **C7 DOCX lists done** 2026-10-29 (`docx_lists.py`). Remaining C: TOC+LoF / 1-pager parked; C6 rejected.  
Source draft click-to-edit **done** 2026-11-02 — preview → click → textarea (Esc/blur); spec `2026-11-02-liber-source-draft-edit-design`.  
Resume failed stage **done** 2026-10-29 (`resume_pipeline` · `POST /resume` · «Продолжить»). Очередь **done** (ADR-0010). Retention и installer всё ещё parked.  
Deck/diagram D/E **done** (Present polish · structure ops · SVG) — KI-liber-deck / KI-liber-ui · spec `2026-10-25-liber-d-e-present-structure-svg`. Rejected D/E stay parked.  
Image G **done** (health chip · pack style-lock · brand-safe) — KI-image-api · [`knowledge/image-brand-safe-and-pack-lock.md`](knowledge/image-brand-safe-and-pack-lock.md). Excel Source — backlog **F** future.  
Desk: SSE v1 + **2A** + **2B** + **finish** (mode scripts · `meta.steps[]`) done — [`knowledge/desk-live-progress-and-health.md`](knowledge/desk-live-progress-and-health.md). Sound + desk health **rejected**. Atelier critique — backlog **J** later.  
«Новое» (K): Ask-the-document ещё ждёт отдельный замысел. Инфографика-постер — maybe later. PDF/DOCX ingest **сделан** (`source_ingest.py`). Остальной brainstorm K — rejected.

### Снимок кода — 2026-11-23

После P0-аудита (ADR-0018). На Windows едут `AGENTS.md`, `docs/MEMORY.md`, `docs/adr/`, `docs/knowledge/`, `.agents/knowledge/`. Спеки `docs/superpowers/` и аудиты `docs/audits/` остаются дома.

| Тема | Как сейчас |
|------|------------|
| Числа | Source, эта реплика, и старое число пользователя только рядом со своим словом (ADR-0016 · ADR-0018). Строка таблицы отдаёт все свои `grid.values` даже при упоминании соседней колонки или `%`; агрегаты `## Производные` (`grid.aggregates`), положительный модуль от отрицательных отклонений и проверяемая кросс-строчная математика (`_verifies_math`: суммы 2–3 слагаемых, разницы, проценты между упомянутыми регионами и 2+ шотами дашборда) разрешены в чате. `_owner_rows` учитывает сущность слева и близко справа от числа. Границы `_NUM` не цепляют `B2B`/`s01`/`#4E79A7`, сохраняют `-`/`−`. В TeX защищены вложенные `{@{}}`/`p{}`/`\fontsize` и границы `\ref`/`%CASE3_CHART`, не ломается `\multicolumn{1}{c}{..., \%}` |
| Чат и графики в чате | Запросы «построй график» без `отчёт`/`pdf`/`docx`/плашки идут в `chat` (`wants_chat_chart`) с inline Chart.js PNG (`generate_chat_charts` → `ChatMessages.tsx`). Правка предыдущего графика/схемы чата ищет визуал по всей цепочке `load_chain_dirs`. Плашка «Отчёт» побеждает голое «проанализируй» (ADR-0017). В `## Производные` разрешены расчёты/доли/отклонения. `LLMClient._content` не выдаёт сырой `reasoning` без TeX/JSON-сигнала; `stream()` режет `<think>` и бросает `LLMError` на пустом потоке; ретрай не затирает валидный первый черновик; `/api/dashboard/phrase` не перехватывает вложенные документы и общие «эти данные» |
| Дашборд | «Выбрать данные» → «В данные». Полная поддержка `\u202f`, минусов, суффиксов единиц, уникальной метки сущности, экранирования `\|`; в `## Производные` добавлены суммы, средние, мин/макс, групповые итоги и `Факт − План` (включая группы). `DashboardPickModal` спаривает PNG+PDF в один запрос. `dashboard_png*.md` не галлюцинирует фильтры ИМНС на чужих дашбордах. Фильтр «на 1 февраля» — поступления за январь, чат это разбирает (ADR-0019) |
| Отчёт / Деки / PPTX | `tex_preamble` поддерживает `xltabular`, вложенные colspec и `Y`-колонки в `maybe_landscape_wide_tables` / `tex_for_pandoc`; для широких таблиц (`>= 8` колонок) не ставит фиксированные `2.5cm` `Z`-колонки, а для `>= 10` колонок включает `\footnotesize` и `\tabcolsep=2.5pt`. `table_edit` сохраняет `\caption{...} \\` в `xltabular`. `tex_preview` поддерживает `\subsubsection` и сохраняет текст внутри `\underline`/`\textsc`/`\textcolor`. `parse_output` сохраняет Vision-подписи `usr_*` при `max_images=0`, восстанавливает голый `{ "charts": ... }` JSON до ```` ```latex ```` и дописывает частично потерянные слоты графиков/схем; `polish_charts` идёт после `ground_generated`, `chart_palette` пишется в `meta.json`; `slides_pptx_layouts` читает живой `_PPTX_FONT` и `pack_id` и не затирает текстурный фон на `chart_hero`/`media_hero`; `slides_pptx_diagrams` парсит цепочки `A --> B --> C` и `A & B --> C`; `source_brief` держит до 120 строк таблиц; `pyproject.toml` задаёт `pythonpath = ["src", "."]` |
| Интерфейс и SSE | `api_stream.py` отдаёт терминал при рестарте с `playable` без финального события. `useLiberRun.ts` не стирает ввод/фото до ответа `/api/run` и читает `output_mode` из `202`. `Ctrl/Cmd+Z/Y` работает по `e.code` и в RU-раскладке; модалки подняты над полноэкранными слоями; UI и промпты очищены от технического жаргона (`Source`, `Mermaid`, `cht_01`, `dia_01`, `fig_01`, `(K = 6, M = 6)`). `web/package.json` `test:helpers` запускает все 51 тест-файлов |

Всё ещё parked: retention прогонов, Win installer, Ask-the-document, Excel/CSV Source, L3 (редизайн Source), L7 (повтор LLM после ошибки стадии). Очередь прогонов и разбор PDF закрыты.

Промпты (wave 2026-11-13): live diagram colors; conditional `system_tex` parts; slim `user_tex` / slides schema / gold; see `prompt/MANIFEST.md` + KI-prompts.

| Тема | Как сейчас |
|------|------------|
| Схемы в отчёте | ADR-0009 снимает UI-only из ADR-0007. Слот `%CASE3_DIAG:dia_NN%` → `figures/dia_NN.png` в PDF/DOCX. Битый Mermaid не валит TeX. `strip_diagram_includegraphics` оставляет только id с `media_status.ok` |
| Схемы в PPTX | `slides_pptx_diagrams.add_native_diagram`: flowchart (≤10 узлов), timeline, mindmap — фигуры и коннекторы. Иначе PNG. sequence / state — PNG |
| Дек | 11 структур, в галерее 8 стилей. Контракт: [`knowledge/deck.md`](knowledge/deck.md). Графики слайдов пачкой: `charts.render_charts_batch` |
| Свои фото | До 5 PNG/JPEG (`user_photos._MAX_COUNT`). Модель видит их (`user_photos_to_vision_images`). В TeX каждый слот один раз (`deduplicate_slots_in_tex`). На слайдах `usr_*` ставятся. Фото не заменяют факты Source |
| Gen `fig_*` | Opt-in (ADR-0012): `image_opt_in.wants_generated_images` + llm budget clamp. Uploads alone ≠ Image API. Spec `2026-11-13-liber-image-opt-in` |
| Born-digital Source | `POST /api/source/ingest` (`source_ingest.py`): PDF/DOCX/DOC/RTF/TXT → md; DOCX tables + PDF `pdfplumber` tables; скан → 422. QA: пз4 PDF≡DOCX 98/98 floats, 71 table rows. Spec `2026-11-13-liber-born-digital-source-ingest-design` |
| Дашборд | «Выбрать данные» сначала список `.mrt` из `local`, затем `/filters` и `/open` выбранного файла, потом «В данные». Снимок карточки — файл с тем же именем рядом (`отчёт.png` к `отчёт.mrt`). Настройки этот разбор не открывают. PNG → Qwen, PDF → ячейки (64 колонки × 500 строк, соседние одинаковые числа остаются). Скан без текста — отказ. Не путать с обрезкой 12×80 в старом TSV. Фильтр «на 1 февраля» показывает поступления за январь: `note_closed_month` и `chat_answer` не дают модели отказаться. Другой месяц или другой год остаются несовпадением. Фраза в чате сначала даёт реплику модели и карточку; модалка открывается с карточки, «В данные» не закрывает её, закрытие шлёт разбор в чат без плашки над вводом. Снимок называется по заголовку экрана, не `dashboard_дата`. Название чата — тот же заголовок, не текст команды. Закрытие экрана пишет короткую реплику и `dashboard_note`, без полотна. Каждый прикреплённый файл и каждый снимок — своя плашка над вводом; крестик снимает только её (`composerPlaques`, `dropSourcePart`). Следующий вопрос, отчёт, схема и презентация читают все снимки этого чата. Число из прошлого ответа повторяется, если оно есть на снимке. ADR-0021 ·  ADR-0020 · ADR-0014 · ADR-0019 · KI-dashboard-source |
| Пустой запрос | `input_validation.validate_input_heuristics`, затем JSON `status: insufficient_data`. `meta.insufficient_data`, пустые артефакты, в чате только текст. Аргумент `has_attachments` гейт не обходит |
| Слот пайплайна и мультипользовательский режим | Пул воркеров `CASE3_MAX_CONCURRENT_RUNS` (default `3`, `1..8`) и FIFO-очередь `CASE3_MAX_QUEUED_RUNS` (default `8`, `1..32`) в `runs/pipeline_queue.json` (ADR-0022 · ADR-0010). Изоляция браузеров без логина через `X-Workspace-Id` (`ws_*`). Запросы `output_mode=chat` и `chat_revise` не занимают слот сборки (`turn=aside`). При переполнении очереди — 409 без id и без слова «перезапуск». Рестарт API поднимает ожидающих из очереди, если meta `queued`. Мёртвый `running` становится `error` с `failed_stage`, сам не продолжается. Отменённый становится `cancelled`. Мёртвая сборка слайдов — ошибка слайдов, отчёт не трогается. SSE-префикс — `meta.steps[]` |
| Подтверждения | `web/src/ConfirmModal.tsx` (`useConfirm`) вместо `window.confirm` |
| Перекрас графиков | `POST /api/runs/{id}/charts/recolor` |
| История чата | `GET /api/history` читает `runs/history_index.json` (не каждый `meta.json`). Ответ: все закреплённые + 24 свежих. Пины: `POST /api/history/sync` |
| Память чата | Цепочка `prior_run_id`, максимум 48. Последние 8 ходов в промпте с абзацами (2000, 1600, 1200, дальше 800). Старше окна — строка на ход, без цифр; совпавший ход поднимается целиком. Потолок вставки 150000 символов. Ответ чата до 4096 токенов. Память не Source. Числа, которые пользователь написал раньше, стоят отдельной строкой со словом рядом (`2 слайд`) и в ответе чата могут повториться; в новом файле то же число остаётся только рядом с этим словом. Числа, которые написала модель, не могут. Пропись («двенадцать») считается цифрой. Открытый отчёт: оглавление и названный раздел. Сборка TeX и слайдов выкидывает число, которого нет в Source, в этой реплике и, для старых реплик, рядом с тем же словом. Массив `data` графика берёт только Source и эту реплику. Экран после открытия сохраняет абзацы. ADR-0013 · ADR-0015 · ADR-0016 · KI-chat-memory |

Всё ещё parked: retention прогонов, Win installer, Ask-the-document, Excel/CSV Source, L3 (редизайн Source), L7 (повтор LLM после ошибки стадии). Очередь (ADR-0010) и разбор PDF закрыты. Хвост Source в чат входит, если абзац совпал с вопросом или это конец документа. Строку таблицы из чата можно добавить или убрать. Легенда схемы отдельным полем не правится.

---

## Быстрый маршрут по задаче

| Задача | Сначала |
|--------|---------|
| Память чата / правка из реплики | [KI-chat-memory](../.agents/knowledge/KI-chat-memory.md) · [ADR-0013](adr/0013-chat-memory-chain.md) |
| Дашборд PNG+PDF → markdown | [KI-dashboard-source](../.agents/knowledge/KI-dashboard-source.md) · [ADR-0014](adr/0014-dashboard-source-markdown.md) |
| Промпт LLM (правка / новый) | [`prompt/MANIFEST.md`](../prompt/MANIFEST.md) → `case3.prompts` · spec `2026-10-30-prompt-catalog` |
| Баг пайплайна / PDF | KI-pipeline → KI-tex-render → ADR-0001 |
| График / палитра / edit | KI-charts → ADR-0002 |
| Таблица / абзац в Preview (edit) | KI-liber-ui · `table_edit.py` / `paragraph_edit.py` · specs table-edit + `2026-10-25-liber-report-depth-c1-c2-c4` |
| Citations / landscape tables | KI-tex-render · `citations.py` · `maybe_landscape_wide_tables` |
| Liber UI | KI-liber-ui → ADR-0003 · ADR-0006 |
| Структура web/ (модули → Angular) | spec `2026-10-25-liber-frontend-modules-design` |
| Схемы Mermaid | ADR-0009 (PDF/DOCX) · ADR-0007 superseded · KI-pipeline / KI-tex-render / KI-liber-deck · edit/legend `2026-10-23-liber-diagram-edit-legend` · native PPTX `slides_pptx_diagrams.py` |
| Inline схемы в Preview | spec+plan `liber-inline-preview-diagrams` (после Liber refactor: `liberTypes` / rail) |
| Фото / Image API | KI-image-api → ADR-0004 · ADR-0012 → specs image-api · image-opt-in |
| Имена media (`fig_`/`cht_`/photo) | KI-media-names |
| Деплой на винду | knowledge/ops-windows.md |
| Презентация / PPTX deck | [`knowledge/deck.md`](knowledge/deck.md) (снимок 2026-11-10) · ADR-0008 · KI-liber-deck · native diagrams `2026-11-07-pptx-native-diagrams` |
| Полный аудит / top-10 probes | [`docs/audits/`](audits/) |
| Отложенные фичи / цикл правок / «новое» K | [`knowledge/backlog-deferred-2026-10-25.md`](knowledge/backlog-deferred-2026-10-25.md) |
| Аудит кода (improve/delete/reuse) | [`knowledge/codebase-audit-2026-10-29.md`](knowledge/codebase-audit-2026-10-29.md) |

---

## Как писать новое

1. **Решение архитектуры** → новый `docs/adr/NNNN-slug.md`, статус Accepted, обновить [`adr/README.md`](adr/README.md).
2. **Подсистема изменилась** → правка KI в `.agents/knowledge/`.
3. **Фича в работе** → `docs/superpowers/specs/` + `plans/`.
4. **Термин / gotcha** → `docs/knowledge/`.

Не раздувай README — он только quick start; глубина здесь.
