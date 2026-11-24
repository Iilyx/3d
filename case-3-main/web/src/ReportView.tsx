/** Liber Print Desk — in-chat report: title, prose, tables, figure PNGs + chart edit. */

import {
  Suspense,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import {
  type ChartEditDraft,
  type ChartEditRequest,
  type PaletteInfo,
} from "./ChartEditSheet";
import {
  type ImageEditRequest,
} from "./ImageEditModal";
import {
  TableEditDraft,
  type TableEditRequest,
} from "./TableEditSheet";
import { type ParagraphEditRequest } from "./ParagraphEditSheet";
import { redoChord, undoChord } from "./domain/undoChord";
import type { HeadingEditRequest } from "./HeadingEditTypes";
import type { ListEditRequest } from "./ListEditTypes";
import { InlineBlockEditor } from "./InlineBlockEditor";
import { RecolorChartsModal } from "./RecolorChartsModal";
import {
  blockEditVisible,
  collapseSetForEditMode,
  recolorChartsButtonVisible,
  reportEditModeHint,
  reportEditToggleVisible,
  type EditHistoryDesc,
} from "./domain/reportEditMode";
import {
  loadCollapsedIds,
  saveCollapsedIds,
} from "./reportSections";
import { ReportBody } from "./ReportBody";
import { RailToc, buildToc } from "./RailToc";
import type { DiagramInfo } from "./DiagramFullscreen";
export { ReportPending } from "./ReportPending";

import { PdfFirstPage } from "./lazyPdfFirstPage";

import type { ReportPreview } from "./domain/reportPreview";
import { reportToMarkdown } from "./domain/reportMarkdown";
export type { PreviewBlock, ReportPreview } from "./domain/reportPreview";

type Downloads = Record<string, string>;

type Props = {
  preview: ReportPreview;
  downloads?: Downloads;
  runId?: string;
  diagrams?: DiagramInfo[];
  warnings?: string[];
  palettes?: PaletteInfo[];
  catalogTypes?: string[];
  defaultPalette?: string;
  editingFigureId?: string | null;
  /** Durable error for the open sheet (not only while busy). */
  editError?: string | null;
  editErrorFigureId?: string | null;
  /** Pulse download links after a successful chart edit. */
  downloadsPulse?: boolean;
  /** Embed PDF slider (false when PDF lives in Artifact rail). */
  showPdf?: boolean;
  /** Footer download links (false when Export lives in rail header). */
  showDownloads?: boolean;
  /** Jump figure → PDF tab (rail). figureIndex is 1-based; pdfPage from TeX when known. */
  onJumpToPdf?: (info: {
    id: string;
    figureIndex: number;
    pdfPage?: number;
    caption?: string;
  }) => void;
  onJumpToDiagram?: (diagramId: string) => void;
  /** C3: open PDF tab when preview body is empty. */
  onOpenPdf?: () => void;
  /** Resolve true on success so the sheet can close. */
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
  /** Session undo/redo while edit mode is on. */
  editHistory?: EditHistoryDesc | null;
  onHistoryUndo?: () => void | Promise<void>;
  onHistoryRedo?: () => void | Promise<void>;
  onClearEditHistory?: () => void | Promise<void>;
  /** Notify parent so toast undo can hide. */
  onEditModeChange?: (on: boolean) => void;
  /** Controlled edit mode (rail chrome). */
  editMode?: boolean;
  /** Hide in-document edit bar when chrome lives in ArtifactRail. */
  showEditChrome?: boolean;
  /** «Готово»: rebuild PDF/DOCX then clear history (parent). */
  onRequestFinishEdit?: () => Promise<void> | void;
};

export function ReportView({
  preview,
  downloads,
  runId,
  diagrams,
  warnings,
  palettes = [],
  catalogTypes = [],
  defaultPalette = "atelier",
  editingFigureId = null,
  editError = null,
  editErrorFigureId = null,
  downloadsPulse = false,
  showPdf = true,
  showDownloads = true,
  onJumpToPdf,
  onJumpToDiagram,
  onOpenPdf,
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
  onEditModeChange,
  editMode: editModeProp,
  showEditChrome = true,
  onRequestFinishEdit,
}: Props) {
  const blocks = preview.blocks || [];
  const hasCharts = useMemo(
    () => blocks.some((b) => b.type === "figure" && b.kind === "chart"),
    [blocks],
  );
  const [recolorOpen, setRecolorOpen] = useState(false);
  const [lightbox, setLightbox] = useState<{
    url: string;
    caption: string;
  } | null>(null);
  const [tableDraftByN, setTableDraftByN] = useState<
    Record<number, TableEditDraft>
  >({});
  const [draftById, setDraftById] = useState<Record<string, ChartEditDraft>>({});
  const [sheetPreviewHtmlById, setSheetPreviewHtmlById] = useState<
    Record<string, string | null>
  >({});
  const [editModeLocal, setEditModeLocal] = useState(false);
  const controlled = editModeProp !== undefined;
  const editMode = controlled ? Boolean(editModeProp) : editModeLocal;
  const [finishing, setFinishing] = useState(false);
  const [activeBlockId, setActiveBlockId] = useState<string | null>(null);
  const [openMediaId, setOpenMediaId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(
    () => loadCollapsedIds(runId || ""),
  );
  const lbTitle = useId();
  const showEditToggle = reportEditToggleVisible({
    onEditFigure,
    onEditImage,
    onEditTable,
    onEditParagraph,
    onEditHeading,
    onEditTitle,
    onEditList,
  });
  const canEditTitle = blockEditVisible(editMode, Boolean(onEditTitle));
  const canEditPara = blockEditVisible(editMode, Boolean(onEditParagraph));
  const canEditHeading = blockEditVisible(editMode, Boolean(onEditHeading));
  const canEditList = blockEditVisible(editMode, Boolean(onEditList));
  const canEditTable = blockEditVisible(editMode, Boolean(onEditTable));
  const canEditFigure = blockEditVisible(editMode, Boolean(onEditFigure));
  const canEditImage = blockEditVisible(editMode, Boolean(onEditImage));
  const [copied, setCopied] = useState(false);

  const handleCopyMarkdown = useCallback(async () => {
    const title = preview.title?.trim() || "Отчёт";
    const md = reportToMarkdown({
      title,
      blocks: preview.blocks,
    });
    try {
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Clipboard copy failed:", err);
    }
  }, [preview]);

  const resetLocalEditUi = useCallback(() => {
    setActiveBlockId(null);
    setOpenMediaId(null);
    setDraftById({});
    setSheetPreviewHtmlById({});
    setTableDraftByN({});
  }, []);

  const prevRunIdRef = useRef(runId);
  useEffect(() => {
    setCollapsed(loadCollapsedIds(runId || ""));
    resetLocalEditUi();
    if (prevRunIdRef.current !== runId) {
      prevRunIdRef.current = runId;
      if (!controlled) setEditModeLocal(false);
      onEditModeChange?.(false);
    }
  }, [runId, onEditModeChange, controlled, resetLocalEditUi]);

  useEffect(() => {
    if (!editMode) {
      resetLocalEditUi();
      return;
    }
    const cleared = collapseSetForEditMode(true);
    if (cleared) {
      setCollapsed(cleared);
      saveCollapsedIds(runId || "", cleared);
    }
  }, [editMode, runId, resetLocalEditUi]);

  const tocItems = useMemo(() => buildToc(blocks), [blocks]);
  const [activeTocId, setActiveTocId] = useState<string | null>(null);
  const handleTocJump = useCallback((id: string) => {
    setActiveTocId(id);
    const target = document.getElementById(id);
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const leaveEditMode = useCallback(async () => {
    if (finishing) return;
    setFinishing(true);
    try {
      if (onRequestFinishEdit) {
        await onRequestFinishEdit();
      } else {
        void onClearEditHistory?.();
      }
      resetLocalEditUi();
      if (!controlled) setEditModeLocal(false);
      onEditModeChange?.(false);
      onEditCancel?.();
    } catch {
      // Rebuild failed: do not exit edit mode or clear history so user can inspect and fix
    } finally {
      setFinishing(false);
    }
  }, [
    finishing,
    onRequestFinishEdit,
    onClearEditHistory,
    controlled,
    onEditModeChange,
    onEditCancel,
    resetLocalEditUi,
  ]);

  const enterEditMode = useCallback(() => {
    resetLocalEditUi();
    if (!controlled) setEditModeLocal(true);
    onEditModeChange?.(true);
  }, [controlled, onEditModeChange, resetLocalEditUi]);
  useEffect(() => {
    if (!editMode) return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      const typing =
        tag === "input" ||
        tag === "textarea" ||
        target?.isContentEditable;
      if (typing) return;
      const mod = e.metaKey || e.ctrlKey;
      if (!mod || e.altKey) return;
      const isZ = e.code === "KeyZ" || e.key.toLowerCase() === "z";
      const isY = e.code === "KeyY" || e.key.toLowerCase() === "y";
      if (isZ && !e.shiftKey) {
        if (!editHistory?.canUndo) return;
        e.preventDefault();
        void onHistoryUndo?.();
      } else if ((isZ && e.shiftKey) || isY) {
        if (!editHistory?.canRedo) return;
        e.preventDefault();
        void onHistoryRedo?.();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editMode, editHistory, onHistoryUndo, onHistoryRedo]);

  const toggleSection = useCallback(
    (headingId: string) => {
      setCollapsed((prev) => {
        const next = new Set(prev);
        if (next.has(headingId)) next.delete(headingId);
        else next.add(headingId);
        saveCollapsedIds(runId || "", next);
        return next;
      });
    },
    [runId],
  );

  const closeLb = useCallback(() => setLightbox(null), []);

  useEffect(() => {
    if (!lightbox) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeLb();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [lightbox, closeLb]);

  return (
    <article className={`report${editMode ? " is-editing-mode" : ""}`}>
      <div className="report-rail" aria-hidden />

      {tocItems.length >= 2 ? (
        <RailToc
          items={tocItems}
          activeId={activeTocId}
          onJump={handleTocJump}
          onActiveChange={setActiveTocId}
        />
      ) : null}

      {showEditToggle && showEditChrome ? (
        <div className="report-edit-bar">
          <p className="report-edit-bar-hint">
            {reportEditModeHint(editMode)}
          </p>
          <div className="report-edit-bar-actions">
            {editMode ? (
              <>
                <button
                  type="button"
                  className="report-edit-history-btn"
                  aria-label="Отменить"
                  title={`Отменить (${undoChord()})`}
                  disabled={!editHistory?.canUndo || finishing}
                  onClick={() => void onHistoryUndo?.()}
                >
                  ←
                </button>
                <button
                  type="button"
                  className="report-edit-history-btn"
                  aria-label="Вернуть"
                  title={`Вернуть (${redoChord()})`}
                  disabled={!editHistory?.canRedo || finishing}
                  onClick={() => void onHistoryRedo?.()}
                >
                  →
                </button>
              </>
            ) : null}
            {!editMode ? (
              <button
                type="button"
                className="report-copy-md-btn secondary"
                title="Скопировать отчёт в формате Markdown"
                onClick={handleCopyMarkdown}
              >
                {copied ? "Скопировано" : "Копировать MD"}
              </button>
            ) : null}
            {recolorChartsButtonVisible(
              editMode,
              hasCharts,
              Boolean(onRecolorCharts),
            ) ? (
              <button
                type="button"
                className="report-recolor-charts-btn secondary"
                title="Перекрасить все графики отчёта"
                disabled={finishing || editingFigureId === "charts_all"}
                onClick={() => setRecolorOpen(true)}
              >
                Перекрасить графики
              </button>
            ) : null}
            <button
              type="button"
              className={`report-edit-toggle${editMode ? " is-on" : ""}`}
              aria-pressed={editMode}
              disabled={finishing}
              onClick={() => {
                if (editMode) void leaveEditMode();
                else enterEditMode();
              }}
            >
              {finishing ? "Собираю…" : editMode ? "Готово" : "Редактировать"}
            </button>
          </div>
        </div>
      ) : null}

      {(() => {
        const displayWarns = (warnings || []).filter(
          (w) =>
            !/charts? (?:failed|skipped)|фото пропущены|Image API|Часть медиа|skipped/i.test(
              w
            )
        );
        return displayWarns.length > 0 ? (
          <header className="report-meta">
            <span className="report-warns">{displayWarns.join(" · ")}</span>
          </header>
        ) : null;
      })()}

      {canEditTitle && activeBlockId === "doc_title" ? (
        <div id="report-doc-title" className="report-title-editor inline-block-wrap">
          <InlineBlockEditor
            hideActions
            kind="heading"
            initialText={preview.title || "Отчёт"}
            busy={editingFigureId === "doc_title"}
            error={editErrorFigureId === "doc_title" ? editError : null}
            onCancel={() => setActiveBlockId(null)}
            onSave={(text) => {
              void (async () => {
                const ok = await onEditTitle?.(text);
                if (ok !== false) setActiveBlockId(null);
              })();
            }}
          />
        </div>
      ) : (
        <h1
          id="report-doc-title"
          className={`report-title${!preview.title ? " muted" : ""}${canEditTitle ? " is-click-edit" : ""}`}
          role={canEditTitle ? "button" : undefined}
          tabIndex={canEditTitle ? 0 : undefined}
          onClick={
            canEditTitle
              ? () => {
                  setOpenMediaId(null);
                  setActiveBlockId("doc_title");
                }
              : undefined
          }
          onKeyDown={
            canEditTitle
              ? (e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setOpenMediaId(null);
                    setActiveBlockId("doc_title");
                  }
                }
              : undefined
          }
        >
          {preview.title || "Отчёт"}
        </h1>
      )}

      <ReportBody
        blocks={blocks}
        downloads={downloads}
        runId={runId}
        diagrams={diagrams}
        palettes={palettes}
        catalogTypes={catalogTypes}
        defaultPalette={defaultPalette}
        editingFigureId={editingFigureId}
        editError={editError}
        editErrorFigureId={editErrorFigureId}
        collapsed={collapsed}
        editMode={editMode}
        canEditPara={canEditPara}
        canEditHeading={canEditHeading}
        canEditList={canEditList}
        canEditTable={canEditTable}
        canEditFigure={canEditFigure}
        canEditImage={canEditImage}
        tableDraftByN={tableDraftByN}
        draftById={draftById}
        sheetPreviewHtmlById={sheetPreviewHtmlById}
        setTableDraftByN={setTableDraftByN}
        setDraftById={setDraftById}
        setSheetPreviewHtmlById={setSheetPreviewHtmlById}
        setLightbox={setLightbox}
        toggleSection={toggleSection}
        onJumpToPdf={onJumpToPdf}
        onJumpToDiagram={onJumpToDiagram}
        onOpenPdf={onOpenPdf}
        onEditFigure={onEditFigure}
        onEditImage={onEditImage}
        onUploadFigure={onUploadFigure}
        onDeleteFigure={onDeleteFigure}
        onEditTable={onEditTable}
        onEditParagraph={onEditParagraph}
        onInsertParagraph={onInsertParagraph}
        onEditHeading={onEditHeading}
        onEditList={onEditList}
        activeBlockId={activeBlockId}
        onActiveBlockId={setActiveBlockId}
        openMediaId={openMediaId}
        onOpenMediaId={setOpenMediaId}
      />

      {showPdf && downloads?.pdf ? (
        <Suspense fallback={<p className="report-pdf-cap">Загружаю стр. 1 PDF…</p>}>
          <PdfFirstPage key={downloads.pdf} url={downloads.pdf} />
        </Suspense>
      ) : null}

      {showDownloads && (
        <footer
          className={`report-actions downloads${downloadsPulse ? " is-pulse" : ""}`}
        >
          {downloads?.pdf && (
            <a href={downloads.pdf} download>
              Скачать PDF
            </a>
          )}
          {downloads?.docx && (
            <a className="secondary" href={downloads.docx} download>
              Скачать DOCX
            </a>
          )}
          <button
            type="button"
            className="report-copy-md-btn secondary"
            title="Скопировать текст отчёта в формате Markdown"
            onClick={handleCopyMarkdown}
          >
            {copied ? "Скопировано в MD" : "Копировать Markdown"}
          </button>
        </footer>
      )}

      {lightbox &&
        createPortal(
          <div
            className="report-lightbox"
            role="dialog"
            aria-modal="true"
            aria-labelledby={lbTitle}
            onClick={closeLb}
          >
            <div
              className="report-lightbox-sheet"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                className="report-lightbox-close"
                onClick={closeLb}
                aria-label="Закрыть"
              >
                ×
              </button>
              <img src={lightbox.url} alt={lightbox.caption} />
              <p id={lbTitle} className="report-lightbox-cap">
                {lightbox.caption}
              </p>
            </div>
          </div>,
          document.body,
        )}
      {showEditChrome && hasCharts && onRecolorCharts ? (
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
                if (!editMode) enterEditMode();
              }
            })();
          }}
        />
      ) : null}
    </article>
  );
}
