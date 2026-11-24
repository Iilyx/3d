/** File borrowed into a new chat. The old transcript stays in the old chat. */

const KEY = "liber-carried-run";

export function rememberCarriedRun(id: string): void {
  const clean = id.trim();
  try {
    if (!clean) sessionStorage.removeItem(KEY);
    else sessionStorage.setItem(KEY, clean);
  } catch {
    /* private mode */
  }
}

export function loadCarriedRun(): string {
  try {
    return sessionStorage.getItem(KEY)?.trim() || "";
  } catch {
    return "";
  }
}
