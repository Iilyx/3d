/** Universal Mermaid code editor modal: edit raw source for any diagram type. */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { MermaidView } from "./MermaidView";
import {
  cleanMermaidCode,
  validateMermaidHeader,
} from "./domain/diagramCodeModal";
import { useFocusTrap } from "./useFocusTrap";

type Props = {
  open: boolean;
  diagramId: string;
  title: string;
  mermaid: string;
  busy?: boolean;
  error?: string | null;
  onCancel: () => void;
  onSave: (mermaid: string, title: string) => void;
};

export function DiagramCodeModal({
  open,
  diagramId,
  title: initialTitle,
  mermaid: initialMermaid,
  busy = false,
  error = null,
  onCancel,
  onSave,
}: Props) {
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [renderError, setRenderError] = useState<string | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useFocusTrap(modalRef, { active: open });

  useEffect(() => {
    if (!open) return;
    setCode(cleanMermaidCode(initialMermaid));
    setTitle((initialTitle || "").trim());
    setRenderError(null);
  }, [open, initialMermaid, initialTitle]);

  const validation = validateMermaidHeader(code);

  const doSave = useCallback(() => {
    if (busy || !validation.ok) return;
    const clean = cleanMermaidCode(code);
    onSave(clean, title.trim() || initialTitle || diagramId);
  }, [busy, code, diagramId, initialTitle, onSave, title, validation.ok]);

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        doSave();
      }
    },
    [doSave, onCancel],
  );

  const onTextareaKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Tab") {
        e.preventDefault();
        const el = e.currentTarget;
        const start = el.selectionStart;
        const end = el.selectionEnd;
        const next = code.slice(0, start) + "  " + code.slice(end);
        setCode(next);
        requestAnimationFrame(() => {
          el.selectionStart = el.selectionEnd = start + 2;
        });
      }
    },
    [code],
  );

  if (!open) return null;

  return (
    <div
      className="diagram-code-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Редактировать код схемы Mermaid"
      onKeyDown={onKeyDown}
    >
      <div className="diagram-code-modal" ref={modalRef}>
        <header className="diagram-code-modal-header">
          <div className="diagram-code-modal-titles">
            <span className="diagram-code-modal-badge">Mermaid</span>
            <input
              type="text"
              className="diagram-code-modal-title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Название схемы"
              disabled={busy}
            />
          </div>
          <button
            type="button"
            className="btn ghost icon-only diagram-code-modal-close"
            onClick={onCancel}
            disabled={busy}
            aria-label="Закрыть"
            title="Закрыть (Esc)"
          >
            ✕
          </button>
        </header>

        {error ? (
          <div className="diagram-code-modal-alert is-error" role="alert">
            {error}
          </div>
        ) : null}

        {!validation.ok ? (
          <div className="diagram-code-modal-alert is-warn" role="alert">
            {validation.error}
          </div>
        ) : null}

        <div className="diagram-code-modal-body">
          <div className="diagram-code-modal-pane is-editor">
            <label className="diagram-code-modal-label" htmlFor="mermaid-editor">
              Исходный код схемы
            </label>
            <textarea
              id="mermaid-editor"
              ref={textareaRef}
              className="diagram-code-modal-textarea"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={onTextareaKeyDown}
              disabled={busy}
              spellCheck={false}
              autoCapitalize="off"
              autoComplete="off"
            />
            <p className="diagram-code-modal-hint muted">
              Поддерживаются: flowchart, sequenceDiagram, mindmap, timeline, stateDiagram. Tab добавляет отступ.
            </p>
          </div>

          <div className="diagram-code-modal-pane is-preview">
            <div className="diagram-code-modal-preview-bar">
              <span className="diagram-code-modal-label">Предпросмотр</span>
              {renderError ? (
                <span className="diagram-code-modal-syntax-err">Ошибка синтаксиса</span>
              ) : (
                <span className="diagram-code-modal-syntax-ok">Синтаксис корректен</span>
              )}
            </div>
            <div className="diagram-code-modal-preview-canvas">
              {validation.ok ? (
                <MermaidView
                  source={cleanMermaidCode(code)}
                  onError={setRenderError}
                />
              ) : (
                <div className="diagram-code-modal-preview-placeholder">
                  Введите корректный заголовок Mermaid
                </div>
              )}
            </div>
          </div>
        </div>

        <footer className="diagram-code-modal-footer">
          <span className="diagram-code-modal-hotkey-hint muted">
            Cmd/Ctrl + Enter для сохранения
          </span>
          <div className="diagram-code-modal-footer-actions">
            <button
              type="button"
              className="btn ghost"
              onClick={onCancel}
              disabled={busy}
            >
              Отмена
            </button>
            <button
              type="button"
              className="btn primary"
              onClick={doSave}
              disabled={busy || !validation.ok}
            >
              {busy ? "Сохранение…" : "Сохранить схему"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
