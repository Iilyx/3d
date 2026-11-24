import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { pageTextMatchesNeedle, pdfSearchNeedles } from "./pdfFindPage";

describe("pdfSearchNeedles", () => {
  it("prefers full caption then bare title", () => {
    const n = pdfSearchNeedles("Рис. 2: Распределение продаж по каналам", "cht_02");
    assert.equal(n[0], "Рис. 2: Распределение продаж по каналам");
    assert.ok(n.includes("Распределение продаж по каналам"));
    assert.ok(n.includes("cht_02"));
  });

  it("skips empty / tiny", () => {
    assert.deepEqual(pdfSearchNeedles("  ", null), []);
    assert.deepEqual(pdfSearchNeedles("ab", "xy"), []);
  });
});

describe("pageTextMatchesNeedle", () => {
  it("matches spaced and compact caption text", () => {
    const page = "Рис. 2 Распределение продаж по каналам Таблица 2";
    assert.equal(
      pageTextMatchesNeedle(page, "Распределение продаж по каналам"),
      true,
    );
    assert.equal(pageTextMatchesNeedle("Рис.2:Foo", "Рис. 2"), true);
    assert.equal(
      pageTextMatchesNeedle(page, "несуществующий текст xyz"),
      false,
    );
  });
});
