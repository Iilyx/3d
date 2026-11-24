/** Pure helpers for Liber report section collapse (C11). */

import type { PreviewBlock } from "./domain/reportPreview";

export type HeadingMeta = {
  blockIndex: number;
  id: string;
  level: number;
  text: string;
};

/** Same id scheme as RailToc.buildToc / ReportView headings: rail-h-1… */
export function listHeadings(blocks: PreviewBlock[]): HeadingMeta[] {
  const out: HeadingMeta[] = [];
  let n = 0;
  blocks.forEach((b, blockIndex) => {
    if (b.type !== "heading") return;
    n += 1;
    out.push({
      blockIndex,
      id: `rail-h-${n}`,
      level: b.level,
      text: b.text,
    });
  });
  return out;
}

/**
 * Body of a heading = following blocks until next heading with level ≤ this one.
 * Returns [start, end) indices into blocks (exclusive of the heading itself).
 */
export function sectionBodyRange(
  blocks: PreviewBlock[],
  headingBlockIndex: number,
): { start: number; end: number } {
  const head = blocks[headingBlockIndex];
  if (!head || head.type !== "heading") {
    return { start: headingBlockIndex + 1, end: headingBlockIndex + 1 };
  }
  const level = head.level;
  let end = blocks.length;
  for (let i = headingBlockIndex + 1; i < blocks.length; i++) {
    const b = blocks[i];
    if (b.type === "heading" && b.level <= level) {
      end = i;
      break;
    }
  }
  return { start: headingBlockIndex + 1, end };
}

/** True if blockIndex is inside a collapsed heading's body (not the heading). */
export function isBlockHiddenByCollapse(
  blocks: PreviewBlock[],
  blockIndex: number,
  collapsedIds: ReadonlySet<string>,
): boolean {
  if (collapsedIds.size === 0) return false;
  const headings = listHeadings(blocks);
  for (const h of headings) {
    if (!collapsedIds.has(h.id)) continue;
    const { start, end } = sectionBodyRange(blocks, h.blockIndex);
    if (blockIndex >= start && blockIndex < end) return true;
  }
  return false;
}

export function collapseStorageKey(runId: string): string {
  return `liber-report-collapse:${runId || "anon"}`;
}

export function loadCollapsedIds(runId: string): Set<string> {
  if (typeof sessionStorage === "undefined") return new Set();
  try {
    const raw = sessionStorage.getItem(collapseStorageKey(runId));
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((x): x is string => typeof x === "string"));
  } catch {
    return new Set();
  }
}

export function saveCollapsedIds(runId: string, ids: ReadonlySet<string>): void {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.setItem(
      collapseStorageKey(runId),
      JSON.stringify([...ids]),
    );
  } catch {
    /* quota / private mode */
  }
}
