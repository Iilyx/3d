/** Settings drop: dashboard PNG + table PDF → markdown. No report run. */

import { formatApiDetailError } from "./runHelpers";

export type DashboardDrop = {
  png: File | null;
  pdf: File | null;
  rejected: string[];
};

export type DashboardParseResult = {
  markdown: string;
  pngMarkdown: string;
  pdfMarkdown: string;
  warnings: string[];
  pdfTableCount: number;
  pdfNumericCells: number;
};

export function emptyDashboardDrop(): DashboardDrop {
  return { png: null, pdf: null, rejected: [] };
}

export function takeDashboardFiles(
  files: File[],
  current: DashboardDrop,
): DashboardDrop {
  let png = current.png;
  let pdf = current.pdf;
  const rejected: string[] = [];
  for (const file of files) {
    const name = file.name || "";
    const type = (file.type || "").toLowerCase();
    if (type === "image/png" || /\.png$/i.test(name)) png = file;
    else if (type === "application/pdf" || /\.pdf$/i.test(name)) pdf = file;
    else rejected.push(name || "файл");
  }
  return { png, pdf, rejected };
}

export function failedDashboardSnapshot(message: string): string {
  const detail = message.trim() || "Не удалось прочитать снимок.";
  return `${detail} Снимок не приложен как фото: чисел из него нет.`;
}

export async function parseDashboard(
  png: File | null,
  pdf: File | null,
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<DashboardParseResult> {
  if (!png && !pdf) {
    throw new Error("Нужен PNG дашборда или PDF таблицы.");
  }
  const body = new FormData();
  if (png) body.append("png", png, png.name);
  if (pdf) body.append("pdf", pdf, pdf.name);
  const res = await fetchImpl("/api/dashboard/parse", {
    method: "POST",
    body,
    signal,
  });
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    throw new Error(
      formatApiDetailError(data, res.statusText || `HTTP ${res.status}`),
    );
  }
  const markdown = typeof data.markdown === "string" ? data.markdown : "";
  if (!markdown.trim()) {
    throw new Error("Сервер вернул пустой разбор.");
  }
  return {
    markdown,
    pngMarkdown: typeof data.png_markdown === "string" ? data.png_markdown : "",
    pdfMarkdown: typeof data.pdf_markdown === "string" ? data.pdf_markdown : "",
    warnings: Array.isArray(data.warnings)
      ? data.warnings.filter((item): item is string => typeof item === "string")
      : [],
    pdfTableCount:
      typeof data.pdf_table_count === "number" ? data.pdf_table_count : 0,
    pdfNumericCells:
      typeof data.pdf_numeric_cells === "number" ? data.pdf_numeric_cells : 0,
  };
}
