/** Liber main run: Source+Intent → POST /api/run + SSE/poll. */

import type {
  Dispatch,
  MutableRefObject,
  RefObject,
  SetStateAction,
} from "react";
import { useCallback, useRef } from "react";
import { openRunEvents } from "../api/runEvents";
import { openSummaryStream } from "../api/summaryStream";
import { createStreamPacer } from "../domain/streamPacer";
import {
  craftParentId,
  formatCraftRecap,
  hydrateCraftFromSteps,
  upsertCraftFilm,
  upsertCraftSubstep,
  type CraftFilmFrame,
  type CraftStepLogEntry,
} from "../domain/craftSteps";
import { cancelIfStopPressed } from "../domain/stopRun";
import { userIntentForRun } from "../domain/userIntent";
import { modeToOutputMode, type LiberWorkMode } from "../domain/liberModes";
import { asksForPhoto, photoLimitChip } from "../domain/photoChip";
import {
  appendBotThinking,
  asString,
  effectiveThinkingMode,
  formatApiDetailError,
  formatRunStatusError,
  isRunInFlight,
  provisionalSessionTitle,
  reportReadyText,
  reportTitle,
  rollbackOptimisticRun,
  RunFailedError,
  slidesJobInFlight,
  slidesJobTerminal,
  pipelineWatchKind,
  stageLabel,
  uid,
} from "../domain/runHelpers";
import { loadCarriedRun } from "../domain/carriedRun";
import { detachSourceAfterSend } from "../domain/sourcePlaque";
import { attachmentsFromDraft } from "../domain/sourcePack";
import { priorRunIdFromMessages } from "../domain/priorRun";
import {
  offersNewChat,
  refreshRevisedArtifact,
  refreshSteps,
} from "../domain/reviseRefresh";
import { saveUserTurn, uploadedPhotoThumbs } from "../domain/reportHistory";
import {
  attachSlidesPayload,
  needsSlidesHydrate,
} from "../domain/attachSlidesPayload";
import type {
  Health,
  Msg,
  RunResult,
  SourceAttachment,
  SourceDraft,
} from "../domain/liberTypes";
import { slidesAutoKickPayload, type DeckStyle } from "../deckStyle";
import type { ActiveArtifact, ArtifactTab } from "../ArtifactRail";
import { buildRunFormData } from "./buildRunFormData";

/** Grouped deps so App wiring stays scannable (composer / desk / runRefs). */
export type LiberSendDeps = {
  composer: {
    canSend: boolean;
    chat: string;
    sourceDraft: SourceDraft | null;
    file: File | null;
    attachPhotos: File[];
    forbidCharts: boolean;
    forbidImages: boolean;
    maxCharts: number;
    maxImages: number;
    maxDiagrams: number;
    targetSlides: number;
    dryRun: boolean;
    workMode: LiberWorkMode;
    deckStyle: DeckStyle;
    chartPalette?: string;
    chatRef: RefObject<HTMLTextAreaElement | null>;
    setChat: Dispatch<SetStateAction<string>>;
    setChatTitle: Dispatch<SetStateAction<string | null>>;
    setFile: Dispatch<SetStateAction<File | null>>;
    setSourceDraft: Dispatch<SetStateAction<SourceDraft | null>>;
    setPlaqueDismissed: Dispatch<SetStateAction<boolean>>;
    setAttachPhotos: Dispatch<SetStateAction<File[]>>;
  };
    desk: {
      health: Health | null;
      imageChip: { ok: boolean };
      msgs: Msg[];
      setMsgs: Dispatch<SetStateAction<Msg[]>>;
    setBusy: Dispatch<SetStateAction<boolean>>;
    setStopping: Dispatch<SetStateAction<boolean>>;
    setHasStoredReport: Dispatch<SetStateAction<boolean>>;
    setToast: Dispatch<SetStateAction<string | null>>;
    setDeckApplyHint: Dispatch<SetStateAction<string | null>>;
    setRailExiting: Dispatch<SetStateAction<boolean>>;
    setRailCollapsed: Dispatch<SetStateAction<boolean>>;
    setActiveArtifact: Dispatch<SetStateAction<ActiveArtifact | null>>;
  };
  runRefs: {
    cancelRequestedRef: MutableRefObject<boolean>;
    activeRunIdRef: MutableRefObject<string | null>;
    pendingBotIdRef: MutableRefObject<string | null>;
    rememberRun: (result: RunResult) => void;
    openReportArtifact: (
      msgId: string,
      result: RunResult,
      tab?: ArtifactTab,
    ) => void;
    openDiagramArtifact: (
      msgId: string,
      result: RunResult,
      diagramId: string,
    ) => void;
    makePresentation: (msgId: string, result: RunResult) => Promise<void>;
  };
};

export function useLiberRun(deps: LiberSendDeps) {
  const {
    composer: {
      canSend,
      chat,
      sourceDraft,
      file,
      attachPhotos,
      forbidCharts,
      forbidImages,
      maxCharts,
      maxImages,
      maxDiagrams,
      targetSlides,
      dryRun,
      workMode,
      deckStyle,
      chartPalette,
      chatRef,
      setChat,
      setChatTitle,
      setFile,
      setSourceDraft,
      setPlaqueDismissed,
      setAttachPhotos,
    },
    desk: {
      health,
      imageChip,
      msgs,
      setMsgs,
      setBusy,
      setStopping,
      setHasStoredReport,
      setToast,
      setDeckApplyHint,
      setRailExiting,
      setRailCollapsed,
      setActiveArtifact,
    },
    runRefs: {
      cancelRequestedRef,
      activeRunIdRef,
      pendingBotIdRef,
      rememberRun,
      openReportArtifact,
      openDiagramArtifact,
      makePresentation,
    },
  } = deps;

  const inFlightRef = useRef(false);

  return useCallback(
async (override?: string, quiet?: { sourceText: string; outputMode: "chat"; title?: string }) => {
  if (inFlightRef.current) return;
  const hidden = (quiet?.sourceText || "").trim();
  const chatTrim = (override ?? chat).trim();
  if (!hidden && !override && !canSend) return;
  const priorRunId = priorRunIdFromMessages(msgs);
  const quietTitle = (quiet?.title || "Дашборд").trim() || "Дашборд";
  const draftSnap = hidden
    ? {
        title: quietTitle,
        text: hidden,
        fileName: `${quietTitle}.md`,
      }
    : sourceDraft;
  const fileForRun = hidden ? null : file;
  const hasSource = Boolean(fileForRun) || Boolean(draftSnap?.text);
  const intentText = userIntentForRun(chatTrim);
  if (!hasSource && !chatTrim) return;
  setDeckApplyHint(null);

  // Soft warn: Image down + photos wanted — run still proceeds (fig_* may skip)
  const wantsPhotos =
    !hidden &&
    !forbidImages &&
    asksForPhoto(chatTrim) &&
    modeToOutputMode(workMode) !== "diagram";
  if (wantsPhotos && health && !imageChip.ok) {
    setToast(
      health.image_api_configured || health.kandinsky_configured
        ? "Сервис изображений не отвечает — соберу без фото"
        : "Генерация изображений отключена",
    );
    window.setTimeout(() => setToast(null), 5200);
  }

  const attachments: SourceAttachment[] =
    hidden || !draftSnap?.text ? [] : attachmentsFromDraft(draftSnap);
  const attachment: SourceAttachment | undefined = attachments[0];
  const userBody = chatTrim
    ? chatTrim
    : attachment
      ? "Собрать отчёт"
      : file
        ? `Файл: ${file.name}`
        : chatTrim;
  const outMode = modeToOutputMode(workMode);
  let liveMode = outMode;
  const userChips = [
    outMode === "diagram"
      ? "схема"
      : outMode === "presentation"
        ? `презентация · ${targetSlides} сл.`
        : outMode === "report"
          ? "отчёт"
          : null,
    photoLimitChip({
      text: chatTrim,
      attached: attachPhotos.length,
      maxImages,
      forbidImages,
      showLimits: Boolean(workMode) && outMode !== "diagram",
    }),
    workMode && outMode !== "diagram" && forbidCharts
      ? "без графиков"
      : workMode && outMode !== "diagram"
        ? `≤${maxCharts} гр.`
        : null,
    workMode
      ? `≤${outMode === "diagram" ? Math.max(maxDiagrams, 1) : maxDiagrams} схем`
      : null,
    dryRun ? "тестовый прогон" : null,
  ].filter((x): x is string => Boolean(x));

  const thinkingMode = effectiveThinkingMode(workMode, quiet?.outputMode);
  const pendingId = uid();
  const userMsgId = uid();
  const photoViews = hidden
    ? []
    : attachPhotos.map((file) => ({
        name: file.name,
        url: URL.createObjectURL(file),
      }));
  inFlightRef.current = true;
  let startedOnServer = false;
  const finishIdle = () => {
    inFlightRef.current = false;
    setBusy(false);
  };
  cancelRequestedRef.current = false;
  pendingBotIdRef.current = pendingId;
  activeRunIdRef.current = null;
  // Presentation builds stay on the chat sheet — close rail if open.
  if (outMode === "presentation") {
    setRailExiting(false);
    setRailCollapsed(false);
    setActiveArtifact(null);
  }
  setMsgs((m) => [
    ...m,
    ...(hidden
      ? []
      : [
          {
            id: userMsgId,
            role: "user" as const,
            text: userBody,
            chips: userChips.length ? userChips : undefined,
            attachment,
            attachments: attachments.length ? attachments : undefined,
            photos: photoViews.length ? photoViews : undefined,
          },
        ]),
    appendBotThinking(
      {
        id: pendingId,
        role: "bot",
        text: "",
        pending: true,
        pendingStage: "queued",
        pendingDetail: null,
        thinkingStartedAt: Date.now(),
        thinkingMode,
        waitLabel: hidden ? "Отвечаю…" : undefined,
      },
      "queued",
      null,
    ),
  ]);
  setBusy(true);
  setStopping(false);
  setChatTitle(workMode ? provisionalSessionTitle(workMode) : null);
  const photosSnapshot = hidden ? [] : [...attachPhotos];
  // Do not auto-open the right rail on send for attached documents (they open in MD modal on click).
  if (!hidden && !fileForRun && draftSnap) {
    setActiveArtifact((a) =>
      a?.kind === "source" || a?.kind === "intent" ? null : a,
    );
  }

  const fd = buildRunFormData({
    file: fileForRun,
    draftSnap,
    chatTrim,
    intentText,
    photosSnapshot,
    outputMode: quiet?.outputMode,
    forbidCharts,
    forbidImages,
    maxCharts,
    maxImages,
    maxDiagrams,
    targetSlides,
    dryRun,
    workMode,
    deckStyle,
    chartPalette,
    priorRunId,
    carriedRunId: loadCarriedRun(),
  });

  try {
    const res = await fetch("/api/run", { method: "POST", body: fd });
    const data = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    if (!res.ok) {
      const fallback =
        res.status === 500 || res.status === 502 || res.status === 503
          ? "Сервер временно недоступен. Попробуйте повторить запрос."
          : res.statusText;
      throw new Error(formatApiDetailError(data, fallback));
    }
    startedOnServer = true;
    const detached = detachSourceAfterSend({
      startedOnServer,
      hidden: Boolean(hidden),
    });
    if (!hidden) {
      setChat("");
      if (chatRef.current) chatRef.current.style.height = "44px";
      setAttachPhotos([]);
    }
    if (detached) {
      setFile(detached.file);
      setSourceDraft(detached.sourceDraft);
      setPlaqueDismissed(detached.plaqueDismissed);
    }

    // Sync photo-edit response (no poll)
    if (data.mode === "photo_edit" && data.status === "ok") {
      const result = data as unknown as RunResult;
      const caption = asString(data.caption, "Фото изменено");
      setChatTitle(caption.trim() || "Правка фото");
      setMsgs((m) =>
        m.map((msg) => {
          if (msg.id !== pendingId || msg.role !== "bot") return msg;
          return {
            ...msg,
            text: caption,
            pending: false,
            result,
          };
        }),
      );
      setToast("Фото изменено");
      window.setTimeout(() => setToast(null), 2800);
      finishIdle();
      return;
    }

    if (data.mode === "chat_revise") {
      const line = asString(data.chat, "Сделал.");
      const runId = asString(data.run_id);
      const isolated = data.isolate === true;
      const steps = refreshSteps({
        op: asString(data.op),
        surface: asString(data.surface),
        artifact_run_id: asString(data.artifact_run_id),
        surfaces: Array.isArray(data.surfaces)
          ? (data.surfaces as Array<{
              surface?: string;
              artifact_run_id?: string;
              op?: string;
            }>)
          : [],
      });
      const nextPreviews = Array.isArray(data.previews)
        ? (data.previews as RunResult["previews"])
        : undefined;
      const nextMemorySection =
        typeof data.memory_section === "string" ? data.memory_section : undefined;
      setMsgs((m) =>
        m.map((msg) => {
          if (msg.id !== pendingId || msg.role !== "bot") return msg;
          return {
            ...msg,
            lead: line,
            text: line,
            pending: false,
            offerNewChat: offersNewChat(asString(data.op)),
            result: runId
              ? ({
                  run_id: runId,
                  isolated,
                  output_mode: asString(data.output_mode, "chat"),
                  chat_summary: line,
                  ...(nextPreviews ? { previews: nextPreviews } : {}),
                  ...(nextMemorySection !== undefined
                    ? { memory_section: nextMemorySection }
                    : {}),
                } as RunResult)
              : msg.result,
          };
        }),
      );
      if (!runId || !steps.length) {
        finishIdle();
        return;
      }
      void (async () => {
        for (const step of steps) {
          await refreshRevisedArtifact(
            runId,
            step.surface,
            pendingId,
            {
              setMsgs,
              rememberRun,
              openReportArtifact,
            },
            step.artifactRunId || asString(data.artifact_run_id),
            {
              remember: !isolated,
              isolated,
              op: step.op || asString(data.op),
              memorySection: nextMemorySection,
            },
          );
        }
      })().finally(() => finishIdle());
      return;
    }

    let result = data as unknown as RunResult;

    // 202 async job: poll until ok/error
    if (res.status === 202 || data.status === "started" || data.status === "running") {
      if (typeof data.output_mode === "string" && data.output_mode) {
        liveMode = data.output_mode;
      }
      const nextThinkingMode = effectiveThinkingMode(workMode, liveMode);
      const runId = asString(data.run_id);
      if (!runId) throw new Error("server did not return run_id");
      activeRunIdRef.current = runId;
      if (
        await cancelIfStopPressed(
          runId,
          cancelRequestedRef.current,
          async (id) => {
            await fetch(`/api/runs/${encodeURIComponent(id)}/cancel`, {
              method: "POST",
            });
          },
        )
      ) {
        finishIdle();
        return;
      }
      saveUserTurn(runId, { text: userBody });
      setMsgs((m) =>
        m.map((msg) => {
          if (msg.id !== pendingId || msg.role !== "bot") return msg;
          const stage = asString(data.stage, "queued");
          const chatAnswer =
            quiet?.outputMode === "chat" || data.output_mode === "chat";
          return appendBotThinking(
            {
              ...msg,
              thinkingMode: nextThinkingMode,
              text: chatAnswer ? msg.text : stageLabel(stage, null, nextThinkingMode),
              pending: true,
              pendingStage: stage,
              pendingDetail: null,
            },
            stage,
            null,
          );
        }),
      );
      const pollDeadlineMs = 20 * 60 * 1000;
      const runCloser = {
        summary: null as null | (() => void),
        events: null as null | (() => void),
      };
      let streamedSummary = "";
      let leadAcc = "";
      let summaryStreamStarted = false;
      let cancelled = false;
      let slidesKicked = false;
      let latestStage = "";
      let latestDetail: string | null = null;
      const instantStream = Boolean(
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
      );
      const answerPacer = createStreamPacer({
        baseCps: 68,
        instant: instantStream,
        onUpdate: (visible, meta) => {
          setMsgs((m) =>
            m.map((msg) => {
              if (msg.id !== pendingId || msg.role !== "bot") return msg;
              return {
                ...msg,
                text: visible,
                pending: true,
                streamingSummary: true,
                streamTyping: meta?.draining ?? answerPacer.isDraining(),
                pendingStage: latestStage || msg.pendingStage,
                pendingDetail: latestDetail,
              };
            }),
          );
        },
      });
      const leadPacer = createStreamPacer({
        baseCps: 76,
        instant: instantStream,
        onUpdate: (visible) => {
          setMsgs((m) =>
            m.map((msg) =>
              msg.id === pendingId && msg.role === "bot"
                ? { ...msg, lead: visible }
                : msg,
            ),
          );
        },
      });

      const ensureSummaryStream = () => {
        if (summaryStreamStarted) return;
        summaryStreamStarted = true;
        runCloser.summary = openSummaryStream(
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
            streamedSummary = full || streamedSummary;
            void answerPacer.markDone(streamedSummary || undefined);
          },
        );
      };

      const applyStage = (
        stage: string | undefined,
        detail: string | null,
        etaSec?: number | null,
      ) => {
        latestStage = stage || latestStage;
        latestDetail = detail;
        setMsgs((m) =>
          m.map((msg) => {
            if (msg.id !== pendingId || msg.role !== "bot") return msg;
            return appendBotThinking(
              {
                ...msg,
                pending: true,
                pendingStage: stage,
                pendingDetail: detail,
                etaSec:
                  etaSec != null && etaSec > 0 ? etaSec : msg.etaSec ?? null,
              },
              stage,
              detail,
            );
          }),
        );
        const shouldStream =
          !summaryStreamStarted &&
          outMode !== "diagram" &&
          (stage === "chat" ||
            stage === "latex" ||
            stage === "docx" ||
            stage === "summary");
        if (shouldStream) {
          ensureSummaryStream();
        }
      };

      const applyFilm = (frame: CraftFilmFrame) => {
        setMsgs((m) =>
          m.map((msg) =>
            msg.id === pendingId && msg.role === "bot"
              ? {
                  ...msg,
                  craftFilm: upsertCraftFilm(msg.craftFilm || [], frame),
                }
              : msg,
          ),
        );
      };

      const fetchFinalStatus = async (): Promise<RunResult> => {
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
        if (body.status === "cancelled") {
          cancelled = true;
          return body as RunResult;
        }
        if (body.status === "error") {
          throw new RunFailedError(
            formatRunStatusError(body as Record<string, unknown>, runId),
            {
              runId,
              canResume: Boolean(
                (body as { can_resume?: boolean }).can_resume,
              ),
              failedStage:
                typeof (body as { failed_stage?: string }).failed_stage ===
                "string"
                  ? (body as { failed_stage: string }).failed_stage
                  : null,
            },
          );
        }
        let result = attachSlidesPayload(body as RunResult, body);
        // Deck IR lives on GET /slides — pull when twins still missing or deck absent.
        if (
          needsSlidesHydrate(result) ||
          (result.slides_status === "ok" && !result.deck)
        ) {
          try {
            const g = await fetch(
              `/api/runs/${encodeURIComponent(runId)}/slides`,
            );
            const gBody = await g.json().catch(() => ({}));
            if (g.ok) result = attachSlidesPayload(result, gBody);
          } catch {
            /* keep status-only twins */
          }
        }
        return result;
      };

      /** Status poll — used as SSE fallback (Windows proxies). */
      const pollUntilDone = async (): Promise<RunResult | null> => {
        const pollStarted = Date.now();
        let soft404 = 0;
        for (;;) {
          if (cancelRequestedRef.current) {
            cancelled = true;
            return null;
          }
          if (Date.now() - pollStarted > pollDeadlineMs) {
            throw new Error(
              "Превышено время ожидания сборки (20 мин). Попробуйте повторить запрос.",
            );
          }
          await new Promise((r) => setTimeout(r, 400));
          if (cancelRequestedRef.current) {
            cancelled = true;
            return null;
          }
          const st = await fetch(
            `/api/runs/${encodeURIComponent(runId)}/status`,
          );
          const body = await st.json().catch(() => ({}));
          if (st.status === 404) {
            soft404 += 1;
            if (soft404 > 8) {
              throw new Error(`run ${runId} не найден (status 404)`);
            }
            continue;
          }
          soft404 = 0;
          if (!st.ok) {
            throw new Error(
              typeof body.detail === "string"
                ? body.detail
                : body.error || st.statusText,
            );
          }
          const stage = body.stage as string | undefined;
          const detail = (body.stage_detail as string | null) || null;
          if (body.status === "cancelled") {
            cancelled = true;
            return null;
          }
          if (isRunInFlight(body.status)) {
            // meta.stage is source of truth — steps[] can lag (persist race)
            // and must NOT pin the checklist on «Читаю Source» for minutes.
            applyStage(stage, detail);
            const rawSteps = body.steps;
            if (Array.isArray(rawSteps) && rawSteps.length) {
              const hydrated = hydrateCraftFromSteps(
                rawSteps as CraftStepLogEntry[],
              );
              if (
                hydrated.substeps.length ||
                Object.keys(hydrated.skipped).length
              ) {
                setMsgs((m) =>
                  m.map((msg) => {
                    if (msg.id !== pendingId || msg.role !== "bot") return msg;
                    return {
                      ...msg,
                      craftSubsteps: hydrated.substeps.length
                        ? hydrated.substeps
                        : msg.craftSubsteps,
                      craftSkipped: {
                        ...(msg.craftSkipped || {}),
                        ...hydrated.skipped,
                      },
                    };
                  }),
                );
              }
            }
            continue;
          }
          if (body.status === "error") {
            throw new RunFailedError(
              formatRunStatusError(body as Record<string, unknown>, runId),
              {
                runId,
                canResume: Boolean(
                  (body as { can_resume?: boolean }).can_resume,
                ),
                failedStage:
                  typeof (body as { failed_stage?: string }).failed_stage ===
                  "string"
                    ? (body as { failed_stage: string }).failed_stage
                    : null,
              },
            );
          }
          // Presentation: pipeline status=ok early — wait for slides job (Windows poll path).
          if (outMode === "presentation") {
            const slidesSt = (body.slides_status as string) || "idle";
            if (slidesJobInFlight(slidesSt)) {
              const ss = (body.slides_stage as string) || "starting";
              applyStage(
                ss.startsWith("slides_") ? ss : `slides_${ss}`,
                null,
              );
              continue;
            }
            if (slidesJobTerminal(slidesSt)) {
              return body as RunResult;
            }
            // idle — return so caller can kick once (do not spin forever)
          }
          return body as RunResult;
        }
      };

      try {
        const terminal = await new Promise<
          "done" | "error" | "cancelled" | "fallback"
        >((resolve) => {
          let settled = false;
          let stageWatch: number | null = null;
          let cancelWatch: number | null = null;
          const settle = (v: "done" | "error" | "cancelled" | "fallback") => {
            if (settled) return;
            settled = true;
            if (stageWatch != null) window.clearInterval(stageWatch);
            if (cancelWatch != null) window.clearInterval(cancelWatch);
            resolve(v);
          };
          runCloser.events = openRunEvents(runId, {
            onStage: (stage, detail, scope, etaSec) => {
              const uiStage =
                scope === "slides" && !stage.startsWith("slides_")
                  ? `slides_${stage}`
                  : stage;
              applyStage(uiStage, detail, etaSec);
              // Presentation: after pipeline_ok, kick slides while SSE stays open
              if (
                liveMode === "presentation" &&
                (stage === "pipeline_ok" || stage === "ok") &&
                scope === "pipeline" &&
                !slidesKicked &&
                !cancelRequestedRef.current
              ) {
                slidesKicked = true;
                void fetch(
                  `/api/runs/${encodeURIComponent(runId)}/slides`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(slidesAutoKickPayload(deckStyle)),
                  },
                ).catch(() => {
                  /* makePresentation path still runs if needed */
                });
              }
            },
            onStep: (step) => {
              setMsgs((m) =>
                m.map((msg) => {
                  if (msg.id !== pendingId || msg.role !== "bot") return msg;
                  const parent = craftParentId(step.parent);
                  const nextSubs = upsertCraftSubstep(
                    msg.craftSubsteps || [],
                    step,
                  );
                  let craftSkipped = msg.craftSkipped;
                  if (step.status === "skipped" && parent) {
                    craftSkipped = {
                      ...(craftSkipped || {}),
                      [parent]: step.reason || "пропущено",
                    };
                  }
                  return {
                    ...msg,
                    craftSubsteps: nextSubs,
                    craftSkipped,
                  };
                }),
              );
            },
            onFilm: applyFilm,
            onNarration: (lines) => {
              setMsgs((m) =>
                m.map((msg) =>
                  msg.id === pendingId && msg.role === "bot"
                    ? { ...msg, stageLines: lines }
                    : msg,
                ),
              );
            },
            onChat: (phase, text, mode) => {
              if (mode) liveMode = mode;
              if (phase === "answer") {
                if (outMode !== "diagram") {
                  ensureSummaryStream();
                }
                return;
              }
              leadAcc = `${leadAcc}${text}`;
              leadPacer.pushTarget(leadAcc);
              setMsgs((m) =>
                m.map((msg) => {
                  if (msg.id !== pendingId || msg.role !== "bot") return msg;
                  return {
                    ...msg,
                    thinkingMode:
                      mode === "diagram" ||
                      mode === "presentation" ||
                      mode === "report"
                        ? mode
                        : msg.thinkingMode,
                  };
                }),
              );
            },
            onTerminal: (kind, _err, hint, recap) => {
              if (kind === "cancelled") {
                setMsgs((m) =>
                  m.map((msg) =>
                    msg.id === pendingId && msg.role === "bot"
                      ? { ...msg, craftFrozen: true, pending: false }
                      : msg,
                  ),
                );
              }
              if (kind === "error" && hint) {
                setMsgs((m) =>
                  m.map((msg) =>
                    msg.id === pendingId && msg.role === "bot"
                      ? { ...msg, errorHint: hint }
                      : msg,
                  ),
                );
              }
              if (kind === "done" && recap) {
                const line = formatCraftRecap(recap);
                if (line) {
                  setMsgs((m) =>
                    m.map((msg) =>
                      msg.id === pendingId && msg.role === "bot"
                        ? { ...msg, craftRecap: line }
                        : msg,
                    ),
                  );
                }
              }
              settle(kind);
            },
            onFallback: () => settle("fallback"),
          });
          // Vite/SSE often buffers: UI stuck on queued/Source while meta.stage=llm.
          // Poll status in parallel — stage truth; SSE still drives film/terminal.
          stageWatch = window.setInterval(() => {
            if (settled || cancelRequestedRef.current) return;
            void fetch(`/api/runs/${encodeURIComponent(runId)}/status`)
              .then(async (st) => {
                if (settled || !st.ok) return;
                const body = (await st.json().catch(() => ({}))) as {
                  status?: string;
                  stage?: string;
                  stage_detail?: string | null;
                  slides_status?: string;
                  slides_stage?: string | null;
                  steps?: CraftStepLogEntry[];
                };
                const terminalKind = pipelineWatchKind(
                  body.status,
                  body.slides_status,
                  outMode,
                );
                if (terminalKind) {
                  settle(terminalKind);
                  return;
                }
                if (!isRunInFlight(body.status)) {
                  return;
                }
                let stage = body.stage || "queued";
                if (
                  outMode === "presentation" &&
                  (body.slides_status === "running" ||
                    body.slides_status === "queued")
                ) {
                  const ss = body.slides_stage || "starting";
                  stage = ss.startsWith("slides_") ? ss : `slides_${ss}`;
                }
                applyStage(stage, body.stage_detail ?? null);
                if (Array.isArray(body.steps) && body.steps.length) {
                  const hydrated = hydrateCraftFromSteps(body.steps);
                  if (
                    hydrated.substeps.length ||
                    Object.keys(hydrated.skipped).length
                  ) {
                    setMsgs((m) =>
                      m.map((msg) => {
                        if (msg.id !== pendingId || msg.role !== "bot")
                          return msg;
                        return {
                          ...msg,
                          craftSubsteps: hydrated.substeps.length
                            ? hydrated.substeps
                            : msg.craftSubsteps,
                          craftSkipped: {
                            ...(msg.craftSkipped || {}),
                            ...hydrated.skipped,
                          },
                        };
                      }),
                    );
                  }
                }
              })
              .catch(() => {
                /* ignore transient */
              });
          }, 2000);
          // Safety: if cancel while waiting SSE
          cancelWatch = window.setInterval(() => {
            if (cancelRequestedRef.current) {
              setMsgs((m) =>
                m.map((msg) =>
                  msg.id === pendingId && msg.role === "bot"
                    ? { ...msg, craftFrozen: true }
                    : msg,
                ),
              );
              settle("cancelled");
            }
          }, 400);
          window.setTimeout(() => {
            if (cancelWatch != null) window.clearInterval(cancelWatch);
          }, pollDeadlineMs);
        });

        if (terminal === "fallback") {
          runCloser.events?.();
          runCloser.events = null;
          const polled = await pollUntilDone();
          if (polled) result = polled;
        } else if (terminal === "cancelled") {
          cancelled = true;
        } else if (terminal === "error") {
          result = await fetchFinalStatus();
        } else {
          result = await fetchFinalStatus();
        }
      } catch (innerErr) {
        answerPacer.stop();
        leadPacer.stop();
        throw innerErr;
      } finally {
        runCloser.events?.();
        runCloser.summary?.();
      }
      if (cancelled || cancelRequestedRef.current) {
        answerPacer.stop();
        leadPacer.stop();
        finishIdle();
        return;
      }
      const drainCancelWatch = window.setInterval(() => {
        if (cancelRequestedRef.current) {
          answerPacer.stop();
          leadPacer.stop();
        }
      }, 100);
      try {
        const finalStreamText =
          streamedSummary ||
          (result.output_mode === "chat" ? result.chat_summary || "" : "");
        await Promise.all([
          leadPacer.markDone(leadAcc || undefined),
          answerPacer.markDone(finalStreamText || undefined),
        ]);
      } finally {
        window.clearInterval(drainCancelWatch);
        answerPacer.stop();
        leadPacer.stop();
      }
      if (cancelRequestedRef.current) {
        finishIdle();
        return;
      }
    }

    // Pipeline may omit output_mode if an older worker rewrote meta — stamp from send.
    result = {
      ...result,
      output_mode: result.output_mode || liveMode || "auto",
    };

    const resolvedMode = result.output_mode || liveMode || outMode || "auto";
    const isPresentationOnly = resolvedMode === "presentation";
    const slidesAlreadyDone =
      result.slides_status === "ok" || Boolean(result.downloads?.pptx);
    const slidesFailed =
      isPresentationOnly &&
      (result.slides_status || "").toLowerCase() === "error";
    const slidesStillBuilding =
      isPresentationOnly &&
      Boolean(result.run_id) &&
      !slidesAlreadyDone &&
      !slidesFailed;

    const stablePhotos = uploadedPhotoThumbs(result.previews);
    if (result.run_id) {
      saveUserTurn(result.run_id, {
        text: userBody,
        photos: stablePhotos,
      });
    }
    try {
      setChatTitle(reportTitle(result));
      if (
        result.preview?.blocks?.length ||
        result.downloads?.pdf ||
        result.downloads?.pptx ||
        (result.diagrams && result.diagrams.length > 0) ||
        isPresentationOnly
      ) {
        rememberRun(result);
        setHasStoredReport(true);
      }
    } catch {
      /* quota */
    }
    setMsgs((m) =>
      m.map((msg) => {
        if (msg.id === userMsgId && msg.role === "user" && stablePhotos.length) {
          return { ...msg, photos: stablePhotos };
        }
        if (msg.id !== pendingId || msg.role !== "bot") return msg;
        const streamed =
          msg.streamingSummary && msg.text.trim() ? msg.text : "";
        if (slidesFailed) {
          return {
            ...msg,
            pending: false,
            text: "Слайды не собрались",
            error: result.slides_error || "Слайды не собрались",
            result,
            thinkingElapsedSec: msg.thinkingStartedAt
              ? Math.max(
                  0,
                  Math.round((Date.now() - msg.thinkingStartedAt) / 1000),
                )
              : msg.thinkingElapsedSec,
          };
        }
        if (slidesStillBuilding) {
          // Keep pending — never flash empty PPTX/PDF cards + «Сделать».
          const ss = result.slides_stage || "starting";
          const stageKey = ss.startsWith("slides_")
            ? ss
            : slidesJobInFlight(result.slides_status)
              ? `slides_${ss}`
              : "slides_queued";
          return appendBotThinking(
            {
              ...msg,
              thinkingMode: "presentation",
              pending: true,
              pendingStage: stageKey,
              pendingDetail: null,
              text: streamed || msg.text?.trim() || "Собираю презентацию…",
              result: {
                ...result,
                slides_status: slidesJobInFlight(result.slides_status)
                  ? result.slides_status
                  : "queued",
                slides_stage: result.slides_stage || "queued",
              },
            },
            stageKey,
            null,
          );
        }
        return {
          id: pendingId,
          role: "bot" as const,
          text: reportReadyText(result, streamed),
          lead:
            msg.lead ||
            (result.chat_opening &&
            result.chat_opening.trim() !== reportReadyText(result, streamed).trim()
              ? result.chat_opening
              : msg.lead),
          result,
          thinking: msg.thinking,
          thinkingStartedAt: msg.thinkingStartedAt,
          thinkingMode: msg.thinkingMode,
          craftFilm: msg.craftFilm,
          craftRecap: msg.craftRecap,
          craftSubsteps: msg.craftSubsteps,
          craftSkipped: msg.craftSkipped,
          errorHint: msg.errorHint,
          craftFrozen: msg.craftFrozen,
          pendingStage: msg.pendingStage,
          thinkingElapsedSec: msg.thinkingStartedAt
            ? Math.max(
                0,
                Math.round((Date.now() - msg.thinkingStartedAt) / 1000),
              )
            : undefined,
        };
      }),
    );
    if (cancelRequestedRef.current) {
      finishIdle();
      return;
    }
    if (result.insufficient_data) {
      activeRunIdRef.current = null;
      finishIdle();
      return;
    }
    if (slidesStillBuilding) {
      // Attach or kick once — never second POST when SSE already got 202.
      inFlightRef.current = false;
      void makePresentation(pendingId, result);
    } else {
      activeRunIdRef.current = null;
      finishIdle();
      if (isPresentationOnly && slidesAlreadyDone) {
        openReportArtifact(pendingId, result, "presentation");
      } else if (result.output_mode === "diagram" && result.diagrams?.[0]) {
        openDiagramArtifact(pendingId, result, result.diagrams[0].id);
      } else if (result.output_mode === "diagram") {
        openReportArtifact(pendingId, result, "diagram");
      } else if (
        result.output_mode === "report" ||
        result.output_mode === "auto" ||
        !result.output_mode
      ) {
        openReportArtifact(pendingId, result);
      }
    }
  } catch (err) {
    if (!startedOnServer && !cancelRequestedRef.current) {
      const message = err instanceof Error ? err.message : String(err);
      setMsgs((m) => rollbackOptimisticRun(m, userMsgId, pendingId));
      if (!hidden && chatTrim) {
        setChat((cur) => (cur.trim() ? cur : chatTrim));
      }
      setToast(message);
      window.setTimeout(() => setToast(null), 5200);
      activeRunIdRef.current = null;
      finishIdle();
      return;
    }
    if (!cancelRequestedRef.current) {
      const message = err instanceof Error ? err.message : String(err);
      const failed =
        err instanceof RunFailedError
          ? err
          : null;
      setMsgs((m) =>
        m.map((msg) =>
          msg.id === pendingId
            ? {
                id: pendingId,
                role: "bot",
                text: "Ошибка",
                error: message,
                canResume: failed?.canResume,
                failedRunId: failed?.runId ?? activeRunIdRef.current,
                failedStage: failed?.failedStage,
              }
            : msg,
        ),
      );
    }
    activeRunIdRef.current = null;
    finishIdle();
  }
}
  ,
    [
      canSend,
      chat,
      sourceDraft,
      file,
      health,
      imageChip,
      msgs,
      workMode,
      deckStyle,
      attachPhotos,
      forbidCharts,
      forbidImages,
      maxCharts,
      maxImages,
      maxDiagrams,
      targetSlides,
      dryRun,
      setMsgs,
      setBusy,
      setStopping,
      setChat,
      setChatTitle,
      setFile,
      setSourceDraft,
      setPlaqueDismissed,
      setAttachPhotos,
      setHasStoredReport,
      setToast,
      setDeckApplyHint,
      setRailExiting,
      setRailCollapsed,
      setActiveArtifact,
      chatRef,
      cancelRequestedRef,
      activeRunIdRef,
      pendingBotIdRef,
      rememberRun,
      openReportArtifact,
      openDiagramArtifact,
      makePresentation,
    ],
  );
}
