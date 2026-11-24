# case-3 — Liber Atelier

Аналитическое рабочее пространство (Chat-first UI + FastAPI + LaTeX/Pandoc/LibreOffice/Playwright) для работы с дашбордами **Stimulsoft** и документами (`.pdf`, `.docx`, `.txt`, `.md`):

- **Чат-аналитика по дашбордам и документам:** снятие одного или нескольких экранов дашборда (визуальный PNG + полная векторная таблица PDF до 64 колонок × 500 строк + автоматический расчёт секции `## Производные`: суммы, средние, мин/макс, доли, отклонения `Факт − План` и групповые итоги по областям).
- **Строгая привязка чисел (Fact Grounding):** модель опирается только на исходные данные, числа из вопроса пользователя (*what-if* сценарии) и проверяемую кросс-строчную арифметику (`+`, `−`, `%`, доли) между регионами и периодами.
- **Генерация артефактов:**
  - **В чате:** таблицы, аналитические ответы, inline-графики Chart.js (PNG) и схемы процессов/структур.
  - **Отчёты (PDF + DOCX):** вёрстка через XeLaTeX и Pandoc (`reference.docx`), нативные редактируемые диаграммы в Word, автоматический альбомный разворот широких таблиц (6–15 колонок, включая многостраничные `xltabular`).
  - **Презентации (PPTX + PDF):** 6–24 слайдов, 8 визуальных стилей, 11 структур, нативные векторные графики и схемы в PowerPoint.
- **Живое редактирование (in-place):** правка текста разделов, таблиц, графиков, подписей, стилей и заголовков конкретных слайдов как через UI-превью, так и обычными фразами в чате (*«перекрась график в закат»*, *«в таблице поменяй Пинский р-н на г. Пинск»*, *«поменяй заголовок слайда 3 на Анализ областей»*, *«распиши раздел Выводы подробнее»*, *«отмени»*).
- **Многопользовательский режим и асинхронность:** изоляция рабочих пространств по браузерам (`X-Workspace-Id`), параллельные ответы в чате, пул воркеров для одновременной сборки отчётов (`CASE3_MAX_CONCURRENT_RUNS`, по умолчанию `3`) и FIFO-очередь (`CASE3_MAX_QUEUED_RUNS`, по умолчанию `8`).

---

## Быстрый запуск в Docker (Full-Stack: Frontend + Backend + TeX)

Весь стек (`frontend` на Nginx `:5173` + `backend` на FastAPI `:8000` со встроенным TeX Live, Pandoc, LibreOffice и Playwright Chromium) поднимается одной командой:

```bash
docker compose up -d --build
```

- **Интерфейс Liber UI:** http://127.0.0.1:5173 (проксирует `/api/*` и SSE-стриминг на `backend:8000`)
- **Swagger / OpenAPI:** http://127.0.0.1:8000/docs
- **Проверка готовности:** `curl -s http://127.0.0.1:5173/api/health`

Если нужен отдельный контейнер `case-3:tex` для внешнего рендера на хосте:

```bash
docker compose --profile tex build tex
```

---

## Сначала проверь Qwen (Win LAN)

Пока модель молчит — Liber «жду модель» крутится зря. Подставь IP/модель из `.env`.

**Важно:** в PowerShell `curl` = `Invoke-WebRequest` → ошибка про Headers / Content-Type. Пиши **`curl.exe`**.

```cmd
curl.exe -s --max-time 30 http://192.168.4.101:8080/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"qwen3.5-4b\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":8,\"chat_template_kwargs\":{\"enable_thinking\":false}}"
```

`--max-time 30` = лимит ожидания ответа (сек), не путать с JSON-полем `"model"`.

- JSON с `choices` за ≤30 с → Vision ок, дальше `api.cmd` / `web.cmd`
- таймаут / ошибка → чини хост `:8080` у коллеги (не UI)
- **404 на `:8080/generate` — нормально (это путь Image API).** Текст: только `/v1/chat/completions`
- Фото отдельно: `curl.exe -s -o NUL -w "%{http_code}" http://192.168.4.101:8000/` (корень может дать 404 — процесс жив; для генерации нужен `POST /generate`)

**Source ingest:** `.pdf` / `.docx` — просмотр во вкладке «Источник» (pdf.js), текст и таблицы извлекаются автоматически. `.txt` / `.md` / снимки дашбордов Stimulsoft — просмотр таблиц с поиском и подсветкой + редактирование по клику до сборки. Скан-PDF без текстового слоя → отказ (422). `.doc`/`.rtf`/PDF-превью DOCX — через LibreOffice.

**Схемы:** вкладка «Схема» — процессы с числами из документа, легенда, скачивание PNG и редактирование узлов. Слот `%CASE3_DIAG:dia_NN%` попадает в PDF и DOCX как `figures/dia_NN.png` (ADR-0009), а в PPTX рисуется нативными фигурами PowerPoint.

**Презентация:** слайдов 6–24 (настройка «Слайдов в презе»). До 5 своих PNG/JPEG. Подробно: [`docs/knowledge/deck.md`](docs/knowledge/deck.md).

**Preview edit:** разделы текста / списки / графики / фото / **таблицы** («Изменить» → редактирование ячеек → «Сохранить» = пересборка TeX + PDF/DOCX). Таблицы: `POST /api/runs/{id}/tables/{n}/edit`.

Фото: офисный Image API `POST /generate` и `POST /edit` (`IMAGE_API_BASE_URL`).  
DOCX: `assets/docx/reference.docx` (pandoc `--reference-doc`).

**Скрипты на Windows:** только `setup.cmd` · `api.cmd` · `web.cmd` · `push-debug.cmd`.

## Запуск на Windows (из корня `case-3\`)

```cmd
git pull origin main
scripts\setup.cmd
```

Правь `.env` под **Qwen**: `VISION_API_BASE_URL=http://<host>:8080`  
(сгенерированные фото: `IMAGE_API_BASE_URL=http://192.168.4.101:8000`, `IMAGE_MAX_IMAGES=2`. Свои вложения в презу — отдельно, до 5)  
Если «нет documentclass» / пустой ответ → `VISION_REASONING=off`, перезапуск `api.cmd`.

**Сайт — два окна cmd:**

```cmd
scripts\api.cmd
scripts\web.cmd
```

После `git pull` в `web\`: `npm install` (нужен `pdfjs-dist` для превью 1-й стр. PDF в чате).

- UI: http://127.0.0.1:5173  (прокси `/api` → `:8000`)
- API: http://127.0.0.1:8000/docs · health: `/api/health`
- Сборка в Liber идёт с прогрессом (`POST /api/run` → poll `/status`); `api.cmd` **без** `--reload` (иначе рвёт длинные job). Dev-reload: `set CASE3_RELOAD=1` перед `api.cmd`.

Сборка и артефакты: через Liber UI → `runs\out\<run_id>\`.

## Env (`.env`)

| Переменная | Описание |
|--|--|
| `VISION_API_BASE_URL` | URL сервера Qwen / OpenAI-совместимого LLM (`http://<host>:8080/v1`) |
| `VISION_API_KEY` | API-ключ LLM (если требуется) |
| `VISION_MODEL` | Имя модели (например, `qwen3.5-4b` или `openrouter/free`) |
| `DASHBOARD_BASE_URL` | URL сервиса предпросмотра Stimulsoft (по умолчанию `http://127.0.0.1:8040`) |
| `CASE3_MAX_CHARTS` | Потолок графиков в отчёте (0 = off, default 5) |
| `CASE3_MAX_DIAGRAMS` | Потолок схем (0–5, default 5). PNG в PDF/DOCX и нативные фигуры в PPTX |
| `IMAGE_API_BASE_URL` | Офисный Image API (`/generate`, `/edit`) |
| `IMAGE_MAX_IMAGES` | Потолок сгенерированных фото (0 = off, default 2) |
| `CASE3_IMAGE` | Имя Docker-образа TeX (`case-3:tex`) |
| `CASE3_LOCAL_TEX` | `1` внутри контейнера `backend` (локальный `latexmk` + `pandoc` без вложенного Docker) |
| `CASE3_MAX_CONCURRENT_RUNS` | Число параллельных воркеров сборки отчётов/презентаций (`1..8`, default `3`) |
| `CASE3_MAX_QUEUED_RUNS` | Размер FIFO-очереди ожидающих сборок (`1..32`, default `8`) |
| `CASE3_CORS_ORIGINS` | Дополнительные разрешённые CORS-ориджины через запятую |

## Если сломалось

| | |
|--|--|
| нет Docker-образа | Docker Desktop → `scripts\setup.cmd` |
| нет графиков / Playwright | `python -m playwright install chromium` → перезапуск `api.cmd` |
| нет `\documentclass` / пустой ответ | `.env`: `VISION_REASONING=off`, перезапуск `api.cmd` |
| HTTP **500** Context size exceeded | `.env`: `VISION_MAX_TOKENS=4096` (не 16384 на LAN GGUF), Source короче, фото/графики=0, рестарт `api.cmd` |
| Завис после TeX на «фото» / `stage=images` / `inject` навсегда | Баг ETA-lock (fixed `4a64a98`+): `git pull`, убей python, один прогон. Image `:8000` мёртв → `IMAGE_MAX_IMAGES=0` |
| «PDF 6 минут» а файла нет | Это не latexmk — LLM + deadlock на 2-й стадии; после pull PDF ~секунды после TeX |
| Куча `running` в `runs\out` | Task Manager → убей все `python`, один `api.cmd`, один прогон |
| HTTP **409** | Третий `POST /api/run`: один прогон уже идёт, второй ждёт (`202 queued`). Сброс слота — `POST /api/pipeline/slot/reset`, только если поток мёртв |
| Коллега «404» | Не тот URL: Qwen≠`/generate`; или качаешь PDF пока `status=running` |
| мало текста / нет графиков (обрыв) | поднять `VISION_MAX_TOKENS` (≥12288 при 4–5 графиках); UI «Графиков ≤» + `CASE3_MAX_CHARTS`; рестарт `api.cmd` |
| Dry-run | графиков не будет — снять галку, нужен Vision |
| нет Vision | `.env` или UI → Dry-run |
| порт занят | закрой старые `api.cmd` / `web.cmd` |
| отдать логи | `scripts\push-debug.cmd` → ветка `debug/upload-STAMP` (slim: tex/logs/json/raw, без PNG/slides; `KEEP_MEDIA=1` / `KEEP_PDF=1` по необходимости) |

## Папки

`scripts\` (4 cmd) · `web\` · `src\` · `prompt\` · `assets\` · `runs\` (out / logs / work / uploads)

## Windows checklist после pull

1. Docker Desktop → `scripts\setup.cmd` (образ `case-3:tex`, Playwright, `pip install -e .`)
2. `.env` с Qwen URL; `.env` не в git
3. `scripts\api.cmd` + `scripts\web.cmd` → health `ok` / `vision_configured`
4. Liber: Source → «Собрать»; PDF/DOCX в панели
5. Логи коллеге: `scripts\push-debug.cmd`
