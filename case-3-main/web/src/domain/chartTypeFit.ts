import type { ConfirmOptions } from "../ConfirmModal";

/** Confirm before a type change the server already called a bad fit. */
export function chartTypeEditConfirm(warning: string): ConfirmOptions | null {
  const message = (warning || "").trim();
  if (!message) return null;
  return {
    title: "График может получиться некрасивым",
    eyebrow: "тип графика",
    message,
    confirmLabel: "Всё равно изменить",
    cancelLabel: "Оставить",
    danger: false,
  };
}

/** Confirm when a style rewrite changed the chart's numbers. */
export function chartNumberEditConfirm(warning: string): ConfirmOptions | null {
  const message = (warning || "").trim();
  if (!message) return null;
  return {
    title: "Модель изменила числа",
    eyebrow: "график · данные",
    message,
    confirmLabel: "Всё равно сохранить",
    cancelLabel: "Оставить",
    danger: false,
  };
}

export function numberChangeFromEditError(
  err: unknown,
): { message: string; html: string } | null {
  if (!err || typeof err !== "object" || !("detail" in err)) return null;
  const detail = (err as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return null;
  const body = detail as { code?: unknown; message?: unknown; html?: unknown };
  if (body.code !== "numbers_changed") return null;
  if (typeof body.message !== "string" || typeof body.html !== "string") return null;
  if (!body.message.trim() || !body.html.trim()) return null;
  return { message: body.message, html: body.html };
}
