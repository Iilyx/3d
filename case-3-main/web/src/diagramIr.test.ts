/** Unit tests for Mermaid flowchart ↔ Liber DiagramIR. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  canParseFlowchart,
  diagramStructureEqual,
  isSupportedFlowchartSubset,
  parseMermaidFlowchart,
  serializeMermaidFlowchart,
  type DiagramIR,
} from "./diagramIr";

const SAMPLE = `flowchart TD
  A[Заявка]:::start --> B{Проверка}:::decision
  B -->|да| C[Готово]:::ok
  B -->|нет| D[Доработка]:::warn
  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22
  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22
  classDef ok fill:#cfe6d4,stroke:#3d7a4a,color:#1a2e22
  classDef warn fill:#f0ddd8,stroke:#a85a4a,color:#1a2e22
`;

describe("diagramIr", () => {
  it("canParseFlowchart accepts flowchart headers", () => {
    assert.equal(canParseFlowchart(SAMPLE), true);
    assert.equal(canParseFlowchart("sequenceDiagram\nA->>B: hi"), false);
  });

  it("parses nodes kinds edges and direction", () => {
    const ir = parseMermaidFlowchart(SAMPLE, {
      id: "dia_01",
      title: "Тест",
    });
    assert.equal(ir.direction, "TD");
    assert.equal(ir.nodes.length, 4);
    const byId = Object.fromEntries(ir.nodes.map((n) => [n.id, n]));
    assert.equal(byId.A.label, "Заявка");
    assert.equal(byId.A.kind, "start");
    assert.equal(byId.B.kind, "decision");
    assert.equal(byId.C.kind, "ok");
    assert.equal(ir.edges.length, 3);
    const yes = ir.edges.find((e) => e.source === "B" && e.target === "C");
    assert.ok(yes);
    assert.equal(yes!.label, "да");
  });

  it("round-trips labels kinds and edge labels", () => {
    const ir = parseMermaidFlowchart(SAMPLE, { id: "dia_01", title: "R" });
    const out = serializeMermaidFlowchart(ir);
    assert.match(out, /^flowchart TD/m);
    // Soft shapes: rounded / stadium (not sharp [rect])
    assert.match(out, /A\(Заявка\):::start/);
    assert.match(out, /B\{Проверка\}:::decision/);
    assert.match(out, /C\(\[Готово\]\):::ok/);
    assert.match(out, /B -->|да\| C/);
    assert.match(out, /classDef start fill:/);
    const again = parseMermaidFlowchart(out, { id: "dia_01", title: "R" });
    assert.equal(again.nodes.length, ir.nodes.length);
    assert.equal(again.edges.length, ir.edges.length);
  });

  it("serialize emits Liber classDef for used kinds", () => {
    const ir: DiagramIR = {
      id: "dia_01",
      title: "X",
      direction: "LR",
      nodes: [
        { id: "a", label: "Старт", kind: "start" },
        { id: "b", label: "Шаг", kind: "process" },
      ],
      edges: [{ id: "e1", source: "a", target: "b" }],
    };
    const out = serializeMermaidFlowchart(ir, {
      start: { fill: "#dce8df", stroke: "#6b8f76" },
      process: { fill: "#eef3ef", stroke: "#5a7a64" },
    });
    assert.match(out, /flowchart LR/);
    assert.match(out, /classDef start/);
    assert.match(out, /classDef process/);
  });

  it("preserves classDef colors on round-trip", () => {
    const ir = parseMermaidFlowchart(SAMPLE, { id: "dia_01", title: "T" });
    assert.equal(ir.colors?.decision?.fill.toLowerCase(), "#f3e6c8");
    const out = serializeMermaidFlowchart(ir);
    assert.match(out, /fill:#f3e6c8/i);
  });

  it("rejects chains but flattens subgraphs for visual subset", () => {
    assert.equal(isSupportedFlowchartSubset(SAMPLE), true);
    assert.equal(
      isSupportedFlowchartSubset("flowchart TD\n  A --> B --> C\n"),
      false,
    );
    assert.equal(
      isSupportedFlowchartSubset(
        "flowchart TD\n  subgraph S\n  A[X]:::start --> B[Y]:::process\n  end\n",
      ),
      true,
    );
  });

  it("diagramStructureEqual ignores order and colors", () => {
    const a = parseMermaidFlowchart(SAMPLE, { id: "d", title: "T" });
    const b = parseMermaidFlowchart(
      serializeMermaidFlowchart(a),
      { id: "d", title: "T" },
    );
    assert.equal(diagramStructureEqual(a, b), true);
    const c = {
      ...b,
      nodes: b.nodes.map((n) =>
        n.id === "A" ? { ...n, label: "Другое" } : n,
      ),
    };
    assert.equal(diagramStructureEqual(a, c), false);
  });

  it("parses subgraph + br + bidirectional edges (desk 091443)", () => {
    const src = `flowchart TD
  subgraph L1 [Уровень 1]
    P[Президент]:::start
    NP[Программа<br/>«Цифра»]:::process
  end
  P -->|Утверждение| NP
  C[Совет]:::decision
  C <-->|Обмен| MinInf[Мин]:::decision
  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22
  classDef process fill:#eef3ef,stroke:#5a7a64,color:#1a2e22
  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22
`;
    assert.equal(isSupportedFlowchartSubset(src), true);
    const ir = parseMermaidFlowchart(src, { id: "dia_01", title: "Org" });
    const byId = Object.fromEntries(ir.nodes.map((n) => [n.id, n]));
    assert.equal(byId.P.kind, "start");
    assert.match(byId.NP.label, /Программа/);
    assert.match(byId.NP.label, /Цифра/);
    assert.ok(ir.edges.some((e) => e.source === "C" && e.target === "MinInf"));
  });

  it("strips wrapping quotes from node labels", () => {
    const src = `flowchart TD
  A(["Лид<br/>340"]):::start --> B["Квалификация 210"]:::process
  B --> C{"Бюджет?"}:::decision
`;
    const ir = parseMermaidFlowchart(src, { id: "dia_01", title: "Quotes" });
    const byId = Object.fromEntries(ir.nodes.map((n) => [n.id, n]));
    assert.equal(byId.A.label, "Лид\n340");
    assert.equal(byId.B.label, "Квалификация 210");
    assert.equal(byId.C.label, "Бюджет?");
  });
});
