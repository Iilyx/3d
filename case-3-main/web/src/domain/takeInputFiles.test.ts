import assert from "node:assert/strict";
import test from "node:test";
import { takeInputFiles } from "./takeInputFiles.ts";

test("keeps the chosen files after the input is cleared", () => {
  const file = new File(["hello"], "note.txt", { type: "text/plain" });
  const live: File[] = [file];
  const input = {
    get files(): FileList | null {
      return (this.value ? live : []) as unknown as FileList;
    },
    value: "C:\\note.txt",
  };
  const taken = takeInputFiles(input);
  assert.equal(input.value, "");
  assert.equal(taken.length, 1);
  assert.equal(taken[0]?.name, "note.txt");
});
