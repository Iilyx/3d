/** Liber empty hero — modes live in composer inner bar. */

import { motion, useReducedMotion } from "framer-motion";
import type { LiberWorkMode } from "./domain/liberModes";

type Props = {
  hasStoredReport?: boolean;
  onRestore?: () => void;
  workMode?: LiberWorkMode;
  onOpenDashboard?: () => void;
  onPickFile?: () => void;
};

export function EmptyState({
  workMode = null,
  onOpenDashboard,
  onPickFile,
}: Props) {
  const reduce = useReducedMotion();
  const title =
    workMode === "presentation"
      ? "Какую презентацию соберём?"
      : workMode === "diagram"
        ? "Какую схему нарисовать?"
        : workMode === "report"
          ? "Какой отчёт собрать?"
          : "Чем могу помочь?";
  const showQuickEntry = workMode === null && (onOpenDashboard || onPickFile);
  return (
    <motion.div
      className="empty empty-hero"
      key={`empty-${workMode || "auto"}`}
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduce ? 0 : 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      <h2>{title}</h2>
      {showQuickEntry ? (
        <div className="empty-actions" role="group" aria-label="Быстрый старт">
          {onOpenDashboard ? (
            <button
              type="button"
              className="empty-action-btn is-primary"
              onClick={onOpenDashboard}
            >
              Выбрать дашборд Stimulsoft
            </button>
          ) : null}
          {onPickFile ? (
            <button
              type="button"
              className="empty-action-btn"
              onClick={onPickFile}
            >
              Загрузить документ (PDF / DOCX / MD)
            </button>
          ) : null}
        </div>
      ) : null}
    </motion.div>
  );
}
