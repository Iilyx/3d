/** Restore last report / clear desk for a new report. */

import type { Dispatch, RefObject, SetStateAction } from "react";
import {
  reportReadyText,
  reportTitle,
  uid,
} from "../domain/runHelpers";
import { rememberCarriedRun } from "../domain/carriedRun";
import { clearOpenChat } from "../domain/openChat";
import type { Msg, RunResult, SourceDraft } from "../domain/liberTypes";
import type { ActiveArtifact } from "../ArtifactRail";
import type { EditError } from "./useLiberEdits";

type Deps = {
  setMsgs: Dispatch<SetStateAction<Msg[]>>;
  setChatTitle: Dispatch<SetStateAction<string | null>>;
  setChat: Dispatch<SetStateAction<string>>;
  setFile: Dispatch<SetStateAction<File | null>>;
  setSourceDraft: Dispatch<SetStateAction<SourceDraft | null>>;
  setAttachPhotos: Dispatch<SetStateAction<File[]>>;
  setRailExiting: Dispatch<SetStateAction<boolean>>;
  setRailCollapsed: Dispatch<SetStateAction<boolean>>;
  setActiveArtifact: Dispatch<SetStateAction<ActiveArtifact | null>>;
  setPlaqueDismissed: Dispatch<SetStateAction<boolean>>;
  setEditError: Dispatch<SetStateAction<EditError>>;
  chatRef: RefObject<HTMLTextAreaElement | null>;
};

export function useReportSession({
  setMsgs,
  setChatTitle,
  setChat,
  setFile,
  setSourceDraft,
  setAttachPhotos,
  setRailExiting,
  setRailCollapsed,
  setActiveArtifact,
  setPlaqueDismissed,
  setEditError,
  chatRef,
}: Deps) {
  function restoreLastReport() {
    try {
      const raw = sessionStorage.getItem("liber-last-report");
      if (!raw) return;
      const result = JSON.parse(raw) as RunResult;
      if (!result?.preview?.blocks?.length) return;
      const id = uid();
      setChatTitle(reportTitle(result));
      setMsgs([
        {
          id,
          role: "bot",
          text: reportReadyText(result),
          result,
        },
      ]);
    } catch {
      /* ignore */
    }
  }

  function startNewReport(options?: { keepSource?: boolean; carryRunId?: string }) {
    clearOpenChat();
    setMsgs([]);
    setChatTitle(null);
    setChat("");
    setAttachPhotos([]);
    if (options?.keepSource) {
      rememberCarriedRun(options.carryRunId || "");
    } else {
      rememberCarriedRun("");
      setFile(null);
      setSourceDraft(null);
    }
    setRailExiting(false);
    setRailCollapsed(false);
    setActiveArtifact(null);
    setPlaqueDismissed(false);
    setEditError(null);
    chatRef.current?.focus();
  }

  return { restoreLastReport, startNewReport };
}
