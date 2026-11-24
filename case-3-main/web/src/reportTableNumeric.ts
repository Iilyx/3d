/** Table numeric-column heuristics for Liber report preview. */

export function bustFromUrl(url?: string): string {
  if (!url) return "";
  const m = /[?&]v=([^&]+)/.exec(url);
  return m?.[1] || "";
}

export function looksNumeric(s: string): boolean {
  const t = (s || "").trim().replace(/\s/g, "").replace(",", ".");
  if (!t) return false;
  return /^-?\d+(\.\d+)?%?$/.test(t) || /^-?\d{1,3}([. ]\d{3})+(,\d+)?%?$/.test(t);
}

export function colIsNumeric(headers: string[], rows: string[][], ci: number): boolean {
  let n = 0;
  let total = 0;
  for (const row of rows) {
    const cell = row[ci];
    if (cell == null || !String(cell).trim()) continue;
    total += 1;
    if (looksNumeric(String(cell))) n += 1;
  }
  if (total === 0) return false;
  if (n / total >= 0.6) return true;
  const h = (headers[ci] || "").toLowerCase();
  return /\d|%|год|года|шт|руб|млн|тыс|доля|рост/.test(h) && n / total >= 0.35;
}
