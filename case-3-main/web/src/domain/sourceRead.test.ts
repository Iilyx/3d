import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  docsForSourceModal,
  resolveOriginalDownload,
  sourceModalEyebrow,
} from "./sourceRead";

describe("sourceRead", () => {
  it("expands multi-part SourceDraft into individual modal tabs", () => {
    const docs = docsForSourceModal({
      title: "2 документа",
      text: "===== a.pdf =====\nРаз\n\n===== b.md =====\nДва",
      fileName: "a.pdf, b.md",
      parts: [
        {
          name: "a.pdf",
          text: "Раз",
          viewMode: "document",
          originalUrl: "/api/source/files/ing_1/original",
          format: "pdf",
        },
        {
          name: "b.md",
          text: "Два",
          viewMode: "text",
          originalUrl: "/api/source/files/ing_2/original",
          format: "md",
        },
      ],
    });
    assert.equal(docs.length, 2);
    assert.equal(docs[0].fileName, "a.pdf");
    assert.equal(docs[0].originalUrl, "/api/source/files/ing_1/original");
    assert.equal(docs[1].fileName, "b.md");
  });

  it("uses originalUrl when available and falls back to markdown blob otherwise", () => {
    assert.deepEqual(
      resolveOriginalDownload({
        title: "отчёт.pdf",
        fileName: "отчёт.pdf",
        text: "# Отчёт",
        originalUrl: "/api/source/files/ing_1/original",
      }),
      {
        kind: "url",
        href: "/api/source/files/ing_1/original",
        fileName: "отчёт.pdf",
      },
    );

    assert.deepEqual(
      resolveOriginalDownload({
        title: "Вставленный текст",
        text: "Строка 1",
      }),
      {
        kind: "blob",
        text: "Строка 1",
        fileName: "Вставленный текст.md",
      },
    );
  });

  it("formats crisp modal eyebrow from format or extension", () => {
    assert.equal(
      sourceModalEyebrow({ title: "x", fileName: "a.pdf", format: "pdf", text: "" }),
      "PDF · предпросмотр MD",
    );
    assert.equal(
      sourceModalEyebrow({ title: "x", fileName: "readme.md", text: "" }),
      "MD · предпросмотр",
    );
  });
});
