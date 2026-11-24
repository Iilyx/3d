/** Mini 16:9 live preview for deck style sheet (no slides job). */

import type { CSSProperties } from "react";
import type { DeckStyle } from "./deckStyle";

type Props = { style: DeckStyle };

export function DeckStylePreview({ style }: Props) {
  const css = {
    ["--deck-primary"]: style.primary,
    ["--deck-accent"]: style.accent,
    ["--deck-bg"]: style.background,
    ["--deck-text"]: style.text,
    ["--deck-font-title"]: style.fontTitle,
    ["--deck-font-body"]: style.fontBody,
  } as CSSProperties;
  return (
    <div
      className="deck-style-preview"
      style={css}
      aria-hidden
    >
      <div className="deck-style-preview-slide">
        <div className="deck-style-preview-bar" />
        <p className="deck-style-preview-kicker">Liber · превью</p>
        <h3 className="deck-style-preview-title">Итоги квартала</h3>
        <p className="deck-style-preview-sub">
          Единое оформление для вашей следующей презентации.
        </p>
        <div className="deck-style-preview-chart">
          <span style={{ height: "42%" }} />
          <span style={{ height: "68%" }} />
          <span style={{ height: "55%" }} />
          <span style={{ height: "88%" }} />
        </div>
        <div className="deck-style-preview-table">
          <div className="deck-style-preview-thead">
            <span>Показатель</span>
            <span>Динамика</span>
          </div>
          <div>
            <span>Выручка</span>
            <span>+18%</span>
          </div>
          <div>
            <span>Клиенты</span>
            <span>+12%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
