/** Liber Diagram IR ↔ Mermaid flowchart (subset for visual editor). */

export type DiaKind =
  | "start"
  | "process"
  | "decision"
  | "ok"
  | "warn"
  | "data";

export type DiaNode = {
  id: string;
  label: string;
  kind: DiaKind;
};

export type DiaEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
};

export type DiagramIR = {
  id: string;
  title: string;
  direction: "TD" | "LR";
  nodes: DiaNode[];
  edges: DiaEdge[];
  /** Optional classDef colors captured from source Mermaid. */
  colors?: Partial<Record<DiaKind, RoleColor>>;
};

export type RoleColor = { fill: string; stroke: string };

const KINDS = new Set<string>([
  "start",
  "process",
  "decision",
  "ok",
  "warn",
  "data",
]);

const DEFAULT_COLORS: Record<DiaKind, RoleColor> = {
  start: { fill: "#dce8df", stroke: "#6b8f76" },
  process: { fill: "#eef3ef", stroke: "#5a7a64" },
  decision: { fill: "#f3e6c8", stroke: "#b8893a" },
  ok: { fill: "#cfe6d4", stroke: "#3d7a4a" },
  warn: { fill: "#f0ddd8", stroke: "#a85a4a" },
  data: { fill: "#d9e6f0", stroke: "#4a6f8c" },
};

/** Stadium ``([…])`` before plain ``(…)`` / ``[…]``. */
const SHAPE = /(\[\[[^\]]*\]\]|\(\[[^\]]*\]\)|\[[^\]]*\]|\([^)]*\)|\{[^}]*\})/;
const CLASS_MARK = /:::[A-Za-z]\w*/;
const CLASSDEF_RE =
  /^classDef\s+([A-Za-z]\w*)\s+.*fill:\s*(#[0-9a-fA-F]{3,8}).*stroke:\s*(#[0-9a-fA-F]{3,8})/i;
/** Include ``<-->`` — LLM org charts often use bidirectional edges. */
const ARROW_RE = /<-->|-->|---|-\.->/g;
const BR_TAG = /<br\s*\/?>/gi;

function stripQuotes(s: string): string {
  let t = (s || "").trim();
  while (
    (t.startsWith('"') && t.endsWith('"') && t.length >= 2) ||
    (t.startsWith("'") && t.endsWith("'") && t.length >= 2)
  ) {
    t = t.slice(1, -1).trim();
  }
  return t;
}

function parseShape(
  raw: string | undefined,
): { label: string; kindHint?: DiaKind } {
  if (!raw) return { label: "" };
  let label = raw;
  let kindHint: DiaKind | undefined;
  if (raw.startsWith("[[") && raw.endsWith("]]")) {
    label = raw.slice(2, -2);
    kindHint = "data";
  } else if (raw.startsWith("([") && raw.endsWith("])")) {
    label = raw.slice(2, -2);
    kindHint = "process";
  } else if (raw.startsWith("{") && raw.endsWith("}")) {
    label = raw.slice(1, -1);
    kindHint = "decision";
  } else if (raw.startsWith("(") && raw.endsWith(")")) {
    label = raw.slice(1, -1);
    kindHint = "ok";
  } else if (raw.startsWith("[") && raw.endsWith("]")) {
    label = raw.slice(1, -1);
  }
  return { label: stripQuotes(label), kindHint };
}

function asKind(raw: string | undefined, hint?: DiaKind): DiaKind {
  const k = (raw || "").toLowerCase();
  if (KINDS.has(k)) return k as DiaKind;
  return hint || "process";
}

export function canParseFlowchart(mermaid: string): boolean {
  const first = (mermaid || "").trim().split(/\r?\n/)[0] || "";
  return /^\s*flowchart\s+/i.test(first) || /^\s*graph\s+/i.test(first);
}

/** True when visual editor can open without risking silent data loss. */
export function isSupportedFlowchartSubset(mermaid: string): boolean {
  if (!canParseFlowchart(mermaid)) return false;
  const lines = (mermaid || "").replace(/\r\n/g, "\n").split("\n");
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("%%")) continue;
    // subgraph/end are flattened by parseMermaidFlowchart — OK for visual edit.
    if (/^(subgraph|end)\b/i.test(line)) continue;
    if (/^(click|linkStyle|style)\b/i.test(line)) return false;
    const arrows = line.match(ARROW_RE);
    if (arrows && arrows.length >= 2) return false;
  }
  try {
    parseMermaidFlowchart(mermaid, { id: "tmp", title: "tmp" });
    return true;
  } catch {
    return false;
  }
}

function cleanLabel(label: string): string {
  let s = stripQuotes(label || "");
  s = s
    .replace(BR_TAG, "\n")
    .replace(/\s+\n/g, "\n")
    .replace(/\n\s+/g, "\n")
    .trim();
  return stripQuotes(s);
}

function splitEdgeLine(line: string): {
  left: string;
  midLabel?: string;
  right: string;
} | null {
  const labeled = line.match(
    /^(.+?)\s*(<-->|-->|---|-\.->)\s*\|([^|]*)\|\s*(.+)$/,
  );
  if (labeled) {
    return {
      left: labeled[1].trim(),
      midLabel: labeled[3].trim(),
      right: labeled[4].trim(),
    };
  }
  const plain = line.match(/^(.+?)\s*(<-->|-->|---|-\.->)\s*(.+)$/);
  if (!plain) return null;
  return { left: plain[1].trim(), right: plain[3].trim() };
}

function parseEndpoint(chunk: string): {
  id: string;
  label: string;
  kind: DiaKind;
} | null {
  const idM = chunk.trim().match(/^([A-Za-z][\w]*)/);
  if (!idM) return null;
  const id = idM[1];
  let rest = chunk.trim().slice(id.length).trim();
  let shapeRaw = "";
  const sm = rest.match(
    /^(\[\[[^\]]*\]\]|\(\[[^\]]*\]\)|\[[^\]]*\]|\([^)]*\)|\{[^}]*\})/,
  );
  if (sm) {
    shapeRaw = sm[1];
    rest = rest.slice(sm[1].length).trim();
  }
  let className = "";
  const cm = rest.match(/^:::([A-Za-z]\w*)/);
  if (cm) className = cm[1];
  const shape = parseShape(shapeRaw);
  return {
    id,
    label: cleanLabel(shape.label),
    kind: asKind(className, shape.kindHint),
  };
}

export function parseMermaidFlowchart(
  mermaid: string,
  meta: { id: string; title: string },
): DiagramIR {
  if (!canParseFlowchart(mermaid)) {
    throw new Error("Поддерживаются только flowchart-схемы");
  }
  const allLines = (mermaid || "").replace(/\r\n/g, "\n").split("\n");
  const colors: Partial<Record<DiaKind, RoleColor>> = {};
  for (const raw of allLines) {
    const m = CLASSDEF_RE.exec(raw.trim());
    if (!m) continue;
    const kind = asKind(m[1]);
    if (KINDS.has(kind)) {
      colors[kind] = { fill: m[2], stroke: m[3] };
    }
  }

  const lines = allLines
    .map((l) => l.trim())
    .filter(
      (l) =>
        l &&
        !l.startsWith("%%") &&
        !/^classDef\b/i.test(l) &&
        !/^style\b/i.test(l),
    );

  let direction: "TD" | "LR" = "TD";
  const nodes = new Map<string, DiaNode>();
  const edges: DiaEdge[] = [];
  let edgeSeq = 0;

  const ensure = (
    id: string,
    label: string,
    kind: DiaKind,
    overwriteLabel: boolean,
  ) => {
    const prev = nodes.get(id);
    if (!prev) {
      nodes.set(id, { id, label: label || id, kind });
      return;
    }
    if (overwriteLabel && label) prev.label = label;
    if (kind !== "process") prev.kind = kind;
  };

  for (const line of lines) {
    // Flatten: keep nodes/edges inside subgraphs; drop wrappers (visual editor
    // has no group UI yet — Win desk 091443 org chart).
    if (/^(subgraph|end)\b/i.test(line)) {
      continue;
    }
    const arrows = line.match(ARROW_RE);
    if (arrows && arrows.length >= 2) {
      throw new Error("Цепочки A-->B-->C пока не поддерживаются — упростите схему");
    }

    const hm = line.match(/^(?:flowchart|graph)\s+(TD|LR|TB|RL)\b/i);
    if (hm) {
      const d = hm[1].toUpperCase();
      direction = d === "LR" || d === "RL" ? "LR" : "TD";
      continue;
    }
    // `class A,B process` OR LLM leak `class A,B:::process`
    const classLine = line.match(
      /^class\s+([A-Za-z][\w,]*)(?:\s+(\w+)|:::([A-Za-z]\w*))\s*$/i,
    );
    if (classLine) {
      const kind = asKind(classLine[2] || classLine[3]);
      for (const id of classLine[1]
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)) {
        ensure(id, "", kind, false);
        const n = nodes.get(id);
        if (n) n.kind = kind;
      }
      continue;
    }

    if (/(<-->|-->|---|-\.->)/.test(line)) {
      const parts = splitEdgeLine(line);
      if (!parts) continue;
      const s = parseEndpoint(parts.left);
      const t = parseEndpoint(parts.right);
      if (!s || !t) continue;
      ensure(s.id, s.label, s.kind, Boolean(s.label));
      ensure(t.id, t.label, t.kind, Boolean(t.label));
      edges.push({
        id: `e${++edgeSeq}`,
        source: s.id,
        target: t.id,
        label: parts.midLabel || undefined,
      });
      continue;
    }

    const alone = parseEndpoint(line);
    if (alone && (SHAPE.test(line) || CLASS_MARK.test(line))) {
      ensure(alone.id, alone.label, alone.kind, true);
    }
  }

  if (nodes.size === 0) {
    throw new Error("Не удалось разобрать блоки схемы");
  }

  return {
    id: meta.id,
    title: meta.title,
    direction,
    nodes: [...nodes.values()],
    edges,
    colors: Object.keys(colors).length ? colors : undefined,
  };
}

export function serializeMermaidFlowchart(
  ir: DiagramIR,
  colors?: Partial<Record<DiaKind, RoleColor>>,
): string {
  const dir = ir.direction === "LR" ? "LR" : "TD";
  const lines: string[] = [`flowchart ${dir}`];
  const used = new Set<DiaKind>();

  const shape = (n: DiaNode): string => {
    used.add(n.kind);
    const text =
      (n.label || n.id).replace(/[\[\]{}|]/g, " ").replace(/\s+/g, " ").trim() ||
      n.id;
    if (n.kind === "decision") return `${n.id}{${text}}:::${n.kind}`;
    // Pill / rounded — closer to React Flow editor than sharp ``[…]``.
    if (n.kind === "ok") return `${n.id}([${text}]):::${n.kind}`;
    if (n.kind === "data") return `${n.id}[[${text}]]:::${n.kind}`;
    if (n.kind === "start" || n.kind === "process" || n.kind === "warn") {
      return `${n.id}(${text}):::${n.kind}`;
    }
    return `${n.id}(${text}):::${n.kind}`;
  };

  for (const n of ir.nodes) {
    if (!ir.edges.some((e) => e.source === n.id || e.target === n.id)) {
      lines.push(`  ${shape(n)}`);
    }
  }

  for (const e of ir.edges) {
    const s = ir.nodes.find((n) => n.id === e.source);
    const t = ir.nodes.find((n) => n.id === e.target);
    if (!s || !t) continue;
    const mid = e.label ? ` -->|${e.label.replace(/\|/g, "")}| ` : " --> ";
    lines.push(`  ${shape(s)}${mid}${shape(t)}`);
  }

  for (const n of ir.nodes) used.add(n.kind);

  const palette = {
    ...DEFAULT_COLORS,
    ...(ir.colors || {}),
    ...(colors || {}),
  };
  for (const kind of [
    "start",
    "process",
    "decision",
    "ok",
    "warn",
    "data",
  ] as DiaKind[]) {
    if (!used.has(kind)) continue;
    const c = palette[kind];
    lines.push(
      `  classDef ${kind} fill:${c.fill},stroke:${c.stroke},color:#1a2e22`,
    );
  }

  return lines.join("\n") + "\n";
}

/** Structural equality for no-op save (ignore node order, edge ids, colors). */
export function diagramStructureEqual(a: DiagramIR, b: DiagramIR): boolean {
  if (a.direction !== b.direction) return false;
  if (a.nodes.length !== b.nodes.length || a.edges.length !== b.edges.length) {
    return false;
  }
  const nodesA = Object.fromEntries(
    a.nodes.map((n) => [n.id, { label: n.label.trim(), kind: n.kind }]),
  );
  const nodesB = Object.fromEntries(
    b.nodes.map((n) => [n.id, { label: n.label.trim(), kind: n.kind }]),
  );
  const ids = Object.keys(nodesA);
  if (ids.length !== Object.keys(nodesB).length) return false;
  for (const id of ids) {
    const na = nodesA[id];
    const nb = nodesB[id];
    if (!nb || na.label !== nb.label || na.kind !== nb.kind) return false;
  }
  const edgeKey = (e: DiaEdge) =>
    `${e.source}\0${e.target}\0${(e.label || "").trim()}`;
  const ea = a.edges.map(edgeKey).sort();
  const eb = b.edges.map(edgeKey).sort();
  return ea.every((k, i) => k === eb[i]);
}

export { DEFAULT_COLORS };
