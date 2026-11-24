/** Resume a failed Liber run from failed_stage (POST /resume + poll). */

import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { useCallback } from "react";
import { openRunEvents } from "../api/runEvents";
import { openSummaryStream } from "../api/summaryStream";
import { createStreamPacer } from "../domain/streamPacer";
import {
  attachSlidesPayload,
  needsSlidesHydrate,
  type SlidesPayload,
} from "../domain/attachSlidesPayload";
import {
  craftParentId,
  upsertCraftFilm,
  upsertCraftSubstep,
} from "../domain/craftSteps";
import {
  appendBotThinking,
  formatRunStatusError,
  reportReadyText,
  reportTitle,
  RunFailedError,
  stageLabel,
} from "../domain/runHelpers";
import type { Msg, RunResult } from "../domain/liberTypes";

type Args = {
  busy: boolean;
  setBusy: Dispatch<SetStateAction<boolean>>;
  setStopping: Dispatch<SetStateAction<boolean>>;
  setMsgs: Dispatch<SetStateAction<Msg[]>>;
  setChatTitle: Dispatch<SetStateAction<string | null>>;
  setHasStoredReport: Dispatch<SetStateAction<boolean>>;
  cancelRequestedRef: MutableRefObject<boolean>;
  activeRunIdRef: MutableRefObject<string | null>;
  rememberRun: (result: RunResult) => void;
  openReportArtifact: (msgId: string, result: RunResult) => void;
};

export function useResumeFailedRun({
  busy,
  setBusy,
  setStopping,
  setMsgs,
  setChatTitle,
  setHasStoredReport,
  cancelRequestedRef,
  activeRunIdRef,
  rememberRun,
  openReportArtifact,
}: Args) {
  return useCallback(
async (botMsgId: string, runId: string) => {
  if (busy) return;
  cancelRequestedRef.current = false;
  setStopping(false);
  setBusy(true);
  activeRunIdRef.current = runId;
  setMsgs((m) =>
    m.map((msg) => {
      if (msg.id !== botMsgId || msg.role !== "bot") return msg;
      return appendBotThinking(
        {
          ...msg,
          text: "Продолжаю…",
          pending: true,
          pendingStage: msg.failedStage || "queued",
          pendingDetail: null,
          error: undefined,
          canResume: undefined,
          failedRunId: runId,
          errorHint: null,
          craftFrozen: false,
          thinkingStartedAt: Date.now(),
        },
        msg.failedStage || "queued",
        null,
      );
    }),
  );
  try {
    const res = await fetch(
      `/api/runs/${encodeURIComponent(runId)}/resume`,
      { method: "POST" },
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : data.error || res.statusText || "resume failed",
      );
    }
    let streamedSummary = "";
    const instantStream = Boolean(
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
    );
    const answerPacer = createStreamPacer({
      baseCps: 68,
      instant: instantStream,
      onUpdate: (visible, meta) => {
        setMsgs((m) =>
          m.map((msg) =>
            msg.id === botMsgId && msg.role === "bot"
              ? {
                  ...msg,
                  text: visible,
                  pending: true,
                  streamingSummary: true,
                  streamTyping: meta?.draining ?? answerPacer.isDraining(),
                }
              : msg,
          ),
        );
      },
    });
    const stopSummaryStream = openSummaryStream(
      runId,
      (full, meta) => {
        streamedSummary = full;
        if (meta?.replaced) {
          answerPacer.replaceTarget(full);
        } else {
          answerPacer.pushTarget(full);
        }
      },
      (full) => {
        if (full && full.trim()) {
          streamedSummary = full;
        }
        void answerPacer.markDone(streamedSummary || undefined);
      },
    );
    const stopRunEvents = openRunEvents(runId, {
      onStage: (stage, detail) => {
        const stg = stage || "queued";
        const det = detail ?? null;
        setMsgs((m) =>
          m.map((msg) => {
            if (msg.id !== botMsgId || msg.role !== "bot") return msg;
            return appendBotThinking(
              {
                ...msg,
                text: msg.streamingSummary
                  ? msg.text
                  : stageLabel(stg, det, msg.thinkingMode || "report"),
                pending: true,
                pendingStage: stg,
                pendingDetail: det,
              },
              stg,
              det,
            );
          }),
        );
      },
      onStep: (ev) => {
        const parent = craftParentId(ev.parent);
        const stepId = ev.id || "";
        if (!parent || !stepId) return;
        const st =
          ev.status === "done" || ev.status === "skipped"
            ? ev.status
            : "active";
        setMsgs((m) =>
          m.map((msg) => {
            if (msg.id !== botMsgId || msg.role !== "bot") return msg;
            return {
              ...msg,
              craftSubsteps: upsertCraftSubstep(msg.craftSubsteps || [], {
                id: stepId,
                parent,
                status: st,
                reason: ev.reason ?? null,
                label: ev.label ?? null,
              }),
            };
          }),
        );
      },
      onFilm: (frame) => {
        if (!frame.id || !frame.url) return;
        setMsgs((m) =>
          m.map((msg) => {
            if (msg.id !== botMsgId || msg.role !== "bot") return msg;
            return {
              ...msg,
              craftFilm: upsertCraftFilm(msg.craftFilm || [], frame),
            };
          }),
        );
      },
    });
    const pollDeadlineMs = 20 * 60 * 1000;
    const pollStarted = Date.now();
    let result: RunResult | null = null;
    try {
      for (;;) {
        if (cancelRequestedRef.current) {
          setBusy(false);
          return;
        }
        if (Date.now() - pollStarted > pollDeadlineMs) {
          throw new Error(
            `таймаут ожидания run ${runId} (20 мин) — смотри runs/logs/${runId}`,
          );
        }
        await new Promise((r) => setTimeout(r, 400));
        const st = await fetch(
          `/api/runs/${encodeURIComponent(runId)}/status`,
        );
        const body = await st.json().catch(() => ({}));
        if (!st.ok) {
          throw new Error(
            typeof body.detail === "string"
              ? body.detail
              : body.error || st.statusText,
          );
        }
        if (body.status === "running" || body.status === "started") {
          const stage = body.stage as string | undefined;
          const detail = (body.stage_detail as string | null) || null;
          setMsgs((m) =>
            m.map((msg) => {
              if (msg.id !== botMsgId || msg.role !== "bot") return msg;
              return appendBotThinking(
                {
                  ...msg,
                  text: stageLabel(
                    stage,
                    detail,
                    msg.thinkingMode || "report",
                  ),
                  pending: true,
                  pendingStage: stage,
                  pendingDetail: detail,
                },
                stage,
                detail,
              );
            }),
          );
          continue;
        }
        if (body.status === "cancelled") {
          setBusy(false);
          return;
        }
        if (body.status === "error") {
          throw new RunFailedError(
            formatRunStatusError(body as Record<string, unknown>, runId),
            {
              runId,
              canResume: Boolean(body.can_resume),
              failedStage:
                typeof body.failed_stage === "string"
                  ? body.failed_stage
                  : null,
            },
          );
        }
        result = body as RunResult;
        break;
      }
    } finally {
      stopRunEvents();
      stopSummaryStream();
      if (result) {
        await answerPacer.markDone(streamedSummary || result.chat_summary || undefined);
      }
      answerPacer.stop();
    }
    if (!result) {
      setBusy(false);
      return;
    }
    if (needsSlidesHydrate(result) || result.output_mode === "presentation") {
      try {
        const sr = await fetch(
          `/api/runs/${encodeURIComponent(runId)}/slides`,
        );
        if (sr.ok) {
          const sp = (await sr.json()) as SlidesPayload;
          result = attachSlidesPayload(result, sp);
        }
      } catch {
        /* status payload is enough */
      }
    }
    try {
      setChatTitle(reportTitle(result));
      if (
        result.preview?.blocks?.length ||
        result.downloads?.pdf ||
        result.downloads?.pptx ||
        result.diagrams?.length
      ) {
        rememberRun(result);
        setHasStoredReport(true);
      }
    } catch {
      /* quota */
    }
    const finalResult = result;
    setMsgs((m) =>
      m.map((msg) => {
        if (msg.id !== botMsgId || msg.role !== "bot") return msg;
        return {
          id: botMsgId,
          role: "bot" as const,
          text: reportReadyText(finalResult, streamedSummary),
          result: finalResult,
          thinking: msg.thinking,
          thinkingStartedAt: msg.thinkingStartedAt,
          thinkingMode: msg.thinkingMode,
          craftSubsteps: msg.craftSubsteps,
          craftFilm: msg.craftFilm,
          thinkingElapsedSec: msg.thinkingStartedAt
            ? Math.max(
                0,
                Math.round((Date.now() - msg.thinkingStartedAt) / 1000),
              )
            : undefined,
        };
      }),
    );
    activeRunIdRef.current = null;
    setBusy(false);
    openReportArtifact(botMsgId, finalResult);
  } catch (err) {
    if (!cancelRequestedRef.current) {
      const message = err instanceof Error ? err.message : String(err);
      const failed = err instanceof RunFailedError ? err : null;
      setMsgs((m) =>
        m.map((msg) =>
          msg.id === botMsgId
            ? {
                id: botMsgId,
                role: "bot",
                text: "Ошибка",
                error: message,
                canResume: failed?.canResume ?? true,
                failedRunId: failed?.runId ?? runId,
                failedStage: failed?.failedStage,
              }
            : msg,
        ),
      );
    }
    activeRunIdRef.current = null;
    setBusy(false);
  }
}

  ,
    [
      busy,
      setBusy,
      setStopping,
      setMsgs,
      setChatTitle,
      setHasStoredReport,
      cancelRequestedRef,
      activeRunIdRef,
      rememberRun,
      openReportArtifact,
    ],
  );
}
