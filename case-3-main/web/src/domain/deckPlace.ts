/** Last deck slide, kept when PresentationPane unmounts (tab switch). */

export type DeckPlace = {
  slideId: string;
  view: "grid" | "slide";
  editing: boolean;
};

const places = new Map<string, DeckPlace>();

export function rememberDeckPlace(runId: string, place: DeckPlace): void {
  if (!runId || !place.slideId) return;
  places.set(runId, {
    slideId: place.slideId,
    view: place.view === "grid" ? "grid" : "slide",
    editing: Boolean(place.editing),
  });
}

export function recallDeckPlace(runId: string): DeckPlace | null {
  return places.get(runId) ?? null;
}

export function forgetDeckPlace(runId: string): void {
  places.delete(runId);
}
