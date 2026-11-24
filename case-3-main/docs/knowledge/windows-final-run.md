# Windows final run — готовность + 3 прогона

Дата: 2026-10-23. Прод-контур: **Windows desk** + **локальный Qwen** (`VISION_*`) + **офисный Image API** (`IMAGE_API_*`).  
Не путать с домашним OpenRouter / wrangler `:8787` — на винде фото идут напрямую на `IMAGE_API_BASE_URL`.

Связанные: [`ops-windows.md`](ops-windows.md) · [`README.md`](../../README.md) · [`.env.example`](../../.env.example)

---

## 1. Детальный анализ: что нужно, чтобы весь пайплайн поднялся на Windows

### 1.1 Стек и порты

| Слой | Кто | Порт / артефакт | Windows-команда |
|------|-----|-----------------|-----------------|
| Vision (TeX + charts JSON + Mermaid) | **Qwen** office | `VISION_API_BASE_URL` (часто `:8080`) | в `.env` |
| Image (фото figures) | **кастомный Image API** | `IMAGE_API_BASE_URL` (`POST /generate`, `/edit`) | в `.env` |
| Liber API | uvicorn `case3.api` | `127.0.0.1:8000` | `scripts\api.cmd` |
| Liber UI | Vite | `127.0.0.1:5173` → proxy `/api` | `scripts\web.cmd` |
| PDF | Docker `case-3:tex` | образ локально | `scripts\setup.cmd` |
| Charts PNG | Playwright Chromium | кэш браузеров | `setup.cmd` / `python -m playwright install chromium` |

**Не нужен на Windows desk:** `workers/case3-image` (wrangler `:8787`) — это home/dev proxy. Прод читает офисный FastAPI по `IMAGE_API_BASE_URL`.

### 1.2 Обязательный `.env` (секреты не в git)

```env
# Qwen (основной путь)
VISION_API_BASE_URL=http://<qwen-host>:8080
# VISION_API_KEY=          # если Qwen требует
# VISION_MODEL=            # если gateway требует имя модели
VISION_REASONING=off
VISION_MAX_TOKENS=16384
VISION_TIMEOUT_S=300

# Кастомный Image API (фото)
IMAGE_API_BASE_URL=http://192.168.4.101:8000
IMAGE_MAX_IMAGES=2
IMAGE_WIDTH=1024
IMAGE_HEIGHT=1024
IMAGE_TIMEOUT_S=180
# IMAGE_API_KEY=           # если API требует

CASE3_IMAGE=case-3:tex
CASE3_MAX_CHARTS=2
```

Проверка после старта API:

```text
GET http://127.0.0.1:8000/api/health
→ ok: true
→ vision_configured: true
→ docker_ok: true
→ playwright_ok: true
→ image_api_configured: true
→ image_api_base_url: <твой IMAGE_API_BASE_URL>
```

Если `vision_configured: false` — нет `VISION_API_BASE_URL`.  
Если `image_api_configured: false` — пустой `IMAGE_API_BASE_URL` (фото вырежутся из слотов).  
Если `docker_ok: false` — Docker Desktop / `setup.cmd`.  
Если `playwright_ok: false` — `python -m playwright install chromium`, перезапуск `api.cmd`.

### 1.3 Чеклист «с нуля» на винде

1. Docker Desktop **запущен**.
2. `git pull origin main`
3. `scripts\setup.cmd` (pip editable, Playwright Chromium, `docker compose build` → `case-3:tex`)
4. Скопировать/поправить `.env` под **Qwen + Image API** (не OpenRouter).
5. `cd web && npm install`
6. Окно 1: `scripts\api.cmd` (**без** `--reload`, иначе рвёт длинные job)
7. Окно 2: `scripts\web.cmd`
8. Health → Liber UI `http://127.0.0.1:5173`
9. Финальный прогон: три запроса ниже (Отчёт → Схема → Презентация)

### 1.4 Риски (что ломалось на Mac / что ждать на Win)

| Симптом | Причина | Фикс на Win |
|---------|---------|-------------|
| Пустой ответ / `finish_reason=length` | thinking жрёт токены; огромный TeX | `VISION_REASONING=off`; Qwen быстрее free OpenRouter; при truncate — continuation в `generate.py` |
| `URLError` / DNS | proxy / сеть | `api.cmd` уже чистит `HTTP(S)_PROXY` |
| Charts blank | нет Chromium | `python -m playwright install chromium` |
| Фото пустые | Image API недоступен | ping `IMAGE_API_BASE_URL`; WinError 10061 = хост/порт |
| Долго «Думаю…» 5–10 мин | длинный LLM + continuation | нормально для полного отчёта; не убивать `api.cmd` |
| Порт занят | старый uvicorn | закрыть окна / Task Manager |

### 1.5 Что сознательно не трогать при финал-прогоне

- Не коммитить `.env`, `runs/`, PDF/DOCX артефакты.
- Не включать OpenRouter `:free` на desk — только Qwen.
- Палитры: atelier / editorial / ocean / sunset / mono — без фиолетового.
- Числа только из Source.

---

## 2. Три больших запроса для финал-прогона

**Общие настройки Liber:** лимиты `2 / 2 / 2` (графики / фото / схемы), палитра **atelier**.  
Source → плашка; Intent → чат (или оба куска в чат).

---

### Прогон A — Отчёт (пилюля «Отчёт»)

**Source:**

```
Liber Atelier — квартальный обзор ops SaaS «Северная логистика», Q3 2026.
Офис: Минск, ул. Интернациональная 25; склад: Брест, логистический хаб «Буг».
Продукт: TMS + last-mile трекинг для ритейла.

KPI Q3 2026 (абсолют):
MRR: июл 412 тыс. BYN, авг 428, сен 451.
Churn: июл 3.1%, авг 2.8%, сен 2.4%.
NPS: июл 41, авг 44, сен 48.
SLA on-time: июл 93.2%, авг 94.1%, сен 95.0%.
Тикеты поддержки: июл 1280, авг 1190, сен 1050.

Выручка по каналам Q3, тыс. BYN:
Direct 380 | Partner 210 | Marketplace 145 | Enterprise 290.

Доля сегментов клиентов Q3, %:
Retail 42 | Food 28 | Pharma 18 | Other 12.

Топ-5 городов по объёму доставок Q3, тыс. заказов:
Минск 86 | Брест 41 | Гродно 33 | Витебск 29 | Гомель 27.

Таблица SLA по неделям (W27–W39), % on-time:
W27 92.1, W28 92.4, W29 93.0, W30 93.5, W31 93.8, W32 94.0,
W33 94.2, W34 94.5, W35 94.7, W36 94.9, W37 95.1, W38 95.0, W39 95.0.

Процесс инцидента: Detect → Triage → Fix → Verify → Postmortem.
Роли: Dispatcher, Driver, Support L1, Ops Lead, Client CSM.
Сцены для иллюстраций: ночной склад в Бресте; диспетчерская с экранами трекинга в Минске.
```

**Intent:**

```
Собери полный отчёт по Source, палитра atelier, без выдуманных цифр.
Обязательно: 1 таблица KPI/каналов; 2 разных Chart.js (line по MRR или SLA + donut по сегментам);
2 фото (склад Брест + диспетчерская Минск); 1–2 Mermaid (flowchart инцидента + sequence ролей).
Заголовок: «Северная логистика — Q3 2026». Текст на русском, цифры только из Source.
```

**Ожидание:** PDF + DOCX; в чате summary + карточка; rail Preview/PDF; 2 chart PNG; 2 figures; Mermaid в UI.

---

### Прогон B — Схема (пилюля «Схема»)

**Source:**

```
Сервис планирования спринтов «Agile Retro Hub».
Акторы: Product Owner, Scrum Master, Dev Team, Stakeholder, Liber Bot.
Спринты: Planning → Daily → Review → Retro → Backlog Grooming.
Ретро доска: Start / Stop / Continue / Action Items.
Поток бага: Open → Triage → In Progress → Code Review → QA → Done;
ветка Blocked → Unblock → In Progress.
Интеграции: GitHub (PR), Telegram (дайджест), S3 (артефакты PDF).
SLA: Critical ≤4ч, High ≤1д, Medium ≤3д.
Метрики спринта (не рисовать графики — только для подписей на схеме):
velocity 34 / 32 / 36 SP за последние 3 спринта; escaped defects 2 / 1 / 0.
```

**Intent:**

```
Режим СХЕМА: только Mermaid, без таблиц KPI и без Chart.js/фото в PDF.
Сделай 2–3 схемы: (1) flowchart жизненного цикла бага с Blocked;
(2) sequence: PO → Scrum Master → Dev → Liber Bot → Stakeholder на Review;
(3 опционально) mindmap или stateDiagram доски Retro (Start/Stop/Continue/Actions).
Короткий stub: заголовок «Agile Retro Hub — процессы» + 1–2 абзаца.
Подписи и числа только из Source. Без выдуманных метрик на рёбрах.
```

**Ожидание:** `formats=none`; 2–3 Mermaid в чате/rail «Схема»; без полного PDF-отчёта.

---

### Прогон C — Презентация (пилюля «Презентация», pack atelier)

**Source:**

```
Кампания запуска Liber Atelier для B2B, сентябрь–октябрь 2026.
Города пилота: Минск, Алматы, Ереван.
Оффер: Source→Intent→PDF/DOCX + Chart.js + фото за один прогон.

Воронка (лиды → SQL → win), шт.:
Минск: 120 → 48 → 11
Алматы: 90 → 31 → 7
Ереван: 70 → 22 → 5

CAC, USD: Минск 180, Алматы 210, Ереван 160.
LTV, USD: Минск 2400, Алматы 1900, Ереван 2100.
Win-rate: Минск 23%, Алматы 23%, Ереван 23% (одинаковый по пилоту).

Недельные демо (шт.): W36 8, W37 11, W38 14, W39 16, W40 19.
NPS пилотных CSM: 52 (Минск), 47 (Алматы), 55 (Ереван).

Слайдовая история: проблема ручных отчётов → пайплайн Liber → цифры пилота → next steps.
Сцены: офис demо в Минске; команда за большим экраном с отчётом.
Процесс продажи: Lead → Demo → Pilot → Contract → Onboarding.
```

**Intent:**

```
Собери презентацию (не PDF-отчёт) по Source, pack atelier, без выдуманных цифр.
Нужны: KPI-слайды; 1–2 графика (line демо по неделям + bar/grouped CAC–LTV или воронка);
таблица воронки по городам; 1–2 фото (демо-офис, команда у экрана);
1 Mermaid flowchart продажи Lead→…→Onboarding.
Takeaways короткие, слайдопригодные. Заголовок дека: «Liber Atelier — пилот B2B Q4».
```

**Ожидание:** после run — сборка слайдов (Working · m:ss); PPTX + deck PDF twin; без классического report PDF/DOCX.

---

## 3. Порядок и критерии «готово»

1. Health все флаги зелёные.  
2. Прогон A → PDF открывается, графики не blank, фото на месте.  
3. Прогон B → Mermaid рендерится, PDF-отчёт не обязателен.  
4. Прогон C → PPTX скачивается, twin PDF ок.  
5. При ошибке: `runs\logs\<run_id>\` + `scripts\push-debug.cmd` (без PDF/DOCX в git).
