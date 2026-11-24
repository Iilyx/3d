/** Filmstrip and fullscreen follow slide ids.

Positional PNG files (`slide_01.png` …) stay in the old order until «Готово».
Duplicate, insert, delete, and drag change `deck.json` immediately, so the
pictures have to travel with the slide id or the strip shows the wrong slide.
*/

export type SlideRef = { id: string };

export function bindSlidePngs(
  slides: SlideRef[],
  pngs: string[],
): Record<string, string | null> {
  const aligned = pngs.length > 0 && pngs.length === slides.length;
  const map: Record<string, string | null> = {};
  for (let i = 0; i < slides.length; i++) {
    map[slides[i].id] = aligned ? pngs[i] : null;
  }
  return map;
}

export function retargetSlidePngs(
  prev: Record<string, string | null>,
  before: SlideRef[],
  after: SlideRef[],
  op: "reorder" | "duplicate" | "delete" | "insert",
): Record<string, string | null> {
  const beforeIds = new Set(before.map((s) => s.id));
  const next: Record<string, string | null> = {};
  for (let i = 0; i < after.length; i++) {
    const id = after[i].id;
    if (beforeIds.has(id)) {
      next[id] = prev[id] ?? null;
      continue;
    }
    if (op === "duplicate" && i > 0 && beforeIds.has(after[i - 1].id)) {
      next[id] = prev[after[i - 1].id] ?? null;
    } else {
      next[id] = null;
    }
  }
  return next;
}

/** Index of the first slide that the structure op added. -1 if none. */
export function addedSlideIndex(before: SlideRef[], after: SlideRef[]): number {
  const beforeIds = new Set(before.map((s) => s.id));
  return after.findIndex((s) => !beforeIds.has(s.id));
}

/** Live deck wins over leftover PNG files, which lag structure edits. */
export function fullscreenCount(opts: {
  liveSlides: number;
  pngs: number;
}): { n: number; useDeck: boolean } {
  if (opts.liveSlides > 0) return { n: opts.liveSlides, useDeck: true };
  return { n: opts.pngs, useDeck: false };
}
