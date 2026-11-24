import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  emptyDashboardDrop,
  failedDashboardSnapshot,
  parseDashboard,
  takeDashboardFiles,
} from "./dashboardParse.ts";

describe("takeDashboardFiles", () => {
  it("keeps a png and a pdf and names the rest", () => {
    const next = takeDashboardFiles(
      [
        new File(["x"], "notes.txt", { type: "text/plain" }),
        new File(["p"], "dash.png", { type: "image/png" }),
        new File(["%PDF"], "table.pdf", { type: "application/pdf" }),
      ],
      emptyDashboardDrop(),
    );
    assert.equal(next.png?.name, "dash.png");
    assert.equal(next.pdf?.name, "table.pdf");
    assert.deepEqual(next.rejected, ["notes.txt"]);
  });

  it("replaces an earlier png when a second one is dropped", () => {
    const first = takeDashboardFiles(
      [new File(["a"], "a.png", { type: "image/png" })],
      emptyDashboardDrop(),
    );
    const next = takeDashboardFiles(
      [new File(["b"], "b.png", { type: "image/png" })],
      first,
    );
    assert.equal(next.png?.name, "b.png");
    assert.equal(next.pdf, null);
  });
});

describe("parseDashboard", () => {
  it("posts both files and returns the markdown", async () => {
    const png = new File(["png"], "dash.png", { type: "image/png" });
    const pdf = new File(["%PDF"], "table.pdf", { type: "application/pdf" });
    const fetchImpl: typeof fetch = async (url, init) => {
      assert.equal(String(url), "/api/dashboard/parse");
      assert.equal(init?.method, "POST");
      const body = init?.body;
      assert.ok(body instanceof FormData);
      assert.equal((body.get("png") as File).name, "dash.png");
      assert.equal((body.get("pdf") as File).name, "table.pdf");
      return new Response(
        JSON.stringify({
          markdown: "# Данные дашборда\n\n| НДС | 10 |",
          png_markdown: "Брест",
          pdf_markdown: "| НДС | 10 |",
          warnings: [],
          pdf_table_count: 1,
          pdf_numeric_cells: 3,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    };
    const result = await parseDashboard(png, pdf, fetchImpl);
    assert.match(result.markdown, /НДС/);
    assert.equal(result.pdfTableCount, 1);
    assert.equal(result.pdfNumericCells, 3);
  });

  it("surfaces the server detail", async () => {
    const pdf = new File(["%PDF"], "scan.pdf", { type: "application/pdf" });
    const fetchImpl: typeof fetch = async () =>
      new Response(JSON.stringify({ detail: "В PDF нет текстового слоя." }), {
        status: 422,
        headers: { "content-type": "application/json" },
      });
    await assert.rejects(
      () => parseDashboard(null, pdf, fetchImpl),
      /текстового слоя/,
    );
  });
});

describe("failedDashboardSnapshot", () => {
  it("keeps a failed screen reading out of the photo tray", () => {
    const toast = failedDashboardSnapshot("Снимок не разобран.");
    assert.match(toast, /Снимок не разобран/);
    assert.match(toast, /не приложен как фото/);
  });
});
