import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { photoLimitChip } from "./photoChip";

describe("photo chip", () => {
  it("stays hidden when nobody asked for a photo", () => {
    assert.equal(
      photoLimitChip({
        text: "Собери отчёт по областям",
        attached: 0,
        maxImages: 2,
        forbidImages: false,
        showLimits: true,
      }),
      null,
    );
  });

  it("shows when a photo is attached or requested", () => {
    assert.equal(
      photoLimitChip({
        text: "отчёт",
        attached: 2,
        maxImages: 2,
        forbidImages: false,
        showLimits: true,
      }),
      "фото ×2",
    );
    assert.equal(
      photoLimitChip({
        text: "добавь фото цеха",
        attached: 0,
        maxImages: 2,
        forbidImages: false,
        showLimits: true,
      }),
      "≤2 фото",
    );
  });
});
