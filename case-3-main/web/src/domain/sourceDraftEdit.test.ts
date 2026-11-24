/** Source draft click-to-edit mode helpers. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  enterSourceEdit,
  exitSourceEditOnBlur,
  exitSourceEditOnKey,
  patchSourceDraftText,
} from "./sourceDraftEdit";

describe("sourceDraftEdit", () => {
  it("enters editing only when editable", () => {
    assert.equal(enterSourceEdit(true, "preview"), "editing");
    assert.equal(enterSourceEdit(false, "preview"), "preview");
    assert.equal(enterSourceEdit(true, "editing"), "editing");
  });

  it("exits editing on Escape only", () => {
    assert.equal(exitSourceEditOnKey("Escape", "editing"), "preview");
    assert.equal(exitSourceEditOnKey("Enter", "editing"), "editing");
    assert.equal(exitSourceEditOnKey("Escape", "preview"), "preview");
  });

  it("exits editing on blur", () => {
    assert.equal(exitSourceEditOnBlur("editing"), "preview");
    assert.equal(exitSourceEditOnBlur("preview"), "preview");
  });

  it("patches draft text immutably", () => {
    const draft = { title: "Source", text: "old", fileName: "a.md" };
    const next = patchSourceDraftText(draft, "new body");
    assert.equal(next.text, "new body");
    assert.equal(next.title, "Source");
    assert.equal(draft.text, "old");
  });
});
