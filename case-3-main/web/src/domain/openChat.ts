/** Which chat the desk should show after a reload. */

const KEY = "liber-open-chat";
const FRESH = "liber-chat-fresh";
const LAST = "liber-last-report";

function sessionRunId(): string {
  try {
    if (typeof sessionStorage === "undefined") return "";
    const raw = sessionStorage.getItem(LAST);
    if (!raw) return "";
    const parsed = JSON.parse(raw) as { run_id?: string };
    return (parsed.run_id || "").trim();
  } catch {
    return "";
  }
}

export function rememberOpenChat(runId: string): void {
  const id = runId.trim();
  if (!id) return;
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* private mode */
  }
  try {
    sessionStorage.removeItem(FRESH);
  } catch {
    /* ignore */
  }
}

export function clearOpenChat(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  try {
    sessionStorage.setItem(FRESH, "1");
  } catch {
    /* ignore */
  }
}

export function loadOpenChat(): string {
  try {
    if (
      typeof sessionStorage !== "undefined" &&
      sessionStorage.getItem(FRESH) === "1"
    ) {
      return "";
    }
  } catch {
    /* ignore */
  }
  try {
    const saved =
      typeof localStorage !== "undefined" ? localStorage.getItem(KEY) || "" : "";
    if (saved.trim()) return saved.trim();
  } catch {
    /* ignore */
  }
  return sessionRunId();
}
