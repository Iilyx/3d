/** Merge GET /api/runs/{id}/slides (or status slide fields) into a RunResult. */

import type { RunResult } from "./liberTypes";

export type SlidesPayload = {
  slide_pngs?: unknown;
  deck?: unknown;
  downloads?: unknown;
  deck_pdf_mode?: unknown;
  slides_status?: unknown;
  slides_stage?: unknown;
  slides_error?: unknown;
};

/** Attach twin PNGs + deck IR so chat/rail preview is not empty after slides ok. */
export function attachSlidesPayload(
  result: RunResult,
  payload: SlidesPayload | null | undefined,
): RunResult {
  if (!payload || typeof payload !== "object") return result;
  const next: RunResult = { ...result };
  if (Array.isArray(payload.slide_pngs)) {
    const pngs = payload.slide_pngs.filter(
      (u): u is string => typeof u === "string" && u.length > 0,
    );
    if (pngs.length) next.slide_pngs = pngs;
  }
  if (payload.deck && typeof payload.deck === "object") {
    next.deck = payload.deck as RunResult["deck"];
  }
  if (payload.downloads && typeof payload.downloads === "object") {
    next.downloads = {
      ...next.downloads,
      ...(payload.downloads as Record<string, string>),
    };
  }
  if (typeof payload.deck_pdf_mode === "string" && payload.deck_pdf_mode) {
    next.deck_pdf_mode = payload.deck_pdf_mode;
  }
  if (typeof payload.slides_status === "string") {
    next.slides_status = payload.slides_status;
  }
  if (typeof payload.slides_stage === "string" || payload.slides_stage === null) {
    next.slides_stage = payload.slides_stage as string | null;
  }
  if (typeof payload.slides_error === "string" || payload.slides_error === null) {
    next.slides_error = payload.slides_error as string | null;
  }
  return next;
}

/** True when status says deck is ready but chat/rail still lacks twin PNGs or deck IR. */
export function needsSlidesHydrate(result: RunResult): boolean {
  const st = result.slides_status || "";
  if (st !== "ok" && !result.downloads?.pptx) return false;
  const noPngs = !(result.slide_pngs && result.slide_pngs.length > 0);
  const noDeck = !(result.deck?.slides && result.deck.slides.length > 0);
  return noPngs || noDeck;
}
