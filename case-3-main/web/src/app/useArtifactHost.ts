/** Artifact rail open/close/tab owner (out of App shell). */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MutableRefObject,
} from "react";
import type {
  ActiveArtifact,
  ArtifactTab,
} from "../ArtifactRail";
import type { CraftFilmFrame } from "../domain/craftSteps";
import type {
  Msg,
  RunResult,
  SourceAttachment,
  SourceDraft,
  UserPhotoThumb,
} from "../domain/liberTypes";
import { reportTitle } from "../domain/runHelpers";
import { loadRailWidth, saveRailWidth } from "../domain/railWidth";

type Deps = {
  msgs: Msg[];
  activeRunIdRef: MutableRefObject<string | null>;
};

export function useArtifactHost({ msgs, activeRunIdRef }: Deps) {
  const [activeArtifact, setActiveArtifact] = useState<ActiveArtifact | null>(
    null,
  );
  const [narrowRail, setNarrowRail] = useState(false);
  const [railWidthPct, setRailWidthPct] = useState(() => loadRailWidth());
  const [railExiting, setRailExiting] = useState(false);
  /** After close animation: thin right stub so user can reopen (like left sidebar). */
  const [railCollapsed, setRailCollapsed] = useState(false);
  const lastArtifactRef = useRef<ActiveArtifact | null>(null);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 899px)");
    const sync = () => setNarrowRail(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (activeArtifact && !railExiting) {
      lastArtifactRef.current = activeArtifact;
    }
  }, [activeArtifact, railExiting]);

  // Source PDF/DOCX needs a wide rail — bump once when document opens.
  useEffect(() => {
    if (
      activeArtifact?.kind !== "source" ||
      activeArtifact.viewMode !== "document"
    ) {
      return;
    }
    setRailWidthPct((w) => {
      if (w >= 70) return w;
      saveRailWidth(70);
      return 70;
    });
  }, [
    activeArtifact?.kind,
    activeArtifact?.kind === "source" ? activeArtifact.viewMode : null,
  ]);

  const openReportArtifact = useCallback(
    (msgId: string, result: RunResult, tab?: ArtifactTab) => {
      const mode = result.output_mode || "auto";
      const preferPreview = Boolean(result.preview?.blocks?.length);
      const preferPdf = Boolean(result.downloads?.pdf);
      let nextTab: ArtifactTab =
        tab ??
        (preferPreview ? "preview" : preferPdf ? "pdf" : "source");
      if (!tab) {
        if (mode === "diagram") nextTab = "diagram";
        else if (mode === "presentation") nextTab = "presentation";
        else if (mode === "report" && preferPreview) nextTab = "preview";
      }
      setRailExiting(false);
      setRailCollapsed(false);
      setActiveArtifact({
        kind: "report",
        msgId,
        tab: nextTab,
        title: reportTitle(result),
        activeDiagramId: result.diagrams?.[0]?.id ?? null,
      });
    },
    [],
  );

  const openDiagramArtifact = useCallback(
    (msgId: string, result: RunResult, diagramId: string) => {
      setRailExiting(false);
      setRailCollapsed(false);
      setActiveArtifact({
        kind: "report",
        msgId,
        tab: "diagram",
        title: reportTitle(result),
        activeDiagramId: diagramId,
      });
    },
    [],
  );

  const openPresentationArtifact = useCallback(
    (msgId: string, result: RunResult) => {
      openReportArtifact(msgId, result, "presentation");
    },
    [openReportArtifact],
  );

  const openDeckSlidesArtifact = useCallback(
    (msgId: string, result: RunResult) => {
      openReportArtifact(msgId, result, "slides");
    },
    [openReportArtifact],
  );

  const openFilmFrame = useCallback(
    (msgId: string, frame: CraftFilmFrame, runId?: string) => {
      const bot = msgs.find((m) => m.id === msgId && m.role === "bot");
      const rid =
        runId ||
        (bot && bot.role === "bot" ? bot.result?.run_id : undefined) ||
        activeRunIdRef.current ||
        "";
      setRailExiting(false);
      setRailCollapsed(false);
      setActiveArtifact({
        kind: "media",
        msgId,
        tab: "preview",
        runId: rid,
        mediaId: frame.id,
        url: frame.url,
        title: frame.id,
      });
    },
    [msgs, activeRunIdRef],
  );

  const openUserPhoto = useCallback(
    (photo: UserPhotoThumb) => {
      setRailExiting(false);
      setRailCollapsed(false);
      setActiveArtifact({
        kind: "media",
        msgId: "",
        tab: "preview",
        runId: activeRunIdRef.current || "",
        mediaId: photo.name || "user_photo",
        url: photo.url,
        title: photo.name || "Фото",
      });
    },
    [activeRunIdRef],
  );

  const openSourceArtifact = useCallback(
    (draft: SourceDraft | SourceAttachment) => {
      setRailExiting(false);
      setRailCollapsed(false);
      const isDoc =
        draft.viewMode === "document" || Boolean(draft.ingestId);
      const viewMode = isDoc ? "document" : draft.viewMode || "text";
      const previewUrl =
        draft.previewUrl ||
        (draft.ingestId
          ? `/api/source/files/${encodeURIComponent(draft.ingestId)}/preview`
          : null);
      const originalUrl =
        draft.originalUrl ||
        (draft.ingestId
          ? `/api/source/files/${encodeURIComponent(draft.ingestId)}/original`
          : null);
      setActiveArtifact({
        kind: "source",
        tab: "source",
        title: draft.title,
        text: draft.text,
        fileName: draft.fileName,
        viewMode,
        previewUrl,
        originalUrl,
        format: draft.format,
      });
      // Document needs room — bump rail if still at a narrow preset.
      if (isDoc) {
        setRailWidthPct((w) => {
          if (w >= 70) return w;
          saveRailWidth(70);
          return 70;
        });
      }
    },
    [],
  );

  const openIntentArtifact = useCallback((text: string) => {
    setRailExiting(false);
    setRailCollapsed(false);
    setActiveArtifact({
      kind: "intent",
      tab: "source",
      title: "Текст запроса",
      text,
    });
  }, []);

  const closeArtifact = useCallback(() => {
    if (!activeArtifact || railExiting) return;
    lastArtifactRef.current = activeArtifact;
    setRailExiting(true);
  }, [activeArtifact, railExiting]);

  const finishArtifactClose = useCallback(() => {
    setRailExiting(false);
    setActiveArtifact(null);
    // Keep a reopen stub when we still have something to show.
    setRailCollapsed(Boolean(lastArtifactRef.current));
  }, []);

  const reopenRail = useCallback(() => {
    const last = lastArtifactRef.current;
    if (!last) {
      setRailCollapsed(false);
      return;
    }
    setRailCollapsed(false);
    setRailExiting(false);
    setActiveArtifact(last);
  }, []);

  const setArtifactTab = useCallback((tab: ArtifactTab) => {
    setActiveArtifact((prev) => {
      if (!prev) return prev;
      if (prev.kind === "report") return { ...prev, tab };
      if (prev.kind === "media") return { ...prev, tab: "preview" };
      return { ...prev, tab: "source" as const };
    });
  }, []);

  const selectDiagram = useCallback((id: string) => {
    setActiveArtifact((prev) => {
      if (!prev || prev.kind !== "report") return prev;
      return { ...prev, tab: "diagram", activeDiagramId: id };
    });
  }, []);

  const railOpen = Boolean(activeArtifact);
  const railLayout = railOpen || railExiting || railCollapsed;
  const railArtifact =
    activeArtifact ?? (railExiting ? lastArtifactRef.current : null);

  return {
    activeArtifact,
    setActiveArtifact,
    narrowRail,
    railWidthPct,
    setRailWidthPct,
    railExiting,
    setRailExiting,
    railCollapsed,
    setRailCollapsed,
    railOpen,
    railLayout,
    railArtifact,
    openReportArtifact,
    openDiagramArtifact,
    openPresentationArtifact,
    openDeckSlidesArtifact,
    openFilmFrame,
    openUserPhoto,
    openSourceArtifact,
    openIntentArtifact,
    closeArtifact,
    finishArtifactClose,
    reopenRail,
    setArtifactTab,
    selectDiagram,
  };
}
