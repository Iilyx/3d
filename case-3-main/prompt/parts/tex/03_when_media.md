# When to add charts / figures

`{{MAX_CHARTS}}` / `{{MAX_IMAGES}}` / `{{MAX_DIAGRAMS}}` are **ceilings**. Do **not** invent numbers to fill the budget.
But if the chart ceiling is **≥ 1** and Source **has usable numbers**, you **should** add charts — **aim for up to {{MAX_CHARTS}}** (UI/env budget), not a soft 1–2. Prefer **variety of types** when adding 2+.
**Token priority:** finish `charts` + `diagrams` in JSON before spending the rest of the budget on `figures`. Shorten prose / fewer photos rather than under-shooting the chart budget.

## Charts — add when **all** hold

1. Source has **explicit numbers** (≥2 comparable points, shares, time series, or one clear KPI).
2. A chart helps the reader more than (or alongside) a table.
3. Every plotted value is from Source (only simple % / differences allowed).
4. Place `%CASE3_CHART:id%` **alone on its line** next to the prose it explains. **Forbidden:** trailing dump sections — «Визуализация данных» / «Иллюстрации» / «Графики» / «Приложение: … для визуализации» / any appendix that only lists charts/photos — scatter slots through the report body instead. Never wrap slots in `\begin{figure}` (pipeline wraps PNGs).
5. `caption`: Russian, specific («Клиенты по годам», not «График 1»).
6. Optional chat card meta (numbers **only from Source**): `insight` (1 short Russian sentence) and `highlights: [{label, value, pct?}]` for the top categories — never invent figures.

If Intent **forbids** charts → `"charts": []`, no slots.  
If Intent **asks** for a chart / names types → honor (map wishes to whitelist).  
If Intent is auto/silent but Source has numbers and ceiling ≥ 1 → **add 1…ceiling charts**, pick types by playbook, prefer **different** types.

## `charts[].type` whitelist (strict)

Only the catalog in **Chart types** above (`bar`, `grouped_bar`, `stacked_bar`, `line`, `horizontal_bar`, `donut`, `kpi`, `area`, `scatter`).

Synonyms: pie/круговая/doughnut → `donut`; column/столбцы → `bar`; тренд → `line`; топ-N → `horizontal_bar`; одна цифра → `kpi`.  
Never emit non-catalog `type`.
