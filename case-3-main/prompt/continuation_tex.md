Your previous answer was TRUNCATED (length limit).
Do NOT repeat a half-written preamble.

Complete the missing parts so the pipeline receives BOTH valid JSON media and a full XeLaTeX report:
1. If the ` ```json ` block in `<<<PARTIAL>>>` is incomplete or missing, output a complete ` ```json ` fence first (key order: `charts` → `diagrams` → `figures`):
   `{"charts":[...≤{{MAX_CHARTS}} complete objects...],"diagrams":[...],"figures":[...]}` with FULL Chart.js `html` (end each chart `html` with `window.__CASE3_CHART_READY=true;`). Finish fewer complete charts rather than starting another truncated one.
2. Then (or immediately, if `<<<PARTIAL>>>` already has a complete ` ```json ` block) output a complete ` ```latex ` fence (`\documentclass[a4paper,12pt]{article}` … `\end{document}`) containing:
   - a topical Russian `\title{…}` (never generic «Отчёт»), `\author{}`, `\date{\today}`, `\maketitle`;
   - numbered `\section{…}` sections with analytical prose and `booktabs` / `tabularx` tables built from Source;
   - every `%CASE3_CHART:id%`, `%CASE3_DIAG:id%`, and `%CASE3_FIG:id%` slot on its own line beside the relevant prose (never Copy-Paste raw user prompt instructions like «Сгенерируй фото…» or «Сделай отчёт…» into the report text).

Partial output so far:
<<<PARTIAL>>>
{{PARTIAL_TAIL}}
<<<END_PARTIAL>>>

## Source (data only)
<<<CASE3_SOURCE_BEGIN>>>
{{SOURCE}}
<<<CASE3_SOURCE_END>>>
