/** Liber Preview edit/undo handlers (charts, figures, tables, paragraphs). */

import {
  useCallback,
  useRef,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";
import type { ChartEditRequest } from "../ChartEditSheet";
import { useConfirm } from "../ConfirmModal";
import {
  chartNumberEditConfirm,
  numberChangeFromEditError,
} from "../domain/chartTypeFit";
import type { ImageEditRequest } from "../ImageEditModal";
import type { ParagraphEditRequest } from "../ParagraphEditSheet";
import type { HeadingEditRequest } from "../HeadingEditTypes";
import type { ListEditRequest } from "../ListEditTypes";
import type { TableEditRequest } from "../TableEditSheet";
import { asDownloads } from "../domain/runHelpers";
import type { Msg, RunResult } from "../domain/liberTypes";
import {
  docsNeedRebuild,
  parseEditHistory,
  toastUndoRebuildsDocs,
  type EditHistoryDesc,
} from "../domain/reportEditMode";
import { scrollReportUndo } from "../domain/reportUndoJump";
import { mapTableEditHttpError, postJsonEdit } from "./postJsonEdit";

/** Preview-only edit session; PDF/DOCX flush on «Готово». */
const EDIT_FORMATS = "none";
const PREVIEW_EDIT_TOAST = "Превью обновлено · Готово обновит PDF/DOCX";

export type EditBusy = { msgId: string; figureId: string } | null;
export type EditError = { msgId: string; figureId: string; message: string } | null;
export type UndoOffer = { msgId: string; runId: string } | null;

type UndoApi = {
  kind?: string | null;
  target?: string | null;
  can_undo?: boolean;
  can_redo?: boolean;
  depth?: number;
} | null;

type EditPayloadData = {
  preview?: RunResult["preview"];
  downloads?: RunResult["downloads"];
  warnings?: string[];
  media_status?: RunResult["media_status"];
  diagrams?: RunResult["diagrams"];
  undo?: UndoApi;
  memory_section?: string;
};

type Args = {
  setMsgs: Dispatch<SetStateAction<Msg[]>>;
  rememberRun: (result: RunResult) => void;
  setEditBusy: Dispatch<SetStateAction<EditBusy>>;
  setEditError: Dispatch<SetStateAction<EditError>>;
  setUndoOffer: Dispatch<SetStateAction<UndoOffer>>;
  setToast: Dispatch<SetStateAction<string | null>>;
  setDownloadsPulseMsgId: Dispatch<SetStateAction<string | null>>;
  setEditHistory?: Dispatch<SetStateAction<EditHistoryDesc>>;
  undoOffer: UndoOffer;
  undoBusyRef?: MutableRefObject<boolean>;
};

export function useLiberEdits({
  setMsgs,
  rememberRun,
  setEditBusy,
  setEditError,
  setUndoOffer,
  setToast,
  setDownloadsPulseMsgId,
  setEditHistory,
  undoOffer,
  undoBusyRef: undoBusyRefProp,
}: Args) {
  const confirm = useConfirm();
  const editLock = useRef(false);
  const undoBusyLocal = useRef(false);
  const undoBusyRef = undoBusyRefProp ?? undoBusyLocal;

  const applyEditPayload = useCallback(
    (
      msgId: string,
      runId: string,
      data: EditPayloadData,
      toastText: string,
      opts?: { pulseDownloads?: boolean },
    ) => {
      setMsgs((list) =>
        list.map((msg) => {
          if (msg.id !== msgId || msg.role !== "bot" || !msg.result) return msg;
          const mergedDownloads = {
            ...(msg.result.downloads || {}),
            ...(data.downloads || {}),
          };
          const next = {
            ...msg,
            result: {
              ...msg.result,
              preview: data.preview ?? msg.result.preview,
              // Merge so report edit envelopes never wipe pptx / deck_pdf.
              downloads: mergedDownloads,
              warnings:
                Array.isArray(data.warnings) && data.warnings.length
                  ? data.warnings
                  : msg.result.warnings,
              media_status: data.media_status ?? msg.result.media_status,
              diagrams: data.diagrams ?? msg.result.diagrams,
              ...(typeof data.memory_section === "string"
                ? { memory_section: data.memory_section }
                : {}),
            },
          };
          if (next.result) rememberRun(next.result);
          return next;
        }),
      );
      const history = parseEditHistory(data.undo);
      setEditHistory?.(history);
      if (history.canUndo) {
        setUndoOffer({ msgId, runId });
      } else {
        setUndoOffer(null);
      }
      if (toastText) {
        setToast(toastText);
        window.setTimeout(() => setToast(null), 4200);
      }
      if (opts?.pulseDownloads) {
        setDownloadsPulseMsgId(msgId);
        window.setTimeout(() => setDownloadsPulseMsgId(null), 2200);
      }
    },
    [
      setMsgs,
      rememberRun,
      setUndoOffer,
      setToast,
      setDownloadsPulseMsgId,
      setEditHistory,
    ],
  );

  async function postHistory(
    msgId: string,
    runId: string,
    path: "undo" | "redo",
    okToast: string,
    opts?: { rebuild?: boolean; quiet?: boolean },
  ): Promise<EditHistoryDesc | null> {
    if (undoBusyRef.current) return null;
    undoBusyRef.current = true;
    try {
      const q =
        opts?.rebuild === false ? "?rebuild=0" : "";
      const res = await fetch(
        `/api/runs/${encodeURIComponent(runId)}/${path}${q}`,
        { method: "POST" },
      );
      const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : typeof data.error === "string"
              ? data.error
              : res.statusText || `${path} failed`,
        );
      }
      applyEditPayload(
        msgId,
        runId,
        {
          preview: data.preview as RunResult["preview"],
          downloads: asDownloads(data.downloads, {}),
          warnings: Array.isArray(data.warnings)
            ? data.warnings.filter((w): w is string => typeof w === "string")
            : undefined,
          media_status: data.media_status as RunResult["media_status"],
          undo: data.undo as UndoApi,
          memory_section:
            typeof data.memory_section === "string"
              ? data.memory_section
              : path === "undo"
                ? ""
                : undefined,
        },
        opts?.quiet ? "" : okToast,
        { pulseDownloads: opts?.rebuild !== false && !opts?.quiet },
      );
      const history = parseEditHistory(data.undo as UndoApi);
      if (!opts?.quiet) {
        const key = path === "undo" ? "undone" : "redone";
        const raw = data[key];
        if (raw && typeof raw === "object") {
          const jump = raw as { kind?: unknown; target?: unknown };
          const kind = typeof jump.kind === "string" ? jump.kind : "";
          const target = typeof jump.target === "string" ? jump.target : "";
          if (kind) scrollReportUndo(kind, target);
        }
      }
      return history;
    } catch (err) {
      if (!opts?.quiet) {
        setToast(err instanceof Error ? err.message : String(err));
        window.setTimeout(() => setToast(null), 3200);
      }
      return null;
    } finally {
      undoBusyRef.current = false;
    }
  }

  async function undoLastEdit() {
    if (!undoOffer) return;
    const { msgId, runId } = undoOffer;
    await postHistory(msgId, runId, "undo", "Правка отменена", {
      rebuild: toastUndoRebuildsDocs(),
    });
  }

  async function undoEdit(msgId: string, runId: string) {
    await postHistory(msgId, runId, "undo", "Правка отменена", {
      rebuild: false,
    });
  }

  async function redoEdit(msgId: string, runId: string) {
    await postHistory(msgId, runId, "redo", "Правка возвращена", {
      rebuild: false,
    });
  }

  async function discardEdits(msgId: string, runId: string) {
    for (let i = 0; i < 40; i++) {
      const hist = await postHistory(msgId, runId, "undo", "", {
        rebuild: false,
        quiet: true,
      });
      if (!hist || !hist.canUndo) break;
    }
    await clearEditHistory(runId);
    setToast("Изменения отменены");
    window.setTimeout(() => setToast(null), 3200);
  }

  async function clearEditHistory(runId: string) {
    try {
      await fetch(
        `/api/runs/${encodeURIComponent(runId)}/edit-history/clear`,
        { method: "POST" },
      );
    } catch {
      /* ignore */
    }
    setEditHistory?.({ canUndo: false, canRedo: false, depth: 0 });
    setUndoOffer(null);
  }

  async function rebuildDocs(msgId: string, runId: string): Promise<boolean> {
    if (editLock.current) return false;
    editLock.current = true;
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(runId)}/docs/rebuild`,
        {},
        "docs rebuild failed",
      );
      applyEditPayload(
        msgId,
        runId,
        {
          preview: data.preview as RunResult["preview"],
          downloads: asDownloads(data.downloads, {}),
          warnings: Array.isArray(data.warnings)
            ? data.warnings.filter((w): w is string => typeof w === "string")
            : undefined,
          media_status: data.media_status as RunResult["media_status"],
          undo: data.undo as UndoApi,
        },
        "PDF и DOCX обновлены",
        { pulseDownloads: true },
      );
      return true;
    } catch (err) {
      setToast(err instanceof Error ? err.message : String(err));
      window.setTimeout(() => setToast(null), 3200);
      return false;
    } finally {
      editLock.current = false;
    }
  }

  async function finishEditSession(
    msgId: string,
    runId: string,
    history: EditHistoryDesc | null | undefined,
  ): Promise<boolean> {
    if (docsNeedRebuild(history)) {
      const ok = await rebuildDocs(msgId, runId);
      if (!ok) return false;
    }
    await clearEditHistory(runId);
    return true;
  }

  async function editFigure(
    msgId: string,
    runId: string,
    req: ChartEditRequest,
    allowNumberRetry = true,
  ): Promise<boolean> {
    if (editLock.current) return false;
    editLock.current = true;
    setEditError(null);
    setEditBusy({ msgId, figureId: req.figureId });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(runId)}/charts/${encodeURIComponent(req.figureId)}/edit`,
        {
          palette: req.palette,
          style: req.styleNotes,
          chart_type: req.chartType,
          formats: EDIT_FORMATS,
          accepted_html: req.acceptedHtml || "",
        },
      );
      applyEditPayload(msgId, runId, data, PREVIEW_EDIT_TOAST);
      return true;
    } catch (err) {
      const changed = allowNumberRetry ? numberChangeFromEditError(err) : null;
      if (changed) {
        const ask = chartNumberEditConfirm(changed.message);
        const ok = ask ? await confirm(ask) : false;
        if (!ok) return false;
        editLock.current = false;
        setEditBusy(null);
        return await editFigure(
          msgId,
          runId,
          { ...req, acceptedHtml: changed.html },
          false,
        );
      }
      setEditError({
        msgId,
        figureId: req.figureId,
        message: err instanceof Error ? err.message : String(err),
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  async function recolorCharts(
    msgId: string,
    runId: string,
    palette: string,
  ): Promise<boolean> {
    if (editLock.current) return false;
    editLock.current = true;
    setEditError(null);
    setEditBusy({ msgId, figureId: "charts_all" });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(runId)}/charts/recolor`,
        {
          palette,
          formats: EDIT_FORMATS,
        },
        "recolor charts failed",
      );
      applyEditPayload(
        msgId,
        runId,
        data,
        `Все графики перекрашены (${palette}) · Готово обновит PDF/DOCX`,
      );
      return true;
    } catch (err) {
      setEditError({
        msgId,
        figureId: "charts_all",
        message: err instanceof Error ? err.message : String(err),
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  async function editImage(
    msgId: string,
    runId: string,
    req: ImageEditRequest,
  ): Promise<boolean> {
    if (editLock.current) return false;
    editLock.current = true;
    setEditError(null);
    setEditBusy({ msgId, figureId: req.figureId });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(runId)}/figures/${encodeURIComponent(req.figureId)}/edit`,
        {
          mode: req.mode,
          prompt: req.prompt,
          caption: req.caption,
          formats: EDIT_FORMATS,
        },
        "image edit failed",
      );
      applyEditPayload(
        msgId,
        runId,
        data,
        req.mode === "edit"
          ? "Фото изменено · Готово обновит PDF/DOCX"
          : "Фото обновлено · Готово обновит PDF/DOCX",
      );
      return true;
    } catch (err) {
      setEditError({
        msgId,
        figureId: req.figureId,
        message: err instanceof Error ? err.message : String(err),
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  async function uploadFigure(
    msgId: string,
    runId: string,
    figureId: string,
    file: File,
    caption?: string,
  ): Promise<boolean> {
    if (editLock.current) return false;
    editLock.current = true;
    setEditError(null);
    setEditBusy({ msgId, figureId });
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (caption) fd.append("caption", caption);
      const res = await fetch(
        `/api/runs/${encodeURIComponent(runId)}/figures/${encodeURIComponent(figureId)}/upload`,
        {
          method: "POST",
          body: fd,
        },
      );
      const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : typeof data.error === "string"
              ? data.error
              : "upload figure failed",
        );
      }
      applyEditPayload(
        msgId,
        runId,
        data,
        "Фото загружено · Готово обновит PDF/DOCX",
      );
      return true;
    } catch (err) {
      setEditError({
        msgId,
        figureId,
        message: err instanceof Error ? err.message : String(err),
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  async function deleteFigure(
    msgId: string,
    runId: string,
    figureId: string,
  ): Promise<boolean> {
    if (editLock.current) return false;
    editLock.current = true;
    setEditError(null);
    setEditBusy({ msgId, figureId });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(runId)}/figures/${encodeURIComponent(figureId)}/delete`,
        { formats: EDIT_FORMATS },
        "delete figure failed",
      );
      applyEditPayload(
        msgId,
        runId,
        data,
        "Элемент удалён · Готово обновит PDF/DOCX",
      );
      return true;
    } catch (err) {
      setEditError({
        msgId,
        figureId,
        message: err instanceof Error ? err.message : String(err),
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  async function editTable(
    msgId: string,
    runId: string,
    req: TableEditRequest,
  ): Promise<boolean> {
    if (editLock.current) return false;
    const rid = (runId || "").trim();
    if (!rid) {
      setEditError({
        msgId,
        figureId: `tab:${req.tableIndex}`,
        message:
          "Откройте сохранённый отчёт, чтобы внести правку",
      });
      return false;
    }
    editLock.current = true;
    const tableId = `tab:${req.tableIndex}`;
    setEditError(null);
    setEditBusy({ msgId, figureId: tableId });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(rid)}/tables/${req.tableIndex}/edit`,
        {
          caption: req.caption,
          headers: req.headers,
          rows: req.rows,
          formats: EDIT_FORMATS,
        },
        "table edit failed",
      );
      applyEditPayload(
        msgId,
        rid,
        {
          preview: data.preview as RunResult["preview"],
          downloads: asDownloads(data.downloads, {}),
          warnings: Array.isArray(data.warnings)
            ? data.warnings.filter((w): w is string => typeof w === "string")
            : undefined,
          media_status: data.media_status as RunResult["media_status"],
          undo: data.undo as { kind?: string; target?: string } | null,
        },
        PREVIEW_EDIT_TOAST,
      );
      return true;
    } catch (err) {
      const mapped = mapTableEditHttpError(err);
      setEditError({
        msgId,
        figureId: tableId,
        message: mapped.message,
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  async function editParagraph(
    msgId: string,
    runId: string,
    req: ParagraphEditRequest,
  ): Promise<boolean> {
    if (editLock.current) return false;
    const rid = (runId || "").trim();
    if (!rid) {
      setEditError({
        msgId,
        figureId: `para:${req.paragraphIndex}`,
        message: "Откройте сохранённый отчёт, чтобы внести правку",
      });
      return false;
    }
    editLock.current = true;
    const paraId = `para:${req.paragraphIndex}`;
    setEditError(null);
    setEditBusy({ msgId, figureId: paraId });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(rid)}/paragraphs/${req.paragraphIndex}/edit`,
        { text: req.text, formats: EDIT_FORMATS },
        "paragraph edit failed",
      );
      applyEditPayload(
        msgId,
        rid,
        {
          preview: data.preview as RunResult["preview"],
          downloads: asDownloads(data.downloads, {}),
          warnings: Array.isArray(data.warnings)
            ? data.warnings.filter((w): w is string => typeof w === "string")
            : undefined,
          media_status: data.media_status as RunResult["media_status"],
          undo: data.undo as { kind?: string; target?: string } | null,
        },
        PREVIEW_EDIT_TOAST,
      );
      return true;
    } catch (err) {
      setEditError({
        msgId,
        figureId: paraId,
        message: err instanceof Error ? err.message : String(err),
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  async function insertParagraph(
    msgId: string,
    runId: string,
    req: {
      text: string;
      afterParagraphIndex?: number;
      afterHeadingIndex?: number;
    },
  ): Promise<boolean> {
    if (editLock.current) return false;
    const rid = (runId || "").trim();
    if (!rid) {
      setEditError({
        msgId,
        figureId: "para:insert",
        message: "Откройте сохранённый отчёт, чтобы внести правку",
      });
      return false;
    }
    editLock.current = true;
    const insertKey = req.afterParagraphIndex
      ? `para:after-${req.afterParagraphIndex}`
      : req.afterHeadingIndex
        ? `head:after-${req.afterHeadingIndex}`
        : "para:insert";
    setEditError(null);
    setEditBusy({ msgId, figureId: insertKey });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(rid)}/paragraphs/insert`,
        {
          text: req.text,
          after_paragraph_index: req.afterParagraphIndex,
          after_heading_index: req.afterHeadingIndex,
          formats: EDIT_FORMATS,
        },
        "paragraph insert failed",
      );
      applyEditPayload(
        msgId,
        rid,
        {
          preview: data.preview as RunResult["preview"],
          downloads: asDownloads(data.downloads, {}),
          warnings: Array.isArray(data.warnings)
            ? data.warnings.filter((w): w is string => typeof w === "string")
            : undefined,
          media_status: data.media_status as RunResult["media_status"],
          undo: data.undo as { kind?: string; target?: string } | null,
        },
        "Абзац добавлен",
        { pulseDownloads: false },
      );
      return true;
    } catch (e) {
      setEditError({
        msgId,
        figureId: insertKey,
        message: e instanceof Error ? e.message : "Не удалось добавить абзац",
      });
      return false;
    } finally {
      editLock.current = false;
      setEditBusy(null);
    }
  }

  async function editHeading(
    msgId: string,
    runId: string,
    req: HeadingEditRequest,
  ): Promise<boolean> {
    if (editLock.current) return false;
    const rid = (runId || "").trim();
    if (!rid) {
      setEditError({
        msgId,
        figureId: `heading:${req.headingIndex}`,
        message: "Откройте сохранённый отчёт, чтобы внести правку",
      });
      return false;
    }
    editLock.current = true;
    const headId = `heading:${req.headingIndex}`;
    setEditError(null);
    setEditBusy({ msgId, figureId: headId });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(rid)}/headings/${req.headingIndex}/edit`,
        { text: req.text, formats: EDIT_FORMATS },
        "heading edit failed",
      );
      applyEditPayload(
        msgId,
        rid,
        {
          preview: data.preview as RunResult["preview"],
          downloads: asDownloads(data.downloads, {}),
          warnings: Array.isArray(data.warnings)
            ? data.warnings.filter((w): w is string => typeof w === "string")
            : undefined,
          media_status: data.media_status as RunResult["media_status"],
          undo: data.undo as { kind?: string; target?: string } | null,
        },
        PREVIEW_EDIT_TOAST,
      );
      return true;
    } catch (err) {
      setEditError({
        msgId,
        figureId: headId,
        message: err instanceof Error ? err.message : String(err),
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  async function editTitle(
    msgId: string,
    runId: string,
    text: string,
  ): Promise<boolean> {
    if (editLock.current) return false;
    const rid = (runId || "").trim();
    if (!rid) {
      setEditError({
        msgId,
        figureId: "doc_title",
        message: "Откройте сохранённый отчёт, чтобы внести правку",
      });
      return false;
    }
    editLock.current = true;
    setEditError(null);
    setEditBusy({ msgId, figureId: "doc_title" });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(rid)}/title/edit`,
        { text, formats: EDIT_FORMATS },
        "title edit failed",
      );
      applyEditPayload(
        msgId,
        rid,
        {
          preview: data.preview as RunResult["preview"],
          downloads: asDownloads(data.downloads, {}),
          warnings: Array.isArray(data.warnings)
            ? data.warnings.filter((w): w is string => typeof w === "string")
            : undefined,
          media_status: data.media_status as RunResult["media_status"],
          undo: data.undo as { kind?: string; target?: string } | null,
        },
        PREVIEW_EDIT_TOAST,
      );
      return true;
    } catch (err) {
      setEditError({
        msgId,
        figureId: "doc_title",
        message: err instanceof Error ? err.message : String(err),
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  async function editList(
    msgId: string,
    runId: string,
    req: ListEditRequest,
  ): Promise<boolean> {
    if (editLock.current) return false;
    const rid = (runId || "").trim();
    if (!rid) {
      setEditError({
        msgId,
        figureId: `list:${req.listIndex}`,
        message: "Откройте сохранённый отчёт, чтобы внести правку",
      });
      return false;
    }
    editLock.current = true;
    const listId = `list:${req.listIndex}`;
    setEditError(null);
    setEditBusy({ msgId, figureId: listId });
    try {
      const data = await postJsonEdit(
        `/api/runs/${encodeURIComponent(rid)}/lists/${req.listIndex}/edit`,
        {
          items: req.items,
          ordered: req.ordered,
          formats: EDIT_FORMATS,
        },
        "list edit failed",
      );
      applyEditPayload(
        msgId,
        rid,
        {
          preview: data.preview as RunResult["preview"],
          downloads: asDownloads(data.downloads, {}),
          warnings: Array.isArray(data.warnings)
            ? data.warnings.filter((w): w is string => typeof w === "string")
            : undefined,
          media_status: data.media_status as RunResult["media_status"],
          undo: data.undo as { kind?: string; target?: string } | null,
        },
        PREVIEW_EDIT_TOAST,
      );
      return true;
    } catch (err) {
      setEditError({
        msgId,
        figureId: listId,
        message: err instanceof Error ? err.message : String(err),
      });
      return false;
    } finally {
      setEditBusy(null);
      editLock.current = false;
    }
  }

  return {
    editFigure,
    recolorCharts,
    uploadFigure,
    deleteFigure,
    editImage,
    editTable,
    editParagraph,
    insertParagraph,
    editHeading,
    editTitle,
    editList,
    undoLastEdit,
    undoEdit,
    redoEdit,
    clearEditHistory,
    discardEdits,
    rebuildDocs,
    finishEditSession,
  };
}
