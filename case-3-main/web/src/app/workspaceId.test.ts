import assert from "node:assert/strict";
import test from "node:test";
import { getOrCreateWorkspaceId, shouldAttachWorkspaceHeader } from "./workspaceId";

test("getOrCreateWorkspaceId reuses persisted id or generates ws_ prefix", () => {
  const store = new Map<string, string>();
  const storage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, v);
    },
  };
  const first = getOrCreateWorkspaceId(storage);
  assert.match(first, /^ws_[a-z0-9]{8,}$/);
  const second = getOrCreateWorkspaceId(storage);
  assert.equal(second, first);
});

test("shouldAttachWorkspaceHeader matches same-origin /api/ calls only", () => {
  assert.equal(shouldAttachWorkspaceHeader("/api/history"), true);
  assert.equal(shouldAttachWorkspaceHeader("http://localhost:5173/api/run"), true);
  assert.equal(shouldAttachWorkspaceHeader("https://example.com/api/run"), false);
  assert.equal(shouldAttachWorkspaceHeader("/viewer"), false);
});
