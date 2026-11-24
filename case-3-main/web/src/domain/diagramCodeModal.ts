/** Helpers for Mermaid code editing modal: cleanup, validation, headers. */

const FENCE_RE = /^```(?:mermaid)?\s*\n([\s\S]*?)\n?```\s*$/i;

export function cleanMermaidCode(raw: string): string {
  const trimmed = (raw || "").trim();
  const m = FENCE_RE.exec(trimmed);
  if (m) {
    return m[1].trim();
  }
  return trimmed;
}

const KNOWN_HEADERS: { pattern: RegExp; type: string }[] = [
  { pattern: /^(flowchart|graph)\b/i, type: "flowchart" },
  { pattern: /^sequenceDiagram\b/i, type: "sequence" },
  { pattern: /^mindmap\b/i, type: "mindmap" },
  { pattern: /^timeline\b/i, type: "timeline" },
  { pattern: /^(stateDiagram-v2|stateDiagram|state)\b/i, type: "stateDiagram" },
  { pattern: /^classDiagram\b/i, type: "classDiagram" },
  { pattern: /^erDiagram\b/i, type: "erDiagram" },
  { pattern: /^gantt\b/i, type: "gantt" },
];

export function validateMermaidHeader(code: string): {
  ok: boolean;
  type?: string;
  error?: string;
} {
  const clean = cleanMermaidCode(code);
  if (!clean) {
    return { ok: false, error: "Код схемы пуст" };
  }
  const firstLine = clean.split("\n")[0].trim();
  for (const h of KNOWN_HEADERS) {
    if (h.pattern.test(firstLine)) {
      return { ok: true, type: h.type };
    }
  }
  return {
    ok: false,
    error:
      "Не распознан тип схемы Mermaid (ожидается flowchart, sequenceDiagram, mindmap, timeline или stateDiagram)",
  };
}
