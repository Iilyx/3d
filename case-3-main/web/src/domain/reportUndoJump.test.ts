import assert from "node:assert/strict";
import test from "node:test";
import { reportUndoElementId } from "./reportUndoJump.ts";

test("paragraph and heading indexes", () => {
  assert.equal(reportUndoElementId("paragraph", "3"), "report-para-3");
  assert.equal(reportUndoElementId("heading", "2"), "rail-h-2");
  assert.equal(reportUndoElementId("list", "1"), "report-list-1");
  assert.equal(reportUndoElementId("table", "4"), "report-table-4");
});

test("insert anchors", () => {
  assert.equal(reportUndoElementId("paragraph_insert", "p:3"), "report-para-3");
  assert.equal(reportUndoElementId("paragraph_insert", "h:2"), "rail-h-2");
  assert.equal(reportUndoElementId("paragraph_insert", "eof"), null);
});

test("figures and title", () => {
  assert.equal(reportUndoElementId("chart", "cht_01"), "report-fig-cht_01");
  assert.equal(reportUndoElementId("figure", "img_02"), "report-fig-img_02");
  assert.equal(reportUndoElementId("figure_delete", "cht_01"), "report-fig-cht_01");
  assert.equal(reportUndoElementId("diagram", "dia_01"), "report-fig-dia_01");
  assert.equal(reportUndoElementId("title", "doc"), "report-doc-title");
});

test("rejects junk", () => {
  assert.equal(reportUndoElementId("paragraph", "0"), null);
  assert.equal(reportUndoElementId("paragraph", "abc"), null);
  assert.equal(reportUndoElementId("batch_recolor", "atelier"), null);
  assert.equal(reportUndoElementId("", "1"), null);
});
