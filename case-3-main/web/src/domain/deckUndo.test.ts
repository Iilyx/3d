import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { slideIndexForUndoTarget } from "./deckUndo";

describe("slideIndexForUndoTarget", () => {
  const slides = [{ id: "s01" }, { id: "s02" }, { id: "s04" }];

  it("finds the slide the undone edit belonged to", () => {
    assert.equal(slideIndexForUndoTarget(slides, "s04"), 2);
  });

  it("uses the first id when a patch names several slides", () => {
    assert.equal(slideIndexForUndoTarget(slides, "s02,s04"), 1);
  });

  it("returns -1 when the target is empty or unknown", () => {
    assert.equal(slideIndexForUndoTarget(slides, ""), -1);
    assert.equal(slideIndexForUndoTarget(slides, "s99"), -1);
    assert.equal(slideIndexForUndoTarget(null, "s01"), -1);
  });

  it("skips an id that the undo removed and uses the next one", () => {
    assert.equal(slideIndexForUndoTarget(slides, "s99,s04"), 2);
  });
});
