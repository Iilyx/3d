/** Chat deck card hero: prefer live IR twin over PNG downscale. */

import type { DeckIR } from "../deckTypes";

/** Design size for scaled chat hero (matches 16:9 slide frame). */
export const CHAT_DECK_HERO_W = 960;
export const CHAT_DECK_HERO_H = 540;

/** Use live DeckCanvas in chat when IR has at least one slide. */
export function prefersLiveChatHero(
  deck: DeckIR | null | undefined,
): boolean {
  return Boolean(deck?.slides && deck.slides.length > 0);
}
