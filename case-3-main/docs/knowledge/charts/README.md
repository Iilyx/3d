# Live charts (Liber web)

- **Whitelist:** bar, grouped_bar, stacked_bar, line, horizontal_bar, donut, kpi, area, scatter
- **Live path:** `LiveChart` mounts Chart.js **inline** (no iframe), DPR ≥ 2, retina → 3
- **Print path:** Playwright PNG → PDF (истина печати)
- **QA gallery:** `http://127.0.0.1:5173/?preview=charts-qa` + `web/public/qa-chart-fixtures.json`

Screenshot (all types, 2026-10-21):

![all live chart types](live-charts-qa-all-types.png)
