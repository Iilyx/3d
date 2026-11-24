import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  updateTableCell,
  addTableRow,
  deleteTableRow,
  addTableCol,
  deleteTableCol,
  ensureTableRows,
} from "./tableSlideEdit";

describe("tableSlideEdit", () => {
  const initialRows = [
    ["Параметр", "План", "Факт"],
    ["Выручка", "10 млн", "12 млн"],
    ["NPS", "40", "45"],
  ];

  it("updates cell immutably", () => {
    const next = updateTableCell(initialRows, 1, 2, "14 млн");
    assert.equal(next[1][2], "14 млн");
    assert.equal(initialRows[1][2], "12 млн");
  });

  it("adds a new row matching current table width", () => {
    const next = addTableRow(initialRows);
    assert.equal(next.length, 4);
    assert.equal(next[3].length, 3);
    assert.equal(next[3][0], "Новая строка");
    assert.equal(next[3][1], "—");
  });

  it("refuses to delete header row 0 or leave fewer than 2 rows", () => {
    const refusedHeader = deleteTableRow(initialRows, 0);
    assert.equal(refusedHeader.length, 3);

    const twoRows = [
      ["Параметр", "Значение"],
      ["Выручка", "10 млн"],
    ];
    const refusedMin = deleteTableRow(twoRows, 1);
    assert.equal(refusedMin.length, 2);

    const deleted = deleteTableRow(initialRows, 1);
    assert.equal(deleted.length, 2);
    assert.equal(deleted[1][0], "NPS");
  });

  it("adds a new column to all rows", () => {
    const next = addTableCol(initialRows, "Статус");
    assert.equal(next[0][3], "Статус");
    assert.equal(next[1][3], "—");
    assert.equal(next[2][3], "—");
  });

  it("deletes a column and preserves at least 2 columns", () => {
    const deleted = deleteTableCol(initialRows, 1);
    assert.equal(deleted[0].length, 2);
    assert.deepEqual(deleted[0], ["Параметр", "Факт"]);
    assert.deepEqual(deleted[1], ["Выручка", "12 млн"]);

    const twoCols = [
      ["A", "B"],
      ["1", "2"],
    ];
    const refused = deleteTableCol(twoCols, 1);
    assert.equal(refused[0].length, 2);
  });

  it("ensureTableRows provides default structure when missing or empty", () => {
    const rows = ensureTableRows(undefined);
    assert.ok(rows.length >= 2);
    assert.ok(rows[0].length >= 2);

    const custom = [["A", "B"], ["1", "2"]];
    assert.equal(ensureTableRows(custom), custom);
  });
});
