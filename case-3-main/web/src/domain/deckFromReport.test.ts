import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { reportCanMakeDeck } from "./deckFromReport";

describe("reportCanMakeDeck", () => {
  it("offers a presentation on a finished report", () => {
    assert.equal(
      reportCanMakeDeck({
        outputMode: "report",
        pdfUrl: "/api/runs/a/download/source.pdf",
        slidesStatus: null,
      }),
      true,
    );
  });

  it("stays quiet while a deck is already running or ready", () => {
    assert.equal(
      reportCanMakeDeck({
        outputMode: "report",
        pdfUrl: "/pdf",
        slidesStatus: "running",
      }),
      false,
    );
    assert.equal(
      reportCanMakeDeck({
        outputMode: "presentation",
        pdfUrl: "/pdf",
        slidesStatus: null,
      }),
      false,
    );
    assert.equal(
      reportCanMakeDeck({
        outputMode: "report",
        pdfUrl: null,
        slidesStatus: null,
      }),
      false,
    );
  });
});
