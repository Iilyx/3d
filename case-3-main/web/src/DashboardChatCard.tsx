/** Chat card for a dashboard the user can open again. Same stage language as a deck card. */

import { cardCaption } from "./domain/dashboardCapture";
import type { DashboardCard } from "./domain/dashboardCapture";

type Props = {
  card: DashboardCard;
  onOpen: () => void;
  onRead?: () => void;
};

export function DashboardChatCard({ card, onOpen, onRead }: Props) {
  const caption = cardCaption(card.filters);
  const names = card.shots.map((shot) => shot.name);
  const lead = names[names.length - 1] || "";
  const count = names.length;
  return (
    <article className="deck-file-card dash-chat-card">
      <button type="button" className="dash-chat-hit" onClick={onOpen}>
        <div className="dash-chat-stage">
          <p className="dash-chat-stage-kicker">Стимулсофт</p>
          <p className="dash-chat-stage-name">{lead || "Дашборд"}</p>
        </div>
        <div className="dash-chat-copy">
          <p className="dash-chat-kicker">Дашборд готов</p>
          <p className="dash-chat-title">{lead || "Нажмите, чтобы открыть"}</p>
          <p className="dash-chat-meta">
            {lead ? "Нажмите, чтобы открыть" : caption}
            {count ? ` · ${count} ${count === 1 ? "снимок" : count < 5 ? "снимка" : "снимков"}` : ""}
          </p>
          {names.length > 1 ? (
            <p className="dash-chat-meta">{names.join(" · ")}</p>
          ) : null}
        </div>
      </button>
      {onRead ? (
        <button type="button" className="dash-chat-read" onClick={onRead}>
          Смотреть таблицу
        </button>
      ) : null}
    </article>
  );
}
