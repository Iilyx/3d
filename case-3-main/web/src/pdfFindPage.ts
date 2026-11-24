/** Normalize PDF caption / figure label into search needles (longest first). */

const CAPTION_PREFIX =
  /^(Рисунок|Рис\.|Илл\.|Ill\.|Fig\.|Figure)\s*\d+\s*[:.\-—–]?\s*/i;

export function pdfSearchNeedles(
  caption?: string | null,
  figureId?: string | null,
): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const push = (s: string) => {
    const t = s.replace(/\s+/g, " ").trim();
    if (t.length < 3 || seen.has(t.toLowerCase())) return;
    seen.add(t.toLowerCase());
    out.push(t);
  };

  const cap = (caption || "").trim();
  if (cap) {
    push(cap);
    // "Рис. 2: Foo" / "Рисунок 3. Foo" / "Fig. 4 — Foo" → also try "Foo"
    const bare = cap.replace(CAPTION_PREFIX, "");
    if (bare && bare !== cap) push(bare);
  }
  if (figureId) push(figureId);
  // Longest first so scorers prefer specific captions over ids.
  out.sort((a, b) => b.length - a.length);
  return out;
}

/** Fold PDF/Preview caption quirks so string includes() works across forms. */
export function normPdfText(s: string): string {
  return s
    .toLowerCase()
    .replace(/\u00ad/g, "") // soft hyphen from TeX line breaks
    .replace(/рисунок/g, "рис")
    .replace(/\bfigure\b/g, "fig")
    .replace(/\billustration\b/g, "илл")
    .replace(/[:.\-—–]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** True if page text contains the needle (space / caption-form insensitive). */
export function pageTextMatchesNeedle(
  pageText: string,
  needle: string,
): boolean {
  const hay = normPdfText(pageText);
  const n = normPdfText(needle);
  if (!n || n.length < 3) return false;
  if (hay.includes(n)) return true;
  // pdf.js often splits "Рис. 2" → try compact form
  const hayC = hay.replace(/\s/g, "");
  const nC = n.replace(/\s/g, "");
  return nC.length >= 3 && hayC.includes(nC);
}

/**
 * 1-based page index with the strongest (longest) needle hit.
 * Avoids TOC / "см. рис. 2" winning over the real caption page.
 */
export function bestPageForNeedles(
  pageTexts: string[],
  needles: string[],
): number | null {
  const list = needles.map((n) => n.trim()).filter((n) => n.length >= 3);
  if (!list.length || !pageTexts.length) return null;

  let bestPage: number | null = null;
  let bestScore = 0;

  for (let i = 0; i < pageTexts.length; i++) {
    const text = pageTexts[i] ?? "";
    for (const needle of list) {
      if (!pageTextMatchesNeedle(text, needle)) continue;
      const score = normPdfText(needle).replace(/\s/g, "").length;
      if (score > bestScore) {
        bestScore = score;
        bestPage = i + 1;
      }
    }
  }
  return bestPage;
}
