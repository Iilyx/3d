/** PipelineFlow stage → node index (stuck-on-Стол regression). */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  pipelineActiveIndex,
  pipelineNodesForMode,
} from "./PipelineFlow";

describe("PipelineFlow stage mapping", () => {
  it("presentation advances past Стол on slides_* stages", () => {
    const nodes = pipelineNodesForMode("presentation");
    assert.equal(nodes[0].label, "Стол");
    assert.equal(pipelineActiveIndex(nodes, "queued"), 0);
    assert.equal(pipelineActiveIndex(nodes, "llm"), 1);
    assert.ok(pipelineActiveIndex(nodes, "slides_llm") > 0);
    assert.ok(pipelineActiveIndex(nodes, "slides_starting") > 0);
    assert.ok(pipelineActiveIndex(nodes, "pipeline_ok") > 0);
    assert.ok(pipelineActiveIndex(nodes, "slides_render") > 1);
    assert.equal(pipelineActiveIndex(nodes, "ok"), nodes.length);
  });

  it("report stays on Стол only for queued", () => {
    const nodes = pipelineNodesForMode("report");
    assert.equal(pipelineActiveIndex(nodes, "queued"), 0);
    assert.equal(pipelineActiveIndex(nodes, "llm"), 1);
    assert.equal(pipelineActiveIndex(nodes, "charts"), 2);
  });
});
