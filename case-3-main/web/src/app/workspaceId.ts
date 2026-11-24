/** Per-browser workspace id (X-Workspace-Id) without login friction. */

export const WORKSPACE_STORAGE_KEY = "liber_workspace_id";

type StorageLike = {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
};

function generateWorkspaceId(): string {
  const rand =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().replace(/-/g, "").slice(0, 12)
      : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
  return `ws_${rand}`;
}

export function getOrCreateWorkspaceId(storage?: StorageLike | null): string {
  const s =
    storage ??
    (typeof window !== "undefined" ? window.localStorage : null);
  try {
    const existing = s?.getItem(WORKSPACE_STORAGE_KEY)?.trim() || "";
    if (/^[A-Za-z0-9_-]{4,48}$/.test(existing)) {
      return existing;
    }
    const created = generateWorkspaceId();
    s?.setItem(WORKSPACE_STORAGE_KEY, created);
    return created;
  } catch {
    return generateWorkspaceId();
  }
}

export function shouldAttachWorkspaceHeader(
  input: string | URL | Request,
  origin = typeof window !== "undefined" ? window.location.origin : "http://localhost:5173",
): boolean {
  const raw =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
  if (!raw) return false;
  if (raw.startsWith("/api/")) return true;
  try {
    const parsed = new URL(raw, origin);
    return parsed.origin === origin && parsed.pathname.startsWith("/api/");
  } catch {
    return false;
  }
}

let installed = false;

export function installWorkspaceFetch(): void {
  if (installed || typeof window === "undefined" || typeof window.fetch !== "function") {
    return;
  }
  installed = true;
  const workspaceId = getOrCreateWorkspaceId();
  const origFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (!shouldAttachWorkspaceHeader(input)) {
      return origFetch(input, init);
    }
    const headers = new Headers(
      init?.headers ?? (input instanceof Request ? input.headers : undefined),
    );
    if (!headers.has("X-Workspace-Id")) {
      headers.set("X-Workspace-Id", workspaceId);
    }
    return origFetch(input, { ...init, headers });
  };
}
