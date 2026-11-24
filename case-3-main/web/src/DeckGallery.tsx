/** Julius-style Preview grid — all slides at once + structure DnD. */

import { motion } from "framer-motion";
import { useState, type DragEvent } from "react";

export type DeckGalleryItem = {
  id: string;
  url: string | null;
  title: string;
};

type Props = {
  items: DeckGalleryItem[];
  activeIndex: number;
  onSelect: (index: number) => void;
  canStructure?: boolean;
  onReorder?: (from: number, to: number) => void;
  onDuplicate?: (index: number) => void;
  onDelete?: (index: number) => void;
  onAddSlide?: (afterIndex?: number) => void;
};

function armSlideDrag(e: DragEvent, index: number): void {
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", String(index));
}

export function DeckGallery({
  items,
  activeIndex,
  onSelect,
  canStructure = false,
  onReorder,
  onDuplicate,
  onDelete,
  onAddSlide,
}: Props) {
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  if (!items.length) return null;
  const canDrag = canStructure && Boolean(onReorder);
  return (
    <div className="deck-gallery" role="list" aria-label="Все слайды">
      {items.map((item, i) => {
        const label = item.title.trim() || `Слайд ${i + 1}`;
        return (
          <div
            key={item.id}
            role="listitem"
            className={`deck-gallery-card${i === activeIndex ? " is-active" : ""}${dragFrom === i ? " is-dragging" : ""}`}
            draggable={canDrag}
            onDragStart={(e) => {
              if (!canDrag) return;
              armSlideDrag(e, i);
              setDragFrom(i);
            }}
            onDragEnd={() => setDragFrom(null)}
            onDragOver={(e) => {
              if (canDrag) e.preventDefault();
            }}
            onDrop={(e) => {
              e.preventDefault();
              const raw = e.dataTransfer.getData("text/plain");
              const from =
                raw !== "" && Number.isFinite(Number(raw))
                  ? Number(raw)
                  : dragFrom;
              if (from != null && onReorder) onReorder(from, i);
              setDragFrom(null);
            }}
            title={canDrag ? `${label} · перетащите для порядка` : label}
          >
            <div
              className="deck-gallery-hit"
              role="button"
              tabIndex={0}
              onClick={() => onSelect(i)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(i);
                }
              }}
            >
              <span className="deck-gallery-frame">
                {item.url ? (
                  <img src={item.url} alt={label} draggable={false} />
                ) : (
                  <span className="deck-gallery-ghost">{label}</span>
                )}
                <span className="deck-gallery-num">
                  {String(i + 1).padStart(2, "0")}
                </span>
              </span>
              <span className="deck-gallery-caption">
                <span className="deck-gallery-caption-title">{label}</span>
              </span>
            </div>
            {canStructure && (onDuplicate || onDelete) ? (
              <div className="deck-gallery-ops" role="group" aria-label="Слайд">
                {onDuplicate ? (
                  <button
                    type="button"
                    className="deck-gallery-op"
                    title="Дублировать"
                    draggable={false}
                    onMouseDown={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.stopPropagation();
                      onDuplicate(i);
                    }}
                  >
                    +
                  </button>
                ) : null}
                {onDelete ? (
                  <button
                    type="button"
                    className="deck-gallery-op is-danger"
                    title="Удалить"
                    draggable={false}
                    onMouseDown={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(i);
                    }}
                  >
                    ×
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        );
      })}
      {canStructure && onAddSlide ? (
        <motion.div
          role="listitem"
          className="deck-gallery-card deck-gallery-card--add"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: 0.28,
            delay: Math.min(items.length * 0.03, 0.35),
            ease: [0.22, 1, 0.36, 1],
          }}
          whileHover={{ y: -2 }}
        >
          <button
            type="button"
            className="deck-gallery-add-btn"
            onClick={() => onAddSlide(items.length - 1)}
            title="Добавить новый слайд"
          >
            <span className="deck-gallery-add-frame">
              <span className="deck-gallery-add-icon" aria-hidden>+</span>
            </span>
            <span className="deck-gallery-caption">
              <span className="deck-gallery-caption-title">Добавить слайд</span>
            </span>
          </button>
        </motion.div>
      ) : null}
    </div>
  );
}
