/** Stop stays open until the server leaves queued/running, then posts cancel. */

export function stopPollSettled(
  pipe: string | undefined,
  slides: string | undefined,
): boolean {
  if (pipe === "cancelled" || slides === "cancelled") return true;
  if (pipe === "running" || pipe === "queued" || pipe === "started") return false;
  if (slides === "running" || slides === "queued") return false;
  return true;
}

export async function cancelIfStopPressed(
  runId: string,
  cancelRequested: boolean,
  post: (runId: string) => Promise<void>,
): Promise<boolean> {
  if (!cancelRequested || !runId) return false;
  try {
    await post(runId);
  } catch {
    /* caller still leaves the bubble; the desk may already be down */
  }
  return true;
}
