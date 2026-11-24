/** Helpers for full-screen Markdown document preview modal + original download. */

import type { SourceAttachment, SourceDraft } from "./liberTypes";
import { attachmentsFromDraft } from "./sourcePack";

export type OriginalDownloadTarget =
  | { kind: "url"; href: string; fileName: string }
  | { kind: "blob"; text: string; fileName: string };

export function docsForSourceModal(
  source: SourceDraft | SourceAttachment,
): SourceAttachment[] {
  if ("parts" in source && source.parts?.length) {
    return attachmentsFromDraft(source);
  }
  const originalUrl =
    source.originalUrl ||
    (source.ingestId
      ? `/api/source/files/${encodeURIComponent(source.ingestId)}/original`
      : null);
  return [
    {
      title: source.title,
      text: source.text,
      fileName: source.fileName,
      viewMode: source.viewMode,
      previewUrl: source.previewUrl,
      originalUrl,
      ingestId: source.ingestId,
      format: source.format,
    },
  ];
}

function safeDownloadName(raw: string | undefined, fallbackExt = ".md"): string {
  const base = (raw || "document").trim() || "document";
  if (/\.[a-z0-9]{1,8}$/i.test(base)) return base;
  return `${base}${fallbackExt}`;
}

export function resolveOriginalDownload(
  doc: Pick<SourceAttachment, "title" | "fileName" | "text" | "originalUrl" | "ingestId">,
): OriginalDownloadTarget {
  const href =
    (doc.originalUrl || "").trim() ||
    (doc.ingestId
      ? `/api/source/files/${encodeURIComponent(doc.ingestId)}/original`
      : "");
  const name = (doc.fileName || doc.title || "document").trim() || "document";
  if (href) {
    return { kind: "url", href, fileName: name };
  }
  return {
    kind: "blob",
    text: doc.text || "",
    fileName: safeDownloadName(name, ".md"),
  };
}

export function sourceModalEyebrow(
  doc: Pick<SourceAttachment, "title" | "fileName" | "format">,
): string {
  const rawFmt = (doc.format || "").trim().toLowerCase();
  const extMatch = (doc.fileName || doc.title || "").match(/\.([a-z0-9]{1,8})$/i);
  const ext = rawFmt || (extMatch ? extMatch[1].toLowerCase() : "");
  if (ext === "md" || ext === "markdown") return "MD · предпросмотр";
  if (ext) return `${ext.toUpperCase()} · предпросмотр MD`;
  return "Документ · предпросмотр MD";
}
