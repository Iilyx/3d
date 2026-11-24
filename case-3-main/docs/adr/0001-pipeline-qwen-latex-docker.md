# ADR-0001: Pipeline Qwen → LaTeX → Docker PDF/DOCX

## Status
Accepted

## Date
2026-10-21

## Context
Нужен офисный отчёт из сырых цифр/текста на Windows: русский текст, таблицы, графики, опционально фото. Модель (Qwen) доступна по HTTP; печать должна быть предсказуемой (A4 PDF + DOCX).

## Decision
Оркестрация в `run_pipeline`: Intent+Source → LLM генерирует `.tex` + `charts[].html` + figure prompts → render Chart.js/Playwright и Image API → inject slots → Docker image `case-3:tex` (`latexmk -xelatex`, затем pandoc DOCX).

## Alternatives Considered

### Pure Markdown → pandoc
- Pros: проще
- Cons: слабый контроль вёрстки RU/A4, графики хуже
- Rejected: нужен «печатный» вид

### Model emits PDF directly
- Pros: один шаг
- Cons: нестабильно, не редактируется, нет DOCX
- Rejected

### Host TeX on Windows without Docker
- Pros: меньше Docker
- Cons: ад зависимостей на корпоративных ПК
- Rejected: Docker `--net=none` + один образ

## Consequences
- Истина артефакта — PDF; чат — приближение.
- Нужны hardeners TeX (ADR-0005).
- Длинные job: API без `--reload` по умолчанию.
