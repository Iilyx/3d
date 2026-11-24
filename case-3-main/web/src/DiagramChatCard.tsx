/** Julius-style in-chat diagram: live Mermaid render (no raw Mermaid toggle). */

import { diagramTypeLabel } from "./diagramLabels";
import { MermaidView } from "./MermaidView";

export type DiagramChatItem = {
  id: string;
  title: string;
  type?: string;
  mermaid?: string;
};

type Props = {
  diagram: DiagramChatItem;
  siblings?: DiagramChatItem[];
  onOpen: (id: string) => void;
};

export function DiagramChatCard({ diagram, siblings = [], onOpen }: Props) {
  const title = diagram.title || diagram.id;
  const src = (diagram.mermaid || "").trim();
  const rest = siblings.filter((d) => d.id !== diagram.id);
  const typeRu = diagramTypeLabel(diagram.type);

  return (
    <div className="diagram-chat" role="group" aria-label="Схема">
      <article className="diagram-chat-card">
        <header className="diagram-chat-head">
          <div className="diagram-chat-titles">
            <p className="diagram-chat-eyebrow">
              {typeRu}
              <span aria-hidden> · </span>
              Liber
            </p>
            <h3 className="diagram-chat-title">{title}</h3>
          </div>
          <button
            type="button"
            className="diagram-chat-open"
            onClick={() => onOpen(diagram.id)}
          >
            Открыть
            <span aria-hidden>→</span>
          </button>
        </header>

        <div
          className="diagram-chat-stage"
          role="button"
          tabIndex={0}
          onClick={() => onOpen(diagram.id)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onOpen(diagram.id);
            }
          }}
          aria-label={`Открыть схему: ${title}`}
        >
          {src ? (
            <MermaidView source={src} className="is-chat-preview" />
          ) : (
            <p className="diagram-chat-empty">Нет схемы</p>
          )}
        </div>
      </article>

      {rest.length > 0 ? (
        <div
          className="diagram-chat-siblings"
          role="group"
          aria-label="Другие схемы"
        >
          {rest.map((d) => (
            <button
              key={d.id}
              type="button"
              className="diagram-chat-sibling"
              onClick={() => onOpen(d.id)}
            >
              {d.title || d.id}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
