/** Quiet empty-home starters under the sheet composer (all Liber modes). */

import type { LiberWorkMode } from "./domain/liberModes";

export type ModeStarter = {
  id: string;
  title: string;
  /** Short human line on the card. */
  blurb: string;
  /** Fills the composer on pick. */
  prompt: string;
};

export const REPORT_STARTERS: ModeStarter[] = [
  {
    id: "kpi-quarter",
    title: "Квартальный KPI",
    blurb: "Таблица KPI и один спокойный график по данным.",
    prompt:
      "Собери отчёт по материалу: таблица показателей за период, один линейный график динамики, спокойная деловая палитра, без выдуманных цифр.",
  },
  {
    id: "budget-mix",
    title: "Бюджет и доли",
    blurb: "Доли бюджета и краткие выводы по ключевым числам.",
    prompt:
      "Отчёт по распределению показателей: краткие выводы и кольцевая диаграмма долей только по переданным числам.",
  },
  {
    id: "exec-brief",
    title: "Краткий бриф",
    blurb: "3–5 выводов и одна таблица — без воды.",
    prompt:
      "Короткий управленческий отчёт: 3–5 главных выводов и одна сводная таблица из материала, без лишней воды.",
  },
  {
    id: "compare-periods",
    title: "Сравнение периодов",
    blurb: "Дельты между периодами и один сравнительный график.",
    prompt:
      "Сравни периоды по материалу: таблица отклонений и один сравнительный столбчатый график, только проверенные факты.",
  },
];

export const DIAGRAM_STARTERS: ModeStarter[] = [
  {
    id: "process-flow",
    title: "Процесс",
    blurb: "Этапы слева направо — наглядная схема.",
    prompt:
      "Нарисуй схему процесса из описания: этапы слева направо, наглядно и понятно.",
  },
  {
    id: "system-arch",
    title: "Архитектура",
    blurb: "Клиент → API → данные с короткими подписями.",
    prompt:
      "Схема компонентов системы: клиент → API → данные. Подписи короткие и точные.",
  },
  {
    id: "decision-tree",
    title: "Решение",
    blurb: "Условия и ветки из текста, без лишних шагов.",
    prompt:
      "Схема принятия решения: условия и ветки из текста, без выдуманных шагов.",
  },
  {
    id: "swimlane",
    title: "Роли и шаги",
    blurb: "Кто что делает — схема по ролям из описания.",
    prompt:
      "Схема с ролями (кто что делает) по тексту описания.",
  },
];

export const PRESENTATION_STARTERS: ModeStarter[] = [
  {
    id: "board-update",
    title: "Обновление совету",
    blurb: "KPI + 1 график + ключевые выводы.",
    prompt:
      "Собери презентацию для совета по материалу: KPI-слайды, один график, короткие выводы, спокойная палитра, без выдуманных цифр.",
  },
  {
    id: "funnel-pilot",
    title: "Воронка пилота",
    blurb: "Лиды → конверсия по городам и метрики.",
    prompt:
      "Презентация воронки по материалу: таблица по городам, график показателей, без выдуманных метрик.",
  },
  {
    id: "quarter-review",
    title: "Квартальный обзор",
    blurb: "Тренд + доли + следующие шаги.",
    prompt:
      "Квартальный обзор: тренд по неделям, диаграмма долей, слайд дальнейших шагов — строго по фактам.",
  },
  {
    id: "pitch-short",
    title: "Короткий питч",
    blurb: "Проблема → решение → цифры → призыв к действию.",
    prompt:
      "Короткий питч: проблема → решение → ключевые цифры → следующий шаг. Спокойный стиль, без воды.",
  },
];

export function startersForMode(mode: LiberWorkMode): ModeStarter[] {
  if (mode === "report") return REPORT_STARTERS;
  if (mode === "diagram") return DIAGRAM_STARTERS;
  if (mode === "presentation") return PRESENTATION_STARTERS;
  return [];
}
