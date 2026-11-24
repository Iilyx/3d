/** Unit smoke for PNG filename + size helpers (no DOM canvas in node). */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { slugDiagramFilename } from "./downloadDiagramPng";

describe("downloadDiagramPng", () => {
  it("slugifies Cyrillic titles", () => {
    const n = slugDiagramFilename("Воронка онбординга B2B", "dia_01");
    assert.match(n, /\.png$/);
    assert.ok(n.length > 4);
  });
});
