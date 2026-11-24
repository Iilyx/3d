import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { deckDownloadLinks } from "./deckDownloads";

describe("deckDownloadLinks", () => {
  it("returns PPTX then deck PDF", () => {
    const links = deckDownloadLinks({
      pptx: "/p.pptx",
      deck_pdf: "/d.pdf",
      pdf: "/report.pdf",
    });
    assert.deepEqual(
      links.map((l) => l.kind),
      ["pptx", "deck_pdf"],
    );
    assert.equal(links[1]?.label, "PDF");
  });

  it("blocks the file while the screen is ahead of it", () => {
    const links = deckDownloadLinks(
      { pptx: "/p.pptx", deck_pdf: "/d.pdf" },
      { blocked: true },
    );
    assert.equal(links.length, 2);
    for (const link of links) {
      assert.equal(link.disabled, true);
      assert.equal(link.href, "");
      assert.equal(link.label, "Сначала Готово");
      assert.match(link.title || "", /Готово/);
    }
  });
});
