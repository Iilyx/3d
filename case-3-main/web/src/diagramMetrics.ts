/** Extract Source-style numeric annotations from Mermaid flowchart labels. */

import { canParseFlowchart, parseMermaidFlowchart } from "./diagramIr";

export type DiagramMetric = {
  entity: string;
  metric: string;
  nodeId?: string;
  /** true when metric came from an edge label (%, отвал). */
  fromEdge?: boolean;
};

/** Short label for chips: drop role noise («SDR ·», «SE ·»). */
export function formatMetricChip(m: DiagramMetric): {
  entity: string;
  metric: string;
} {
  let entity = (m.entity || "")
    .replace(/\b(SDR|SE|AE|CS|Legal|ICP)\b/gi, "")
    .replace(/\s*[·|]\s*/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (entity.length > 28) entity = `${entity.slice(0, 26)}…`;
  let metric = (m.metric || "").replace(/\s+/g, " ").trim();
  if (m.fromEdge && /^\d/.test(metric) && !/%/.test(metric)) {
    /* keep as-is */
  }
  return { entity: entity || "—", metric };
}

/** Digit run with optional thin/nbsp thousands and a short unit/% . */
const METRIC_TAIL =
  /(?:^|[\s·|])((?:\d[\d\s\u00a0\u202f]*)+(?:[.,]\d+)?\s*(?:%|шт\.?|₽|руб\.?|тыс\.?|млн\.?|€|\$|заявок?|ед\.?)?)\s*$/iu;

function cleanLabel(raw: string): string {
  let s = (raw || "").trim();
  // Mermaid often wraps stadium/rect labels as ["…"] or ("…")
  const wrapped = s.match(/^\(\["([\s\S]*)"\]\)$|^\["([\s\S]*)"\]$|^"([\s\S]*)"$|^'([\s\S]*)'$/);
  if (wrapped) {
    s = wrapped[1] ?? wrapped[2] ?? wrapped[3] ?? wrapped[4] ?? s;
  } else {
    s = s.replace(/^["']+|["']+$/g, "");
  }
  return s.replace(/\\n/g, "\n").replace(/<br\s*\/?>/gi, "\n").trim();
}

function splitAnnotated(label: string): { entity: string; metric: string } | null {
  const text = cleanLabel(label);
  if (!text) return null;

  // Two-line / · / | separators (prefer last segment as metric)
  const parts = text
    .split(/\n|(?:\s*[·|]\s*)/)
    .map((p) => p.replace(/\s+/g, " ").trim())
    .filter(Boolean);
  if (parts.length >= 2) {
    const metric = parts[parts.length - 1];
    const entity = parts.slice(0, -1).join(" · ");
    if (METRIC_TAIL.test(` ${metric}`) || /\d/.test(metric)) {
      METRIC_TAIL.lastIndex = 0;
      if (/\d/.test(metric)) {
        return { entity: entity || metric, metric };
      }
    }
  }

  // Single line ending with a metric
  const m = text.match(METRIC_TAIL);
  if (m && /\d/.test(m[1])) {
    const metric = m[1].trim();
    const entity = text.slice(0, m.index).replace(/[·|\s]+$/u, "").trim();
    if (entity && entity !== metric) {
      return { entity, metric };
    }
  }
  return null;
}

function dedupeKey(m: DiagramMetric): string {
  return `${m.entity}::${m.metric}`.toLowerCase();
}

/**
 * Pull entity→metric pairs from flowchart node/edge labels.
 * Empty when the diagram is structure-only or not a parseable flowchart.
 */
export function parseDiagramMetrics(mermaid: string): DiagramMetric[] {
  const src = mermaid || "";
  if (!canParseFlowchart(src)) return [];
  let ir;
  try {
    ir = parseMermaidFlowchart(src, { id: "m", title: "" });
  } catch {
    return [];
  }

  const out: DiagramMetric[] = [];
  const seen = new Set<string>();

  const push = (raw: string, nodeId?: string) => {
    const hit = splitAnnotated(raw);
    if (!hit) return;
    const item: DiagramMetric = {
      entity: hit.entity,
      metric: hit.metric.replace(/\s+/g, " ").trim(),
      nodeId,
    };
    const k = dedupeKey(item);
    if (seen.has(k)) return;
    seen.add(k);
    out.push(item);
  };

  for (const n of ir.nodes) {
    push(n.label, n.id);
  }
  const nodeOnly = out.length;
  for (const e of ir.edges) {
    if (e.label) push(e.label);
  }
  for (let i = nodeOnly; i < out.length; i++) {
    out[i].fromEdge = true;
  }
  return out;
}
