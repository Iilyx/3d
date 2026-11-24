/** Liber desk defaults (no React). */

import type { PaletteInfo } from "./liberTypes";

export const LONG_TEXT_CHARS = 400;

export const DEFAULT_INTENT =
  "Оформи понятный русскоязычный отчёт: структура, таблицы где уместны числа.";

export const FALLBACK_TYPES = [
  "bar",
  "grouped_bar",
  "stacked_bar",
  "line",
  "horizontal_bar",
  "donut",
  "kpi",
  "area",
  "scatter",
] as const;

export const STAGE_LABELS: Record<string, string> = {
  queued: "В очереди…",
  llm: "Думаю над структурой…",
  diagram_repair: "Уточняю схему…",
  charts: "Рисую графики…",
  images: "Готовлю иллюстрации…",
  inject: "Вставляю рисунки в текст…",
  latex: "Собираю PDF…",
  docx: "Собираю DOCX…",
  summary: "Краткое описание…",
  ok: "Готово",
  error: "Ошибка",
};

/** Offline palette chips when /api/health has not answered yet. */
export const FALLBACK_PALETTES: PaletteInfo[] = [
  { id: "auto", label: "Auto", swatches: ["#2E4208", "#F07A3A", "#0B4F8C", "#FF8C2A"] },
  { id: "atelier", label: "Atelier", swatches: ["#2E4208", "#4F6B14", "#7A9A28", "#B8D45A"] },
  { id: "editorial", label: "Editorial", swatches: ["#0F3D3E", "#F07A3A", "#2EC4B6", "#E8B84A"] },
  { id: "ocean", label: "Ocean", swatches: ["#0B4F8C", "#1E8AD4", "#2EC4E0", "#5ED4F0"] },
  { id: "sunset", label: "Sunset", swatches: ["#EE6677", "#CCBB44", "#4477AA", "#228833"] },
  { id: "mono", label: "Mono", swatches: ["#1A1F28", "#3A4250", "#8B939E", "#B0B6BE"] },
];
