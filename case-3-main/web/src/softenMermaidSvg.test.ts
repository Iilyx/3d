import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { softRxForBox } from "./softenMermaidSvg";

describe("softRxForBox", () => {
  it("returns 0 for tiny boxes", () => {
    assert.equal(softRxForBox(4, 40), 0);
    assert.equal(softRxForBox(40, 4), 0);
  });

  it("clamps to soft 8–14px range for normal nodes", () => {
    const rx = softRxForBox(120, 44);
    assert.ok(rx >= 8 && rx <= 14);
  });
});
