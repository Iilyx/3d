import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { mermaidNodeIdFromElement } from "./mermaidSvgInteract";

describe("mermaidSvgInteract", () => {
  it("extracts id from flowchart-A-0 group", () => {
    const g = {
      closest: () => ({ id: "flowchart-A-0", getAttribute: () => null }),
    } as unknown as Element;
    assert.equal(mermaidNodeIdFromElement(g), "A");
  });

  it("extracts id case-insensitively from prefix", () => {
    const g = {
      closest: () => ({ id: "flowchart-START-12", getAttribute: () => null }),
    } as unknown as Element;
    assert.equal(mermaidNodeIdFromElement(g), "START");
  });

  it("extracts id when Mermaid prefixes render id", () => {
    const g = {
      closest: () => ({
        id: "mmd__r_8__vnecil-flowchart-C-3",
        getAttribute: () => null,
      }),
    } as unknown as Element;
    assert.equal(mermaidNodeIdFromElement(g), "C");
  });

  it("returns null outside node", () => {
    const el = { closest: () => null } as unknown as Element;
    assert.equal(mermaidNodeIdFromElement(el), null);
  });
});
