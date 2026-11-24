import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  cellSemanticTone,
  dashboardStarterChips,
  isTotalTableRow,
  splitDashboardBlocks,
  splitDashboardSections,
  tableToCsv,
} from "./dashboardTables.ts";

const wide = [
  "# Данные дашборда",
  "",
  "Числа скопированы из ячеек PDF.",
  "",
  "## Таблица PDF",
  "",
  "| Налог | Факт | План | Доля |",
  "| --- | --- | --- | --- |",
  "| НДС | 1 234,56 | 100,0 | 17,8% |",
  "| Акциз | 77 | 77 | -12,4% |",
  "| A\\|B |  | 3 |  |",
].join("\n");

describe("splitDashboardBlocks", () => {
  it("keeps every column, a repeated neighbour, and an escaped pipe", () => {
    const blocks = splitDashboardBlocks(wide);
    const table = blocks.find((block) => block.kind === "table");
    assert.ok(table && table.kind === "table");
    assert.deepEqual(table.header, ["Налог", "Факт", "План", "Доля"]);
    assert.equal(table.rows[0][1], "1 234,56");
    assert.equal(table.rows[1][1], "77");
    assert.equal(table.rows[1][2], "77");
    assert.equal(table.rows[2][0], "A|B");
    assert.equal(table.rows.length, 3);
    assert.deepEqual(table.numeric, [false, true, true, true]);
  });

  it("drops the machine intro and keeps the table title", () => {
    const blocks = splitDashboardBlocks(wide);
    const text = blocks
      .filter((block) => block.kind === "heading")
      .map((block) => block.text);
    assert.deepEqual(text, ["Таблица PDF"]);
    assert.equal(
      blocks.some(
        (block) => block.kind === "text" && block.text.includes("скопированы"),
      ),
      false,
    );
  });

  it("counts a wide grid without dropping the last column", () => {
    const header = ["Название", ...Array.from({ length: 20 }, (_, i) => `c${i}`)];
    const row = ["НДС", ...Array.from({ length: 20 }, (_, i) => String(i))];
    const md = [
      `| ${header.join(" | ")} |`,
      `| ${header.map(() => "---").join(" | ")} |`,
      `| ${row.join(" | ")} |`,
    ].join("\n");
    const table = splitDashboardBlocks(md).find((block) => block.kind === "table");
    assert.ok(table && table.kind === "table");
    assert.equal(table.header.length, 21);
    assert.equal(table.header[20], "c19");
    assert.equal(table.rows[0][20], "19");
    assert.equal(table.numeric[0], false);
    assert.equal(table.numeric[20], true);
  });

  it("shows the screen reading without asterisks", () => {
    const md = [
      "## Экран",
      "",
      "**Заголовок и фильтры**",
      "*   **Регион:** Республика Беларусь / Брестская область",
      "*   **Период:** январь 2025",
      "",
      "| Наименование | Факт (руб.) |",
      "| --- | --- |",
      "| **Налог на добавленную стоимость, всего** | 105 865,2 |",
      "| НДС | -20,7% |",
    ].join("\n");
    const blocks = splitDashboardBlocks(md);
    assert.deepEqual(
      blocks.filter((block) => block.kind === "heading").map((block) => block.text),
      ["Экран", "Заголовок и фильтры"],
    );
    const list = blocks.find((block) => block.kind === "list");
    assert.ok(list && list.kind === "list");
    assert.deepEqual(list.items, [
      "Регион: Республика Беларусь / Брестская область",
      "Период: январь 2025",
    ]);
    const table = blocks.find((block) => block.kind === "table");
    assert.ok(table && table.kind === "table");
    assert.equal(table.rows[0][0], "Налог на добавленную стоимость, всего");
    assert.equal(table.rows[0][1], "105 865,2");
    assert.equal(table.rows[1][1], "-20,7%");
    assert.equal(table.numeric[1], true);
  });

  it("splits main blocks from auto-calculated derivatives (## Производные)", () => {
    const md = [
      "# Данные дашборда",
      "## Таблица PDF",
      "| Область | План | Факт | Отклонение | Выполнение (%) |",
      "| --- | --- | --- | --- | --- |",
      "| г. Минск | 179 500,0 | 184 520,0 | +5 020,0 | 102,8% |",
      "| Брестская область | 59 200,0 | 57 846,4 | -1 353,6 | 97,7% |",
      "| Итого | 238 700,0 | 242 366,4 | +3 666,4 | 101,5% |",
      "",
      "## Производные",
      "Доли, суммы и отклонения посчитаны из ячеек. Копируй их как здесь.",
      "",
      "Факт",
      "- г. Минск — доля 76,1%, место 1",
    ].join("\n");
    const sections = splitDashboardSections(md);
    assert.equal(sections.mainBlocks.some((b) => b.kind === "table"), true);
    assert.equal(sections.derivativeBlocks.length > 0, true);
    assert.equal(
      sections.derivativeBlocks.some(
        (b) => b.kind === "text" && b.text.includes("Копируй их как здесь"),
      ),
      false,
    );
  });

  it("detects total rows, positive/negative cell tones, and exports CSV with BOM", () => {
    const header = ["Область", "План", "Факт", "Отклонение", "Выполнение (%)"];
    const rowMinsk = ["г. Минск", "179 500,0", "184 520,0", "+5 020,0", "102,8%"];
    const rowBrest = ["Брестская область", "59 200,0", "57 846,4", "−1 353,6", "97,7%"];
    const rowTotal = ["Итого по всем", "238 700,0", "242 366,4", "+3 666,4", "101,5%"];

    assert.equal(isTotalTableRow(rowMinsk), false);
    assert.equal(isTotalTableRow(rowTotal), true);

    assert.equal(cellSemanticTone(rowMinsk[3], header[3]), "pos");
    assert.equal(cellSemanticTone(rowBrest[3], header[3]), "neg");
    assert.equal(cellSemanticTone(rowMinsk[4], header[4]), "pos");
    assert.equal(cellSemanticTone(rowBrest[4], header[4]), "neg");
    assert.equal(cellSemanticTone(rowMinsk[1], header[1]), null);

    const csv = tableToCsv(header, [rowMinsk, rowBrest]);
    assert.equal(csv.startsWith("\uFEFF"), true);
    assert.equal(csv.includes("Область;План;Факт;Отклонение;Выполнение (%)"), true);
    assert.equal(csv.includes("Брестская область;59 200,0;57 846,4;−1 353,6;97,7%"), true);
  });

  it("returns emoji-free context-aware dashboard starter chips for 1 and 2+ shots", () => {
    const singleChips = dashboardStarterChips(wide, 1);
    assert.equal(singleChips.length >= 4, true);
    for (const chip of singleChips) {
      assert.equal(/[\u{1F300}-\u{1FAFF}]/u.test(chip.label), false);
    }
    const multiChips = dashboardStarterChips(wide, 2);
    assert.equal(multiChips[0].label, "Сравнить снимки в динамике");
  });
});
