/** Up to five labeled documents in one chat. */

import type { SourceAttachment, SourceDraft, SourcePart } from "./liberTypes";
import { SCREEN_READ_NOTE } from "./sourceCopy";

export type { SourcePart };

export type ComposerPlaque = {
  title: string;
  subtitle: string;
  fileName?: string;
};

const PACKED_DOC = /^===== (.+?) =====$/;

const MAX_DOCS = 5;

function docsTitle(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  const word =
    mod10 === 1 && mod100 !== 11
      ? "документ"
      : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)
        ? "документа"
        : "документов";
  return `${n} ${word}`;
}

function docUrls(draft: {
  viewMode?: "text" | "document";
  previewUrl?: string | null;
  originalUrl?: string | null;
  ingestId?: string;
}) {
  const isDoc = draft.viewMode === "document" || Boolean(draft.ingestId);
  const previewUrl = isDoc
    ? draft.previewUrl ||
      (draft.ingestId
        ? `/api/source/files/${encodeURIComponent(draft.ingestId)}/preview`
        : null)
    : draft.previewUrl;
  const originalUrl = isDoc
    ? draft.originalUrl ||
      (draft.ingestId
        ? `/api/source/files/${encodeURIComponent(draft.ingestId)}/original`
        : null)
    : draft.originalUrl;
  return {
    viewMode: (isDoc ? "document" : "text") as "document" | "text",
    previewUrl: previewUrl ?? null,
    originalUrl: originalUrl ?? null,
  };
}

export function mergeSourcePack(
  current: SourceDraft | null,
  next: SourceDraft,
): SourceDraft {
  const normalized = current ? ensureSourceParts(current) : null;
  const existing: SourcePart[] =
    normalized?.parts?.length
      ? normalized.parts
      : normalized?.text
        ? [
            {
              name: normalized.fileName || normalized.title || "Документ",
              text: normalized.text,
              title: normalized.title,
              ...docUrls(normalized),
              ingestId: normalized.ingestId,
              format: normalized.format,
            },
          ]
        : [];
  const name = (next.fileName || next.title || "Документ").trim() || "Документ";
  const part: SourcePart = {
    name,
    text: next.text,
    title: next.title || name,
    ...docUrls(next),
    ingestId: next.ingestId,
    format: next.format,
  };
  const idx = existing.findIndex((p) => p.name === name);
  let parts = existing.slice();
  if (idx >= 0) parts[idx] = part;
  else if (parts.length < MAX_DOCS) parts.push(part);
  else parts = [...parts.slice(1), part];
  return packParts(parts, next);
}

function splitPacked(text: string): { name: string; markdown: string }[] {
  const docs: { name: string; lines: string[] }[] = [];
  let current: { name: string; lines: string[] } | null = null;
  for (const line of (text || "").replace(/\r\n/g, "\n").split("\n")) {
    const mark = PACKED_DOC.exec(line.trim());
    if (mark) {
      current = { name: mark[1].trim(), lines: [] };
      docs.push(current);
      continue;
    }
    if (!current) {
      current = { name: "", lines: [] };
      docs.push(current);
    }
    current.lines.push(line);
  }
  return docs
    .map((doc) => ({ name: doc.name, markdown: doc.lines.join("\n").trim() }))
    .filter((doc) => doc.markdown);
}

export function sourceParts(draft: SourceDraft): SourcePart[] {
  if (draft.parts?.length) return draft.parts;
  const split = splitPacked(draft.text);
  if (split.length > 1) {
    return split.map((doc) => ({
      name: doc.name || draft.fileName || draft.title || "Документ",
      text: doc.markdown,
      title: doc.name || draft.title,
      viewMode: "text" as const,
    }));
  }
  return [
    {
      name: draft.fileName || draft.title || "Документ",
      text: draft.text,
      title: draft.title,
      viewMode: draft.viewMode,
      previewUrl: draft.previewUrl,
      originalUrl: draft.originalUrl,
      ingestId: draft.ingestId,
      format: draft.format,
    },
  ];
}

function packParts(parts: SourcePart[], seed: SourceDraft): SourceDraft {
  const text = parts
    .map((part) => `===== ${part.name} =====\n${part.text.trim()}`)
    .join("\n\n");
  const only = parts.length === 1 ? parts[0] : null;
  return {
    ...seed,
    title: only ? only.title || only.name : docsTitle(parts.length),
    text,
    fileName: only ? only.name : parts.map((part) => part.name).join(", "),
    parts,
    ...(only
      ? {}
      : {
          viewMode: "text" as const,
          previewUrl: null,
          originalUrl: null,
          ingestId: undefined,
          format: undefined,
        }),
  };
}

export function dropSourcePart(
  draft: SourceDraft,
  index: number,
): SourceDraft | null {
  const parts = sourceParts(draft).filter((_, i) => i !== index);
  if (!parts.length) return null;
  return packParts(parts, draft);
}

export function ensureSourceParts(draft: SourceDraft | null): SourceDraft | null {
  if (!draft?.text?.trim() && !draft?.parts?.length) return draft;
  if (!draft) return null;
  if (draft.parts?.length) return draft;
  const parts = sourceParts(draft).filter((part) => part.text.trim());
  if (parts.length <= 1) return draft;
  return packParts(parts, draft);
}

export function composerPlaques(draft: SourceDraft | null): ComposerPlaque[] {
  if (!draft?.text?.trim() && !draft?.parts?.length) return [];
  if (!draft) return [];
  const parts = sourceParts(draft).filter((part) => part.text.trim());
  const singleScreen = Boolean(draft.fromScreen) && parts.length === 1;
  return parts.map((part) => ({
    title: part.title || part.name,
    fileName: part.name,
    subtitle:
      part.viewMode === "document"
        ? "Документ · предпросмотр MD"
        : singleScreen
          ? SCREEN_READ_NOTE
          : `${part.text.length.toLocaleString("ru-RU")} символов`,
  }));
}

export function attachmentsFromDraft(
  draft: SourceDraft | null | undefined,
): SourceAttachment[] {
  if (!draft || (!draft.text && !draft.parts?.length)) return [];
  return sourceParts(draft)
    .filter((part) => (part.text || "").trim())
    .slice(0, MAX_DOCS)
    .map((part) => {
      const urls = docUrls(part);
      return {
        title: part.title || part.name,
        text: part.text,
        fileName: part.name,
        viewMode: urls.viewMode,
        previewUrl: urls.previewUrl,
        originalUrl: urls.originalUrl,
        ingestId: part.ingestId,
        format: part.format,
      };
    });
}

export function draftFromDocuments(
  docs: { name?: string; text?: string }[] | null | undefined,
): SourceDraft | null {
  const parts: SourcePart[] = (docs || [])
    .map((doc) => ({
      name: (doc.name || "Документ").trim() || "Документ",
      text: (doc.text || "").trim(),
    }))
    .filter((doc) => doc.text)
    .slice(0, MAX_DOCS);
  if (!parts.length) return null;
  const text = parts
    .map((part) => `===== ${part.name} =====\n${part.text}`)
    .join("\n\n");
  const title = parts.length > 1 ? docsTitle(parts.length) : parts[0].name;
  return {
    title,
    text,
    fileName: parts.map((part) => part.name).join(", "),
    parts,
    viewMode: "text",
  };
}
