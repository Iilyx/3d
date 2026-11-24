/** SSE client for Liber chat-summary stream (no React). */

export type SummaryDeltaMeta = {
  replaced?: boolean;
};

/** Open SSE summary stream; returns closer. */
export function openSummaryStream(
  runId: string,
  onDelta: (full: string, meta?: SummaryDeltaMeta) => void,
  onDone: (full: string, status: string) => void,
): () => void {
  const es = new EventSource(
    `/api/runs/${encodeURIComponent(runId)}/summary/stream`,
  );
  let acc = "";
  const onDeltaEv = (ev: Event) => {
    try {
      const data = JSON.parse((ev as MessageEvent).data) as { text?: string };
      acc += data.text || "";
      onDelta(acc, { replaced: false });
    } catch {
      /* ignore */
    }
  };
  const onReplaceEv = (ev: Event) => {
    try {
      const data = JSON.parse((ev as MessageEvent).data) as { text?: string };
      acc = data.text || "";
      onDelta(acc, { replaced: true });
    } catch {
      /* ignore */
    }
  };
  const onDoneEv = (ev: Event) => {
    try {
      const data = JSON.parse((ev as MessageEvent).data) as {
        text?: string;
        status?: string;
      };
      const final = (data.text || acc || "").trim();
      onDone(final, data.status || "ok");
    } catch {
      onDone(acc, "ok");
    }
    es.close();
  };
  es.addEventListener("delta", onDeltaEv);
  es.addEventListener("replace", onReplaceEv);
  es.addEventListener("done", onDoneEv);
  es.onerror = () => {
    es.close();
  };
  return () => {
    es.removeEventListener("delta", onDeltaEv);
    es.removeEventListener("replace", onReplaceEv);
    es.removeEventListener("done", onDoneEv);
    es.close();
  };
}
