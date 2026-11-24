# Gold exemplars

Фрагменты LaTeX, которые подмешиваются в system prompt (top 2–3 по тегам Intent).

## Charts vs prototip

В `prototip-repo` графики строятся так: **LLM → ChartSpec → Plotly `build_chart`** (без HTML и без `exec`).

В case-3 рендер другой: **LLM → HTML Chart.js → Playwright PNG**.

Поэтому Plotly-код из прототипа **не копируем** как gold. Берём:

- каталог/эвристики типов из `chart_playbook.yaml` (line / horizontal_bar / donut / …);
- слот `%CASE3_CHART:…%` в `chart_slot.tex`;
- HTML-рецепты Chart.js — в `prompt/parts/tex/` (composed `system_tex`).

Бюджет графиков везде только через env **`CASE3_MAX_CHARTS`**.
