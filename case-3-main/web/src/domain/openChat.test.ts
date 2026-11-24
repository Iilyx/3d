import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { clearOpenChat, loadOpenChat, rememberOpenChat } from "./openChat";

const mem = new Map<string, string>();

beforeEach(() => {
  mem.clear();
  (globalThis as { localStorage?: Storage }).localStorage = {
    getItem: (k) => mem.get(k) ?? null,
    setItem: (k, v) => {
      mem.set(k, String(v));
    },
    removeItem: (k) => {
      mem.delete(k);
    },
    clear: () => mem.clear(),
    key: () => null,
    length: 0,
  };
});

test("the open chat survives a reload and a new chat clears it", () => {
  assert.equal(loadOpenChat(), "");
  rememberOpenChat("source_20261118T100000Z");
  assert.equal(loadOpenChat(), "source_20261118T100000Z");
  clearOpenChat();
  assert.equal(loadOpenChat(), "");
});
