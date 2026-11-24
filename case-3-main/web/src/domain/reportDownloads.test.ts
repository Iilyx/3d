import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { reportDownloadLinks } from "./reportDownloads";

describe("reportDownloadLinks", () => {
  it("returns PDF then DOCX when both exist", () => {
    const links = reportDownloadLinks({
      pdf: "/api/runs/r1/files/source.pdf",
      docx: "/api/runs/r1/files/source.docx",
      pptx: "/api/runs/r1/files/deck.pptx",
    });
    assert.deepEqual(
      links.map((l) => l.kind),
      ["pdf", "docx"],
    );
    assert.equal(links[1]?.label, "DOCX");
  });

  it("returns empty when surface disabled", () => {
    assert.deepEqual(
      reportDownloadLinks(
        { pdf: "/x.pdf", docx: "/x.docx" },
        { enabled: false },
      ),
      [],
    );
  });

  it("omits missing formats", () => {
    assert.deepEqual(
      reportDownloadLinks({ pdf: "/x.pdf" }).map((l) => l.kind),
      ["pdf"],
    );
    assert.deepEqual(
      reportDownloadLinks({ docx: "/x.docx" }).map((l) => l.kind),
      ["docx"],
    );
  });

  it("marks links stale during deferred rebuild", () => {
    const links = reportDownloadLinks(
      { pdf: "/x.pdf", docx: "/x.docx" },
      { stale: true },
    );
    assert.equal(links[0]?.stale, true);
    assert.equal(links[0]?.href, "");
    assert.match(links[0]?.label || "", /устарел/i);
    assert.match(links[0]?.title || "", /Готово/i);
  });
});
