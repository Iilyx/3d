/** Born-digital office/PDF → silent extract + optional PDF preview URL. */

import { formatApiDetailError } from "./runHelpers";

export const OFFICE_SOURCE_RE =
  /\.(pdf|docx|docm|doc|rtf)$/i;

export type OfficeIngestResponse = {
  markdown: string;
  text?: string;
  filename: string;
  format: string;
  warnings?: string[];
  ingest_id?: string;
  view_mode?: "text" | "document";
  preview_url?: string | null;
  original_url?: string | null;
};

export function isOfficeSourceFile(file: File): boolean {
  if (OFFICE_SOURCE_RE.test(file.name)) return true;
  const t = (file.type || "").toLowerCase();
  return (
    t === "application/pdf" ||
    t ===
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    t === "application/msword" ||
    t === "application/rtf" ||
    t === "text/rtf"
  );
}

export async function ingestOfficeSource(
  file: File,
  fetchImpl: typeof fetch = fetch,
): Promise<OfficeIngestResponse> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const res = await fetchImpl("/api/source/ingest", {
    method: "POST",
    body: fd,
  });
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    throw new Error(
      formatApiDetailError(data, res.statusText || `HTTP ${res.status}`),
    );
  }
  const markdown =
    typeof data.text === "string" && data.text.trim()
      ? data.text
      : typeof data.markdown === "string"
        ? data.markdown
        : "";
  if (!markdown.trim()) {
    throw new Error("Сервер вернул пустой Source");
  }
  return {
    markdown,
    text: markdown,
    filename:
      typeof data.filename === "string" && data.filename
        ? data.filename
        : file.name,
    format: typeof data.format === "string" ? data.format : "unknown",
    warnings: Array.isArray(data.warnings)
      ? data.warnings.filter((w): w is string => typeof w === "string")
      : [],
    ingest_id:
      typeof data.ingest_id === "string" ? data.ingest_id : undefined,
    view_mode:
      data.view_mode === "document" || data.view_mode === "text"
        ? data.view_mode
        : OFFICE_SOURCE_RE.test(file.name)
          ? "document"
          : "text",
    preview_url:
      typeof data.preview_url === "string" ? data.preview_url : null,
    original_url:
      typeof data.original_url === "string" ? data.original_url : null,
  };
}
