/** Stop → POST /cancel + poll until pipeline/slides settle. */

import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { Msg } from "../domain/liberTypes";
import { stopPollSettled } from "../domain/stopRun";

type Deps = {
  stopping: boolean;
  setStopping: Dispatch<SetStateAction<boolean>>;
  setBusy: Dispatch<SetStateAction<boolean>>;
  setMsgs: Dispatch<SetStateAction<Msg[]>>;
  cancelRequestedRef: MutableRefObject<boolean>;
  activeRunIdRef: MutableRefObject<string | null>;
  pendingBotIdRef: MutableRefObject<string | null>;
};

export function useStopGeneration({
  stopping,
  setStopping,
  setBusy,
  setMsgs,
  cancelRequestedRef,
  activeRunIdRef,
  pendingBotIdRef,
}: Deps) {
  return function stopGeneration() {
    if (stopping) return;
    cancelRequestedRef.current = true;
    const runId = activeRunIdRef.current;
    const pendingId = pendingBotIdRef.current;
    setStopping(true);
    if (pendingId) {
      setMsgs((m) =>
        m.map((msg) => {
          if (msg.id !== pendingId || msg.role !== "bot") return msg;
          return {
            ...msg,
            pending: true,
            text: "Останавливаю…",
            error: undefined,
          };
        }),
      );
    }
    void (async () => {
      if (runId) {
        try {
          await fetch(`/api/runs/${encodeURIComponent(runId)}/cancel`, {
            method: "POST",
          });
        } catch {
          /* UI still finishes below */
        }
        const deadline = Date.now() + 20_000;
        while (Date.now() < deadline) {
          try {
            const st = await fetch(
              `/api/runs/${encodeURIComponent(runId)}/status`,
            );
            const body = await st.json().catch(() => ({}));
            const pipe = body.status as string | undefined;
            const slides = body.slides_status as string | undefined;
            if (stopPollSettled(pipe, slides)) {
              break;
            }
          } catch {
            break;
          }
          await new Promise((r) => setTimeout(r, 400));
        }
      }
      if (pendingId) {
        setMsgs((m) =>
          m.map((msg) => {
            if (msg.id !== pendingId || msg.role !== "bot") return msg;
            return {
              ...msg,
              pending: false,
              text: "Остановлено",
              error: undefined,
              result: msg.result
                ? {
                    ...msg.result,
                    slides_status:
                      msg.result.slides_status === "running" ||
                      msg.result.slides_status === "queued"
                        ? "cancelled"
                        : msg.result.slides_status,
                    slides_error: "Остановлено",
                  }
                : msg.result,
            };
          }),
        );
      }
      setStopping(false);
      setBusy(false);
      activeRunIdRef.current = null;
    })();
  };
}
