/** Pure Liber run helpers (no React state, no network). */

import {
  pushThinkingLine,
  stageKey as thinkingStageKey,
  stageLabelForMode,
  type ThinkingMode,
} from "./pipelinePhrases";
import { STAGE_LABELS } from "./liberConstants";
import type { LiberWorkMode } from "./liberModes";
import type { BotMsg, RunResult } from "./liberTypes";

export function effectiveThinkingMode(
  workMode: LiberWorkMode,
  outputMode?: string | null,
): ThinkingMode {
  const raw = (outputMode || "").trim().toLowerCase();
  if (raw === "diagram" || raw === "presentation" || raw === "report" || raw === "chat") {
    return raw;
  }
  if (workMode === "diagram" || workMode === "presentation" || workMode === "report") {
    return workMode;
  }
  return "chat";
}

export function rollbackOptimisticRun<T extends { id: string }>(
  msgs: T[],
  userMsgId: string,
  pendingId: string,
): T[] {
  return msgs.filter((msg) => msg.id !== userMsgId && msg.id !== pendingId);
}

export function appendBotThinking(
  msg: BotMsg,
  stage?: string | null,
  detail?: string | null,
  beat = false,
): BotMsg {
  const mode: ThinkingMode = msg.thinkingMode || "report";
  const key = thinkingStageKey(stage, detail, mode);
  const now = Date.now();
  const stageAt =
    msg.thinkingStageKey === key && msg.thinkingStageAt
      ? msg.thinkingStageAt
      : now;
  const dwellSec = (now - stageAt) / 1000;
  const startedAt = msg.thinkingStartedAt || now;
  const thinking = pushThinkingLine(msg.thinking || [], {
    stage,
    detail,
    dwellSec,
    beat,
    seed: startedAt,
    mode,
  });
  return {
    ...msg,
    thinking,
    thinkingStartedAt: startedAt,
    thinkingStageKey: key,
    thinkingStageAt: stageAt,
  };
}

export function reportReadyText(result?: RunResult, streamed?: string): string {
  if (result?.insufficient_data) {
    return (
      (result.chat_summary || "").trim() ||
      "В запросе недостаточно данных для составления документа. Пожалуйста, укажите конкретные данные или прикрепите файл."
    );
  }
  const fromResult = (result?.chat_summary || "").trim();
  if (fromResult) return fromResult;
  const fromStream = (streamed || "").trim();
  if (fromStream) return fromStream;
  if (result?.output_mode === "diagram" || result?.diagrams?.length) {
    const n = result.diagrams?.length || 0;
    return n
      ? `Схема готова (${n}). Откройте карточку ниже, чтобы развернуть.`
      : "Схема не собралась — нажмите «Ещё вариант» в панели или отправьте снова.";
  }
  return "Отчёт готов";
}

/** Suppressed: soft media failures are handled silently without popup toasts. */
export function softMediaFailToast(_result?: {
  warnings?: string[];
  failed_charts?: string[];
  failed_figures?: string[];
  media_status?: Record<string, unknown>;
}): string | null {
  return null;
}

export function stageLabel(
  stage?: string,
  detail?: string | null,
  mode: ThinkingMode = "report",
): string {
  if (mode !== "report") {
    return stageLabelForMode(stage, detail, mode);
  }
  if (stage === "queued" && detail) return detail;
  if (detail && stage === "charts") return "Рисую график…";
  if (stage && STAGE_LABELS[stage]) return STAGE_LABELS[stage];
  return "Генерирую документ…";
}

export function isRunInFlight(status?: string | null): boolean {
  return status === "running" || status === "started" || status === "queued";
}

export function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () =>
      reject(reader.error ?? new Error("Не удалось прочитать файл"));
    reader.readAsText(file);
  });
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function reportThumb(result: RunResult): string | null {
  const blocks = result.preview?.blocks;
  if (blocks) {
    for (const b of blocks) {
      if (b.type === "figure" && b.url) return b.url;
    }
  }
  return result.previews?.[0]?.url ?? null;
}

export function reportTitle(result: RunResult): string {
  const named = result.title?.trim();
  if (named) return named;
  const t = result.preview?.title?.trim();
  if (t) return t;
  const isRawStamp = /^source_[0-9]{8}T[0-9]{6}Z/i.test(result.run_id || "");
  const suffix = result.run_id && !isRawStamp ? ` · ${result.run_id}` : "";
  if (result.output_mode === "diagram" || result.diagrams?.length) {
    return `Схема${suffix}`;
  }
  if (result.output_mode === "presentation") {
    return `Презентация${suffix}`;
  }
  if (result.output_mode === "chat") {
    const line = (result.chat_summary || "")
      .split("\n")
      .map((s) => s.trim())
      .find((s) => s && !s.startsWith("|"));
    const short = (line || "").replace(/\*\*/g, "").slice(0, 52).trim();
    return short || "Ответ";
  }
  return `Отчёт${suffix}`;
}

/** Slides job already accepted (POST 202) — attach SSE/poll, do not POST again. */
export function slidesJobInFlight(status?: string | null): boolean {
  const st = (status || "").toLowerCase();
  return st === "running" || st === "queued" || st === "starting";
}

export function slidesJobTerminal(status?: string | null): boolean {
  return slidesTerminalKind(status) != null;
}

/** SSE may miss the deck crash. Poll uses this to leave «жду модель». */
export function slidesTerminalKind(
  status?: string | null,
): "done" | "error" | "cancelled" | null {
  const st = (status || "").toLowerCase();
  if (st === "ok") return "done";
  if (st === "error") return "error";
  if (st === "cancelled") return "cancelled";
  return null;
}

/**
 * What the status poll should do while SSE is still open.
 * `null` means keep waiting: the run is in flight, or a presentation
 * still owes a deck after the report status flipped to ok.
 */
export function pipelineWatchKind(
  status?: string | null,
  slidesStatus?: string | null,
  outputMode?: string | null,
): "done" | "error" | "cancelled" | null {
  const st = (status || "").toLowerCase();
  if (st === "error") return "error";
  if (st === "cancelled") return "cancelled";
  if (st !== "ok") return null;
  if (outputMode === "presentation") {
    return slidesTerminalKind(slidesStatus);
  }
  return "done";
}

/** True when Liber should POST /slides (idle / failed), false when done or in-flight. */
export function slidesJobNeedsKick(result: {
  slides_status?: string | null;
  downloads?: Record<string, string | undefined> | null;
}): boolean {
  if (result.downloads?.pptx) return false;
  const st = (result.slides_status || "idle").toLowerCase();
  if (st === "ok") return false;
  if (slidesJobInFlight(st)) return false;
  return true;
}

/** Provisional chat header while a run is in flight (Julius rename). */
export function provisionalSessionTitle(
  mode: "report" | "diagram" | "presentation" | null | undefined,
): string {
  if (mode === "diagram") return "Новая схема";
  if (mode === "presentation") return "Новая презентация";
  return "Новый отчёт";
}

/** Pipeline error that Liber can offer «Продолжить» for. */
export class RunFailedError extends Error {
  readonly canResume: boolean;
  readonly runId: string;
  readonly failedStage: string | null;

  constructor(
    message: string,
    opts: { canResume?: boolean; runId: string; failedStage?: string | null },
  ) {
    super(message);
    this.name = "RunFailedError";
    this.canResume = Boolean(opts.canResume);
    this.runId = opts.runId;
    this.failedStage = opts.failedStage ?? null;
  }
}

/** C8: human status error with failed charts + TeX log tail. */
export function formatRunStatusError(
  body: Record<string, unknown>,
  runId: string,
): string {
  const failedC = Array.isArray(body.failed_charts)
    ? body.failed_charts.filter(Boolean)
    : [];
  const failedF = Array.isArray(body.failed_figures)
    ? body.failed_figures.filter(Boolean)
    : [];
  const logTail =
    typeof body.latex_log_tail === "string" ? body.latex_log_tail.trim() : "";
  const logHint = logTail
    ? logTail
        .split("\n")
        .filter((ln: string) => ln.trim())
        .slice(-6)
        .join(" | ")
    : "";
  return [
    (body.error as string) || (body.message as string),
    failedC.length ? `график ${failedC.join(", ")}` : null,
    failedF.length ? `фото ${failedF.join(", ")}` : null,
    logHint ? `TeX: ${logHint}` : null,
    runId && !/^source_[0-9]{8}T[0-9]{6}Z/i.test(runId) ? `run ${runId}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

/** Narrow JSON `downloads` from Record<string, unknown> API bodies. */
export function asDownloads(
  v: unknown,
  fallback: Record<string, string>,
): Record<string, string> {
  if (!v || typeof v !== "object" || Array.isArray(v)) return fallback;
  const out: Record<string, string> = { ...fallback };
  for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
    if (typeof val === "string") out[k] = val;
  }
  return out;
}

export function asString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

/** FastAPI error body → message string (sync /api/run failures). */
export function formatApiDetailError(
  data: Record<string, unknown>,
  statusText: string,
): string {
  const detail = data.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as { message?: string; run_id?: string; hint?: string };
    const showRun =
      d.run_id && !/^source_[0-9]{8}T[0-9]{6}Z/i.test(d.run_id)
        ? `run ${d.run_id}`
        : null;
    return [d.message, showRun, d.hint]
      .filter(Boolean)
      .join(" · ");
  }
  if (Array.isArray(detail)) {
    return detail
      .map((d: { msg?: string }) => d.msg || JSON.stringify(d))
      .join("; ");
  }
  return (data.error as string) || statusText;
}

export function paradeHintFromHealth(health: {
  vision_configured?: boolean;
  vision_ok?: boolean;
  docker_ok?: boolean;
  playwright_ok?: boolean;
  soffice_ok?: boolean;
  image_api_configured?: boolean;
  kandinsky_configured?: boolean;
  image_api_ok?: boolean;
  image_api_error?: string | null;
} | null): string {
  if (!health) return "проверка сервисов…";
  const imageConfigured =
    health.image_api_configured || health.kandinsky_configured;
  let visionBit: string | null = null;
  if (health.vision_ok) visionBit = "Модель готова";
  else if (health.vision_configured) visionBit = "Модель отвечает медленно";
  let imageBit: string | null = null;
  if (imageConfigured) {
    imageBit = health.image_api_ok ? "Фото готовы" : "Фото недоступны";
  }
  return (
    [
      visionBit,
      health.docker_ok ? "PDF" : null,
      health.playwright_ok ? "Графики" : null,
      health.soffice_ok ? "Слайды" : null,
      imageBit,
    ]
      .filter(Boolean)
      .join(" · ") || "сервисы не готовы"
  );
}

/** Compact chip label for sidebar / composer. */
export function imageChipFromHealth(health: {
  image_api_configured?: boolean;
  kandinsky_configured?: boolean;
  image_api_ok?: boolean;
  image_api_error?: string | null;
} | null): { label: string; ok: boolean; hint: string } {
  if (!health) {
    return { label: "", ok: false, hint: "Проверка сервиса изображений…" };
  }
  const configured =
    health.image_api_configured || health.kandinsky_configured;
  if (!configured) {
    return {
      label: "",
      ok: false,
      hint: "Генерация изображений отключена",
    };
  }
  if (health.image_api_ok) {
    return { label: "Фото: готово", ok: true, hint: "Сервис изображений отвечает" };
  }
  return {
    label: "",
    ok: false,
    hint:
      health.image_api_error ||
      "Сервис изображений не отвечает — отчёт соберётся без фото",
  };
}
