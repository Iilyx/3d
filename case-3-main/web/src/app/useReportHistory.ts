/** Sidebar history + folders owner (out of App shell). */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  needsSlidesHydrate,
  type SlidesPayload,
} from "../domain/attachSlidesPayload";
import { rememberCarriedRun } from "../domain/carriedRun";
import {
  createFolder,
  deleteFolder,
  hydrateHistoryResult,
  loadFolders,
  loadHistory,
  loadHistoryPayload,
  loadUserTurn,
  mergeServerFolders,
  mergeServerHistory,
  moveHistoryToFolder,
  pushHistory,
  renameFolder,
  saveRunPayload,
  syncServerHistory,
  togglePinHistory,
  uploadedPhotoThumbs,
  type HistoryFolder,
  type HistoryItem,
} from "../domain/reportHistory";
import { reportReadyText, reportTitle, uid } from "../domain/runHelpers";
import { loadOpenChat, rememberOpenChat } from "../domain/openChat";
import { botHistoryResult, messagesFromMemory } from "../domain/priorRun";
import { chatToReopen, historyRailRun } from "../domain/reviseRefresh";
import type { Msg, RunResult, SourceDraft } from "../domain/liberTypes";

type Deps = {
  busy: boolean;
  setMsgs: Dispatch<SetStateAction<Msg[]>>;
  setChatTitle: Dispatch<SetStateAction<string | null>>;
  showToast: (message: string, ms?: number) => void;
  openReportArtifact?: (msgId: string, result: RunResult) => void;
  onResetSurface?: () => void;
  onRestoreSource?: (draft: SourceDraft | null) => void;
};

export function useReportHistory({
  busy,
  setMsgs,
  setChatTitle,
  showToast,
  openReportArtifact,
  onResetSurface,
  onRestoreSource,
}: Deps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>(() => loadHistory());
  const [folders, setFolders] = useState<HistoryFolder[]>(() => loadFolders());
  const [historyReady, setHistoryReady] = useState(false);
  const restored = useRef(false);

  // Hydrate history from server on mount
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/api/history");
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as {
          items?: HistoryItem[];
          folders?: HistoryFolder[];
        };
        if (cancelled) return;
        if (Array.isArray(data.items) && data.items.length > 0) {
          setHistory((prev) => mergeServerHistory(prev, data.items || []));
        }
        if (Array.isArray(data.folders) && data.folders.length > 0) {
          setFolders((prev) => mergeServerFolders(prev, data.folders || []));
        }
      } catch {
        /* ignore offline/server not ready */
      } finally {
        if (!cancelled) setHistoryReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const persistServer = useCallback(
    (items: HistoryItem[], nextFolders: HistoryFolder[]) => {
      void syncServerHistory(items, nextFolders).then((result) => {
        if (!result.ok) showToast("История не сохранилась на сервере");
      });
    },
    [showToast],
  );

  const rememberRun = useCallback(
    (result: RunResult) => {
      saveRunPayload(result);
      rememberOpenChat(result.run_id);
      const title = reportTitle(result);
      setChatTitle(title);
      const next = pushHistory({
        id: result.run_id,
        title,
        runId: result.run_id,
        savedAt: Date.now(),
        priorRunId: result.prior_run_id || undefined,
      });
      setHistory(next);
      void persistServer(next, folders);
    },
    [folders, persistServer, setChatTitle],
  );

  const openHistoryItem = useCallback(
    (item: HistoryItem) => {
      if (busy) return;
      rememberCarriedRun("");
      void (async () => {
        const stored = loadHistoryPayload(item.runId);
        let remote: RunResult | null = null;
        try {
          const res = await fetch(
            `/api/runs/${encodeURIComponent(item.runId)}/status`,
          );
          if (res.ok) remote = (await res.json()) as RunResult;
        } catch {
          /* session copy is enough */
        }
        let result = hydrateHistoryResult(stored, remote);
        if (!result) {
          showToast("Отчёт недоступен в этой сессии");
          return;
        }
        if (
          needsSlidesHydrate(result) ||
          result.output_mode === "presentation"
        ) {
          try {
            const sr = await fetch(
              `/api/runs/${encodeURIComponent(item.runId)}/slides`,
            );
            if (sr.ok) {
              const sp = (await sr.json()) as SlidesPayload;
              result = hydrateHistoryResult(stored, remote, sp) || result;
            }
          } catch {
            /* status payload is enough */
          }
        }
        saveRunPayload(result);
        rememberOpenChat(item.runId);
        const turn = loadUserTurn(item.runId);
        const userText = (turn?.text || result.user_text || "").trim();
        const photos = turn?.photos?.length
          ? turn.photos
          : uploadedPhotoThumbs(result.previews);
        const hasArtifact = Boolean(
          result.preview?.blocks?.length ||
            result.downloads?.pdf ||
            result.downloads?.pptx ||
            result.downloads?.deck_pdf ||
            result.diagrams?.length ||
            result.deck?.slides?.length ||
            result.slide_pngs?.length,
        );
        const hasChat =
          Boolean((result.chat_summary || "").trim()) ||
          result.output_mode === "chat";
        if (!hasArtifact && !hasChat && !userText && !photos.length) {
          showToast("Отчёт недоступен в этой сессии");
          return;
        }
        onResetSurface?.();
        setChatTitle(item.title || reportTitle(result));
        let memory: {
          turns?: Parameters<typeof messagesFromMemory>[0];
          documents?: { name?: string; text?: string }[];
          artifact_run_id?: string;
        } | null = null;
        try {
          const mr = await fetch(
            `/api/runs/${encodeURIComponent(item.runId)}/memory`,
          );
          if (mr.ok) memory = await mr.json();
        } catch {
          memory = null;
        }
        let shown = result;
        const railId = historyRailRun(result, memory?.artifact_run_id || "");
        if (railId && railId !== result.run_id) {
          try {
            const ar = await fetch(`/api/runs/${encodeURIComponent(railId)}/status`);
            if (ar.ok) {
              shown = {
                ...((await ar.json()) as RunResult),
                chain_head: result.run_id,
              };
            }
          } catch {
            shown = result;
          }
        }
        const shownHasArtifact = Boolean(
          shown.preview?.blocks?.length ||
            shown.downloads?.pdf ||
            shown.downloads?.pptx ||
            shown.downloads?.deck_pdf ||
            shown.diagrams?.length ||
            shown.deck?.slides?.length ||
            shown.slide_pngs?.length,
        );
        const remembered = messagesFromMemory(memory?.turns || [], uid);
        const next: Msg[] = remembered.length
          ? remembered.map((line) =>
              line.role === "user"
                ? {
                    id: line.id,
                    role: "user" as const,
                    text: line.text,
                    photos: line.photos,
                    attachment: line.attachment,
                    attachments: line.attachments,
                  }
                : {
                    id: line.id,
                    role: "bot" as const,
                    text: line.text,
                    lead: line.lead,
                    dashboard: line.dashboard,
                    result: botHistoryResult(line, result.run_id),
                  },
            )
          : [];
        if (!next.length && (userText || photos.length)) {
          next.push({
            id: uid(),
            role: "user",
            text: userText,
            photos,
          });
        }
        if (!remembered.length && (hasArtifact || hasChat)) {
          next.push({
            id: uid(),
            role: "bot",
            text: reportReadyText(result),
            lead:
              result.chat_opening &&
              result.chat_opening.trim() !== reportReadyText(result).trim()
                ? result.chat_opening
                : undefined,
            result: shown,
          });
        }
        let botMsgId: string | null = null;
        if (remembered.length && (hasArtifact || hasChat || shownHasArtifact)) {
          for (let i = next.length - 1; i >= 0; i -= 1) {
            const line = next[i];
            if (line.role !== "bot") continue;
            const prevPreviews = line.result?.previews;
            line.result =
              prevPreviews?.length && !(shown.previews || []).length
                ? { ...shown, previews: prevPreviews }
                : shown;
            botMsgId = line.id;
            break;
          }
        } else {
          const bot = [...next].reverse().find((line) => line.role === "bot");
          botMsgId = bot?.id ?? null;
        }
        setMsgs(next);
        onRestoreSource?.(null);
        if (botMsgId && shownHasArtifact) {
          openReportArtifact?.(botMsgId, shown);
        }
      })();
    },
    [
      busy,
      onResetSurface,
      onRestoreSource,
      openReportArtifact,
      setChatTitle,
      setMsgs,
      showToast,
    ],
  );

  useEffect(() => {
    if (!historyReady || restored.current) return;
    restored.current = true;
    if (typeof window !== "undefined" && /preview=/.test(window.location.search)) {
      return;
    }
    const id = chatToReopen(history, loadOpenChat(), false);
    const item = history.find((row) => row.runId === id);
    if (item) openHistoryItem(item);
  }, [history, historyReady, openHistoryItem]);

  const onTogglePin = useCallback(
    (runId: string) => {
      const next = togglePinHistory(runId);
      setHistory(next);
      void persistServer(next, folders);
    },
    [folders, persistServer],
  );

  const onMoveToFolder = useCallback(
    (runId: string, folderId: string | null) => {
      const next = moveHistoryToFolder(runId, folderId);
      setHistory(next);
      void persistServer(next, folders);
    },
    [folders, persistServer],
  );

  const onCreateFolder = useCallback(
    (name: string) => {
      const next = createFolder(name);
      setFolders(next);
      void persistServer(history, next);
    },
    [history, persistServer],
  );

  const onRenameFolder = useCallback(
    (id: string, name: string) => {
      const next = renameFolder(id, name);
      setFolders(next);
      void persistServer(history, next);
    },
    [history, persistServer],
  );

  const onDeleteFolder = useCallback(
    (id: string) => {
      const next = deleteFolder(id);
      setFolders(next.folders);
      setHistory(next.history);
      void persistServer(next.history, next.folders);
    },
    [persistServer],
  );

  return {
    sidebarCollapsed,
    setSidebarCollapsed,
    history,
    folders,
    rememberRun,
    openHistoryItem,
    onTogglePin,
    onMoveToFolder,
    onCreateFolder,
    onRenameFolder,
    onDeleteFolder,
  };
}
