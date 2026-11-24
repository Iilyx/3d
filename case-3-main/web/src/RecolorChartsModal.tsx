/** Modal dialog to batch recolor all charts in the document to a new palette. */

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { FALLBACK_PALETTES } from "./domain/liberConstants";
import type { PaletteInfo } from "./domain/liberTypes";
import { useFocusTrap } from "./useFocusTrap";

type Props = {
  open: boolean;
  currentPalette?: string;
  palettes?: PaletteInfo[];
  busy?: boolean;
  onCancel: () => void;
  onApply: (paletteId: string) => void;
};

export function RecolorChartsModal({
  open,
  currentPalette = "atelier",
  palettes = FALLBACK_PALETTES,
  busy = false,
  onCancel,
  onApply,
}: Props) {
  const [selected, setSelected] = useState(currentPalette);
  const modalRef = useRef<HTMLDivElement>(null);

  useFocusTrap(modalRef, { active: open });

  useEffect(() => {
    if (open) {
      setSelected(currentPalette || "atelier");
    }
  }, [open, currentPalette]);

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    },
    [onCancel],
  );

  if (!open) return null;

  // Filter out 'auto' from batch recolor options
  const list = palettes.filter((p) => p.id !== "auto");

  return (
    <div
      className="recolor-charts-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Перекрасить графики"
      onKeyDown={onKeyDown}
    >
      <div className="recolor-charts-modal" ref={modalRef}>
        <header className="recolor-charts-header">
          <div className="recolor-charts-titles">
            <h3 className="recolor-charts-title">Перекрасить все графики</h3>
            <p className="recolor-charts-subtitle muted">
              Применить цветовую тему ко всем графикам документа мгновенно без вызова ИИ
            </p>
          </div>
          <button
            type="button"
            className="btn ghost icon-only recolor-charts-close"
            onClick={onCancel}
            disabled={busy}
            aria-label="Закрыть"
            title="Закрыть (Esc)"
          >
            ✕
          </button>
        </header>

        <div className="recolor-charts-body">
          <div className="recolor-charts-grid" role="radiogroup" aria-label="Палитры графиков">
            {list.map((pal) => {
              const isSelected = pal.id === selected;
              return (
                <button
                  key={pal.id}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  className={`recolor-palette-card${isSelected ? " is-selected" : ""}`}
                  onClick={() => setSelected(pal.id)}
                  disabled={busy}
                >
                  <div className="recolor-palette-header">
                    <span className="recolor-palette-name">{pal.label}</span>
                    {isSelected ? (
                      <span className="recolor-palette-check" aria-hidden>
                        ✓
                      </span>
                    ) : null}
                  </div>
                  <div className="recolor-palette-swatches" aria-hidden>
                    {pal.swatches.map((color, idx) => (
                      <span
                        key={idx}
                        className="recolor-palette-swatch"
                        style={{ background: color }}
                      />
                    ))}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <footer className="recolor-charts-footer">
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
            onClick={() => onApply(selected)}
            disabled={busy}
          >
            {busy ? "Перекрашивание…" : "Применить ко всем графикам"}
          </button>
        </footer>
      </div>
    </div>
  );
}
