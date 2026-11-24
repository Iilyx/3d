/** Stimulsoft viewer → one markdown per PNG and per table PDF. */

import { mergeSourcePack } from "./sourcePack";
import type { SourceDraft } from "./liberTypes";

export const CAPTURE_MESSAGE = "liber-dashboard-capture";

const DEFAULT_VIEWER = "http://127.0.0.1:8040/viewer";

export type CaptureFile = {
  name: string;
  ext: "png" | "pdf";
  data_b64: string;
};

export function viewerFrameUrl(raw?: string | null): string {
  const trimmed = (raw || "").trim().replace(/\/+$/, "");
  const base = trimmed || DEFAULT_VIEWER.replace(/\/viewer$/, "");
  if (/\/viewer$/i.test(base)) return base;
  return `${base}/viewer`;
}

export function captureOriginOk(origin: string, viewerUrl: string): boolean {
  try {
    return new URL(viewerUrl).origin === origin;
  } catch {
    return false;
  }
}

export function filesFromCapture(data: unknown): CaptureFile[] {
  if (!data || typeof data !== "object") return [];
  const msg = data as { type?: unknown; files?: unknown };
  if (msg.type !== CAPTURE_MESSAGE || !Array.isArray(msg.files)) return [];
  const out: CaptureFile[] = [];
  for (const item of msg.files) {
    if (!item || typeof item !== "object") continue;
    const row = item as { name?: unknown; ext?: unknown; data_b64?: unknown };
    const ext = row.ext === "png" || row.ext === "pdf" ? row.ext : null;
    const name = typeof row.name === "string" ? row.name.trim() : "";
    const data_b64 = typeof row.data_b64 === "string" ? row.data_b64.trim() : "";
    if (!ext || !name || !data_b64) continue;
    out.push({ name, ext, data_b64 });
  }
  return out;
}

export function markdownDocName(fileName: string): string {
  const base = (fileName || "").trim().split(/[/\\]/).pop() || "dashboard";
  const stem = base.replace(/\.(png|pdf|md)$/i, "") || "dashboard";
  return `${stem}.md`;
}

export function fileFromCapture(file: CaptureFile): File {
  const binary = atob(file.data_b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const type = file.ext === "png" ? "image/png" : "application/pdf";
  return new File([bytes], file.name, { type });
}

export type PhrasePlan = {
  pull: boolean;
  viewer: string;
  reply: string;
  filters: Record<string, string>;
  mrt?: string;
};

export function phrasePlan(data: unknown): PhrasePlan | null {
  if (!data || typeof data !== "object") return null;
  const row = data as {
    pull?: unknown;
    viewer?: unknown;
    reply?: unknown;
    filters?: unknown;
    mrt?: unknown;
  };
  if (row.pull !== true) return null;
  const viewer = typeof row.viewer === "string" ? row.viewer.trim() : "";
  if (!viewer) return null;
  const filters: Record<string, string> = {};
  if (row.filters && typeof row.filters === "object") {
    for (const [key, value] of Object.entries(row.filters as Record<string, unknown>)) {
      if (!key.trim() || value == null) continue;
      filters[key] = String(value);
    }
  }
  if (!Object.keys(filters).length) return null;
  const reply = typeof row.reply === "string" ? row.reply.trim() : "";
  const mrt = typeof row.mrt === "string" && row.mrt.trim() ? row.mrt.trim() : undefined;
  return mrt ? { pull: true, viewer, reply, filters, mrt } : { pull: true, viewer, reply, filters };
}

export type PhraseRoute = "send" | "miss" | "open";

/** A down dashboard service must not swallow the message. A real miss still stops. */
export function phraseRoute(ok: boolean, data: unknown): PhraseRoute {
  if (!ok) return "send";
  if (phraseMiss(data)) return "miss";
  if (phrasePlan(data)) return "open";
  return "send";
}

export function phraseMiss(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const row = data as { pull?: unknown; asked?: unknown; reply?: unknown };
  if (row.pull === true || row.asked !== true) return null;
  return typeof row.reply === "string" && row.reply.trim()
    ? row.reply.trim()
    : "В фразе нет фильтра, который есть в дашборде.";
}

export function documentsFromService(
  data: unknown,
): { name: string; markdown: string; warnings: string[] }[] {
  if (!data || typeof data !== "object") return [];
  const docs = (data as { documents?: unknown }).documents;
  if (!Array.isArray(docs)) return [];
  const out: { name: string; markdown: string; warnings: string[] }[] = [];
  for (const item of docs) {
    if (!item || typeof item !== "object") continue;
    const row = item as { name?: unknown; markdown?: unknown; warnings?: unknown };
    const name = typeof row.name === "string" ? row.name.trim() : "";
    const markdown = typeof row.markdown === "string" ? row.markdown.trim() : "";
    if (!name || !markdown) continue;
    const warnings = Array.isArray(row.warnings)
      ? row.warnings
          .filter((note): note is string => typeof note === "string")
          .map((note) => note.trim())
          .filter(Boolean)
      : [];
    out.push({ name, markdown, warnings });
  }
  return out;
}

export function captureWarning(
  docs: { warnings?: string[] }[],
): string {
  for (const doc of docs) {
    const note = (doc.warnings || []).find((item) => item.trim());
    if (note) return note.trim();
  }
  return "";
}

export type DashboardShot = {
  name: string;
  markdown: string;
  warnings: string[];
};

export type DashboardCard = {
  viewer: string;
  /** .mrt that this card opened, so a later click raises the same file. */
  mrt?: string;
  filters: Record<string, string>;
  shots: DashboardShot[];
  /** How many shots were already sent to the model. */
  analyzed: number;
};

export const DASHBOARD_SHOT_TOAST = "Данные текущего экрана попали в чат.";

export const DASHBOARD_ANALYSIS_ASK =
  "Экраны уже в тексте. Коротко скажи, что на них, и что по этим числам можно спросить дальше. Длинный разбор в чат не пиши.";

export function cardCaption(filters: Record<string, string>): string {
  const bits = Object.values(filters)
    .map((value) => value.trim())
    .filter((value) => value && value.length <= 40 && !/^0+$/.test(value));
  const words = bits.filter((value) => /[A-Za-zА-Яа-яЁё]/.test(value));
  if (!words.length) return "Экран дашборда";
  const years = bits.filter((value) => /^20\d\d$/.test(value));
  return [...words, ...years].slice(0, 4).join(" · ");
}

const _SKIP_HEADS = new Set([
  "данные дашборда",
  "экран",
  "таблица pdf",
  "производные",
  "фильтры",
  "карточки",
  "график или карта",
  "заголовок",
]);

export function dashboardTitle(markdown: string): string {
  const text = (markdown || "").replace(/\r\n/g, "\n");
  const heading = text.match(/^##[ \t]+Заголовок[ \t]*\n+([^\n#|][^\n]*)/im);
  let raw = heading?.[1]?.trim() || "";
  if (!raw) {
    for (const match of text.matchAll(/^#{1,3}[ \t]+(.+)$/gm)) {
      const title = match[1].trim();
      const key = title.toLocaleLowerCase("ru").replaceAll("ё", "е");
      if (_SKIP_HEADS.has(key)) continue;
      raw = title;
      break;
    }
  }
  return cleanDashboardTitle(raw);
}

function cleanDashboardTitle(raw: string): string {
  let text = raw.replace(/\s+/g, " ").trim();
  text = text.replace(/\s*\([^)]*\)\s*$/g, "").trim();
  text = text.replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim();
  if (text.length > 72) text = `${text.slice(0, 69).trimEnd()}…`;
  return text;
}

function isStampName(name: string): boolean {
  const base = (name || "").trim().split(/[/\\]/).pop() || "";
  const stem = base.replace(/\.(png|pdf|md)$/i, "");
  return /^dashboard([_\-\s]|\d|$)/i.test(stem);
}

export function shotTitle(name: string, markdown: string): string {
  const fromText = dashboardTitle(markdown);
  const stem = markdownDocName(name).replace(/\.md$/i, "").trim();
  if (fromText && (!stem || isStampName(stem))) return fromText;
  if (!stem || isStampName(stem)) return "Экран дашборда";
  return stem;
}

function uniqueShotTitle(taken: string[], title: string): string {
  if (!taken.includes(title)) return title;
  let n = 2;
  while (taken.includes(`${title} · ${n}`)) n += 1;
  return `${title} · ${n}`;
}

export function shotsTitle(shots: DashboardShot[]): string {
  if (!shots.length) return "Дашборд";
  if (shots.length === 1) return shots[0].name;
  const rest = shots.length - 1;
  const word = rest === 1 ? "экран" : rest < 5 ? "экрана" : "экранов";
  return `${shots[0].name}, ещё ${rest} ${word}`;
}

export function withShots(
  card: DashboardCard,
  docs: { name: string; markdown: string; warnings?: string[] }[],
): DashboardCard {
  const taken = card.shots.map((shot) => shot.name);
  const shots = docs
    .map((doc) => {
      const markdown = doc.markdown.trim();
      if (!doc.name.trim() || !markdown) return null;
      const name = uniqueShotTitle(taken, shotTitle(doc.name, markdown));
      taken.push(name);
      return {
        name,
        markdown,
        warnings: (doc.warnings || []).map((note) => note.trim()).filter(Boolean),
      };
    })
    .filter((shot): shot is DashboardShot => Boolean(shot));
  if (!shots.length) return card;
  return { ...card, shots: [...card.shots, ...shots] };
}

export function freshShots(card: DashboardCard): DashboardShot[] {
  return card.shots.slice(Math.max(0, card.analyzed));
}

export function removeShotAt(card: DashboardCard, index: number): DashboardCard {
  if (index < 0 || index >= card.shots.length) return card;
  const shots = card.shots.filter((_, idx) => idx !== index);
  const analyzed = Math.min(Math.max(0, card.analyzed), shots.length);
  return { ...card, shots, analyzed };
}

const PACKED_DOC = /^===== (.+?) =====$/;

/** Parsed dashboard markdown, including several shots joined for the chat. */
export function isDashboardSource(text: string): boolean {
  return /(?:^|\n)# Данные дашборда\s*(?:\n|$)/.test(text || "");
}

/** A saved chat turn's source, rebuilt as the card that opens the table. */
export function dashboardCardFromSource(text: string): DashboardCard | null {
  if (!isDashboardSource(text)) return null;
  const shots = splitPackedSources(text)
    .filter((part) => isDashboardSource(part.markdown))
    .map((part) => ({
      name: shotTitle(part.name, part.markdown),
      markdown: part.markdown,
      warnings: [] as string[],
    }));
  if (!shots.length) return null;
  return { viewer: "", filters: {}, shots, analyzed: shots.length };
}

function _normDash(value: string): string {
  return value
    .toLocaleLowerCase("ru")
    .replaceAll("ё", "е")
    .replace(/\.mrt$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** The .mrt whose name is the screen title. Empty when none of the files match. */
export function matchDashboardFile(
  shots: { name: string }[],
  rows: { name: string; title?: string }[],
): string {
  const wanted = shots
    .map((shot) => _normDash(shot.name))
    .filter((name) => name.length >= 4);
  let best = "";
  let bestLen = 0;
  for (const row of rows) {
    const title = _normDash(row.title || "");
    const stem = _normDash(row.name || "");
    const len = Math.max(title.length, stem.length);
    const hit = wanted.some(
      (want) =>
        (title.length >= 4 && (want === title || want.includes(title) || title.includes(want))) ||
        (stem.length >= 4 && (want === stem || want.includes(stem) || stem.includes(want))),
    );
    if (hit && len > bestLen && row.name) {
      best = row.name;
      bestLen = len;
    }
  }
  return best;
}

export function splitPackedSources(
  text: string,
): { name: string; markdown: string }[] {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const docs: { name: string; lines: string[] }[] = [];
  let current: { name: string; lines: string[] } | null = null;
  for (const line of lines) {
    const mark = PACKED_DOC.exec(line.trim());
    if (mark) {
      current = { name: mark[1].trim(), lines: [] };
      docs.push(current);
      continue;
    }
    if (!current) {
      current = { name: "", lines: [] };
      docs.push(current);
    }
    current.lines.push(line);
  }
  return docs
    .map((doc) => ({ name: doc.name, markdown: doc.lines.join("\n").trim() }))
    .filter((doc) => doc.markdown);
}

export function shotsSource(shots: DashboardShot[]): string {
  return shots
    .map((shot) => {
      const body = shot.markdown.trim();
      if (!body) return "";
      return `===== ${markdownDocName(shot.name)} =====\n${body}`;
    })
    .filter(Boolean)
    .join("\n\n");
}

export function attachCaptureMarkdowns(
  current: SourceDraft | null,
  docs: { name: string; markdown: string }[],
): SourceDraft | null {
  let next = current;
  for (const doc of docs) {
    const text = (doc.markdown || "").trim();
    if (!text) continue;
    const title = shotTitle(doc.name, text);
    const fileName = `${title}.md`;
    next = mergeSourcePack(next, {
      title,
      text,
      fileName,
      viewMode: "text",
    });
  }
  return next;
}
