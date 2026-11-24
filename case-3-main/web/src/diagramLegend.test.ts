import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { nodeIdsForRole, parseDiagramLegend } from "./diagramLegend";

const SAMPLE = `flowchart TD
  A([Старт]):::start --> B{Решение}:::decision
  B -->|да| C[Ок]:::ok
  B -->|нет| D[Риск]:::warn
  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22
  classDef decision fill:#f5e6c8,stroke:#c4a35a,color:#1a2e22
  classDef ok fill:#cfe8d6,stroke:#5a9a6e,color:#1a2e22
  classDef warn fill:#f0d4d0,stroke:#b56a5e,color:#1a2e22
`;

describe("diagramLegend", () => {
  it("lists used roles with fills", () => {
    const items = parseDiagramLegend(SAMPLE);
    const roles = items.map((i) => i.role);
    assert.ok(roles.includes("start"));
    assert.ok(roles.includes("decision"));
    assert.equal(items.find((i) => i.role === "ok")?.fill, "#cfe8d6");
  });

  it("nodeIdsForRole returns matching ids", () => {
    const ids = nodeIdsForRole(SAMPLE, "decision");
    assert.deepEqual([...ids], ["B"]);
  });

  it("nodeIdsForRole works inside subgraphs (legend highlight)", () => {
    const src = `flowchart TD
  subgraph S [G]
    A[Старт]:::start --> B{Ок?}:::decision
  end
  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22
  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22
`;
    const ids = nodeIdsForRole(src, "decision");
    assert.ok(ids.has("B"));
    const starts = nodeIdsForRole(src, "start");
    assert.ok(starts.has("A"));
  });
});
