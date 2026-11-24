import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  forgetDeckPlace,
  recallDeckPlace,
  rememberDeckPlace,
} from "./deckPlace";

describe("deckPlace", () => {
  it("remembers the slide across a pane remount, per run", () => {
    forgetDeckPlace("run-a");
    forgetDeckPlace("run-b");
    rememberDeckPlace("run-a", {
      slideId: "s04",
      view: "slide",
      editing: true,
    });
    rememberDeckPlace("run-b", {
      slideId: "s01",
      view: "grid",
      editing: false,
    });
    assert.deepEqual(recallDeckPlace("run-a"), {
      slideId: "s04",
      view: "slide",
      editing: true,
    });
    assert.equal(recallDeckPlace("missing"), null);
    forgetDeckPlace("run-a");
    assert.equal(recallDeckPlace("run-a"), null);
    assert.equal(recallDeckPlace("run-b")?.slideId, "s01");
  });
});
