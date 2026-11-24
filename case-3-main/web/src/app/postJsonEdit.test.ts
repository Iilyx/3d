import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { mapTableEditHttpError, postJsonEdit } from "./postJsonEdit";

describe("postJsonEdit", () => {
  it("returns JSON on ok", async () => {
    const orig = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ status: "ok", preview: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch;
    try {
      const data = await postJsonEdit("/api/x", { a: 1 });
      assert.equal(data.status, "ok");
    } finally {
      globalThis.fetch = orig;
    }
  });

  it("throws detail string on error", async () => {
    const orig = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ detail: "bad formats" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch;
    try {
      await assert.rejects(
        () => postJsonEdit("/api/x", {}),
        (e: unknown) => e instanceof Error && e.message === "bad formats",
      );
    } finally {
      globalThis.fetch = orig;
    }
  });
});

describe("mapTableEditHttpError", () => {
  it("rewrites Not Found", () => {
    const e = mapTableEditHttpError(new Error("Not Found"));
    assert.match(e.message, /api\.cmd/i);
  });

  it("rewrites status 404", () => {
    const base = new Error("x") as Error & { status?: number };
    base.status = 404;
    assert.match(mapTableEditHttpError(base).message, /404/);
  });
});
