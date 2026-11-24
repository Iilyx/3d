import assert from "node:assert/strict";
import { describe, it, beforeEach } from "node:test";
import {
  createFolder,
  deleteFolder,
  historyInFolder,
  hydrateHistoryResult,
  loadFolders,
  loadHistory,
  loadUserTurn,
  mergeServerFolders,
  mergeServerHistory,
  moveHistoryToFolder,
  pushHistory,
  saveUserTurn,
  syncServerHistory,
  togglePinHistory,
  uploadedPhotoThumbs,
} from "./domain/reportHistory";

const mem = new Map<string, string>();

beforeEach(() => {
  mem.clear();
  (globalThis as { sessionStorage?: Storage }).sessionStorage = {
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

describe("reportHistory folders + pin", () => {
  it("pins float to top", () => {
    pushHistory({
      id: "a",
      title: "A",
      runId: "a",
      savedAt: 1,
    });
    pushHistory({
      id: "b",
      title: "B",
      runId: "b",
      savedAt: 2,
    });
    togglePinHistory("a");
    const list = loadHistory();
    assert.equal(list[0].runId, "a");
    assert.equal(list[0].pinned, true);
  });

  it("create folder and move chat", () => {
    pushHistory({
      id: "x",
      title: "X",
      runId: "x",
      savedAt: 3,
    });
    const folders = createFolder("Клиенты");
    assert.equal(folders.length, 1);
    const moved = moveHistoryToFolder("x", folders[0].id);
    assert.equal(moved[0].folderId, folders[0].id);
    const after = deleteFolder(folders[0].id);
    assert.equal(after.folders.length, 0);
    assert.equal(loadHistory()[0].folderId, null);
    assert.equal(loadFolders().length, 0);
  });

  it("keeps the sent text and drops blob photo urls", () => {
    saveUserTurn("run_a", {
      text: "Собери презу",
      photos: [
        { url: "blob:http://local/1", name: "a.jpg" },
        { url: "/api/runs/run_a/figures/usr_01.png", name: "usr_01" },
      ],
    });
    const turn = loadUserTurn("run_a");
    assert.equal(turn?.text, "Собери презу");
    assert.deepEqual(turn?.photos, [
      { url: "/api/runs/run_a/figures/usr_01.png", name: "usr_01" },
    ]);
  });

  it("picks only uploaded figure thumbs", () => {
    const thumbs = uploadedPhotoThumbs([
      { id: "cht_01", url: "/c.png" },
      { id: "usr_01", url: "/u.png" },
      { id: "fig_01", url: "/f.png" },
    ]);
    assert.deepEqual(thumbs, [{ url: "/u.png", name: "usr_01" }]);
  });

  it("merges server history with local history", () => {
    const local = [
      { id: "run_1", runId: "run_1", title: "Local 1", savedAt: 100, pinned: false },
    ];
    const server = [
      { id: "run_1", runId: "run_1", title: "Server 1", savedAt: 100, pinned: true, folderId: "f_1" },
      { id: "run_2", runId: "run_2", title: "Server 2", savedAt: 200, pinned: false },
    ];
    const merged = mergeServerHistory(local, server);
    assert.equal(merged.length, 2);
    // Pinned should float to top
    assert.equal(merged[0].runId, "run_1");
    assert.equal(merged[0].pinned, true);
    assert.equal(merged[0].folderId, "f_1");
    assert.equal(merged[1].runId, "run_2");
  });

  it("merges server folders without duplicates", () => {
    const local = [{ id: "f_1", name: "Финансы", createdAt: 100 }];
    const server = [
      { id: "f_1", name: "Финансы", createdAt: 100 },
      { id: "f_2", name: "Маркетинг", createdAt: 200 },
    ];
    const merged = mergeServerFolders(local, server);
    assert.equal(merged.length, 2);
    assert.deepEqual(merged.map((f) => f.id).sort(), ["f_1", "f_2"]);
  });

  it("hydrates presentation deck IR and slide_pngs when opening history with cold sessionStorage", () => {
    const remote = {
      run_id: "pres_1",
      status: "ok",
      output_mode: "presentation",
      slides_status: "ok",
      downloads: { pptx: "/api/runs/pres_1/files/deck.pptx" },
    };
    const slidesPayload = {
      slides_status: "ok",
      slide_pngs: ["/api/runs/pres_1/slides/png/slide_01.png"],
      deck: {
        title: "Обзор Q3",
        slides: [{ id: "s1", layout: "title_slide", title: "Обзор Q3" }],
      },
    };
    const hydrated = hydrateHistoryResult(null, remote, slidesPayload);
    assert.ok(hydrated);
    assert.equal(hydrated?.deck?.slides?.length, 1);
    assert.deepEqual(hydrated?.slide_pngs, [
      "/api/runs/pres_1/slides/png/slide_01.png",
    ]);
  });

  it("persists merged server history and folders so togglePinHistory in a fresh tab does not wipe items", () => {
    // Fresh tab: sessionStorage starts empty, server returns 2 items and 1 folder
    const serverItems = [
      { id: "run_1", runId: "run_1", title: "Отчёт Q1", savedAt: 100, pinned: false },
      { id: "run_2", runId: "run_2", title: "Отчёт Q2", savedAt: 200, pinned: false },
    ];
    const serverFolders = [{ id: "f_1", name: "Стратегия", createdAt: 100 }];

    const mergedItems = mergeServerHistory(loadHistory(), serverItems);
    const mergedFolders = mergeServerFolders(loadFolders(), serverFolders);
    assert.equal(mergedItems.length, 2);
    assert.equal(mergedFolders.length, 1);

    // Pinning an item right after server hydration must NOT wipe the list to []
    const afterPin = togglePinHistory("run_1");
    assert.equal(afterPin.length, 2);
    assert.equal(afterPin[0].runId, "run_1");
    assert.equal(afterPin[0].pinned, true);

    const afterMove = moveHistoryToFolder("run_2", "f_1");
    assert.equal(afterMove.length, 2);
    assert.equal(afterMove.find((h) => h.runId === "run_2")?.folderId, "f_1");
  });

  it("folder lists pinned items that were moved into it", () => {
    const items = [
      {
        id: "run_1",
        runId: "run_1",
        title: "Север",
        savedAt: 2,
        pinned: true,
        folderId: "fld_1",
      },
      {
        id: "run_2",
        runId: "run_2",
        title: "Черновик",
        savedAt: 1,
        pinned: false,
        folderId: null,
      },
    ];
    const inFolder = historyInFolder(items, "fld_1");
    assert.equal(inFolder.length, 1);
    assert.equal(inFolder[0].runId, "run_1");
  });

  it("syncServerHistory reports HTTP and network failures", async () => {
    const item = {
      id: "run_1",
      runId: "run_1",
      title: "A",
      savedAt: 1,
    };
    const fetchMock = async () =>
      new Response("no", { status: 500 });
    (globalThis as { fetch?: typeof fetch }).fetch = fetchMock as typeof fetch;
    const httpFail = await syncServerHistory([item], []);
    assert.equal(httpFail.ok, false);
    if (!httpFail.ok) assert.equal(httpFail.error, "HTTP 500");

    (globalThis as { fetch?: typeof fetch }).fetch = (async () => {
      throw new Error("offline");
    }) as typeof fetch;
    const netFail = await syncServerHistory([item], []);
    assert.equal(netFail.ok, false);
    if (!netFail.ok) assert.match(netFail.error, /offline/);
  });

  it("pushHistory keeps one row for a continued chat", () => {
    pushHistory({ id: "a", runId: "a", title: "Отчёт", savedAt: 1 });
    const next = pushHistory({
      id: "b",
      runId: "b",
      title: "Ещё",
      savedAt: 2,
      priorRunId: "a",
    });
    assert.deepEqual(
      next.map((item) => item.runId),
      ["b"],
    );
  });
});

