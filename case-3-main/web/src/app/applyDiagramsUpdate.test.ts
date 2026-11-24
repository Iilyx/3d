import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { applyDiagramsUpdate } from "./applyDiagramsUpdate";
import type { Msg } from "../domain/liberTypes";

describe("applyDiagramsUpdate", () => {
  it("updates result.diagrams and cache-busts matching figure blocks in result.preview", () => {
    let currentMsgs: Msg[] = [
      {
        id: "msg-1",
        role: "bot",
        text: "Report ready",
        result: {
          run_id: "run-123",
          diagrams: [
            { id: "dia_01", title: "Old Title", type: "flowchart", mermaid: "flowchart TD\nA-->B" },
          ],
          preview: {
            title: "Test Report",
            blocks: [
              {
                type: "figure",
                id: "dia_01",
                kind: "diagram",
                caption: "Old Title",
                url: "/api/runs/run-123/figures/dia_01.png",
              },
            ],
          },
        },
      },
    ];

    const setMsgs = (updater: any) => {
      currentMsgs = typeof updater === "function" ? updater(currentMsgs) : updater;
    };

    applyDiagramsUpdate({
      msgId: "msg-1",
      runId: "run-123",
      diagrams: [
        { id: "dia_01", title: "New Title", type: "flowchart", mermaid: "flowchart TD\nA-->B-->C" },
      ],
      setMsgs: setMsgs as any,
      setActiveArtifact: (() => {}) as any,
      setUndoOffer: (() => {}) as any,
      rememberRun: (() => {}) as any,
      showToast: (() => {}) as any,
    });

    const updated = currentMsgs[0];
    assert.equal(updated.role, "bot");
    assert.ok(updated.result);
    assert.equal(updated.result.diagrams[0].title, "New Title");
    assert.equal(updated.result.diagrams[0].mermaid, "flowchart TD\nA-->B-->C");

    // Preview blocks must also be updated with new caption and cache-busted URL!
    const figBlock = updated.result.preview?.blocks.find(
      (b) => b.type === "figure" && b.id === "dia_01"
    );
    assert.ok(figBlock && figBlock.type === "figure");
    assert.equal(figBlock.caption, "New Title");
    assert.match(figBlock.url || "", /\/api\/runs\/run-123\/figures\/dia_01\.png\?v=/);
  });
});
