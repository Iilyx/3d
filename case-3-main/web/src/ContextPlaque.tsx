/** Compact source chip — composer + sent user bubble. */

import { IconSourceDoc } from "./icons";
import { SOURCE_LABEL } from "./domain/sourceCopy";

export type SourcePlaqueKind = "md" | "txt" | "pdf" | "docx" | "paste";

type Props = {
  title: string;
  subtitle?: string;
  /** Original filename when known — drives MD/TXT badge. */
  fileName?: string;
  onOpen: () => void;
  /** Composer only — omit in chat history. */
  onDismiss?: () => void;
  disabled?: boolean;
};

export function resolveSourceKind(
  fileName?: string,
  title?: string,
): SourcePlaqueKind {
  const name = (fileName || title || "").trim();
  if (/\.(md|markdown)$/i.test(name)) return "md";
  if (/\.txt$/i.test(name)) return "txt";
  if (/\.pdf$/i.test(name)) return "pdf";
  if (/\.(docx?|docm|rtf)$/i.test(name)) return "docx";
  if (
    !fileName &&
    (/^текст(\s+запроса)?$/i.test(name) || name === "Текст" || name === "Текст запроса")
  ) {
    return "paste";
  }
  if (fileName) return "txt";
  return "paste";
}

function kindLabel(kind: SourcePlaqueKind): string {
  if (kind === "md") return "MD";
  if (kind === "txt") return "TXT";
  if (kind === "pdf") return "PDF";
  if (kind === "docx") return "DOC";
  return SOURCE_LABEL;
}

function displayTitle(title: string, kind: SourcePlaqueKind): string {
  if (kind === "paste" && /^текст(\s+запроса)?$/i.test(title.trim())) {
    return "Вставленный текст";
  }
  return title;
}

export function ContextPlaque({
  title,
  subtitle,
  fileName,
  onOpen,
  onDismiss,
  disabled = false,
}: Props) {
  const kind = resolveSourceKind(fileName, title);
  const shown = displayTitle(title, kind);
  const badge = kindLabel(kind);
  const tip = subtitle ? `${shown} · ${subtitle}` : shown;

  return (
    <div
      className={`context-plaque is-${kind}`}
      role="region"
      aria-label={`Источник: ${shown}`}
    >
      <button
        type="button"
        className={`context-plaque-main${onDismiss ? "" : " is-solo"}`}
        onClick={onOpen}
        disabled={disabled}
        title={tip}
      >
        <span className="context-plaque-tile" aria-hidden>
          <IconSourceDoc kind={kind} size={17} />
          <span className="context-plaque-badge">{badge}</span>
        </span>
        <span className="context-plaque-copy">
          <span className="context-plaque-eyebrow">{SOURCE_LABEL}</span>
          <span className="context-plaque-title">{shown}</span>
          {subtitle ? (
            <span className="context-plaque-meta">{subtitle}</span>
          ) : null}
        </span>
        {!onDismiss ? (
          <span className="context-plaque-open" aria-hidden>
            ›
          </span>
        ) : null}
      </button>
      {onDismiss ? (
        <button
          type="button"
          className="context-plaque-x"
          aria-label="Убрать источник"
          title="Убрать источник"
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
        >
          ×
        </button>
      ) : null}
    </div>
  );
}
