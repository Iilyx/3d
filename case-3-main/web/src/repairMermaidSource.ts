/** Soft-repair LLM Mermaid before render (mirrors case3.diagrams.sanitize). */

const CLASS_ASSIGN =
  /^([ \t]*)class(?!Def\b)[ \t]+([A-Za-z][\w,-]*)[ \t]+(.+?)\s*$/i;
const EDGE_LABEL_SPACES = /([-=.~]{2,})\s+\|([^|]+)\|\s+/g;
const SEQ_KEYWORDS =
  /^(participant|actor|note|box|create|destroy|activate|deactivate|rect|loop|alt|opt|par|critical|break|end|autonumber|links?|title|accTitle|accDescr)\b/i;
const SEQ_ARROW = /->|-->|->>|-->>|-x|--x|-\)|--\)/;
const SEQ_KEYWORD_AS =
  /^([ \t]*)(participant|actor)\s+(.+?)\s+as\s+(.+)$/i;
const AS_LINE = /^([ \t]*)(.+?)\s+as\s+(.+)$/i;

function repairSequenceDiagramLines(src: string): string {
  const lines = src.split("\n");
  if (!lines.some((l) => /^\s*sequenceDiagram\b/i.test(l))) {
    return src;
  }
  return lines
    .map((line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("%%") || SEQ_ARROW.test(trimmed)) {
        return line;
      }
      const kwMatch = SEQ_KEYWORD_AS.exec(line);
      if (kwMatch) {
        const indent = kwMatch[1] ?? "";
        const kw = kwMatch[2];
        let id = (kwMatch[3] ?? "").trim();
        const alias = (kwMatch[4] ?? "").trim();
        if (/\s/.test(id) && !(id.startsWith('"') && id.endsWith('"'))) {
          id = `"${id}"`;
        }
        return `${indent}${kw} ${id} as ${alias}`;
      }
      if (SEQ_KEYWORDS.test(trimmed)) {
        return line;
      }
      const m = AS_LINE.exec(line);
      if (m) {
        const indent = m[1] ?? "";
        let id = (m[2] ?? "").trim();
        const alias = (m[3] ?? "").trim();
        if (/\s/.test(id) && !(id.startsWith('"') && id.endsWith('"'))) {
          id = `"${id}"`;
        }
        return `${indent}participant ${id} as ${alias}`;
      }
      return line;
    })
    .join("\n");
}

function repairClassAssignLines(src: string): string {
  return src
    .split("\n")
    .flatMap((line) => {
      const m = CLASS_ASSIGN.exec(line);
      if (!m) return [line];
      const indent = m[1] ?? "";
      const rawNodes = m[2] ?? "";
      const rawNames = m[3] ?? "";
      const nodes = rawNodes
        .split(",")
        .map((n) => n.trim().replace(/^:+/, ""))
        .filter(Boolean);
      const names = rawNames
        .trim()
        .split(/\s+/)
        .map((n) => n.replace(/^:+/, ""))
        .filter(Boolean);
      if (names.length === 1 && nodes.length >= 1) {
        return [`${indent}class ${nodes.join(",")} ${names[0]}`];
      }
      if (
        names.length === nodes.length &&
        names.every((n) => /^[A-Za-z][\w-]*$/.test(n))
      ) {
        return nodes.map((node, i) => `${indent}class ${node} ${names[i]}`);
      }
      // Unmappable — drop (:::role / classDef may still style).
      return [];
    })
    .join("\n");
}

const SHORT_ROLE = /(?<=[\]\)\}>])::(?!:)(?=[A-Za-z])/g;

/** Repair broken `class A,B foo bar` lines + sequence diagram participants + edge-label spaces for live Mermaid. */
export function repairMermaidSource(source: string): string {
  let raw = (source || "").trim();
  if (!raw) return raw;
  raw = raw.replace(SHORT_ROLE, ":::");
  raw = repairClassAssignLines(raw);
  raw = repairSequenceDiagramLines(raw);
  raw = raw.replace(EDGE_LABEL_SPACES, "$1|$2| ");
  return raw;
}
