/** Liber desk: edit one report paragraph — plain text → TeX patch. */

import { useEffect, useId, useRef, useState } from "react";
import { submitChord } from "./domain/undoChord";
import { useFocusTrap } from "./useFocusTrap";

export type ParagraphEditRequest = {
  paragraphIndex: number;
  text: string;
};

type Props = {
  open: boolean;
  /** When false, skip focus trap (multi-open edit desk). */
  trapFocus?: boolean;
  paragraphIndex: number;
  initialText?: string;
  busy?: boolean;
  error?: string | null;
  onCancel: () => void;
  onSubmit: (req: ParagraphEditRequest) => void;
};

export function ParagraphEditSheet({
  open,
  trapFocus = true,
  paragraphIndex,
  initialText = "",
  busy,
  error,
  onCancel,
  onSubmit,
}: Props) {
  const [text, setText] = useState(initialText);
  const sheetRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const uid = useId();
  useFocusTrap(sheetRef, { active: open && trapFocus });

  useEffect(() => {
    if (!open) return;
    setText(initialText || "");
    const t = window.setTimeout(() => areaRef.current?.focus(), 40);
    return () => window.clearTimeout(t);
  }, [open, paragraphIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;

  function apply() {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSubmit({ paragraphIndex, text: trimmed });
  }

  return (
    <div
      ref={sheetRef}
      className="chart-edit-sheet paragraph-edit-sheet"
      role="region"
      aria-label="Изменить абзац"
    >
      <header className="chart-edit-head">
        <div>
          <p className="chart-edit-eyebrow">Редактирование абзаца</p>
          <h3 className="chart-edit-title">Абзац {paragraphIndex}</h3>
        </div>
        <button
          type="button"
          className="chart-edit-x"
          onClick={onCancel}
          disabled={busy}
          aria-label="Закрыть"
        >
          ×
        </button>
      </header>

      <section className="chart-edit-block">
        <label className="field" htmlFor={`para-text-${uid}`}>
          Текст
        </label>
        <textarea
          ref={areaRef}
          id={`para-text-${uid}`}
          className="paragraph-edit-area"
          rows={6}
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !busy) {
              e.preventDefault();
              apply();
            }
          }}
        />
        <p className="chart-edit-style-hint">
          {submitChord()} сохранить · только этот абзац · числа не выдумывать
        </p>
      </section>

      {error && <p className="err">{error}</p>}

      <footer className="chart-edit-foot">
        <p className="chart-edit-foot-hint">
          «Сохранить в отчёт» обновит абзац и пересоберёт PDF и Word.
        </p>
        <div className="chart-edit-actions">
          <button
            type="button"
            className="chart-edit-apply"
            disabled={busy || !text.trim()}
            onClick={apply}
          >
            {busy ? "Пересобираю…" : "Сохранить в отчёт"}
          </button>
          <button
            type="button"
            className="chart-edit-cancel"
            disabled={busy}
            onClick={onCancel}
          >
            Отмена
          </button>
        </div>
      </footer>
    </div>
  );
}
