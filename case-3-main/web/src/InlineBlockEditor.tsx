/** Compact inline editor for one active preview prose / heading / list block. */

import { useEffect, useRef, useState } from "react";
import { submitChord } from "./domain/undoChord";

type Common = {
  busy?: boolean;
  error?: string | null;
  saveLabel?: string;
  onCancel?: () => void;
  onDelete?: () => void;
  autoFocus?: boolean;
  /** Hide Save/Cancel row — blur / Enter / ⌘↵ still apply. */
  hideActions?: boolean;
};

type ProseProps = Common & {
  kind: "paragraph" | "heading";
  initialText: string;
  rows?: number;
  onSave: (text: string) => void;
};

type ListProps = Common & {
  kind: "list";
  initialItems: string[];
  ordered?: boolean;
  onSave: (items: string[]) => void;
};

export type InlineBlockEditorProps = ProseProps | ListProps;

export function InlineBlockEditor(props: InlineBlockEditorProps) {
  if (props.kind === "list") {
    return <ListInline {...props} />;
  }
  return <ProseInline {...props} />;
}

function ProseInline({
  kind,
  initialText,
  rows = kind === "heading" ? 1 : 5,
  busy,
  error,
  saveLabel = "Сохранить",
  onSave,
  onCancel,
  onDelete,
  autoFocus = true,
  hideActions = false,
}: ProseProps) {
  const [text, setText] = useState(initialText);
  const headingRef = useRef<HTMLInputElement | null>(null);
  const paraRef = useRef<HTMLTextAreaElement | null>(null);
  const skipBlurRef = useRef(false);
  useEffect(() => {
    setText(initialText);
  }, [initialText]);
  useEffect(() => {
    if (!autoFocus) return;
    const el = kind === "heading" ? headingRef.current : paraRef.current;
    el?.focus({ preventScroll: true });
  }, [autoFocus, kind]);

  const dirty = text.trim() !== (initialText || "").trim();

  const commit = () => {
    const t = text.trim();
    if (!dirty || busy) return;
    if (!t) {
      if (onDelete) {
        skipBlurRef.current = true;
        onDelete();
      }
      return;
    }
    skipBlurRef.current = true;
    onSave(t);
  };

  const discard = () => {
    skipBlurRef.current = true;
    setText(initialText);
    onCancel?.();
  };

  const onBlurCommit = () => {
    if (skipBlurRef.current) {
      skipBlurRef.current = false;
      return;
    }
    if (dirty && !busy) {
      if (text.trim()) commit();
      else if (onDelete) onDelete();
      else onCancel?.();
    } else if (!busy) {
      onCancel?.();
    }
  };

  return (
    <div className={`inline-block-editor is-${kind}${busy ? " is-busy" : ""}`}>
      {kind === "heading" ? (
        <input
          ref={headingRef}
          className="inline-block-input is-heading"
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          onBlur={onBlurCommit}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              e.stopPropagation();
              discard();
              return;
            }
            if (e.key === "Enter" && dirty && !busy) {
              e.preventDefault();
              commit();
            }
          }}
        />
      ) : (
        <textarea
          ref={paraRef}
          className="inline-block-input is-paragraph"
          rows={rows}
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          onBlur={onBlurCommit}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              e.stopPropagation();
              discard();
              return;
            }
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && dirty && !busy) {
              e.preventDefault();
              commit();
            }
          }}
        />
      )}
      {hideActions ? (
        <div className="inline-block-hint-row">
          <p className="inline-block-hint is-solo">
            {kind === "paragraph" ? `${submitChord()} · Esc · клик вне поля` : "Enter · Esc · клик вне поля"}
          </p>
          {onDelete && (
            <button
              type="button"
              className="inline-block-delete-link"
              title="Удалить блок"
              disabled={busy}
              onMouseDown={() => {
                skipBlurRef.current = true;
              }}
              onClick={() => {
                skipBlurRef.current = true;
                onDelete();
              }}
            >
              Удалить
            </button>
          )}
        </div>
      ) : (
        <div className="inline-block-actions">
          <button
            type="button"
            className="inline-block-save"
            disabled={busy || !dirty || (!text.trim() && !onDelete)}
            onMouseDown={() => {
              skipBlurRef.current = true;
            }}
            onClick={commit}
          >
            {busy ? "Сохраняю…" : !text.trim() && onDelete ? "Удалить" : saveLabel}
          </button>
          <button
            type="button"
            className="inline-block-cancel"
            disabled={busy}
            onMouseDown={() => {
              skipBlurRef.current = true;
            }}
            onClick={discard}
          >
            Отмена
          </button>
          {onDelete && (
            <button
              type="button"
              className="inline-block-delete"
              disabled={busy}
              onMouseDown={() => {
                skipBlurRef.current = true;
              }}
              onClick={() => {
                skipBlurRef.current = true;
                onDelete();
              }}
            >
              Удалить
            </button>
          )}
          {kind === "paragraph" ? (
            <span className="inline-block-hint">{submitChord()} · Esc</span>
          ) : (
            <span className="inline-block-hint">Enter · Esc</span>
          )}
        </div>
      )}
      {error ? <p className="err">{error}</p> : null}
    </div>
  );
}

function ListInline({
  initialItems,
  ordered,
  busy,
  error,
  saveLabel = "Сохранить",
  onSave,
  onCancel,
  onDelete,
  autoFocus = true,
  hideActions = false,
}: ListProps) {
  const seed = (initialItems || []).join("\n");
  const [text, setText] = useState(seed);
  const areaRef = useRef<HTMLTextAreaElement | null>(null);
  const skipBlurRef = useRef(false);
  useEffect(() => {
    setText((initialItems || []).join("\n"));
  }, [initialItems]);
  useEffect(() => {
    if (!autoFocus) return;
    areaRef.current?.focus({ preventScroll: true });
  }, [autoFocus]);
  const items = text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  const dirty = text.replace(/\s+$/, "") !== seed.replace(/\s+$/, "");

  const commit = () => {
    if (!dirty || busy) return;
    if (!items.length) {
      if (onDelete) {
        skipBlurRef.current = true;
        onDelete();
      }
      return;
    }
    skipBlurRef.current = true;
    onSave(items);
  };

  const discard = () => {
    skipBlurRef.current = true;
    setText(seed);
    onCancel?.();
  };

  const onBlurCommit = () => {
    if (skipBlurRef.current) {
      skipBlurRef.current = false;
      return;
    }
    if (dirty && !busy) {
      if (items.length) commit();
      else if (onDelete) onDelete();
      else onCancel?.();
    } else if (!busy) {
      onCancel?.();
    }
  };

  return (
    <div className={`inline-block-editor is-list${busy ? " is-busy" : ""}`}>
      <p className="inline-block-eyebrow">
        {ordered ? "Нумерованный список" : "Маркированный список"} · один пункт =
        строка
      </p>
      <textarea
        ref={areaRef}
        className="inline-block-input is-list"
        rows={Math.max(3, items.length + 1)}
        value={text}
        disabled={busy}
        onChange={(e) => setText(e.target.value)}
        onBlur={onBlurCommit}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            discard();
            return;
          }
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && dirty && !busy) {
            e.preventDefault();
            commit();
          }
        }}
      />
      {hideActions ? (
        <div className="inline-block-hint-row">
          <p className="inline-block-hint is-solo">{submitChord()} · Esc · клик вне поля</p>
          {onDelete && (
            <button
              type="button"
              className="inline-block-delete-link"
              title="Удалить список"
              disabled={busy}
              onMouseDown={() => {
                skipBlurRef.current = true;
              }}
              onClick={() => {
                skipBlurRef.current = true;
                onDelete();
              }}
            >
              Удалить
            </button>
          )}
        </div>
      ) : (
        <div className="inline-block-actions">
          <button
            type="button"
            className="inline-block-save"
            disabled={busy || !dirty || (!items.length && !onDelete)}
            onMouseDown={() => {
              skipBlurRef.current = true;
            }}
            onClick={commit}
          >
            {busy ? "Сохраняю…" : !items.length && onDelete ? "Удалить" : saveLabel}
          </button>
          <button
            type="button"
            className="inline-block-cancel"
            disabled={busy}
            onMouseDown={() => {
              skipBlurRef.current = true;
            }}
            onClick={discard}
          >
            Отмена
          </button>
          {onDelete && (
            <button
              type="button"
              className="inline-block-delete"
              disabled={busy}
              onMouseDown={() => {
                skipBlurRef.current = true;
              }}
              onClick={() => {
                skipBlurRef.current = true;
                onDelete();
              }}
            >
              Удалить
            </button>
          )}
          <span className="inline-block-hint">{submitChord()} · Esc</span>
        </div>
      )}
      {error ? <p className="err">{error}</p> : null}
    </div>
  );
}
