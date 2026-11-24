import test from "node:test";
import assert from "node:assert/strict";
import { reportToMarkdown } from "./reportMarkdown";
import type { PreviewBlock } from "./reportPreview";

test("reportToMarkdown produces formatted document with headings, paras, tables, and lists", () => {
  const blocks: PreviewBlock[] = [
    { type: "heading", level: 1, text: "Введение" },
    { type: "paragraph", text: "Абзац с **жирным** текстом." },
    {
      type: "list",
      ordered: false,
      items: [{ text: "Пункт 1" }, { text: "Пункт 2" }],
    },
    {
      type: "table",
      caption: "Ключевые показатели",
      headers: ["Метрика", "Значение"],
      rows: [
        ["Выручка", "100 млн руб."],
        ["EBITDA", "25 млн руб."],
      ],
    },
    {
      type: "figure",
      id: "cht_01",
      kind: "chart",
      caption: "Динамика выручки",
      url: "/api/runs/demo/figures/cht_01.png",
    },
  ];

  const md = reportToMarkdown({
    title: "Финансовый отчёт 2024",
    blocks,
  });

  assert.match(md, /^# Финансовый отчёт 2024\n/);
  assert.match(md, /## Введение/);
  assert.match(md, /Абзац с \*\*жирным\*\* текстом\./);
  assert.match(md, /- Пункт 1\n- Пункт 2/);
  assert.match(md, /\*Таблица 1: Ключевые показатели\*/);
  assert.match(md, /\| Метрика \| Значение \|/);
  assert.match(md, /\| Выручка \| 100 млн руб\. \|/);
  assert.match(md, /!\[Диаграмма: Динамика выручки\]\(\/api\/runs\/demo\/figures\/cht_01\.png\)/);
});
