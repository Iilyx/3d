import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  addedSlideIndex,
  bindSlidePngs,
  fullscreenCount,
  retargetSlidePngs,
} from "./slideStrip";

const slides = [{ id: "s01" }, { id: "s02" }, { id: "s03" }];
const pngs = ["/a.png", "/b.png", "/c.png"];

describe("bindSlidePngs", () => {
  it("keeps a picture with its slide id, not the slot index", () => {
    assert.deepEqual(bindSlidePngs(slides, pngs), {
      s01: "/a.png",
      s02: "/b.png",
      s03: "/c.png",
    });
  });

  it("drops pictures when the deck and the files disagree", () => {
    assert.deepEqual(bindSlidePngs(slides, ["/a.png", "/b.png"]), {
      s01: null,
      s02: null,
      s03: null,
    });
  });
});

describe("retargetSlidePngs", () => {
  const bound = bindSlidePngs(slides, pngs);

  it("follows the slide when the order changes", () => {
    const after = [{ id: "s03" }, { id: "s01" }, { id: "s02" }];
    assert.deepEqual(retargetSlidePngs(bound, slides, after, "reorder"), {
      s03: "/c.png",
      s01: "/a.png",
      s02: "/b.png",
    });
  });

  it("gives a duplicate the same picture as its source", () => {
    const after = [
      { id: "s01" },
      { id: "s01b" },
      { id: "s02" },
      { id: "s03" },
    ];
    const next = retargetSlidePngs(bound, slides, after, "duplicate");
    assert.equal(next.s01b, "/a.png");
    assert.equal(next.s02, "/b.png");
  });

  it("leaves a brand-new slide without a stale picture", () => {
    const after = [{ id: "s01" }, { id: "sNew" }, { id: "s02" }, { id: "s03" }];
    const next = retargetSlidePngs(bound, slides, after, "insert");
    assert.equal(next.sNew, null);
    assert.equal(Object.keys(next).length, 4);
  });

  it("drops the picture of a deleted slide", () => {
    const after = [{ id: "s01" }, { id: "s03" }];
    assert.deepEqual(retargetSlidePngs(bound, slides, after, "delete"), {
      s01: "/a.png",
      s03: "/c.png",
    });
  });
});

describe("addedSlideIndex", () => {
  it("points at the copy, not the original", () => {
    const after = [
      { id: "s01" },
      { id: "s01b" },
      { id: "s02" },
      { id: "s03" },
    ];
    assert.equal(addedSlideIndex(slides, after), 1);
  });
});

describe("fullscreenCount", () => {
  it("uses the live deck when pictures are still the old file", () => {
    assert.deepEqual(fullscreenCount({ liveSlides: 4, pngs: 3 }), {
      n: 4,
      useDeck: true,
    });
  });

  it("uses pictures when there is no live deck", () => {
    assert.deepEqual(fullscreenCount({ liveSlides: 0, pngs: 3 }), {
      n: 3,
      useDeck: false,
    });
  });
});
