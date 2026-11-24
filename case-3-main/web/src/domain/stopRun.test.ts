/** Stop polling and the late run_id cancel. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { cancelIfStopPressed, stopPollSettled } from "./stopRun";

describe("stopPollSettled", () => {
  it("keeps waiting while the pipeline is queued", () => {
    assert.equal(stopPollSettled("queued", "idle"), false);
    assert.equal(stopPollSettled("running", "idle"), false);
    assert.equal(stopPollSettled("started", undefined), false);
  });

  it("settles on cancel, or when neither pipeline nor slides are in flight", () => {
    assert.equal(stopPollSettled("cancelled", "idle"), true);
    assert.equal(stopPollSettled("ok", "cancelled"), true);
    assert.equal(stopPollSettled("ok", "idle"), true);
    assert.equal(stopPollSettled("ok", "running"), false);
    assert.equal(stopPollSettled("ok", "queued"), false);
  });
});

describe("cancelIfStopPressed", () => {
  it("posts cancel once the run id exists", async () => {
    let called = "";
    const stopped = await cancelIfStopPressed("run_a", true, async (id) => {
      called = id;
    });
    assert.equal(stopped, true);
    assert.equal(called, "run_a");
  });

  it("does not post when Stop was not pressed", async () => {
    const stopped = await cancelIfStopPressed("run_a", false, async () => {
      throw new Error("must not post");
    });
    assert.equal(stopped, false);
  });

  it("still counts as stopped if the cancel request fails", async () => {
    const stopped = await cancelIfStopPressed("run_a", true, async () => {
      throw new Error("offline");
    });
    assert.equal(stopped, true);
  });
});
