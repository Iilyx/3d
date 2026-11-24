import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { paperclipAction } from "./paperclipRoute.ts";

describe("paperclipAction", () => {
  it("reads a png as dashboard data, not as a photo", () => {
    assert.equal(
      paperclipAction({ name: "shot.png", type: "image/png" }),
      "dashboard-png",
    );
  });

  it("keeps a jpeg as a photo", () => {
    assert.equal(
      paperclipAction({ name: "face.jpg", type: "image/jpeg" }),
      "photo",
    );
  });

  it("keeps a pdf on the document path", () => {
    assert.equal(
      paperclipAction({ name: "table.pdf", type: "application/pdf" }),
      "office",
    );
  });
});
