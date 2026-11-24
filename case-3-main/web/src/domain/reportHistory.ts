/** Sidebar list is stored on the server (`runs/user_history.json`).
 *  sessionStorage caches that list and the run payload so a report can reopen offline.
 */

import { attachSlidesPayload, type SlidesPayload } from "./attachSlidesPayload";
import type { RunResult } from "./liberTypes";

const KEY = "liber-report-history";
const FOLDERS_KEY = "liber-history-folders";
const LAST = "liber-last-report";
const MAX = 24;

export type HistoryItem = {
  id: string;
  title: string;
  runId: string;
  savedAt: number;
  pinned?: boolean;
  folderId?: string | null;
  /** Run this chat continues. Hidden from the sidebar when the child is listed. */
  priorRunId?: string;
};

/** Items assigned to a folder, including pinned ones. */
export function historyInFolder(
  items: HistoryItem[],
  folderId: string,
): HistoryItem[] {
  return items.filter((h) => h.folderId === folderId);
}

export type HistoryFolder = {
  id: string;
  name: string;
  createdAt: number;
};

export type StoredRun = {
  run_id: string;
  status: string;
  downloads: Record<string, string>;
  preview?: {
    title?: string;
    blocks?: unknown[];
  };
  charts_ok?: number;
  figures_ok?: number;
  charts_planned?: string[];
  figures_planned?: string[];
  warnings?: string[];
  previews?: { id: string; kind: string; url: string }[];
};

function sortHistory(list: HistoryItem[]): HistoryItem[] {
  return [...list].sort((a, b) => {
    const ap = a.pinned ? 1 : 0;
    const bp = b.pinned ? 1 : 0;
    if (ap !== bp) return bp - ap;
    return (b.savedAt || 0) - (a.savedAt || 0);
  });
}

export function loadHistory(): HistoryItem[] {
  try {
    const raw =
      sessionStorage.getItem(KEY) ??
      (typeof localStorage !== "undefined" ? localStorage.getItem(KEY) : null);
    if (!raw) return [];
    const list = JSON.parse(raw) as HistoryItem[];
    if (!Array.isArray(list)) return [];
    return sortHistory(
      list.map((h) => ({
        ...h,
        pinned: Boolean(h.pinned),
        folderId: h.folderId || null,
      })),
    ).slice(0, MAX);
  } catch {
    return [];
  }
}

function writeHistory(list: HistoryItem[]): HistoryItem[] {
  const next = sortHistory(list).slice(0, MAX);
  const serialized = JSON.stringify(next);
  try {
    sessionStorage.setItem(KEY, serialized);
  } catch {
    /* quota */
  }
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(KEY, serialized);
    }
  } catch {
    /* quota */
  }
  return next;
}

export function collapseChatHeads(items: HistoryItem[]): HistoryItem[] {
  const continued = new Set(
    items
      .map((item) => item.priorRunId)
      .filter((id): id is string => Boolean(id)),
  );
  return items.filter((item) => !continued.has(item.runId));
}

export function pushHistory(item: HistoryItem): HistoryItem[] {
  const prev = loadHistory();
  const existing = prev.find((h) => h.runId === item.runId);
  const merged: HistoryItem = {
    ...item,
    pinned: item.pinned ?? existing?.pinned ?? false,
    folderId:
      item.folderId !== undefined
        ? item.folderId
        : (existing?.folderId ?? null),
  };
  const rest = prev.filter((h) => h.runId !== item.runId);
  return writeHistory(collapseChatHeads([merged, ...rest]));
}

export function updateHistoryItem(
  runId: string,
  patch: Partial<Pick<HistoryItem, "pinned" | "folderId" | "title">>,
): HistoryItem[] {
  const next = loadHistory().map((h) =>
    h.runId === runId ? { ...h, ...patch } : h,
  );
  return writeHistory(next);
}

export function togglePinHistory(runId: string): HistoryItem[] {
  const cur = loadHistory().find((h) => h.runId === runId);
  if (!cur) return loadHistory();
  return updateHistoryItem(runId, { pinned: !cur.pinned });
}

export function moveHistoryToFolder(
  runId: string,
  folderId: string | null,
): HistoryItem[] {
  return updateHistoryItem(runId, { folderId });
}

export function mergeServerHistory(
  local: HistoryItem[],
  server: HistoryItem[],
): HistoryItem[] {
  const localMap = new Map(local.map((h) => [h.runId, h]));
  const result: HistoryItem[] = [...local];

  for (const s of server) {
    const existing = localMap.get(s.runId);
    if (!existing) {
      result.push(s);
    } else {
      if (s.pinned && !existing.pinned) existing.pinned = true;
      if (s.folderId && !existing.folderId) existing.folderId = s.folderId;
      if (s.priorRunId) existing.priorRunId = s.priorRunId;
    }
  }

  return writeHistory(collapseChatHeads(result));
}

export function mergeServerFolders(
  local: HistoryFolder[],
  server: HistoryFolder[],
): HistoryFolder[] {
  const ids = new Set(local.map((f) => f.id));
  const result = [...local];
  for (const f of server) {
    if (!ids.has(f.id)) {
      result.push(f);
      ids.add(f.id);
    }
  }
  return writeFolders(result);
}

export async function syncServerHistory(
  items: HistoryItem[],
  folders: HistoryFolder[],
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    const res = await fetch("/api/history/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: items.map((it) => ({
          runId: it.runId,
          pinned: it.pinned,
          folderId: it.folderId,
        })),
        folders,
      }),
    });
    if (!res.ok) {
      return { ok: false, error: `HTTP ${res.status}` };
    }
    return { ok: true };
  } catch (err) {
    const error = err instanceof Error ? err.message : "network";
    return { ok: false, error };
  }
}

export function loadFolders(): HistoryFolder[] {
  try {
    const raw =
      sessionStorage.getItem(FOLDERS_KEY) ??
      (typeof localStorage !== "undefined"
        ? localStorage.getItem(FOLDERS_KEY)
        : null);
    if (!raw) return [];
    const list = JSON.parse(raw) as HistoryFolder[];
    return Array.isArray(list)
      ? list.sort((a, b) => a.name.localeCompare(b.name, "ru"))
      : [];
  } catch {
    return [];
  }
}

function writeFolders(list: HistoryFolder[]): HistoryFolder[] {
  const next = [...list].sort((a, b) => a.name.localeCompare(b.name, "ru"));
  const serialized = JSON.stringify(next);
  try {
    sessionStorage.setItem(FOLDERS_KEY, serialized);
  } catch {
    /* quota */
  }
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(FOLDERS_KEY, serialized);
    }
  } catch {
    /* quota */
  }
  return next;
}

export function createFolder(name: string): HistoryFolder[] {
  const trimmed = name.trim().slice(0, 40);
  if (!trimmed) return loadFolders();
  const folders = loadFolders();
  if (folders.some((f) => f.name.toLowerCase() === trimmed.toLowerCase())) {
    return folders;
  }
  const folder: HistoryFolder = {
    id: `fld_${Date.now().toString(36)}`,
    name: trimmed,
    createdAt: Date.now(),
  };
  return writeFolders([...folders, folder]);
}

export function renameFolder(id: string, name: string): HistoryFolder[] {
  const trimmed = name.trim().slice(0, 40);
  if (!trimmed) return loadFolders();
  return writeFolders(
    loadFolders().map((f) => (f.id === id ? { ...f, name: trimmed } : f)),
  );
}

export function deleteFolder(id: string): {
  folders: HistoryFolder[];
  history: HistoryItem[];
} {
  const folders = writeFolders(loadFolders().filter((f) => f.id !== id));
  const history = writeHistory(
    loadHistory().map((h) =>
      h.folderId === id ? { ...h, folderId: null } : h,
    ),
  );
  return { folders, history };
}

export function loadHistoryPayload(runId: string): StoredRun | null {
  try {
    const raw = sessionStorage.getItem(`liber-run-${runId}`);
    if (!raw) return null;
    return JSON.parse(raw) as StoredRun;
  } catch {
    return null;
  }
}

export type StoredUserTurn = {
  text: string;
  photos?: { url: string; name?: string }[];
};

function userTurnKey(runId: string): string {
  return `liber-user-${runId}`;
}

export function saveUserTurn(runId: string, turn: StoredUserTurn): void {
  if (!runId) return;
  const photos = (turn.photos || []).filter(
    (p) => p.url && !p.url.startsWith("blob:"),
  );
  try {
    sessionStorage.setItem(
      userTurnKey(runId),
      JSON.stringify({ text: turn.text || "", photos }),
    );
  } catch {
    /* quota */
  }
}

export function loadUserTurn(runId: string): StoredUserTurn | null {
  try {
    const raw = sessionStorage.getItem(userTurnKey(runId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredUserTurn;
    if (!parsed || typeof parsed.text !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function uploadedPhotoThumbs(
  previews?: { id?: string; url?: string }[] | null,
): { url: string; name: string }[] {
  return (previews || [])
    .filter((p) => (p.id || "").startsWith("usr_") && Boolean(p.url))
    .map((p) => ({ url: String(p.url), name: String(p.id) }));
}

export function saveRunPayload(result: StoredRun): void {
  try {
    sessionStorage.setItem(LAST, JSON.stringify(result));
    if (result.run_id) {
      sessionStorage.setItem(
        `liber-run-${result.run_id}`,
        JSON.stringify(result),
      );
    }
  } catch {
    /* quota */
  }
}

export function hydrateHistoryResult(
  stored: StoredRun | RunResult | null | undefined,
  remote: RunResult | null | undefined,
  slidesPayload?: SlidesPayload | null,
): RunResult | null {
  const base = (stored || remote) as RunResult | null;
  if (!base) return null;
  const merged: RunResult = {
    ...base,
    ...(remote || {}),
    downloads: {
      ...(base.downloads || {}),
      ...(remote?.downloads || {}),
    },
    preview: remote?.preview?.blocks?.length ? remote.preview : base.preview,
    previews: remote?.previews?.length ? remote.previews : base.previews,
    deck: remote?.deck?.slides?.length ? remote.deck : base.deck,
    slide_pngs: remote?.slide_pngs?.length ? remote.slide_pngs : base.slide_pngs,
    user_text: remote?.user_text || base.user_text || "",
  };
  return slidesPayload ? attachSlidesPayload(merged, slidesPayload) : merged;
}

