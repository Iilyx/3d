/** Unit tests: extract Source-style metrics from Mermaid labels. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatMetricChip, parseDiagramMetrics } from "./diagramMetrics";

describe("diagramMetrics", () => {
  it("extracts · annotations from flowchart nodes", () => {
    const src = `flowchart TD
  A[Склад · 1 240 шт]:::data --> B{ОК?}:::decision
  B -->|да · 88%| C[Отгрузка · 1 090]:::ok
  B -->|нет · 12%| D[Отказ]:::warn
`;
    const m = parseDiagramMetrics(src);
    assert.ok(m.length >= 3);
    assert.ok(m.some((x) => x.entity.includes("Склад") && /1240|1\s*240/.test(x.metric)));
    assert.ok(m.some((x) => /88%/.test(x.metric) || /12%/.test(x.metric)));
  });

  it("extracts br-separated two-line labels", () => {
    const src = `flowchart LR
  A["Приёмка<br/>340 заявок"]:::start --> B["Склад<br/>1 240 шт"]:::data
`;
    const m = parseDiagramMetrics(src);
    assert.equal(m.length, 2);
    assert.match(m[0].metric, /340/);
    assert.match(m[1].metric, /1240|1\s*240/);
  });

  it("extracts stadium ([\"…<br/>…\"]) node labels", () => {
    const src = `flowchart TD
  A(["Лид<br/>340"]):::start --> B(["Сделка<br/>185"]):::ok
  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22
  classDef ok fill:#cfe8d6,stroke:#5a9a6e,color:#1a2e22
`;
    const m = parseDiagramMetrics(src);
    assert.ok(m.some((x) => x.entity === "Лид" && x.metric === "340"));
    assert.ok(m.some((x) => x.entity === "Сделка" && x.metric === "185"));
  });

  it("returns empty for structure-only diagrams", () => {
    const src = `flowchart TD
  A[Заявка]:::start --> B{Проверка}:::decision
  B -->|да| C[Готово]:::ok
`;
    assert.deepEqual(parseDiagramMetrics(src), []);
  });

  it("formatMetricChip strips role codes", () => {
    const chip = formatMetricChip({
      entity: "Квалификация SDR · SDR",
      metric: "510",
    });
    assert.equal(chip.metric, "510");
    assert.ok(!/SDR/i.test(chip.entity));
  });
});
