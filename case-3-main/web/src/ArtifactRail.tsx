/** Right-side Artifact rail: Preview · PDF · Source — resize, TOC, polish. */

import {
  Suspense,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type RefObject,
} from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { ChartEditRequest, PaletteInfo } from "./ChartEditSheet";
import type { ImageEditRequest } from "./ImageEditModal";
import type { TableEditRequest } from "./TableEditSheet";
import type { ParagraphEditRequest } from "./ParagraphEditSheet";
import type { HeadingEditRequest } from "./HeadingEditTypes";
import type { ListEditRequest } from "./ListEditTypes";
import { RecolorChartsModal } from "./RecolorChartsModal";
import { DiagramPane } from "./DiagramPane";
import type { DiagramInfo } from "./DiagramFullscreen";
import { DeckSlidesFilm } from "./DeckSlidesFilm";
import { PresentationPane } from "./PresentationPane";
import type { ReportPreview } from "./domain/reportPreview";
import { ReportView } from "./ReportView";
import { IconPanelRight } from "./icons";
import { deckDownloadLinks } from "./domain/deckDownloads";
import { reportDownloadLinks } from "./domain/reportDownloads";
import {
  copyMarkdownButtonVisible,
  docsNeedRebuild,
  recolorChartsButtonVisible,
  reportEditModeHint,
  reportEditToggleVisible,
  slidesFilmTabLabel,
} from "./domain/reportEditMode";
import { reportToMarkdown } from "./domain/reportMarkdown";
import { modeSurfaces } from "./domain/liberModes";
import { SOURCE_LABEL } from "./domain/sourceCopy";
import { redoChord, undoChord } from "./domain/undoChord";
import { SourcePane } from "./SourcePane";
import {
  RAIL_WIDTH_DEFAULT,
  clampRailWidth,
  saveRailWidth,
} from "./domain/railWidth";
import { pdfSearchNeedles } from "./pdfFindPage";
import { PdfFirstPage } from "./lazyPdfFirstPage";

export type ArtifactTab =
  | "preview"
  | "pdf"
  | "source"
  | "diagram"
  | "presentation"
  | "slides";

export type ActiveArtifact =
  | {
      kind: "report";
      msgId: string;
      tab: ArtifactTab;
      title?: string;
      /** Which Mermaid diagram is focused when tab === "diagram". */
      activeDiagramId?: string | null;
    }
  | {
      kind: "source";
      tab: "source";
      title: string;
      text: string;
      fileName?: string;
      viewMode?: "text" | "document";
      previewUrl?: string | null;
      originalUrl?: string | null;
      format?: string;
    }
  | {
      kind: "intent";
      tab: "source";
      title: string;
      text: string;
    }
  | {
      /** SSE 2B film click — PNG in rail */
      kind: "media";
      msgId: string;
      tab: "preview";
      runId: string;
      mediaId: string;
      url: string;
      title: string;
    };

type ReportBundle = {
  preview?: ReportPreview;
  downloads?: Record<string, string>;
  runId?: string;
  warnings?: string[];
  diagrams?: DiagramInfo[];
  slidesStatus?: string | null;
  slidesStage?: string | null;
  slidesError?: string | null;
  slidePngs?: string[];
  deck?: import("./deckTypes").DeckIR | null;
  deckPdfMode?: string | null;
  /** Liber composer mode for this run — gates rail tabs. */
  outputMode?: string | null;
  onDeckUpdated?: (
    deck: import("./deckTypes").DeckIR,
    slidePngs: string[],
    extras?: {
      downloads?: Record<string, string>;
      diagrams?: DiagramInfo[];
    },
  ) => void;
};

type Props = {
  artifact: ActiveArtifact;
  report: ReportBundle | null;
  sourceText?: string | null;
  sourceTitle?: string | null;
  /** Prior user-message Source (PDF/DOCX) — report «Текст» tab shows viewer. */
  sourceAttachment?: import("./domain/liberTypes").SourceAttachment | null;
  /** Pre-run sourceDraft — Source tab click-to-edit. */
  sourceEditable?: boolean;
  onSourceTextChange?: (text: string) => void;
  palettes?: PaletteInfo[];
  catalogTypes?: string[];
  defaultPalette?: string;
  editingFigureId?: string | null;
  editError?: string | null;
  editErrorFigureId?: string | null;
  downloadsPulse?: boolean;
  narrow?: boolean;
  widthPct?: number;
  onWidthChange?: (pct: number) => void;
  onTab: (tab: ArtifactTab) => void;
  onSelectDiagram?: (id: string) => void;
  onClose: () => void;
  /** Controlled close: keep mounted, animate width → 0, then onClosed. */
  closing?: boolean;
  onClosed?: () => void;
  onEditFigure?: (req: ChartEditRequest) => Promise<boolean> | boolean;
  onRecolorCharts?: (palette: string) => Promise<boolean> | boolean;
  onEditImage?: (req: ImageEditRequest) => Promise<boolean> | boolean;
  onUploadFigure?: (
    figureId: string,
    file: File,
    caption?: string,
  ) => Promise<boolean> | boolean;
  onDeleteFigure?: (figureId: string) => Promise<boolean> | boolean;
  onEditTable?: (req: TableEditRequest) => Promise<boolean> | boolean;
  onEditParagraph?: (req: ParagraphEditRequest) => Promise<boolean> | boolean;
  onInsertParagraph?: (req: {
    text: string;
    afterParagraphIndex?: number;
    afterHeadingIndex?: number;
  }) => Promise<boolean> | boolean;
  onEditHeading?: (req: HeadingEditRequest) => Promise<boolean> | boolean;
  onEditTitle?: (text: string) => Promise<boolean> | boolean;
  onEditList?: (req: ListEditRequest) => Promise<boolean> | boolean;
  onEditCancel?: () => void;
  editHistory?: import("./domain/reportEditMode").EditHistoryDesc | null;
  onHistoryUndo?: () => void | Promise<void>;
  onHistoryRedo?: () => void | Promise<void>;
  onClearEditHistory?: () => void | Promise<void>;
  onEditHistory?: (
    h: import("./domain/reportEditMode").EditHistoryDesc,
  ) => void;
  onReportEditModeChange?: (on: boolean) => void;
  /** Controlled report edit mode (rail chrome). */
  reportEditMode?: boolean;
  /** «Готово»: flush PDF/DOCX then leave edit. */
  onFinishReportEdit?: () => Promise<void> | void;
  /** Undo every pending edit so the files on disk match the screen again. */
  onDiscardReportEdits?: () => Promise<void> | void;
  finishReportEditBusy?: boolean;
  makingPresentation?: boolean;
  onDiagramsUpdated?: (
    diagrams: DiagramInfo[],
    meta?: import("./DiagramPane").DiagramUpdateMeta,
  ) => void;
  /** Deck file lags the screen until «Готово». */
  deckDownloadsBlocked?: boolean;
  onDeckDownloadsBlockedChange?: (blocked: boolean) => void;
};

export function ArtifactRail({
  artifact,
  report,
  sourceText,
  sourceTitle,
  sourceAttachment = null,
  sourceEditable = false,
  onSourceTextChange,
  palettes = [],
  catalogTypes = [],
  defaultPalette = "atelier",
  editingFigureId = null,
  editError = null,
  editErrorFigureId = null,
  downloadsPulse = false,
  narrow = false,
  widthPct = RAIL_WIDTH_DEFAULT,
  onWidthChange,
  onTab,
  onSelectDiagram,
  onClose,
  closing = false,
  onClosed,
  onEditFigure,
  onRecolorCharts,
  onEditImage,
  onUploadFigure,
  onDeleteFigure,
  onEditTable,
  onEditParagraph,
  onInsertParagraph,
  onEditHeading,
  onEditTitle,
  onEditList,
  onEditCancel,
  editHistory = null,
  onHistoryUndo,
  onHistoryRedo,
  onClearEditHistory,
  onEditHistory,
  onReportEditModeChange,
  reportEditMode = false,
  onFinishReportEdit,
  onDiscardReportEdits,
  finishReportEditBusy = false,
  makingPresentation = false,
  onDiagramsUpdated,
  deckDownloadsBlocked = false,
  onDeckDownloadsBlockedChange,
}: Props) {
  const reduceMotion = useReducedMotion();
  const [stalePrompt, setStalePrompt] = useState<null | "report" | "deck">(null);
  const tab = artifact.tab;
  const openWidthRef = useRef<number | null>(null);
  const isMedia = artifact.kind === "media";
  const isUserPhoto =
    artifact.kind === "media" && !artifact.mediaId.startsWith("film_");
  const isReport = artifact.kind === "report";
  const diagrams = isReport ? report?.diagrams || [] : [];
  const openStalePrompt = useCallback((scope: "report" | "deck") => {
    setStalePrompt(scope);
  }, []);
  const saveStale = useCallback(async () => {
    const scope = stalePrompt;
    if (!scope) return;
    if (scope === "report") {
      await onFinishReportEdit?.();
      setStalePrompt(null);
      return;
    }
    const runId = report?.runId;
    if (!runId) return;
    const res = await fetch(
      `/api/runs/${encodeURIComponent(runId)}/slides/rebuild`,
      { method: "POST" },
    );
    if (!res.ok) return;
    for (let i = 0; i < 120; i++) {
      await new Promise((r) => setTimeout(r, 500));
      const g = await fetch(`/api/runs/${encodeURIComponent(runId)}/slides`);
      const gBody = await g.json().catch(() => ({}));
      if (gBody.slides_status === "ok") {
        const pngs = (gBody.slide_pngs as string[]) || [];
        const dl =
          gBody.downloads && typeof gBody.downloads === "object"
            ? (gBody.downloads as Record<string, string>)
            : undefined;
        if (gBody.deck) {
          report?.onDeckUpdated?.(gBody.deck, pngs, { downloads: dl, diagrams });
        }
        onDeckDownloadsBlockedChange?.(false);
        setStalePrompt(null);
        return;
      }
      if (gBody.slides_status === "error" || gBody.slides_status === "cancelled") {
        return;
      }
    }
  }, [
    diagrams,
    onDeckDownloadsBlockedChange,
    onFinishReportEdit,
    report,
    stalePrompt,
  ]);
  const discardStale = useCallback(async () => {
    await onDiscardReportEdits?.();
    onDeckDownloadsBlockedChange?.(false);
    setStalePrompt(null);
  }, [onDeckDownloadsBlockedChange, onDiscardReportEdits]);
  const activeDiagramId =
    isReport && artifact.kind === "report"
      ? artifact.activeDiagramId || diagrams[0]?.id || null
      : null;
  const activeDiagram =
    diagrams.find((d) => d.id === activeDiagramId) || diagrams[0] || null;
  const surfaces = modeSurfaces(report?.outputMode);
  const showDiagramEmpty =
    tab === "diagram" &&
    !activeDiagram &&
    surfaces.showDiagram &&
    Boolean(report?.runId);
  const showDiagramSurface =
    (tab === "diagram" && Boolean(activeDiagram)) || showDiagramEmpty;
  const hasPreview =
    surfaces.showReportPreview && Boolean(report?.preview?.blocks?.length);
  const hasCharts = useMemo(
    () =>
      Boolean(
        report?.preview?.blocks?.some(
          (b) => b.type === "figure" && b.kind === "chart",
        ),
      ),
    [report?.preview?.blocks],
  );
  const [recolorOpen, setRecolorOpen] = useState(false);
  const [copiedMd, setCopiedMd] = useState(false);
  const handleCopyMarkdown = useCallback(async () => {
    const blocks = report?.preview?.blocks;
    if (!blocks?.length) return;
    const title = report?.preview?.title?.trim() || "Отчёт";
    const md = reportToMarkdown({ title, blocks });
    try {
      await navigator.clipboard.writeText(md);
      setCopiedMd(true);
      window.setTimeout(() => setCopiedMd(false), 2000);
    } catch (err) {
      console.error("Clipboard copy failed:", err);
    }
  }, [report?.preview]);
  const hasPdf =
    surfaces.showReportPdf && Boolean(report?.downloads?.pdf);
  /** Diagram mode always keeps the tab — even when generation returned 0. */
  const hasDiagrams =
    surfaces.showDiagram &&
    (diagrams.length > 0 || report?.outputMode === "diagram");
  const slidesStatus = isReport ? report?.slidesStatus || null : null;
  /* Show tab only when deck exists or failed — never open rail mid-build. */
  const hasPresentationTab =
    surfaces.showPresentation &&
    isReport &&
    Boolean(
      slidesStatus === "ok" ||
        slidesStatus === "error" ||
        (report?.slidePngs && report.slidePngs.length > 0),
    );
  const hasSlidesFilmTab =
    surfaces.showPresentation &&
    isReport &&
    Boolean(
      (report?.slidePngs && report.slidePngs.length > 0) ||
        report?.downloads?.deck_pdf,
    );
  const reportSourceDoc =
    artifact.kind === "report" &&
    sourceAttachment &&
    (sourceAttachment.viewMode === "document" ||
      Boolean(sourceAttachment.ingestId))
      ? sourceAttachment
      : null;
  const sourceAsDocument =
    (artifact.kind === "source" && artifact.viewMode === "document") ||
    Boolean(reportSourceDoc);

  const hasSource =
    surfaces.showSource &&
    Boolean(
      (sourceText && sourceText.length > 0) ||
        reportSourceDoc ||
        artifact.kind === "source" ||
        artifact.kind === "intent",
    );

  const displaySource =
    artifact.kind === "source" || artifact.kind === "intent"
      ? artifact.text
      : reportSourceDoc?.text || sourceText || "";
  const displaySourceTitle =
    artifact.kind === "source" || artifact.kind === "intent"
      ? artifact.title
      : reportSourceDoc?.title || sourceTitle || SOURCE_LABEL;
  const sourceFileName =
    artifact.kind === "source"
      ? artifact.fileName
      : reportSourceDoc?.fileName;

  const [pdfPage, setPdfPage] = useState(1);
  /** Caption/id search after figure→PDF click (TeX page hints miss natural breaks). */
  const [pdfFind, setPdfFind] = useState<{
    needles: string[];
    token: number;
  } | null>(null);
  const [dragging, setDragging] = useState(false);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLElement>(null);
  const titleId = useId();
  const setBodyRef = useCallback((el: HTMLDivElement | null) => {
    bodyRef.current = el;
  }, []);

  const visibleTabs = useMemo(() => {
    if (isMedia) {
      return [
        {
          id: "preview" as ArtifactTab,
          label: isUserPhoto ? "Фото" : "Кадр",
          show: true,
        },
      ];
    }
    // Peer order for documents: Превью · Схема · PDF (schema sits next to preview).
    const diagramLabel =
      diagrams.length > 1 ? `Схема · ${diagrams.length}` : "Схема";
    const all: { id: ArtifactTab; label: string; show: boolean }[] = [
      { id: "preview", label: "Превью", show: isReport && hasPreview },
      { id: "diagram", label: diagramLabel, show: isReport && hasDiagrams },
      { id: "pdf", label: "PDF", show: isReport && hasPdf },
      {
        id: "presentation",
        label: "PPTX",
        show: Boolean(hasPresentationTab),
      },
      {
        id: "slides",
        label: slidesFilmTabLabel(),
        show: Boolean(hasSlidesFilmTab),
      },
      {
        id: "source",
        label: SOURCE_LABEL,
        show: hasSource,
      },
    ];
    return all.filter((t) => t.show);
  }, [
    isMedia,
    isUserPhoto,
    isReport,
    hasPreview,
    hasPdf,
    hasDiagrams,
    hasPresentationTab,
    hasSlidesFilmTab,
    hasSource,
    sourceAsDocument,
    diagrams.length,
  ]);

  /* If mode hid the active tab (e.g. presentation run opened on preview), snap. */
  useEffect(() => {
    if (!isReport || visibleTabs.length === 0) return;
    if (visibleTabs.some((t) => t.id === tab)) return;
    onTab(visibleTabs[0].id);
  }, [isReport, tab, visibleTabs, onTab]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      // Diagram fullscreen owns Esc while open.
      if (document.querySelector(".diagram-fullscreen")) return;
      if (document.querySelector(".presentation-fullscreen")) return;
      if (document.querySelector(".source-doc-fullscreen")) return;
      // Source draft click-to-edit: Esc exits editor first (not rail).
      if (document.querySelector(".artifact-source.is-editing")) return;
      onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  /* Focus trap when overlay */
  useEffect(() => {
    if (!narrow || !panelRef.current) return;
    const root = panelRef.current;
    const focusables = root.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    first?.focus();
    const onTabKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || focusables.length === 0) return;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    root.addEventListener("keydown", onTabKey);
    return () => root.removeEventListener("keydown", onTabKey);
  }, [narrow, tab]);

  const jumpFigureToPdf = useCallback(
    (info: {
      id: string;
      figureIndex: number;
      pdfPage?: number;
      caption?: string;
    }) => {
      // Don't seed pdfPage from TeX hints — without \\newpage they are almost
      // always «1» and fight pdf.js caption search (figure may be on p.2+).
      setPdfFind({
        needles: pdfSearchNeedles(info.caption, info.id),
        token: Date.now(),
      });
      onTab("pdf");
    },
    [onTab],
  );

  const onResizePointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (narrow || !onWidthChange) return;
      e.preventDefault();
      const handle = e.currentTarget;
      handle.setPointerCapture(e.pointerId);
      setDragging(true);
      const split = handle.closest(".desk-split") as HTMLElement | null;
      const startX = e.clientX;
      const startPct = widthPct;
      let latest = startPct;

      const onMove = (ev: PointerEvent) => {
        if (!split) return;
        const rect = split.getBoundingClientRect();
        if (rect.width < 1) return;
        const dx = startX - ev.clientX;
        latest = clampRailWidth(startPct + (dx / rect.width) * 100);
        onWidthChange(latest);
      };
      const onUp = (ev: PointerEvent) => {
        try {
          handle.releasePointerCapture(ev.pointerId);
        } catch {
          /* already released */
        }
        setDragging(false);
        saveRailWidth(latest);
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onUp);
      };
      handle.addEventListener("pointermove", onMove);
      handle.addEventListener("pointerup", onUp);
    },
    [narrow, onWidthChange, widthPct],
  );

  const resetWidth = useCallback(() => {
    onWidthChange?.(RAIL_WIDTH_DEFAULT);
    saveRailWidth(RAIL_WIDTH_DEFAULT);
  }, [onWidthChange]);

  const deskOpen = !narrow && !closing;
  /** Width-driven collapse — flexBasis % fought CSS `flex` shorthand and stalled. */
  const deskClosed = {
    width: 0,
    minWidth: 0,
    marginLeft: 0,
    opacity: 1,
  };
  const deskOpened = {
    opacity: 1,
    width: `${widthPct}%`,
    minWidth: 280,
    marginLeft: 6,
  };
  const onClosedRef = useRef(onClosed);
  onClosedRef.current = onClosed;
  const closedOnceRef = useRef(false);
  const closingRef = useRef(closing);
  closingRef.current = closing;

  const finishClose = useCallback(() => {
    if (closedOnceRef.current) return;
    closedOnceRef.current = true;
    onClosedRef.current?.();
  }, []);

  useEffect(() => {
    if (!closing) {
      closedOnceRef.current = false;
      return;
    }
    if (reduceMotion) {
      finishClose();
      return;
    }
    /* Fallback if onAnimationComplete misses (e.g. interrupted). */
    const t = window.setTimeout(finishClose, 520);
    return () => window.clearTimeout(t);
  }, [closing, reduceMotion, finishClose]);

  const panel = (
    <motion.aside
      ref={panelRef as RefObject<HTMLElement>}
      className={`artifact-rail${narrow ? " is-overlay" : ""}${dragging ? " is-dragging" : ""}${closing ? " is-closing" : ""}`}
      role="complementary"
      aria-label="Артефакт"
      aria-labelledby={titleId}
      {...(narrow ? { "aria-modal": true as const } : {})}
      style={
        narrow
          ? undefined
          : {
              flex: "0 0 auto",
              maxWidth: closing ? undefined : "min(780px, 72vw)",
              overflow: "hidden",
            }
      }
      initial={
        reduceMotion
          ? false
          : narrow
            ? { opacity: 0, x: 36 }
            : { ...deskClosed, opacity: 0 }
      }
      animate={
        narrow
          ? closing
            ? { opacity: 0, x: 28 }
            : { opacity: 1, x: 0 }
          : closing
            ? deskClosed
            : deskOpened
      }
      exit={
        reduceMotion
          ? undefined
          : narrow
            ? { opacity: 0, x: 28 }
            : deskClosed
      }
      transition={
        reduceMotion
          ? { duration: 0 }
          : narrow
            ? { type: "spring", stiffness: 420, damping: 36, mass: 0.75 }
            : {
                width: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
                minWidth: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
                marginLeft: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
                opacity: { duration: 0.28, ease: [0.22, 1, 0.36, 1] },
              }
      }
      onUpdate={() => {
        if (!narrow && panelRef.current && deskOpen) {
          openWidthRef.current = panelRef.current.getBoundingClientRect().width;
        }
      }}
      onAnimationComplete={() => {
        // Ignore completion of the *previous* open tween when `animate` flips
        // to closed — that used to call finishClose while width was still full,
        // unmounting the rail and snapping the chat bubble.
        if (!closingRef.current) return;
        const w = panelRef.current?.getBoundingClientRect().width ?? 0;
        if (w > 32) return;
        finishClose();
      }}
    >
      {!narrow && (
        <div
          className="artifact-rail-resize"
          role="separator"
          aria-orientation="vertical"
          aria-valuenow={widthPct}
          aria-valuemin={34}
          aria-valuemax={70}
          aria-label="Ширина панели. Двойной клик — сброс"
          onPointerDown={onResizePointerDown}
          onDoubleClick={resetWidth}
        >
          <span className="artifact-rail-resize-grip" aria-hidden>
            <i />
            <i />
            <i />
          </span>
        </div>
      )}

      <div className="artifact-rail-inner">
        <header className="artifact-rail-head">
          <span id={titleId} className="sr-only">
            {artifact.kind === "media"
              ? artifact.title
              : artifact.kind === "report"
                ? artifact.title || "Отчёт"
                : displaySourceTitle}
          </span>
          <nav
            className="artifact-rail-tabs"
            aria-label="Вкладки артефакта"
            onKeyDown={(e) => {
              const ids = visibleTabs.map((t) => t.id);
              const i = ids.indexOf(tab);
              if (i < 0) return;
              if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                e.preventDefault();
                const next =
                  e.key === "ArrowRight"
                    ? ids[(i + 1) % ids.length]
                    : ids[(i - 1 + ids.length) % ids.length];
                onTab(next);
              }
            }}
          >
            {visibleTabs.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`artifact-rail-tab${tab === t.id ? " is-active" : ""}`}
                aria-selected={tab === t.id}
                onClick={() => {
                  if (
                    t.id === "pdf" &&
                    reportEditMode &&
                    docsNeedRebuild(editHistory)
                  ) {
                    void onFinishReportEdit?.();
                  }
                  onTab(t.id);
                }}
              >
                {tab === t.id && !reduceMotion && (
                  <motion.span
                    className="artifact-rail-tab-ink"
                    layoutId="rail-tab-ink"
                    transition={{
                      type: "spring",
                      stiffness: 480,
                      damping: 38,
                    }}
                  />
                )}
                <span className="artifact-rail-tab-label">{t.label}</span>
              </button>
            ))}
          </nav>
          <div className="artifact-rail-actions">
            {isReport &&
            tab === "preview" &&
            reportEditToggleVisible({
              onEditFigure,
              onEditImage,
              onEditTable,
              onEditParagraph,
              onEditHeading,
              onEditTitle,
              onEditList,
            }) ? (
              <div
                className="artifact-rail-edit"
                title={reportEditModeHint(reportEditMode)}
              >
                {reportEditMode ? (
                  <>
                    <button
                      type="button"
                      className="artifact-rail-edit-hist"
                      aria-label="Отменить"
                      title={`Отменить (${undoChord()})`}
                      disabled={!editHistory?.canUndo || finishReportEditBusy}
                      onClick={() => void onHistoryUndo?.()}
                    >
                      ←
                    </button>
                    <button
                      type="button"
                      className="artifact-rail-edit-hist"
                      aria-label="Вернуть"
                      title={`Вернуть (${redoChord()})`}
                      disabled={!editHistory?.canRedo || finishReportEditBusy}
                      onClick={() => void onHistoryRedo?.()}
                    >
                      →
                    </button>
                    {recolorChartsButtonVisible(
                      reportEditMode,
                      hasCharts,
                      Boolean(onRecolorCharts),
                    ) ? (
                      <button
                        type="button"
                        className="artifact-rail-edit-recolor"
                        title="Перекрасить все графики отчёта"
                        disabled={finishReportEditBusy || editingFigureId === "charts_all"}
                        onClick={() => setRecolorOpen(true)}
                      >
                        Перекрасить графики
                      </button>
                    ) : null}
                  </>
                ) : copyMarkdownButtonVisible(reportEditMode, hasPreview) ? (
                  <button
                    type="button"
                    className="artifact-rail-edit-recolor"
                    title="Скопировать отчёт в формате Markdown"
                    onClick={() => void handleCopyMarkdown()}
                  >
                    {copiedMd ? "Скопировано" : "Копировать MD"}
                  </button>
                ) : null}
                <button
                  type="button"
                  className={`artifact-rail-edit-toggle${reportEditMode ? " is-on" : ""}`}
                  aria-pressed={reportEditMode}
                  disabled={finishReportEditBusy}
                  onClick={() => {
                    if (reportEditMode) void onFinishReportEdit?.();
                    else onReportEditModeChange?.(true);
                  }}
                >
                  {finishReportEditBusy
                    ? "Собираю…"
                    : reportEditMode
                      ? "Готово"
                      : "Редактировать"}
                </button>
              </div>
            ) : null}
            {isReport && (tab === "preview" || tab === "pdf")
              ? reportDownloadLinks(report?.downloads, {
                  enabled: surfaces.showReportPdf,
                  stale: docsNeedRebuild(editHistory),
                }).map((link) =>
                  link.stale || !link.href ? (
                    <button
                      key={link.kind}
                      type="button"
                      title={link.title}
                      className={`artifact-rail-dl is-stale${downloadsPulse ? " is-pulse" : ""}`}
                      onClick={() => openStalePrompt("report")}
                    >
                      {link.label}
                    </button>
                  ) : (
                    <a
                      key={link.kind}
                      href={link.href}
                      download
                      title={link.title}
                      className={`artifact-rail-dl${downloadsPulse ? " is-pulse" : ""}`}
                    >
                      {link.label}
                    </a>
                  ),
                )
              : null}
            {isReport && (tab === "presentation" || tab === "slides")
              ? deckDownloadLinks(report?.downloads, {
                  blocked: deckDownloadsBlocked,
                }).map((link) => {
                  const current =
                    (tab === "presentation" && link.kind === "pptx") ||
                    (tab === "slides" && link.kind === "deck_pdf");
                  const label = link.disabled
                    ? link.label
                    : link.kind === "pptx"
                      ? "Скачать PPTX"
                      : "Скачать PDF";
                  if (link.disabled) {
                    return (
                      <button
                        key={link.kind}
                        type="button"
                        title={link.title}
                        className="artifact-rail-dl is-stale"
                        onClick={() => openStalePrompt("deck")}
                      >
                        {label}
                      </button>
                    );
                  }
                  return (
                    <a
                      key={link.kind}
                      href={link.href}
                      download
                      title={link.title || label}
                      aria-current={current ? "true" : undefined}
                      className={`artifact-rail-dl${downloadsPulse ? " is-pulse" : ""}${current ? " is-current" : ""}`}
                    >
                      {label}
                    </a>
                  );
                })
              : null}
            <button
              type="button"
              className="artifact-rail-close"
              aria-label="Свернуть панель"
              title="Свернуть"
              onClick={onClose}
            >
              <IconPanelRight size={16} />
            </button>
          </div>
        </header>
        {stalePrompt ? (
          <div className="artifact-rail-stale" role="status">
            <p>
              Сохраните изменения или отмените их. После этого файл можно
              скачать.
            </p>
            <button type="button" onClick={() => void saveStale()}>
              Сохранить
            </button>
            <button type="button" onClick={() => void discardStale()}>
              Отменить изменения
            </button>
            <button type="button" onClick={() => setStalePrompt(null)}>
              Закрыть
            </button>
          </div>
        ) : null}

        <div className="artifact-rail-body" ref={setBodyRef}>
          <AnimatePresence mode="wait">
            <motion.div
              key={
                showDiagramSurface
                  ? `diagram-${activeDiagramId}`
                  : `${artifact.kind}-${tab}`
              }
              className="artifact-rail-pane"
              initial={reduceMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: -6 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            >
              {isMedia && artifact.kind === "media" ? (
                <div className="artifact-rail-media">
                  <div className="artifact-rail-media-header">
                    <p className="artifact-rail-media-caption">{artifact.title}</p>
                    {artifact.url ? (
                      <a
                        className="artifact-rail-media-link"
                        href={artifact.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        download={isUserPhoto ? artifact.title : undefined}
                      >
                        Открыть оригинал ↗
                      </a>
                    ) : null}
                  </div>
                  <div className="artifact-rail-media-img-wrap">
                    <img
                      className="artifact-rail-media-img"
                      src={artifact.url}
                      alt={artifact.title}
                    />
                  </div>
                </div>
              ) : null}

              {showDiagramSurface ? (
                <DiagramPane
                  diagram={activeDiagram}
                  emptyMode={showDiagramEmpty}
                  siblings={diagrams.length > 1 ? diagrams : undefined}
                  onSelectSibling={onSelectDiagram}
                  runId={report?.runId}
                  onDiagramsUpdated={onDiagramsUpdated}
                />
              ) : null}

              {!isMedia &&
              !showDiagramSurface &&
              tab === "preview" &&
              report?.preview ? (
                <ReportView
                  preview={report.preview}
                  downloads={report.downloads}
                  runId={report.runId}
                  diagrams={report.diagrams}
                  warnings={report.warnings}
                  palettes={palettes}
                  catalogTypes={catalogTypes}
                  defaultPalette={defaultPalette}
                  editingFigureId={editingFigureId}
                  editError={editError}
                  editErrorFigureId={editErrorFigureId}
                  downloadsPulse={downloadsPulse}
                  showPdf={false}
                  showDownloads={false}
                  showEditChrome={false}
                  editMode={reportEditMode}
                  onJumpToPdf={hasPdf ? jumpFigureToPdf : undefined}
                  onJumpToDiagram={
                    hasDiagrams
                      ? (diagramId: string) => {
                          onSelectDiagram?.(diagramId);
                          onTab("diagram");
                        }
                      : undefined
                  }
                  onOpenPdf={hasPdf ? () => onTab("pdf") : undefined}
                  onEditFigure={onEditFigure}
                  onRecolorCharts={onRecolorCharts}
                  onEditImage={onEditImage}
                  onUploadFigure={onUploadFigure}
                  onDeleteFigure={onDeleteFigure}
                  onEditTable={onEditTable}
                  onEditParagraph={onEditParagraph}
                  onInsertParagraph={onInsertParagraph}
                  onEditHeading={onEditHeading}
                  onEditTitle={onEditTitle}
                  onEditList={onEditList}
                  onEditCancel={onEditCancel}
                  editHistory={editHistory}
                  onHistoryUndo={onHistoryUndo}
                  onHistoryRedo={onHistoryRedo}
                  onClearEditHistory={onClearEditHistory}
                  onEditModeChange={onReportEditModeChange}
                  onRequestFinishEdit={onFinishReportEdit}
                />
              ) : null}

              {!showDiagramSurface && tab === "pdf" && report?.downloads?.pdf ? (
                <Suspense
                  fallback={
                    <div className="pdf-skeleton pdf-skeleton-solo" aria-busy>
                      <div className="pdf-skeleton-shine" />
                      <p className="artifact-rail-loading">Загружаю PDF…</p>
                    </div>
                  }
                >
                  <PdfFirstPage
                    key={report.downloads.pdf}
                    url={report.downloads.pdf}
                    page={pdfPage}
                    findNeedles={pdfFind?.needles}
                    findToken={pdfFind?.token}
                    onPageChange={(p) => setPdfPage(p)}
                  />
                </Suspense>
              ) : null}

              {!showDiagramSurface && tab === "presentation" && report?.runId ? (
                <PresentationPane
                  runId={report.runId}
                  slidePngs={report.slidePngs || []}
                  deck={report.deck}
                  status={report.slidesStatus}
                  stage={report.slidesStage}
                  error={report.slidesError}
                  downloads={report.downloads}
                  deckPdfMode={report.deckPdfMode}
                  making={makingPresentation}
                  onDeckUpdated={report.onDeckUpdated}
                  palettes={palettes}
                  catalogTypes={catalogTypes}
                  defaultPalette={defaultPalette}
                  editingFigureId={editingFigureId}
                  editError={editError}
                  editErrorFigureId={editErrorFigureId}
                  editHistory={editHistory}
                  onEditFigure={onEditFigure}
                  onEditImage={onEditImage}
                  diagrams={diagrams}
                  onHistoryUndo={onHistoryUndo}
                  onHistoryRedo={onHistoryRedo}
                  onClearEditHistory={onClearEditHistory}
                  onEditHistory={onEditHistory}
                  downloadsBlocked={deckDownloadsBlocked}
                  onDocsDirtyChange={onDeckDownloadsBlockedChange}
                  onStaleDownload={() => openStalePrompt("deck")}
                />
              ) : null}

              {!showDiagramSurface && tab === "slides" ? (
                <DeckSlidesFilm
                  slides={report?.slidePngs || []}
                  downloadHref={
                    deckDownloadsBlocked
                      ? null
                      : report?.downloads?.deck_pdf || null
                  }
                  downloadBlocked={deckDownloadsBlocked}
                  onBlockedClick={() => openStalePrompt("deck")}
                />
              ) : null}

              {!showDiagramSurface && tab === "source" ? (
                <SourcePane
                  title={displaySourceTitle}
                  text={displaySource}
                  fileName={sourceFileName}
                  editable={sourceEditable && !sourceAsDocument}
                  onTextChange={onSourceTextChange}
                  viewMode={sourceAsDocument ? "document" : "text"}
                  previewUrl={
                    artifact.kind === "source"
                      ? artifact.previewUrl
                      : reportSourceDoc
                        ? reportSourceDoc.previewUrl ||
                          (reportSourceDoc.ingestId
                            ? `/api/source/files/${encodeURIComponent(reportSourceDoc.ingestId)}/preview`
                            : null)
                        : null
                  }
                  originalUrl={
                    artifact.kind === "source"
                      ? artifact.originalUrl
                      : reportSourceDoc
                        ? reportSourceDoc.originalUrl ||
                          (reportSourceDoc.ingestId
                            ? `/api/source/files/${encodeURIComponent(reportSourceDoc.ingestId)}/original`
                            : null)
                        : null
                  }
                  format={
                    artifact.kind === "source"
                      ? artifact.format
                      : reportSourceDoc?.format
                  }
                />
              ) : null}

              {!isMedia &&
              !showDiagramSurface &&
              tab === "preview" &&
              !hasPreview ? (
                <p className="artifact-rail-loading muted">
                  Превью пустое — откройте вкладку PDF.
                </p>
              ) : null}
              {!isMedia && !showDiagramSurface && tab === "pdf" && !hasPdf ? (
                <p className="artifact-rail-loading muted">PDF ещё нет.</p>
              ) : null}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
      <RecolorChartsModal
        open={recolorOpen}
        currentPalette={defaultPalette}
        palettes={palettes}
        busy={editingFigureId === "charts_all"}
        onCancel={() => setRecolorOpen(false)}
        onApply={(pal) => {
          void (async () => {
            const ok = await onRecolorCharts?.(pal);
            if (ok !== false) {
              setRecolorOpen(false);
              onReportEditModeChange?.(true);
            }
          })();
        }}
      />
    </motion.aside>
  );

  if (narrow) {
    return (
      <motion.div
        className="artifact-rail-backdrop"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        initial={reduceMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={reduceMotion ? undefined : { opacity: 0 }}
        onClick={onClose}
      >
        <div
          className="artifact-rail-overlay-slot"
          onClick={(e) => e.stopPropagation()}
        >
          {panel}
        </div>
      </motion.div>
    );
  }

  return panel;
}
