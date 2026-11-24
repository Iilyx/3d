/** Which slide to show after a deck undo/redo.

`target` is the slide id stored with the snapshot. Several ids are joined
with commas. The first id that is still in the deck wins, so undo of a
duplicate (copy gone) falls through to the original slide.
*/

export function slideIndexForUndoTarget(
  slides: { id?: string }[] | null | undefined,
  target: string | null | undefined,
): number {
  if (!slides?.length) return -1;
  for (const part of (target || "").split(",")) {
    const id = part.trim();
    if (!id) continue;
    const idx = slides.findIndex((s) => s.id === id);
    if (idx >= 0) return idx;
  }
  return -1;
}
