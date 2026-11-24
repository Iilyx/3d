/** Conversational pipeline phrases (templates — not LLM). Varied per run + output mode. */

export type ThinkingLine = {
  id: string;
  text: string;
  /** stage key that produced this line */
  stageKey: string;
};

/** Liber composer / run output mode for phrase pools. */
export type ThinkingMode = "report" | "diagram" | "presentation" | "chat";

const QUEUED_REPORT = [
  "Ок, беру задачу…",
  "Изучаю запрос и переданные материалы…",
  "Принял — раскладываю на столе…",
  "Запрос понятен, изучаю материал…",
  "Стартую: сначала сверю входные данные…",
  "Беру в работу, без спешки…",
  "Изучаю задачу и контекст…",
  "Поехали — сначала сверка фактов…",
];

const QUEUED_DIAGRAM = [
  "Ок, рисуем схему…",
  "Смотрю ключевые этапы и связи…",
  "Принял — набрасываю граф…",
  "Схема: сначала сущности, потом стрелки…",
  "Беру поток процесса из запроса…",
  "Раскладываю шаги по порядку…",
];

const QUEUED_DECK = [
  "Ок, собираем презентацию…",
  "Смотрю материал — что войдёт на слайды…",
  "Принял бриф — планирую слайды…",
  "Презентация: сначала структура, потом медиа…",
  "Беру ключевые тезисы под слайды…",
  "Изучаю материал и структуру…",
];

const LLM_REPORT = [
  "Изучаю материал и задачу…",
  "Ловлю структуру документа…",
  "Структура ясна — собираю каркас отчёта…",
  "Пишу текст под печать, без лишней воды…",
  "Собираю вёрстку документа…",
  "Проверяю точность всех цифр…",
  "Выстраиваю разделы так, чтобы читалось сверху вниз…",
  "Подбираю формулировки под тон отчёта…",
  "Сжимаю воду, оставляю суть и цифры…",
  "Сверяю заголовки по структуре…",
  "Держу факты жёстко: ничего от себя не дописываю…",
  "Набрасываю каркас: введение → данные → выводы…",
  "Чищу формулировки под спокойный печатный тон…",
  "Смотрю, где таблица уместнее абзаца…",
];

const LLM_DIAGRAM = [
  "Выделяю ключевые этапы и переходы…",
  "Решаю, это flowchart или последовательность…",
  "Формирую схему без лишних деталей…",
  "Подписываю шаги коротко, по делу…",
  "Сверяю точность фактов в схеме…",
  "Убираю декоративные узлы — оставляю смысл…",
  "Раскладываю развилки: да / нет / исключение…",
  "Проверяю направление стрелок…",
  "Сжимаю длинные подписи до читаемых…",
  "Держу один главный поток сверху вниз…",
];

const DIAGRAM_REPAIR = [
  "Уточняю схему — убираю лишние шаги…",
  "Добавляю развилки и роли из текста…",
  "Проверяю, что каждый узел назван по факту…",
  "Сжимаю линейный черновик в осмысленный граф…",
  "Сверяю подписи и названия ещё раз…",
];

const LLM_DECK = [
  "Собираю структуру слайдов по материалу…",
  "Решаю, сколько кадров и какой ритм…",
  "Пишу тезисы на слайд — без воды…",
  "Раскладываю KPI и сравнения по кадрам…",
  "Сверяю цифры по материалу…",
  "Подбираю заголовки, которые читаются с экрана…",
  "Держу один месседж на слайд…",
  "Форматирую списки и акценты на слайдах…",
  "Проверяю, что нет «слайда-простыни»…",
  "Набрасываю storyline: контекст → данные → вывод…",
];

const IMAGES = [
  "Подбираю иллюстрацию к смыслу текста…",
  "Готовлю фото для разворота…",
  "Дожимаю картинку под макет…",
  "Подбираю кадр без лишнего текста…",
  "Ищу ракурс, который не спорит с графиком…",
  "Собираю иллюстрацию так, чтобы дышала страница…",
  "Генерирую кадр под подпись в документе…",
  "Проверяю, что на фото нет лишних надписей…",
  "Кладу иллюстрацию рядом с нужным абзацем…",
];

const IMAGES_DECK = [
  "Подбираю визуал под слайд…",
  "Готовлю медиа, которое не спорит с тезисом…",
  "Подбираю кадр для слайда…",
  "Сверяю иллюстрацию с палитрой деки…",
];

const CHARTS = [
  "Смотрю, какие числа можно показать графиком…",
  "Собираю диаграмму по данным…",
  "Рисую график, чтобы читалось с первого взгляда…",
  "Выбираю тип: сравнение, доли или тренд…",
  "Кладу подписи так, чтобы легенда не мешала…",
  "Сверяю шкалы и значения…",
  "Палитра и тип — чтобы не спорили друг с другом…",
  "Готовлю графики под печать…",
  "Убираю шум с оси, оставляю читаемые метки…",
  "Проверяю точность процентов на графике…",
];

const CHARTS_DECK = [
  "Какие цифры вынести на график слайда…",
  "Оформляю график для слайда…",
  "Тип графика — чтобы читалось с проектора…",
  "Сверяю подписи и легенду…",
  "Рендерю график для слайда…",
];

const CHARTS_DIAGRAM = [
  "Если есть доли — оформлю рядом со схемой…",
  "Сверяю, нужен ли отдельный график или хватит схемы…",
];

const INJECT = [
  "Вставляю фигуры в текст…",
  "Связываю подписи и слоты в документе…",
  "Сверяю, что всё село в макет…",
  "Встраиваю изображения в документ…",
  "Проверяю подписи: Рис. / Илл. на местах…",
  "Объединяю текст и графику в макет…",
  "Проверяю целостность макета…",
];

const LATEX = [
  "Готовлю чистовой PDF…",
  "Вёрстка на печать, ещё чуть-чуть…",
  "Дожимаю страницы и поля…",
  "Компилирую чистовой документ…",
  "Сверяю поля и переносы под A4…",
  "Собираю печатную версию — PDF…",
  "Чищу предупреждения вёрстки на лету…",
  "Финишная сборка страниц…",
];

const DOCX = [
  "Параллельно собираю DOCX…",
  "Упаковываю Word-вариант…",
  "Готовлю DOCX рядом с PDF…",
  "Собираю редактируемую версию документа…",
  "Дублирую документ в Word без потери структуры…",
];

/** Slides job stages (after report/presentation IR). */
const SLIDES_QUEUED = [
  "Ставлю деку в очередь…",
  "Запускаю сборку слайдов…",
  "Запускаю сборку слайдов…",
];

const SLIDES_LLM = [
  "Пишу структуру слайдов…",
  "Раскладываю тезисы по кадрам…",
  "Формирую структуру слайдов…",
  "Сверяю порядок слайдов…",
  "Дожимаю заголовки под экран…",
];

const SLIDES_LLM_RETRY = [
  "Пересобираю каркас слайдов…",
  "Ещё один проход по структуре деки…",
];

const SLIDES_DIAGRAMS = [
  "Готовлю схемы для слайдов…",
  "Встраиваю диаграммы в кадры…",
  "Оформляю схемы для слайдов…",
];

const SLIDES_RENDER = [
  "Рисую слайды…",
  "Создаю превью слайдов…",
  "Собираю превью для чата…",
];

const SLIDES_PPTX = [
  "Собираю презентацию PPTX…",
  "Упаковываю слайды в файл…",
  "Финишная сборка презентации…",
];

const SLIDES_STARTING = [
  "Запускаю сборку презентации…",
  "Готовлю воркер слайдов…",
];

const SLIDES_PATCH = [
  "Сохраняю правки в PPTX…",
  "Обновляю деку после правок…",
];

const CHART_DETAIL = [
  (_d: string) => "Рисую график…",
  (_d: string) => "Собираю диаграмму по данным…",
  (_d: string) => "Дожимаю диаграмму…",
  (_d: string) => "Готовлю график…",
  (_d: string) => "Кладу график на страницу…",
];

const IMAGE_DETAIL = [
  (_d: string) => "Готовлю иллюстрацию…",
  (_d: string) => "Генерирую изображение…",
  (_d: string) => "Обрабатываю фото…",
  (_d: string) => "Подбираю визуал…",
];

type BeatMap = Record<string, string[]>;

const BEATS_REPORT: BeatMap = {
  queued: QUEUED_REPORT,
  llm: LLM_REPORT,
  images: IMAGES,
  charts: CHARTS,
  inject: INJECT,
  latex: LATEX,
  docx: DOCX,
};

const BEATS_DIAGRAM: BeatMap = {
  queued: QUEUED_DIAGRAM,
  llm: LLM_DIAGRAM,
  diagram_repair: DIAGRAM_REPAIR,
  images: IMAGES,
  charts: CHARTS_DIAGRAM,
  inject: [
    "Связываю схему с описанием…",
    "Проверяю, что граф самодостаточен…",
  ],
  summary: [
    "Кладу схему в чат…",
    "Открываю превью схемы…",
  ],
  latex: [
    "Схема готова в Liber…",
    "Фиксирую граф для панели…",
  ],
  docx: ["Схема остаётся в чате и панели…"],
};

const BEATS_DECK: BeatMap = {
  queued: QUEUED_DECK,
  llm: LLM_DECK,
  images: IMAGES_DECK,
  charts: CHARTS_DECK,
  inject: [
    "Кладу медиа на слайды…",
    "Сверяю макет слайдов…",
  ],
  latex: [
    "Перехожу к подготовке слайдов…",
    "Переключаюсь на сборку слайдов…",
  ],
  docx: ["Фокус на презентации…"],
  slides_queued: SLIDES_QUEUED,
  slides_starting: SLIDES_STARTING,
  slides_llm: SLIDES_LLM,
  slides_llm_retry: SLIDES_LLM_RETRY,
  slides_diagrams: SLIDES_DIAGRAMS,
  slides_render: SLIDES_RENDER,
  slides_pptx: SLIDES_PPTX,
  slides_patch: SLIDES_PATCH,
  slides_media: SLIDES_DIAGRAMS,
  slides_charts: SLIDES_DIAGRAMS,
  slides_plan: SLIDES_LLM,
  slides_ir: SLIDES_LLM,
};

const BEATS_CHAT: BeatMap = {
  queued: [
    "Изучаю запрос…",
    "Смотрю данные и контекст…",
  ],
  llm: [
    "Анализирую цифры и факты…",
    "Готовлю ответ…",
  ],
  charts: [
    "Строю график…",
    "Рисую наглядный график…",
  ],
  images: ["Готовлю визуал…"],
  inject: ["Собираю ответ…"],
  summary: ["Завершаю ответ…"],
  latex: ["Завершаю ответ…"],
  docx: ["Завершаю ответ…"],
};

function beatsFor(mode: ThinkingMode): BeatMap {
  if (mode === "diagram") return BEATS_DIAGRAM;
  if (mode === "presentation") return BEATS_DECK;
  if (mode === "chat") return BEATS_CHAT;
  return BEATS_REPORT;
}

function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Mulberry32 — stable variety per run, not Math.random flicker. */
function mulberry32(seed: number): () => number {
  let t = seed >>> 0;
  return () => {
    t += 0x6d2b79f5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function stageBucket(stage?: string | null, mode: ThinkingMode = "report"): string {
  const raw = (stage || "queued").toLowerCase();
  if (raw === "ok" || raw === "error") return raw;
  const beats = beatsFor(mode);
  if (raw in beats) return raw;
  // Slides job stages → slides_* buckets
  if (
    mode === "presentation" &&
    [
      "starting",
      "llm_retry",
      "diagrams",
      "render",
      "pptx",
      "patch",
      "plan",
      "ir",
      "media",
    ].includes(raw)
  ) {
    return `slides_${raw}`;
  }
  if (raw.startsWith("slides_")) return raw;
  if (raw in BEATS_REPORT) return raw;
  return "queued";
}

export function stageKey(
  stage?: string | null,
  detail?: string | null,
  mode: ThinkingMode = "report",
): string {
  return `${mode}:${stageBucket(stage, mode)}:${detail || ""}`;
}

function detailPhrase(
  stage?: string | null,
  detail?: string | null,
  rand?: () => number,
  mode: ThinkingMode = "report",
): string | null {
  const d = (detail || "").trim();
  if (!d) return null;
  const bucket = stageBucket(stage, mode);
  const roll = rand ? rand() : 0;
  if (bucket === "charts" || bucket === "slides_charts") {
    const fn = CHART_DETAIL[Math.floor(roll * CHART_DETAIL.length)]!;
    return fn(d);
  }
  if (bucket === "images") {
    const fn = IMAGE_DETAIL[Math.floor(roll * IMAGE_DETAIL.length)]!;
    return fn(d);
  }
  return null;
}

function nextFromPool(
  pool: string[],
  usedTexts: Set<string>,
  rand: () => number,
  fallback: string,
): string {
  const unused = pool.filter((p) => !usedTexts.has(p));
  const list = unused.length ? unused : pool;
  const i = Math.floor(rand() * list.length) % list.length;
  return list[i] || pool[0] || fallback;
}

function fallbackLine(mode: ThinkingMode): string {
  if (mode === "diagram") return "Работаю над схемой…";
  if (mode === "presentation") return "Собираю презентацию…";
  if (mode === "chat") return "Готовлю ответ…";
  return "Работаю над отчётом…";
}

/**
 * Append a line when stage/detail changes, or a micro-beat after dwell.
 * Pass `mode` so report / diagram / presentation get different voice.
 */
export function pushThinkingLine(
  prev: ThinkingLine[],
  opts: {
    stage?: string | null;
    detail?: string | null;
    dwellSec?: number;
    beat?: boolean;
    seed?: number;
    mode?: ThinkingMode;
  },
): ThinkingLine[] {
  const mode = opts.mode || "report";
  const bucket = stageBucket(opts.stage, mode);
  if (bucket === "ok" || bucket === "error") return prev;

  const key = stageKey(opts.stage, opts.detail, mode);
  const used = new Set(prev.map((l) => l.text));
  const last = prev[prev.length - 1];
  const seed =
    (opts.seed ?? 1) ^
    (prev.length * 2654435761) ^
    (key.length * 1597334677) ^
    hashStr(key) ^
    hashStr(mode);
  const rand = mulberry32(seed >>> 0);
  const beats = beatsFor(mode);
  const pool = beats[bucket] || beats.queued || QUEUED_REPORT;
  const fallback = fallbackLine(mode);

  if (!last || last.stageKey !== key) {
    const specific = detailPhrase(opts.stage, opts.detail, rand, mode);
    const text = specific || nextFromPool(pool, used, rand, fallback);
    const id = `${key}#${prev.length}`;
    return [...prev, { id, text, stageKey: key }];
  }

  if (!opts.beat) return prev;
  const dwell = opts.dwellSec ?? 0;
  const beatsOnStage = prev.filter((l) => l.stageKey === key).length;
  if (beatsOnStage >= 4) return prev;
  if (dwell < 4 * beatsOnStage) return prev;

  const text = nextFromPool(pool, used, rand, fallback);
  if (used.has(text) && beatsOnStage >= pool.length) return prev;
  const id = `${key}#beat${prev.length}`;
  return [...prev, { id, text, stageKey: key }];
}

/** Short status label for composer / pending header. */
export function stageLabelForMode(
  stage?: string | null,
  detail?: string | null,
  mode: ThinkingMode = "report",
): string {
  if (detail && stage === "queued") return detail;
  if (detail && (stage === "charts" || stage === "slides_charts")) {
    return mode === "presentation"
      ? "График на слайд…"
      : "Рисую график…";
  }
  const bucket = stageBucket(stage, mode);
  const labels: Record<ThinkingMode, Record<string, string>> = {
    report: {
      queued: "В очереди…",
      llm: "Пишу текст (жду модель)…",
      charts: "Рисую графики…",
      images: "Готовлю иллюстрации…",
      inject: "Вставляю рисунки в текст…",
      latex: "Собираю PDF…",
      docx: "Собираю DOCX…",
    },
    diagram: {
      queued: "В очереди…",
      llm: "Пишу схему (жду модель)…",
      diagram_repair: "Уточняю схему…",
      charts: "Сверяю числа со схемой…",
      images: "Медиа для схемы…",
      inject: "Связываю граф…",
      summary: "Кладу схему в чат…",
      latex: "Фиксирую схему…",
      docx: "Почти готово…",
    },
    presentation: {
      queued: "В очереди…",
      llm: "Пишу структуру слайдов…",
      charts: "Графики для деки…",
      images: "Медиа для слайдов…",
      inject: "Кладу медиа на кадры…",
      latex: "Перехожу к деке…",
      docx: "Перехожу к деке…",
      slides_queued: "Дека в очереди…",
      slides_starting: "Запускаю сборку…",
      slides_llm: "Пишу структуру слайдов…",
      slides_llm_retry: "Уточняю каркас…",
      slides_diagrams: "Схемы для слайдов…",
      slides_media: "Медиа для слайдов…",
      slides_charts: "Графики для слайдов…",
      slides_render: "Рисую слайды…",
      slides_pptx: "Собираю PPTX…",
      slides_patch: "Сохраняю правки…",
      slides_plan: "План слайдов…",
      slides_ir: "Структура слайдов…",
    },
    chat: {
      queued: "Изучаю запрос…",
      llm: "Готовлю ответ…",
      charts: "Рисую график…",
      images: "Готовлю визуал…",
      inject: "Собираю ответ…",
      summary: "Готовлю ответ…",
      latex: "Готовлю ответ…",
      docx: "Готовлю ответ…",
    },
  };
  return labels[mode][bucket] || fallbackLine(mode);
}
