import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  attachmentsFromDraft,
  composerPlaques,
  dropSourcePart,
  ensureSourceParts,
  mergeSourcePack,
} from "./sourcePack";

describe("sourcePack", () => {
  it("preserves per-document preview metadata when merging multiple files", () => {
    const pdf = mergeSourcePack(null, {
      title: "отчёт.pdf",
      text: "Выручка 120",
      fileName: "отчёт.pdf",
      viewMode: "document",
      previewUrl: "/api/source/files/ing_1/preview",
      originalUrl: "/api/source/files/ing_1/original",
      ingestId: "ing_1",
      format: "pdf",
    });
    const combined = mergeSourcePack(pdf, {
      title: "таблица.md",
      text: "| А | Б |\n| --- | --- |\n| 1 | 2 |",
      fileName: "таблица.md",
      viewMode: "text",
    });

    const attachments = attachmentsFromDraft(combined);
    assert.equal(attachments.length, 2);
    assert.equal(attachments[0].fileName, "отчёт.pdf");
    assert.equal(attachments[0].viewMode, "document");
    assert.equal(attachments[0].previewUrl, "/api/source/files/ing_1/preview");
    assert.equal(attachments[1].fileName, "таблица.md");
    assert.equal(attachments[1].viewMode, "text");
    assert.match(attachments[1].text, /\| 1 \| 2 \|/);
  });

  it("gives each attached file and each snapshot its own plaque", () => {
    const packed = mergeSourcePack(
      mergeSourcePack(null, {
        title: "Поступления.md",
        text: "# Данные дашборда\nянварь",
        fileName: "Поступления.md",
      }),
      {
        title: "Брест.md",
        text: "# Данные дашборда\nбрест",
        fileName: "Брест.md",
      },
    );
    const plaques = composerPlaques(packed);
    assert.equal(plaques.length, 2);
    assert.equal(plaques[0].title, "Поступления.md");
    assert.equal(plaques[1].title, "Брест.md");
    assert.match(plaques[0].subtitle, /символ/);

    const left = dropSourcePart(packed, 1);
    assert.equal(left?.parts?.length, 1);
    assert.equal(left?.parts?.[0].name, "Поступления.md");
    assert.doesNotMatch(left?.text || "", /Брест/);
    assert.equal(dropSourcePart(left!, 0), null);
  });

  it("splits a glued snapshot pack so one screen can be removed", () => {
    const glued = {
      title: "2 документа",
      text: "===== Январь.md =====\n# Данные дашборда\nянварь\n\n===== Брест.md =====\n# Данные дашборда\nбрест",
      fileName: "Январь.md, Брест.md",
      viewMode: "text" as const,
    };
    assert.equal(composerPlaques(glued).length, 2);
    const kept = ensureSourceParts(dropSourcePart(glued, 0));
    assert.equal(kept?.parts?.length, 1);
    assert.match(kept?.text || "", /Брест\.md/);
    assert.doesNotMatch(kept?.text || "", /Январь\.md/);
  });

  it("wraps a single draft cleanly in attachmentsFromDraft", () => {
    const single = attachmentsFromDraft({
      title: "notes.txt",
      text: "Текст заметки",
      fileName: "notes.txt",
      viewMode: "text",
    });
    assert.equal(single.length, 1);
    assert.equal(single[0].title, "notes.txt");
    assert.equal(single[0].text, "Текст заметки");
  });
});
