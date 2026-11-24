/** Shared Liber edit POST: JSON body → payload or Error with API detail. */

export async function postJsonEdit(
  url: string,
  body: unknown,
  fallbackError = "edit failed",
): Promise<Record<string, unknown>> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data: Record<string, unknown> = {};
  try {
    data = (await res.json()) as Record<string, unknown>;
  } catch {
    data = {};
  }
  if (!res.ok) {
    const detail = data.detail;
    let raw =
      typeof detail === "string"
        ? detail
        : typeof data.error === "string"
          ? data.error
          : res.statusText || fallbackError;
    if (detail && typeof detail === "object" && "message" in detail) {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) raw = message;
    }
    const err = new Error(raw) as Error & { status?: number; detail?: unknown };
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

/** Table-edit 404 often means empty run_id or stale desk API. */
export function mapTableEditHttpError(err: unknown): Error {
  const raw = err instanceof Error ? err.message : String(err);
  const status =
    err && typeof err === "object" && "status" in err
      ? Number((err as { status?: number }).status)
      : undefined;
  if (raw === "Not Found" || status === 404) {
    return new Error(
      raw === "run not found"
        ? "Run не найден на диске — нужен свежий отчёт с этого API"
        : "API не нашёл правку таблицы (404). Перезапусти api.cmd и сохрани ещё раз",
    );
  }
  return err instanceof Error ? err : new Error(raw);
}
