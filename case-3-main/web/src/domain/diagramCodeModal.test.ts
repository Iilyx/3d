import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { cleanMermaidCode, validateMermaidHeader } from "./diagramCodeModal";

describe("diagramCodeModal helpers", () => {
  it("strips wrapping markdown fences and trims whitespace", () => {
    const raw = "```mermaid\nflowchart TD\n  A --> B\n```";
    assert.equal(cleanMermaidCode(raw), "flowchart TD\n  A --> B");
  });

  it("leaves clean code unchanged", () => {
    const code = "sequenceDiagram\n  Alice->>Bob: Hello";
    assert.equal(cleanMermaidCode(code), "sequenceDiagram\n  Alice->>Bob: Hello");
  });

  it("validates recognized Mermaid headers", () => {
    assert.deepEqual(validateMermaidHeader("flowchart LR\n  A --> B"), {
      ok: true,
      type: "flowchart",
    });
    assert.deepEqual(validateMermaidHeader("sequenceDiagram\n  autonumber"), {
      ok: true,
      type: "sequence",
    });
    assert.deepEqual(validateMermaidHeader("mindmap\n  root((Idea))"), {
      ok: true,
      type: "mindmap",
    });
    assert.deepEqual(validateMermaidHeader("timeline\n  title History"), {
      ok: true,
      type: "timeline",
    });
    assert.deepEqual(validateMermaidHeader("stateDiagram-v2\n  [*] --> Still"), {
      ok: true,
      type: "stateDiagram",
    });
  });

  it("flags empty or missing header", () => {
    const res = validateMermaidHeader("   ");
    assert.equal(res.ok, false);
    assert.match(res.error || "", /пуст/i);
  });
});
