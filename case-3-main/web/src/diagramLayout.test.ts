/** Unit tests for Liber DiagramIR layout. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { parseMermaidFlowchart } from "./diagramIr";
import { layoutPositions } from "./diagramLayout";

const SAMPLE_FORK = `flowchart TD
  A[Заявка]:::start --> B{Проверка}:::decision
  B -->|да| C[Готово]:::ok
  B -->|нет| D[Отказ]:::warn
`;

describe("diagramLayout", () => {
  it("assigns descending Y positions in TD direction", () => {
    const ir = parseMermaidFlowchart(SAMPLE_FORK, { id: "dia_01", title: "Тест" });
    const pos = layoutPositions(ir);

    assert.ok(pos.A);
    assert.ok(pos.B);
    assert.ok(pos.C);
    assert.ok(pos.D);

    // Root A must be above B
    assert.ok(pos.A.y < pos.B.y);
    // B must be above C and D
    assert.ok(pos.B.y < pos.C.y);
    assert.ok(pos.B.y < pos.D.y);
    // C and D are at the same level
    assert.equal(pos.C.y, pos.D.y);
    // C and D must be horizontally separated
    assert.notEqual(pos.C.x, pos.D.x);
  });

  it("assigns ascending X positions in LR direction", () => {
    const ir = parseMermaidFlowchart(SAMPLE_FORK.replace("TD", "LR"), {
      id: "dia_01",
      title: "Тест",
    });
    const pos = layoutPositions(ir);

    // Root A must be to the left of B
    assert.ok(pos.A.x < pos.B.x);
    // B must be to the left of C and D
    assert.ok(pos.B.x < pos.C.x);
    assert.ok(pos.B.x < pos.D.x);
    // C and D are at the same X level
    assert.equal(pos.C.x, pos.D.x);
    // C and D must be vertically separated
    assert.notEqual(pos.C.y, pos.D.y);
  });
});
