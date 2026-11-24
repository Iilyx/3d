import { useEffect, useRef } from "react";
import { useFocusTrap } from "./useFocusTrap";

export type LayoutOption = {
  id: string;
  name: string;
  icon: string;
  desc: string;
};

export const LAYOUT_OPTIONS: LayoutOption[] = [
  { id: "bullets", name: "Тезисы (список)", icon: "📝", desc: "Заголовок и список ключевых тезисов" },
  { id: "section", name: "Раздел (глава)", icon: "📑", desc: "Титул главы с крупным номером и описанием" },
  { id: "callout", name: "Ключевой тезис", icon: "💡", desc: "Акцентная карточка с термином и определением" },
  { id: "quote", name: "Цитата / позиция", icon: "💬", desc: "Фокусная мысль спикера или эксперта" },
  { id: "scorecard", name: "Сводка показателей", icon: "📊", desc: "Сетка ключевых KPI с дельтами и статусами" },
  { id: "stat_hero", name: "Главная цифра", icon: "🎯", desc: "Крупная якорная метрика и выводы" },
  { id: "compare", name: "Сравнение 2 сторон", icon: "⚖️", desc: "Две контрастные карточки (За vs Против / Модели)" },
  { id: "card_row", name: "3 направления", icon: "🗂", desc: "Три параллельных трека с описанием" },
  { id: "table_hero", name: "Таблица", icon: "📋", desc: "Сводная таблица параметров и статусов" },
  { id: "timeline", name: "Таймлайн (этапы)", icon: "⏳", desc: "Дорожная карта реализации по шагам" },
  { id: "closing", name: "Финальный слайд", icon: "🏁", desc: "Главный вердикт и следующие шаги" },
];

type Props = {
  open: boolean;
  onClose: () => void;
  onPick: (layout: string) => void;
  afterSlideNum?: number;
};

export function LayoutPickerModal({
  open,
  onClose,
  onPick,
  afterSlideNum,
}: Props) {
  const modalRef = useRef<HTMLDivElement>(null);
  useFocusTrap(modalRef, { active: open });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="presentation-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="layout-picker-title"
      onClick={onClose}
    >
      <div
        ref={modalRef}
        className="presentation-layout-picker"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="presentation-layout-picker-head">
          <div>
            <h3 id="layout-picker-title" className="presentation-layout-picker-title">
              Добавить слайд
            </h3>
            <p className="presentation-layout-picker-sub">
              {afterSlideNum != null
                ? `Выберите макет для вставки после слайда ${afterSlideNum}`
                : "Выберите макет нового слайда"}
            </p>
          </div>
          <button
            type="button"
            className="presentation-layout-picker-close"
            onClick={onClose}
            aria-label="Закрыть"
            title="Закрыть (Esc)"
          >
            ×
          </button>
        </header>

        <div className="presentation-layout-picker-grid">
          {LAYOUT_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className="presentation-layout-opt"
              onClick={() => {
                onPick(opt.id);
                onClose();
              }}
            >
              <span className="presentation-layout-opt-icon" aria-hidden>
                {opt.icon}
              </span>
              <div className="presentation-layout-opt-info">
                <span className="presentation-layout-opt-name">{opt.name}</span>
                <span className="presentation-layout-opt-desc">{opt.desc}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
