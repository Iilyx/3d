/** Safe-ish markdown → HTML (escape first). Shared by Source + chat summary. */

import { memo } from "react";

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Light markdown for Liber chat / Source pane. */
function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isTableRow(line: string): boolean {
  return /^\s*\|.+\|\s*$/.test(line);
}

function isTableSep(line: string): boolean {
  return /^\s*\|[\s:|-]+\|\s*$/.test(line) && line.includes("-");
}

function renderTables(src: string): string {
  const lines = src.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    if (
      isTableRow(lines[i]) &&
      i + 1 < lines.length &&
      isTableSep(lines[i + 1])
    ) {
      const head = splitTableRow(lines[i]);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && isTableRow(lines[i])) {
        rows.push(splitTableRow(lines[i]));
        i += 1;
      }
      const th = head.map((cell) => `<th>${cell}</th>`).join("");
      const body = rows
        .map((row) => {
          const cells = head.map((_, idx) => `<td>${row[idx] || ""}</td>`).join("");
          return `<tr>${cells}</tr>`;
        })
        .join("");
      out.push(
        `<div class="msg-table-wrap"><table class="msg-table"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`,
      );
      continue;
    }
    out.push(lines[i]);
    i += 1;
  }
  return out.join("\n");
}

/** A "2. Вывод" glued to the previous sentence becomes its own paragraph. */
export function spaceAnswer(raw: string): string {
  let text = (raw || "").replace(/\r\n/g, "\n");
  text = text.replace(
    /([.!?…:%»"])[ \t]+(\d{1,2})\.\s+(?=\p{L})/gu,
    "$1\n\n$2. ",
  );
  text = text.replace(/([^\n])\n(?=\d{1,2}\.\s+\p{L})/gu, "$1\n\n");
  return text;
}

/** Stabilize incomplete trailing markdown constructs during live streaming. */
export function stabilizeStreamingMd(raw: string): string {
  let text = (raw || "").replace(/\r\n/g, "\n");
  // Avoid flashing bare heading hashes ("## ") before heading text arrives.
  text = text.replace(/(?:^|\n)#{1,3}[ \t]*$/, "");
  const fenceCount = (text.match(/```/g) || []).length;
  if (fenceCount % 2 === 1) {
    return `${text}\n\`\`\``;
  }
  // Hide incomplete trailing pipe rows or unconfirmed header lines so raw pipes don't flicker as text.
  const lines = text.split("\n");
  while (lines.length > 0) {
    const last = lines[lines.length - 1];
    const prev = lines.length >= 2 ? lines[lines.length - 2] : "";
    if (/^\s*\|/.test(last) && !isTableRow(last)) {
      lines.pop();
      continue;
    }
    if (isTableRow(last) && !isTableSep(last) && !isTableSep(prev) && !isTableRow(prev)) {
      lines.pop();
      continue;
    }
    break;
  }
  text = lines.join("\n");
  // Close dangling bold/inline-code in the active trailing paragraph so lines don't snap later.
  const lastBreak = text.lastIndexOf("\n\n");
  const head = lastBreak >= 0 ? text.slice(0, lastBreak + 2) : "";
  let tail = lastBreak >= 0 ? text.slice(lastBreak + 2) : text;
  if (tail.endsWith("**")) {
    // Wait for content after opening "**"
    const boldMarkers = (tail.match(/\*\*/g) || []).length;
    if (boldMarkers % 2 === 1) {
      tail = tail.slice(0, -2);
    }
  } else {
    if (tail.endsWith("*") && !tail.endsWith("**")) {
      const prevBold = (tail.slice(0, -1).match(/\*\*/g) || []).length;
      if (prevBold % 2 === 0) {
        tail = tail.slice(0, -1);
      } else {
        tail = `${tail}*`;
      }
    }
    const boldMarkers = (tail.match(/\*\*/g) || []).length;
    if (boldMarkers % 2 === 1) {
      tail = `${tail}**`;
    }
  }
  return `${head}${tail}`.trimEnd();
}

function highlightQueryHtml(html: string, query: string): string {
  if (!query.trim()) return html;
  const q = escapeHtml(query.trim());
  const re = new RegExp(
    `(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
    "gi",
  );
  // Highlight text nodes between tags only so attribute/tag names are never mutated.
  return html
    .split(/(<[^>]+>)/g)
    .map((seg) =>
      seg.startsWith("<") ? seg : seg.replace(re, '<mark class="src-hit">$1</mark>'),
    )
    .join("");
}

export function renderLightMdBlocks(raw: string, query = ""): string[] {
  let s = escapeHtml(spaceAnswer(raw));
  const codePlaceholders: string[] = [];
  s = s.replace(/```([\s\S]*?)```/g, (_m, code: string) => {
    const idx = codePlaceholders.length;
    codePlaceholders.push(`<pre class="src-code"><code>${code.trim()}</code></pre>`);
    return `\n\n@@CODEBLOCK${idx}@@\n\n`;
  });
  s = s.replace(/^### (.+)$/gm, '<h4 class="src-h">$1</h4>');
  s = s.replace(/^## (.+)$/gm, '<h3 class="src-h">$1</h3>');
  s = s.replace(/^# (.+)$/gm, '<h2 class="src-h">$1</h2>');
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/_([^_\n]+)_/g, "<em>$1</em>");
  s = renderTables(s);
  s = s.replace(/^- (.+)$/gm, '<li class="src-li">$1</li>');
  s = s.replace(/(?:<li class="src-li">.*<\/li>\n?)+/g, (block) => {
    return `<ul class="src-ul">${block}</ul>`;
  });

  const blocks = s
    .split(/\n{2,}/)
    .map((chunk) => {
      const trimmed = chunk.trim();
      if (!trimmed) return "";
      const codeMatch = trimmed.match(/^@@CODEBLOCK(\d+)@@$/);
      if (codeMatch) {
        return codePlaceholders[Number(codeMatch[1])] || "";
      }
      if (/^<(h[2-4]|ul|pre|table|div\s+class="msg-table-wrap")/.test(trimmed)) {
        return chunk;
      }
      if (chunk.includes('<div class="msg-table-wrap">')) {
        return chunk
          .split(/(<div class="msg-table-wrap"><table[\s\S]*?<\/table><\/div>)/)
          .map((part) => {
            if (part.startsWith('<div class="msg-table-wrap">')) return part;
            const partTrimmed = part.trim();
            if (!partTrimmed) return "";
            if (/^<(h[2-4]|ul|pre)/.test(partTrimmed)) return part;
            return `<p class="src-p">${part.replace(/\n/g, "<br/>")}</p>`;
          })
          .join("");
      }
      return `<p class="src-p">${chunk.replace(/\n/g, "<br/>")}</p>`;
    })
    .filter(Boolean);

  if (!query.trim()) return blocks;
  return blocks.map((b) => highlightQueryHtml(b, query));
}

export function renderLightMd(raw: string, query = ""): string {
  return renderLightMdBlocks(raw, query).join("");
}

const MdBlock = memo(function MdBlock({ html }: { html: string }) {
  return (
    <div
      className="msg-md-block"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
});

export function MsgMarkdown({
  text,
  streaming = false,
  className = "",
}: {
  text: string;
  streaming?: boolean;
  className?: string;
}) {
  const source = streaming ? stabilizeStreamingMd(text || "") : text || "";
  const blocks = renderLightMdBlocks(source);
  return (
    <div
      className={`msg-body msg-md${streaming ? " is-streaming" : ""}${className ? ` ${className}` : ""}`}
    >
      {blocks.map((html, idx) => (
        <MdBlock key={idx} html={html} />
      ))}
    </div>
  );
}
