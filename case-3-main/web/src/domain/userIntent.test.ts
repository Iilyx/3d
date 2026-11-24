/** File-only sends must not invent a brief before input_validation. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { DEFAULT_INTENT } from "./liberConstants";
import { userIntentForRun } from "./userIntent";

describe("userIntentForRun", () => {
  it("posts the typed text and nothing else", () => {
    assert.equal(userIntentForRun(""), "");
    assert.equal(userIntentForRun("  привет  "), "привет");
    assert.equal(userIntentForRun("Выручка 10"), "Выручка 10");
  });

  it("does not substitute the canned report brief", () => {
    assert.notEqual(userIntentForRun(""), DEFAULT_INTENT);
    assert.equal(userIntentForRun("").includes("русскоязычный"), false);
  });
});
