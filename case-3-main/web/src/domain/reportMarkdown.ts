/**
 * Export report preview model to clean Github Flavored Markdown.
 */

import type { PreviewBlock } from "./reportPreview";

export function reportToMarkdown(data: {
  title?: string;
  blocks?: PreviewBlock[];
}): string {
  const parts: string[] = [];
  const title = (data.title || "").trim();
  if (title) {
    parts.push(`# ${title}`);
  }

  const blocks = data.blocks || [];
  let tableIdx = 0;
  for (const b of blocks) {
    if (b.type === "heading") {
      const text = (b.text || "").trim();
      if (!text) continue;
      const level = Math.max(1, Math.min(6, (b.level ?? 1) + (title ? 1 : 0)));
      parts.push(`${"#".repeat(level)} ${text}`);
    } else if (b.type === "paragraph") {
      const text = (b.text || "").trim();
      if (text) {
        parts.push(text);
      }
    } else if (b.type === "list") {
      const items = b.items || [];
      if (items.length > 0) {
        const lines = items.map((it, idx) => {
          const itemText = (it.text || "").trim();
          return b.ordered ? `${idx + 1}. ${itemText}` : `- ${itemText}`;
        });
        parts.push(lines.join("\n"));
      }
    } else if (b.type === "table") {
      tableIdx += 1;
      const headers = b.headers || [];
      const rows = b.rows || [];
      const cap = (b.caption || "").trim();
      const capText = cap ? `*Таблица ${tableIdx}: ${cap}*` : `*Таблица ${tableIdx}*`;
      const tableLines: string[] = [capText];

      if (headers.length > 0) {
        tableLines.push(`| ${headers.map((h) => (h || "").trim()).join(" | ")} |`);
        tableLines.push(`| ${headers.map(() => "---").join(" | ")} |`);
      }
      for (const row of rows) {
        tableLines.push(`| ${row.map((cell) => (cell || "").trim()).join(" | ")} |`);
      }
      parts.push(tableLines.join("\n"));
    } else if (b.type === "figure") {
      const cap = (b.caption || b.id || "").trim();
      const url = b.url || b.id || "";
      const kindLabel = b.kind === "chart" ? "Диаграмма" : "Иллюстрация";
      parts.push(`![${kindLabel}: ${cap}](${url})`);
    }
  }

  return parts.join("\n\n").trim() + "\n";
}
