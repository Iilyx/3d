import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ingestOfficeSource,
  isOfficeSourceFile,
} from "./sourceOfficeIngest.ts";

describe("isOfficeSourceFile", () => {
  it("accepts pdf/docx by name", () => {
    assert.equal(
      isOfficeSourceFile(new File([""], "a.pdf", { type: "application/pdf" })),
      true,
    );
    assert.equal(
      isOfficeSourceFile(
        new File([""], "a.docx", {
          type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }),
      ),
      true,
    );
  });

  it("rejects plain images and txt", () => {
    assert.equal(
      isOfficeSourceFile(new File([""], "p.png", { type: "image/png" })),
      false,
    );
    assert.equal(
      isOfficeSourceFile(new File([""], "n.txt", { type: "text/plain" })),
      false,
    );
  });
});

describe("ingestOfficeSource", () => {
  it("posts multipart and returns markdown", async () => {
    const file = new File(["%PDF"], "report.pdf", { type: "application/pdf" });
    const fetchImpl: typeof fetch = async (_url, init) => {
      assert.equal(init?.method, "POST");
      assert.ok(init?.body instanceof FormData);
      return new Response(
        JSON.stringify({
          markdown: "A\tB\n1\t42\n",
          text: "A\tB\n1\t42\n",
          filename: "report.pdf",
          format: "pdf",
          warnings: [],
          ingest_id: "20261113T100000Z_abcdef",
          view_mode: "document",
          preview_url: "/api/source/files/20261113T100000Z_abcdef/preview",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    };
    const out = await ingestOfficeSource(file, fetchImpl);
    assert.equal(out.markdown.includes("42"), true);
    assert.equal(out.filename, "report.pdf");
    assert.equal(out.view_mode, "document");
    assert.ok(out.preview_url?.includes("/preview"));
  });

  it("surfaces API detail on failure", async () => {
    const file = new File(["%PDF"], "scan.pdf", { type: "application/pdf" });
    const fetchImpl: typeof fetch = async () =>
      new Response(
        JSON.stringify({ detail: "В PDF нет пригодного текстового слоя" }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      );
    await assert.rejects(
      () => ingestOfficeSource(file, fetchImpl),
      /текстового слоя/,
    );
  });
});
