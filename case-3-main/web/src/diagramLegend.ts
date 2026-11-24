/** Parse Mermaid classDef / :::roles into a legend for Liber Schema pane. */

import { parseMermaidFlowchart } from "./diagramIr";

export type DiagramLegendItem = {
  role: string;
  fill: string;
  label: string;
};

const ROLE_RU: Record<string, string> = {
  start: "Старт",
  process: "Процесс",
  decision: "Решение",
  ok: "Успех",
  warn: "Риск / возврат",
  data: "Данные / система",
};

const ROLE_ORDER = ["start", "process", "decision", "ok", "warn", "data"];

const CLASSDEF_FILL =
  /classDef\s+([a-zA-Z][\w-]*)\s+[^;\n]*fill:\s*(#[0-9a-fA-F]{3,8})/gi;
const NODE_CLASS = /:::\s*([a-zA-Z][\w-]*)/g;

export function parseDiagramLegend(mermaid: string): DiagramLegendItem[] {
  const text = mermaid || "";
  const fills = new Map<string, string>();
  for (const m of text.matchAll(CLASSDEF_FILL)) {
    fills.set(m[1].toLowerCase(), m[2]);
  }
  const used = new Set<string>();
  for (const m of text.matchAll(NODE_CLASS)) {
    used.add(m[1].toLowerCase());
  }
  const order: string[] = [];
  for (const role of ROLE_ORDER) {
    if (used.has(role) || fills.has(role)) order.push(role);
  }
  for (const role of fills.keys()) {
    if (!order.includes(role)) order.push(role);
  }
  return order.map((role) => ({
    role,
    fill: fills.get(role) || "#dce8df",
    label: ROLE_RU[role] || role,
  }));
}

/** Node ids that carry a Liber role (`:::role` / class). Empty if none. */
export function nodeIdsForRole(
  mermaid: string,
  role: string,
): Set<string> {
  const want = (role || "").toLowerCase();
  if (!want) return new Set();
  try {
    const ir = parseMermaidFlowchart(mermaid || "", {
      id: "leg",
      title: "",
    });
    return new Set(
      ir.nodes.filter((n) => n.kind === want).map((n) => n.id),
    );
  } catch {
    // Regex fallback when IR parse fails (legacy chains / exotic syntax).
    return nodeIdsForRoleLoose(mermaid || "", want);
  }
}

/** Scan ``:::role`` / ``class id role`` without full IR parse. */
export function nodeIdsForRoleLoose(mermaid: string, role: string): Set<string> {
  const want = (role || "").toLowerCase();
  const out = new Set<string>();
  if (!want) return out;
  const text = mermaid || "";
  for (const m of text.matchAll(
    /\b([A-Za-z][\w]*)\s*(?:\[[^\]]*\]|\([^)]*\)|\{[^}]*\}|\[\[[^\]]*\]\])?\s*:::([A-Za-z]\w*)/g,
  )) {
    if (m[2].toLowerCase() === want) out.add(m[1]);
  }
  for (const m of text.matchAll(
    /^[ \t]*class\s+([A-Za-z][\w,]*)(?:\s+(\w+)|:::([A-Za-z]\w*))\s*$/gim,
  )) {
    const kind = (m[2] || m[3] || "").toLowerCase();
    if (kind !== want) continue;
    for (const id of m[1].split(",").map((s) => s.trim()).filter(Boolean)) {
      out.add(id);
    }
  }
  return out;
}
