/** Deck-only style sheet — packs + hex + fonts + live preview. */

import { useEffect, useId, useRef } from "react";
import {
  DECK_FONT_OPTIONS,
  FALLBACK_DECK_PACKS,
  applyPackToStyle,
  type DeckStyle,
  type DeckThemePackInfo,
} from "./deckStyle";
import { DeckStylePreview } from "./DeckStylePreview";
import { useFocusTrap } from "./useFocusTrap";

type Props = {
  open: boolean;
  style: DeckStyle;
  packs?: DeckThemePackInfo[];
  onChange: (next: DeckStyle) => void;
  onClose: () => void;
  onSave?: (style: DeckStyle) => void;
};

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="deck-style-color">
      <span>{label}</span>
      <span className="deck-style-color-row">
        <input
          type="color"
          value={value.length === 7 ? value : "#000000"}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          aria-label={label}
        />
        <input
          type="text"
          value={value}
          spellCheck={false}
          onChange={(e) => onChange(e.target.value)}
        />
      </span>
    </label>
  );
}

export function DeckStyleSheet({
  open,
  style,
  packs = FALLBACK_DECK_PACKS,
  onChange,
  onClose,
  onSave,
}: Props) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, { active: open });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  const usable = packs.length ? packs : FALLBACK_DECK_PACKS;

  return (
    <div
      ref={dialogRef}
      className="deck-style-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="deck-style-sheet-panel">
        <header className="deck-style-sheet-head">
          <div>
            <p className="deck-style-eyebrow">презентация · стиль</p>
            <h2 id={titleId}>Стиль презентации</h2>
            <p className="deck-style-hint">
              Только для слайдов и презентации. Отчёт PDF/DOCX не меняется.
            </p>
          </div>
          <div className="deck-style-sheet-actions">
            <button
              type="button"
              className="deck-style-ghost"
              onClick={() => {
                const pack =
                  usable.find((p) => p.id === "atelier") || usable[0];
                if (pack) onChange(applyPackToStyle(pack, style));
              }}
            >
              Сбросить
            </button>
            <button
              type="button"
              className="deck-style-save"
              onClick={() => {
                onSave?.(style);
                onClose();
              }}
            >
              Сохранить стиль
            </button>
            <button
              type="button"
              className="deck-style-x"
              onClick={onClose}
              aria-label="Закрыть"
            >
              ×
            </button>
          </div>
        </header>

        <div className="deck-style-sheet-body">
          <div className="deck-style-controls">
            <div className="deck-style-packs" role="group" aria-label="Шаблон стиля">
              {usable.map((p) => {
                const on = style.themePack === p.id;
                const bg = p.swatches[2] || p.swatches[0] || "#f0ede4";
                const ink = p.swatches[3] || "#14161a";
                const accent = p.swatches[1] || p.swatches[0] || "#4F6B14";
                return (
                  <button
                    key={p.id}
                    type="button"
                    className={`deck-style-pack-card${on ? " on" : ""}`}
                    onClick={() => onChange(applyPackToStyle(p, style))}
                    aria-pressed={on}
                  >
                    <span
                      className={`deck-style-pack-thumb${p.id === "botanical" ? " is-botanical" : ""}${p.id === "relay" || p.id === "pastel" ? " is-split" : ""}${p.id === "ink" || p.id === "voltage" ? " is-ink" : ""}`}
                      style={{
                        background: bg,
                        color: ink,
                        ["--pack-accent" as string]: accent,
                      }}
                    >
                      <span className="deck-style-pack-thumb-bar" />
                      <span className="deck-style-pack-thumb-kicker">{p.label}</span>
                      <span className="deck-style-pack-thumb-title">
                        {p.id === "botanical"
                          ? "Мягкий финал"
                          : p.id === "voltage"
                            ? "Быстрый старт"
                            : p.id === "studio"
                              ? "Рабочая сессия"
                              : p.id === "ink"
                                ? "Сигнал роста"
                                : p.id === "relay"
                                  ? "Итоги квартала"
                                  : p.id === "signal"
                                    ? "Главный тезис"
                                    : p.id === "atelier"
                                      ? "Неделя запуска"
                                      : "Отчёт совету"}
                      </span>
                      {p.id === "botanical" ? (
                        <span className="deck-style-pack-thumb-fern" aria-hidden />
                      ) : (
                        <span className="deck-style-pack-thumb-panel" />
                      )}
                    </span>
                    <span className="deck-style-pack-meta">
                      <span className="deck-style-pack-swatches">
                        {p.swatches.slice(0, 4).map((c) => (
                          <i key={c} style={{ background: c }} />
                        ))}
                      </span>
                      <span className="deck-style-pack-name">{p.label}</span>
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="deck-style-colors">
              <ColorField
                label="Основной"
                value={style.primary}
                onChange={(primary) =>
                  onChange({ ...style, primary, presetId: "custom" })
                }
              />
              <ColorField
                label="Акцент"
                value={style.accent}
                onChange={(accent) =>
                  onChange({ ...style, accent, presetId: "custom" })
                }
              />
              <ColorField
                label="Фон"
                value={style.background}
                onChange={(background) =>
                  onChange({ ...style, background, presetId: "custom" })
                }
              />
              <ColorField
                label="Текст"
                value={style.text}
                onChange={(text) =>
                  onChange({ ...style, text, presetId: "custom" })
                }
              />
            </div>

            <div className="deck-style-fonts">
              <label>
                <span>Заголовок</span>
                <select
                  value={style.fontTitle}
                  onChange={(e) =>
                    onChange({
                      ...style,
                      fontTitle: e.target.value,
                      presetId: "custom",
                    })
                  }
                >
                  {DECK_FONT_OPTIONS.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Текст</span>
                <select
                  value={style.fontBody}
                  onChange={(e) =>
                    onChange({
                      ...style,
                      fontBody: e.target.value,
                      presetId: "custom",
                    })
                  }
                >
                  {DECK_FONT_OPTIONS.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          <DeckStylePreview style={style} />
        </div>
      </div>
    </div>
  );
}
