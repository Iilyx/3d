/** SSE client for Liber run progress (stages / artifacts / terminal). */

import type { CraftFilmFrame, CraftRecap } from "../domain/craftSteps";

export type RunStepPayload = {
  parent: string;
  id: string;
  status: "active" | "done" | "skipped" | string;
  reason?: string | null;
  label?: string | null;
  scope?: string;
};

export type RunEventsHandlers = {
  onStage?: (
    stage: string,
    detail: string | null,
    scope: string,
    etaSec?: number | null,
  ) => void;
  onStep?: (step: RunStepPayload) => void;
  onFilm?: (frame: CraftFilmFrame) => void;
  /** Kept for protocol; UI no longer shows kind plaques. */
  onArtifact?: (kind: string) => void;
  onTerminal?: (
    kind: "done" | "error" | "cancelled",
    error?: string,
    hint?: string,
    recap?: CraftRecap | null,
  ) => void;
  /** Agent line: opening before an artifact, or the chat answer. */
  onChat?: (phase: string, text: string, mode: string) => void;
  /** Model sentences for craft steps. Shown only after each step starts. */
  onNarration?: (lines: Record<string, string>) => void;
  /** SSE failed — caller should fall back to status poll. */
  onFallback?: () => void;
};

/**
 * Open GET /api/runs/{id}/events. Returns closer.
 * Does not stream model thoughts — only craft stages + artifacts.
 *
 * Note: SSE event name `error` collides with EventSource connection errors —
 * we distinguish MessageEvent (server terminal) vs bare Event (transport).
 */
export function openRunEvents(
  runId: string,
  handlers: RunEventsHandlers,
): () => void {
  const es = new EventSource(
    `/api/runs/${encodeURIComponent(runId)}/events`,
  );
  let closed = false;
  let gotEvent = false;
  let fallbackFired = false;
  let finished = false;

  const fireFallback = () => {
    if (fallbackFired || closed || finished) return;
    fallbackFired = true;
    handlers.onFallback?.();
  };

  const finish = (
    kind: "done" | "error" | "cancelled",
    err?: string,
    hint?: string,
    recap?: CraftRecap | null,
  ) => {
    if (finished) return;
    finished = true;
    handlers.onTerminal?.(kind, err, hint, recap);
    es.close();
  };

  const onStage = (ev: Event) => {
    gotEvent = true;
    try {
      const data = JSON.parse((ev as MessageEvent).data) as {
        stage?: string;
        detail?: string | null;
        scope?: string;
        eta_s?: number;
      };
      const eta =
        typeof data.eta_s === "number" && data.eta_s > 0 ? data.eta_s : null;
      handlers.onStage?.(
        data.stage || "queued",
        data.detail ?? null,
        data.scope || "pipeline",
        eta,
      );
    } catch {
      /* ignore */
    }
  };

  const onStep = (ev: Event) => {
    gotEvent = true;
    try {
      const data = JSON.parse((ev as MessageEvent).data) as RunStepPayload;
      if (data?.id && data?.parent) handlers.onStep?.(data);
    } catch {
      /* ignore */
    }
  };

  const onFilm = (ev: Event) => {
    gotEvent = true;
    try {
      const data = JSON.parse((ev as MessageEvent).data) as {
        id?: string;
        kind?: string;
        url?: string;
      };
      if (data?.id && data?.url) {
        handlers.onFilm?.({
          id: data.id,
          kind: data.kind || "chart",
          url: data.url,
        });
      }
    } catch {
      /* ignore */
    }
  };

  const onArtifact = (ev: Event) => {
    gotEvent = true;
    try {
      const data = JSON.parse((ev as MessageEvent).data) as { kind?: string };
      if (data.kind) handlers.onArtifact?.(data.kind);
    } catch {
      /* ignore */
    }
  };

  const onDone = (ev: Event) => {
    gotEvent = true;
    let err: string | undefined;
    let hint: string | undefined;
    let recap: CraftRecap | null = null;
    try {
      const data = JSON.parse((ev as MessageEvent).data) as {
        error?: string;
        hint?: string;
        recap?: CraftRecap;
      };
      err = data.error;
      hint = data.hint;
      if (data.recap && typeof data.recap === "object") recap = data.recap;
    } catch {
      /* ignore */
    }
    finish("done", err, hint, recap);
  };

  const onCancelled = (ev: Event) => {
    gotEvent = true;
    finish("cancelled");
    void ev;
  };

  const onChat = (ev: Event) => {
    gotEvent = true;
    try {
      const data = JSON.parse((ev as MessageEvent).data) as {
        phase?: string;
        text?: string;
        mode?: string;
      };
      if (data.text) {
        handlers.onChat?.(data.phase || "answer", data.text, data.mode || "");
      }
    } catch {
      /* ignore */
    }
  };

  const onErrorEv = (ev: Event) => {
    // Server `event: error` is MessageEvent with JSON {status|error}.
    // Bare EventSource transport errors must NOT be treated as run failure.
    if (ev instanceof MessageEvent && typeof ev.data === "string" && ev.data) {
      try {
        const data = JSON.parse(ev.data) as {
          error?: string;
          status?: string;
          hint?: string;
        };
        if (data.error != null || data.status === "error") {
          gotEvent = true;
          finish("error", data.error, data.hint, null);
          return;
        }
      } catch {
        /* not our terminal payload — fall through to transport handling */
      }
    }
    // Transport failure — poll fallback.
    if (!gotEvent) {
      fireFallback();
      es.close();
    } else if (es.readyState === EventSource.CLOSED) {
      fireFallback();
    }
  };

  es.addEventListener("stage", onStage);
  es.addEventListener("step", onStep);
  es.addEventListener("film", onFilm);
  es.addEventListener("artifact", onArtifact);
  const onNarration = (ev: Event) => {
    gotEvent = true;
    try {
      const data = JSON.parse((ev as MessageEvent).data) as {
        lines?: Record<string, string>;
      };
      const lines = data.lines && typeof data.lines === "object" ? data.lines : {};
      handlers.onNarration?.(lines);
    } catch {
      /* ignore */
    }
  };

  es.addEventListener("chat", onChat);
  es.addEventListener("narration", onNarration);
  es.addEventListener("done", onDone);
  es.addEventListener("cancelled", onCancelled);
  es.addEventListener("error", onErrorEv);

  return () => {
    closed = true;
    es.removeEventListener("stage", onStage);
    es.removeEventListener("step", onStep);
    es.removeEventListener("film", onFilm);
    es.removeEventListener("artifact", onArtifact);
    es.removeEventListener("chat", onChat);
    es.removeEventListener("narration", onNarration);
    es.removeEventListener("done", onDone);
    es.removeEventListener("cancelled", onCancelled);
    es.removeEventListener("error", onErrorEv);
    es.close();
  };
}
