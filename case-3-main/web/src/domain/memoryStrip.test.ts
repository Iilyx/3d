import assert from "node:assert/strict";
import { test } from "node:test";
import { memoryStripLine } from "./memoryStrip";

test("the strip names documents and the section", () => {
  assert.equal(
    memoryStripLine({ documents: 3, section: "Введение", turn: 12 }),
    "3 документа · правили Введение",
  );
});

test("the strip drops empty parts and does not show the turn", () => {
  assert.equal(memoryStripLine({ documents: 1, section: "", turn: 0 }), "1 документ");
  assert.equal(memoryStripLine({ documents: 0, section: "", turn: 4 }), "");
  assert.equal(memoryStripLine({ documents: 0, section: "", turn: 0 }), "");
});
