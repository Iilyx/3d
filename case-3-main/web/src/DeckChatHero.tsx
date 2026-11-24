/** Scaled read-only DeckCanvas for chat file-card hero (crisp vs PNG). */

import { useEffect, useRef, useState } from "react";
import { DeckCanvas } from "./DeckCanvas";
import type { DeckIR } from "./deckTypes";
import {
  CHAT_DECK_HERO_H,
  CHAT_DECK_HERO_W,
} from "./domain/chatDeckHero";

type Props = {
  runId: string;
  deck: DeckIR;
};

const noopDeck = () => undefined;
const noopPatch = async () => undefined;

export function DeckChatHero({ runId, deck }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth;
      if (w > 0) setScale(w / CHAT_DECK_HERO_W);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div
      ref={hostRef}
      className="deck-file-card-live-host"
      aria-hidden
    >
      <div
        className="deck-file-card-live-scale"
        style={{
          width: CHAT_DECK_HERO_W,
          height: CHAT_DECK_HERO_H,
          transform: `scale(${scale || 0})`,
          transformOrigin: "top left",
          visibility: scale > 0 ? "visible" : "hidden",
        }}
      >
        <DeckCanvas
          runId={runId}
          deck={deck}
          index={0}
          editing={false}
          onDeckChange={noopDeck}
          onPatch={noopPatch}
          diagramPalette={deck.palette}
        />
      </div>
    </div>
  );
}
