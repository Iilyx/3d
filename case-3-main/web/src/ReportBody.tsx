/** Report preview body: empty state + block list (headings/tables/figures). */

import {
  ChartEditSheet,
  type ChartEditDraft,
  type ChartEditRequest,
  type PaletteInfo,
} from "./ChartEditSheet";
import { ChartCard } from "./ChartCard";
import { ChartLivePane } from "./ChartLivePane";
import { chartTypeChipLabel } from "./ChartTypePreview";
import {
  ImageEditModal,
  type ImageEditRequest,
} from "./ImageEditModal";
import {
  TableEditSheet,
  type TableEditDraft,
  type TableEditRequest,
} from "./TableEditSheet";
import { type ParagraphEditRequest } from "./ParagraphEditSheet";
import { InlineBlockEditor } from "./InlineBlockEditor";
import type { HeadingEditRequest } from "./HeadingEditTypes";
import type { ListEditRequest } from "./ListEditTypes";
import { isBlockHiddenByCollapse } from "./reportSections";
import { bustFromUrl, colIsNumeric } from "./reportTableNumeric";
import type { PreviewBlock } from "./domain/reportPreview";
import { renderKatexInHtml } from "./domain/renderMath";
import { MermaidView } from "./MermaidView";
import type { DiagramInfo } from "./DiagramFullscreen";
import { Fragment, type Dispatch, type SetStateAction } from "react";

export type ReportBodyProps = {
  blocks: PreviewBlock[];
  downloads?: Record<string, string>;
  runId?: string;
  diagrams?: DiagramInfo[];
  palettes: PaletteInfo[];
  catalogTypes: string[];
  defaultPalette: string;
  editingFigureId: string | null;
  editError: string | null;
  editErrorFigureId: string | null;
  collapsed: Set<string>;
  editMode: boolean;
  canEditPara: boolean;
  canEditHeading: boolean;
  canEditList: boolean;
  canEditTable: boolean;
  canEditFigure: boolean;
  canEditImage: boolean;
  tableDraftByN: Record<number, TableEditDraft>;
  draftById: Record<string, ChartEditDraft>;
  sheetPreviewHtmlById: Record<string, string | null>;
  setTableDraftByN: Dispatch<SetStateAction<Record<number, TableEditDraft>>>;
  setDraftById: Dispatch<SetStateAction<Record<string, ChartEditDraft>>>;
  setSheetPreviewHtmlById: Dispatch<
    SetStateAction<Record<string, string | null>>
  >;
  setLightbox: (v: { url: string; caption: string } | null) => void;
  toggleSection: (headingId: string) => void;
  onJumpToPdf?: (info: {
    id: string;
    figureIndex: number;
    pdfPage?: number;
    caption?: string;
  }) => void;
  onJumpToDiagram?: (diagramId: string) => void;
  onOpenPdf?: () => void;
  onEditFigure?: (req: ChartEditRequest) => Promise<boolean> | boolean;
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
  onEditList?: (req: ListEditRequest) => Promise<boolean> | boolean;
  /** Exactly one prose/list block open at a time (document click-to-edit). */
  activeBlockId?: string | null;
  onActiveBlockId?: (id: string | null) => void;
  /** On-demand chart/table/image sheet id (`tab:N` / figure id). */
  openMediaId?: string | null;
  onOpenMediaId?: (id: string | null) => void;
};

export function ReportBody({
  blocks,
  downloads,
  runId,
  diagrams,
  palettes,
  catalogTypes,
  defaultPalette,
  editingFigureId,
  editError,
  editErrorFigureId,
  collapsed,
  editMode,
  canEditPara,
  canEditHeading,
  canEditList,
  canEditTable,
  canEditFigure,
  canEditImage,
  tableDraftByN,
  draftById,
  sheetPreviewHtmlById,
  setTableDraftByN,
  setDraftById,
  setSheetPreviewHtmlById,
  setLightbox,
  toggleSection,
  onJumpToPdf,
  onJumpToDiagram,
  onOpenPdf,
  onEditFigure,
  onEditImage,
  onUploadFigure,
  onDeleteFigure,
  onEditTable,
  onEditParagraph,
  onInsertParagraph,
  onEditHeading,
  onEditList,
  activeBlockId = null,
  onActiveBlockId,
  openMediaId = null,
  onOpenMediaId,
}: ReportBodyProps) {
  let figN = 0;
  let tabN = 0;
  let headN = 0;
  let paraN = 0;
  let listN = 0;

  return (
      <div className="report-body">
        {blocks.length === 0 && (
          <div
            className={`report-empty-warn${downloads?.pdf ? " has-pdf" : ""}`}
            role="status"
          >
            <p className="report-p muted" style={{ margin: 0 }}>
              Превью пустое
              {downloads?.pdf
                ? " — PDF готов. Откройте вкладку PDF для просмотра печатной версии."
                : " — тело отчёта не разобралось."}
            </p>
            {downloads?.pdf && onOpenPdf ? (
              <button
                type="button"
                className="report-empty-warn-btn"
                onClick={onOpenPdf}
              >
                Открыть PDF
              </button>
            ) : null}
          </div>
        )}
        {blocks.map((b, i) => {
          const delayStyle = {
            animationDelay: `${Math.min(i * 0.045, 0.55)}s`,
          } as const;
          const hiddenByCollapse = isBlockHiddenByCollapse(
            blocks,
            i,
            collapsed,
          );

          if (b.type === "heading") {
            headN += 1;
            const headingIndex = headN;
            const headingId = `rail-h-${headingIndex}`;
            const headEditId = `heading:${headingIndex}`;
            // Nested under a collapsed ancestor — hide (parent heading stays).
            if (hiddenByCollapse) return null;
            const Tag = b.level >= 2 ? "h3" : "h2";
            const expanded = !collapsed.has(headingId);
            const isEditingHead = editingFigureId === headEditId;
            const headActive = canEditHeading && activeBlockId === headEditId;
            const headError =
              isEditingHead || editErrorFigureId === headEditId
                ? editError
                : null;
            const insertHeadKey = `para:insert-head-${headingIndex}`;
            const insertHeadActive = canEditPara && activeBlockId === insertHeadKey;
            const isInsertingHead =
              editingFigureId === `head:after-${headingIndex}` ||
              editingFigureId === "para:insert";
            const insertHeadError =
              editErrorFigureId === `head:after-${headingIndex}` ||
              editErrorFigureId === "para:insert"
                ? editError
                : null;
            return (
              <Fragment key={i}>
                <div
                  id={headingId}
                  className={`report-h-row report-block${headActive || isEditingHead ? " is-editing" : ""}${canEditHeading && !headActive ? " is-editable-idle" : ""}`}
                  style={delayStyle}
                >
                  <button
                    type="button"
                    className="report-h-toggle"
                    aria-expanded={expanded}
                    aria-label={
                      expanded ? `Свернуть «${b.text}»` : `Развернуть «${b.text}»`
                    }
                    onClick={() => toggleSection(headingId)}
                    disabled={editMode}
                  >
                    <span className="report-h-toggle-chevron" aria-hidden>
                      ▸
                    </span>
                  </button>
                  {headActive ? (
                    <div className="report-h-edit">
                      <InlineBlockEditor
                        hideActions
                        kind="heading"
                        initialText={b.text}
                        busy={isEditingHead}
                        error={headError}
                        onCancel={() => onActiveBlockId?.(null)}
                        onDelete={() => {
                          void (async () => {
                            const ok = await onEditHeading?.({
                              headingIndex,
                              text: "",
                            });
                            if (ok !== false) onActiveBlockId?.(null);
                          })();
                        }}
                        onSave={(text) => {
                          void (async () => {
                            const ok = await onEditHeading?.({
                              headingIndex,
                              text,
                            });
                            if (ok !== false) onActiveBlockId?.(null);
                          })();
                        }}
                      />
                    </div>
                  ) : (
                    <Tag
                      className={`report-h report-h${b.level}${canEditHeading ? " is-click-edit" : ""}`}
                      role={canEditHeading ? "button" : undefined}
                      tabIndex={canEditHeading ? 0 : undefined}
                      onClick={
                        canEditHeading
                          ? () => {
                              onOpenMediaId?.(null);
                              onActiveBlockId?.(headEditId);
                            }
                          : undefined
                      }
                      onKeyDown={
                        canEditHeading
                          ? (e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                onOpenMediaId?.(null);
                                onActiveBlockId?.(headEditId);
                              }
                            }
                          : undefined
                      }
                    >
                      {b.text}
                    </Tag>
                  )}
                </div>
                {canEditPara && onInsertParagraph && (
                  <div
                    className={`report-insert-slot${insertHeadActive ? " is-active" : ""}`}
                  >
                    {insertHeadActive ? (
                      <InlineBlockEditor
                        kind="paragraph"
                        initialText=""
                        saveLabel="Добавить абзац"
                        busy={isInsertingHead}
                        error={insertHeadError}
                        onCancel={() => onActiveBlockId?.(null)}
                        onSave={(text) => {
                          void (async () => {
                            const ok = await onInsertParagraph?.({
                              text,
                              afterHeadingIndex: headingIndex,
                            });
                            if (ok !== false) onActiveBlockId?.(null);
                          })();
                        }}
                      />
                    ) : (
                      <button
                        type="button"
                        className="report-insert-btn"
                        title="Добавить абзац под заголовком"
                        onClick={() => {
                          onOpenMediaId?.(null);
                          onActiveBlockId?.(insertHeadKey);
                        }}
                      >
                        + Добавить абзац
                      </button>
                    )}
                  </div>
                )}
              </Fragment>
            );
          }

          if (hiddenByCollapse) {
            // Keep fig/tab/para counters stable when section is collapsed.
            if (b.type === "figure") figN += 1;
            if (b.type === "table") tabN += 1;
            if (b.type === "paragraph") paraN += 1;
            if (b.type === "list") {
              const idMatch = b.id ? /^list-(\d+)$/.exec(b.id) : null;
              if (idMatch) listN = Math.max(listN, Number(idMatch[1]));
              else listN += 1;
            }
            return null;
          }

          if (b.type === "paragraph") {
            paraN += 1;
            const idMatch = b.id ? /^para-(\d+)$/.exec(b.id) : null;
            const n = idMatch ? Number(idMatch[1]) : paraN;
            if (idMatch) paraN = Math.max(paraN, n);
            const paraId = `para:${n}`;
            const isEditingPara = editingFigureId === paraId;
            const paraActive = canEditPara && activeBlockId === paraId;
            const sheetError =
              editErrorFigureId === paraId ? editError : null;
            const insertKey = `para:insert-after-${n}`;
            const insertActive = canEditPara && activeBlockId === insertKey;
            const isInsertingParaAfter =
              editingFigureId === `para:after-${n}` ||
              editingFigureId === "para:insert";
            const insertParaError =
              editErrorFigureId === `para:after-${n}` ||
              editErrorFigureId === "para:insert"
                ? editError
                : null;
            return (
              <Fragment key={i}>
                <div
                  id={`report-para-${n}`}
                  className={`report-para-wrap report-block${paraActive || isEditingPara ? " is-editing" : ""}${canEditPara && !paraActive ? " is-editable-idle" : ""}`}
                  style={delayStyle}
                >
                  <div className="report-para-frame">
                    {paraActive ? (
                      <InlineBlockEditor
                        hideActions
                        kind="paragraph"
                        initialText={b.text}
                        busy={isEditingPara}
                        error={sheetError}
                        onCancel={() => onActiveBlockId?.(null)}
                        onDelete={() => {
                          void (async () => {
                            const ok = await onEditParagraph?.({
                              paragraphIndex: n,
                              text: "",
                            });
                            if (ok !== false) onActiveBlockId?.(null);
                          })();
                        }}
                        onSave={(text) => {
                          void (async () => {
                            const ok = await onEditParagraph?.({
                              paragraphIndex: n,
                              text,
                            });
                            if (ok !== false) onActiveBlockId?.(null);
                          })();
                        }}
                      />
                    ) : b.html ? (
                      <p
                        className={`report-p${canEditPara ? " is-click-edit" : ""}`}
                        role={canEditPara ? "button" : undefined}
                        tabIndex={canEditPara ? 0 : undefined}
                        onClick={
                          canEditPara
                            ? () => {
                                onOpenMediaId?.(null);
                                onActiveBlockId?.(paraId);
                              }
                            : undefined
                        }
                        onKeyDown={
                          canEditPara
                            ? (e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  onOpenMediaId?.(null);
                                  onActiveBlockId?.(paraId);
                                }
                              }
                            : undefined
                        }
                        dangerouslySetInnerHTML={{ __html: renderKatexInHtml(b.html) }}
                      />
                    ) : (
                      <p
                        className={`report-p${canEditPara ? " is-click-edit" : ""}`}
                        role={canEditPara ? "button" : undefined}
                        tabIndex={canEditPara ? 0 : undefined}
                        onClick={
                          canEditPara
                            ? () => {
                                onOpenMediaId?.(null);
                                onActiveBlockId?.(paraId);
                              }
                            : undefined
                        }
                        onKeyDown={
                          canEditPara
                            ? (e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  onOpenMediaId?.(null);
                                  onActiveBlockId?.(paraId);
                                }
                              }
                            : undefined
                        }
                      >
                        {b.text}
                      </p>
                    )}
                    {isEditingPara && (
                      <div className="report-fig-busy" aria-live="polite">
                        <p className="fig-press-label">Пересобираю абзац…</p>
                      </div>
                    )}
                  </div>
                </div>
                {canEditPara && onInsertParagraph && (
                  <div
                    className={`report-insert-slot${insertActive ? " is-active" : ""}`}
                  >
                    {insertActive ? (
                      <InlineBlockEditor
                        kind="paragraph"
                        initialText=""
                        saveLabel="Добавить абзац"
                        busy={isInsertingParaAfter}
                        error={insertParaError}
                        onCancel={() => onActiveBlockId?.(null)}
                        onSave={(text) => {
                          void (async () => {
                            const ok = await onInsertParagraph?.({
                              text,
                              afterParagraphIndex: n,
                            });
                            if (ok !== false) onActiveBlockId?.(null);
                          })();
                        }}
                      />
                    ) : (
                      <button
                        type="button"
                        className="report-insert-btn"
                        title="Добавить абзац после этого"
                        onClick={() => {
                          onOpenMediaId?.(null);
                          onActiveBlockId?.(insertKey);
                        }}
                      >
                        + Добавить абзац
                      </button>
                    )}
                  </div>
                )}
              </Fragment>
            );
          }
          if (b.type === "list") {
            listN += 1;
            const idMatch = b.id ? /^list-(\d+)$/.exec(b.id) : null;
            const n = idMatch ? Number(idMatch[1]) : listN;
            if (idMatch) listN = Math.max(listN, n);
            const listId = `list:${n}`;
            const isEditingList = editingFigureId === listId;
            const listActive = canEditList && activeBlockId === listId;
            const listError =
              editErrorFigureId === listId ? editError : null;
            const Tag = b.ordered ? "ol" : "ul";
            if (listActive) {
              return (
                <div
                  key={i}
                  id={`report-list-${n}`}
                  className={`report-list-wrap report-block is-editing`}
                  style={delayStyle}
                >
                  <InlineBlockEditor
                    hideActions
                    kind="list"
                    ordered={Boolean(b.ordered)}
                    initialItems={(b.items || []).map((it) => it.text)}
                    busy={isEditingList}
                    error={listError}
                    onCancel={() => onActiveBlockId?.(null)}
                    onDelete={() => {
                      void (async () => {
                        const ok = await onEditList?.({
                          listIndex: n,
                          items: [],
                          ordered: Boolean(b.ordered),
                        });
                        if (ok !== false) onActiveBlockId?.(null);
                      })();
                    }}
                    onSave={(items) => {
                      void (async () => {
                        const ok = await onEditList?.({
                          listIndex: n,
                          items,
                          ordered: Boolean(b.ordered),
                        });
                        if (ok !== false) onActiveBlockId?.(null);
                      })();
                    }}
                  />
                </div>
              );
            }
            return (
              <Tag
                key={i}
                id={`report-list-${n}`}
                className={`report-list report-block${b.ordered ? " is-ol" : ""}${canEditList ? " is-editable-idle is-click-edit" : ""}`}
                style={delayStyle}
                role={canEditList ? "button" : undefined}
                tabIndex={canEditList ? 0 : undefined}
                onClick={
                  canEditList
                    ? () => {
                        onOpenMediaId?.(null);
                        onActiveBlockId?.(listId);
                      }
                    : undefined
                }
                onKeyDown={
                  canEditList
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onOpenMediaId?.(null);
                          onActiveBlockId?.(listId);
                        }
                      }
                    : undefined
                }
              >
                {(b.items || []).map((it, j) =>
                  it.html ? (
                    <li
                      key={j}
                      dangerouslySetInnerHTML={{ __html: renderKatexInHtml(it.html) }}
                    />
                  ) : (
                    <li key={j}>{it.text}</li>
                  ),
                )}
              </Tag>
            );
          }
          if (b.type === "table") {
            tabN += 1;
            const n = tabN;
            const tableId = `tab:${n}`;
            const tableOpen = canEditTable && openMediaId === tableId;
            const isEditingTable = editingFigureId === tableId;
            const tableError =
              tableOpen && editErrorFigureId === tableId ? editError : null;
            const live =
              tableOpen && tableDraftByN[n]
                ? tableDraftByN[n]
                : {
                    caption: b.caption || "",
                    headers: b.headers || [],
                    rows: b.rows || [],
                  };
            const numericCols = live.headers.map((_, ci) =>
              colIsNumeric(live.headers, live.rows, ci),
            );
            const capText = live.caption.trim()
              ? `Таблица ${n}: ${live.caption.trim()}`
              : `Таблица ${n}`;
            return (
              <figure
                key={i}
                id={`report-table-${n}`}
                className={`report-table-wrap report-block${b.landscape ? " is-landscape" : ""}${isEditingTable ? " is-editing" : ""}${tableOpen ? " is-tuning" : ""}${canEditTable && !tableOpen ? " is-editable-idle" : ""}`}
                style={delayStyle}
              >
                <div className="report-table-toolbar">
                  <figcaption
                    className={`report-caption${live.caption.trim() ? "" : " muted"}${tableOpen ? " is-draft" : ""}`}
                  >
                    {capText}
                    {b.landscape ? (
                      <span className="report-table-landscape"> · альбомная страница</span>
                    ) : null}
                    {tableOpen && !isEditingTable ? (
                      <span className="report-table-draft-tag"> черновик</span>
                    ) : null}
                  </figcaption>
                  {canEditTable && !tableOpen ? (
                    <button
                      type="button"
                      className="report-media-edit-btn"
                      onClick={() => {
                        onActiveBlockId?.(null);
                        onOpenMediaId?.(tableId);
                      }}
                    >
                      Править
                    </button>
                  ) : null}
                </div>
                <div className="report-table-scroll">
                  <table className="report-table">
                    <thead>
                      <tr>
                        {live.headers.map((h, hi) => (
                          <th
                            key={hi}
                            className={numericCols[hi] ? "num" : undefined}
                          >
                            {h || (
                              <span className="report-table-ph">Столбец {hi + 1}</span>
                            )}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {live.rows.map((row, ri) => (
                        <tr key={ri}>
                          {row.map((cell, ci) => (
                            <td
                              key={ci}
                              className={numericCols[ci] ? "num" : undefined}
                            >
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {isEditingTable && (
                  <div className="report-table-busy" aria-live="polite">
                    <p className="fig-press-label">Пересобираю таблицу в отчёте…</p>
                    <p className="fig-press-hint">PDF и Word</p>
                  </div>
                )}
                {tableOpen && onEditTable && (
                  <TableEditSheet
                    open
                    trapFocus={false}
                    tableIndex={n}
                    initialCaption={b.caption || ""}
                    initialHeaders={b.headers || []}
                    initialRows={b.rows || []}
                    busy={isEditingTable}
                    error={tableError}
                    onDraftChange={(d) =>
                      setTableDraftByN((prev) => ({ ...prev, [n]: d }))
                    }
                    onCancel={() => {
                      setTableDraftByN((prev) => {
                        const next = { ...prev };
                        delete next[n];
                        return next;
                      });
                      onOpenMediaId?.(null);
                    }}
                    onSubmit={(req) => {
                      void onEditTable(req);
                    }}
                  />
                )}
              </figure>
            );
          }
          if (b.type === "figure") {
            figN += 1;
            const n = figN;
            const isChart = b.kind === "chart";
            const isDiagram = b.kind === "diagram" || b.id.startsWith("dia_");
            const dia =
              isDiagram && diagrams
                ? diagrams.find((d) => d.id === b.id)
                : undefined;
            const isPhoto = !isChart && !isDiagram;
            const label = isChart ? "Рис." : isDiagram ? "Схема" : "Илл.";
            const caption = b.caption
              ? `${label} ${n}: ${b.caption}`
              : `${label} ${n}`;
            const isEditing = editingFigureId === b.id;
            const sheetOpen =
              isChart && canEditFigure && openMediaId === b.id;
            const imageOpen =
              isPhoto && canEditImage && openMediaId === b.id;
            const sheetError =
              (sheetOpen || imageOpen) && editErrorFigureId === b.id
                ? editError
                : null;
            const intent =
              sheetOpen && draftById[b.id] && !isEditing
                ? draftById[b.id]
                : null;
            const jumpPdf = () => {
              onJumpToPdf?.({
                id: b.id,
                figureIndex: n,
                pdfPage: b.pdfPage,
                caption,
              });
            };
            const jumpDiagram = () => {
              onJumpToDiagram?.(b.id);
            };
            const figInner = (
              <>
                <div className="report-fig-frame">
                  {isChart && runId ? (
                    <ChartLivePane
                      runId={runId}
                      chartId={b.id}
                      caption={b.caption || caption}
                      fallbackUrl={b.url}
                      version={bustFromUrl(b.url)}
                      htmlOverride={
                        sheetOpen ? sheetPreviewHtmlById[b.id] ?? null : null
                      }
                      disabled={isEditing}
                      onJumpToPdf={onJumpToPdf ? jumpPdf : undefined}
                    />
                  ) : isDiagram && dia?.mermaid ? (
                    <button
                      type="button"
                      className="report-fig-link report-fig-diagram-link"
                      onClick={() => {
                        if (isDiagram && onJumpToDiagram) jumpDiagram();
                        else if (onJumpToPdf) jumpPdf();
                        else setLightbox({ url: b.url || "", caption });
                      }}
                      aria-label={
                        isDiagram && onJumpToDiagram
                          ? `Открыть схему ${caption}`
                          : onJumpToPdf
                            ? `Показать ${caption} в PDF`
                            : `Открыть ${caption}`
                      }
                      disabled={isEditing}
                    >
                      <MermaidView
                        source={dia.mermaid}
                        className="is-report-diagram-preview"
                      />
                    </button>
                  ) : b.url ? (
                    <button
                      type="button"
                      className="report-fig-link"
                      onClick={() => {
                        if (isDiagram && onJumpToDiagram) jumpDiagram();
                        else if (onJumpToPdf) jumpPdf();
                        else setLightbox({ url: b.url!, caption });
                      }}
                      aria-label={
                        isDiagram && onJumpToDiagram
                          ? `Открыть схему ${caption}`
                          : onJumpToPdf
                            ? `Показать ${caption} в PDF`
                            : `Открыть ${caption}`
                      }
                      disabled={isEditing}
                    >
                      <img src={b.url} alt={b.caption || b.id} loading="lazy" />
                    </button>
                  ) : (
                    <div className="report-fig-missing">
                      {isDiagram ? "Схема недоступна" : "Изображение недоступно"}
                    </div>
                  )}
                  {intent && (
                    <div
                      className="report-fig-intent"
                      style={
                        intent.wash
                          ? {
                              background: `linear-gradient(135deg, ${intent.wash}33, transparent 65%)`,
                            }
                          : undefined
                      }
                      aria-hidden
                    >
                      <span className="report-fig-intent-badge">
                        будет:{" "}
                        {chartTypeChipLabel(intent.chartType) || intent.chartType}
                        {intent.paletteLabel
                          ? ` · ${intent.paletteLabel}`
                          : ""}
                      </span>
                      <span className="report-fig-intent-note">
                        после сохранения
                      </span>
                    </div>
                  )}
                  {b.url && !isEditing && (
                    <button
                      type="button"
                      className="report-fig-zoom"
                      title="Увеличить"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setLightbox({ url: b.url!, caption });
                      }}
                    >
                      ↗
                    </button>
                  )}
                  {isEditing && (
                    <div
                      className={`report-fig-busy${isPhoto ? " is-photo" : ""}`}
                      aria-live="polite"
                    >
                      {isPhoto ? (
                        <div className="fig-photo-spin" aria-hidden>
                          <div className="fig-photo-frame">
                            <div className="fig-photo-shutter" />
                            <div className="fig-photo-grain" />
                          </div>
                        </div>
                      ) : (
                        <div className="fig-press" aria-hidden>
                          <div className="fig-press-sheet">
                            <i className="fig-press-bar" style={{ width: "72%" }} />
                            <i className="fig-press-bar" style={{ width: "88%" }} />
                            <i
                              className="fig-press-bar short"
                              style={{ width: "54%" }}
                            />
                            <div className="fig-press-plot">
                              <span />
                              <span />
                              <span />
                              <span />
                              <span />
                            </div>
                          </div>
                          <div className="fig-press-roller" />
                        </div>
                      )}
                      <p className="fig-press-label">
                        {isPhoto
                          ? "Генерирую фото…"
                          : isDiagram
                            ? "Пересобираю схему…"
                            : "Пересобираю график…"}
                      </p>
                      <p className="fig-press-hint">
                        {isPhoto ? "Фото и PDF" : isDiagram ? "Схема и PDF" : "График и PDF"}
                      </p>
                    </div>
                  )}
                </div>

                <div className="report-fig-cap-row">
                  <figcaption
                    className={`report-caption report-fig-cap${(onJumpToPdf || (isDiagram && onJumpToDiagram)) ? " is-jump" : ""}`}
                    title={
                      isDiagram && onJumpToDiagram
                        ? "Клик → перейти к схеме"
                        : b.chartType
                          ? `Тип: ${b.chartType}${onJumpToPdf ? " · клик → PDF" : ""}`
                          : onJumpToPdf
                            ? "Клик → страница PDF"
                            : undefined
                    }
                    onClick={
                      !isEditing
                        ? (e) => {
                            e.preventDefault();
                            if (isDiagram && onJumpToDiagram) jumpDiagram();
                            else if (onJumpToPdf) jumpPdf();
                          }
                        : undefined
                    }
                    role={onJumpToPdf || (isDiagram && onJumpToDiagram) ? "link" : undefined}
                    tabIndex={onJumpToPdf || (isDiagram && onJumpToDiagram) ? 0 : undefined}
                    onKeyDown={
                      (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          if (isDiagram && onJumpToDiagram) jumpDiagram();
                          else if (onJumpToPdf) jumpPdf();
                        }
                      }
                    }
                  >
                    {caption}
                  </figcaption>
                  {((isChart && canEditFigure) || (isPhoto && canEditImage)) &&
                  !sheetOpen &&
                  !imageOpen ? (
                    <button
                      type="button"
                      className="report-media-edit-btn"
                      onClick={() => {
                        onActiveBlockId?.(null);
                        onOpenMediaId?.(b.id);
                      }}
                    >
                      Править
                    </button>
                  ) : isDiagram && onJumpToDiagram ? (
                    <button
                      type="button"
                      className="report-media-edit-btn"
                      title="Редактировать схему"
                      onClick={() => {
                        jumpDiagram();
                      }}
                    >
                      Схема
                    </button>
                  ) : null}
                </div>

                {sheetOpen && onEditFigure && (
                  <ChartEditSheet
                    open
                    trapFocus={false}
                    figureId={b.id}
                    runId={runId}
                    caption={b.caption || caption}
                    palettes={palettes}
                    catalogTypes={catalogTypes}
                    initialPalette={
                      (b.palette && b.palette !== "auto"
                        ? b.palette
                        : defaultPalette) || "atelier"
                    }
                    initialType={b.chartType || ""}
                    busy={isEditing}
                    error={sheetError}
                    onDraftChange={(d) =>
                      setDraftById((prev) => ({ ...prev, [b.id]: d }))
                    }
                    onPreviewHtml={(html) =>
                      setSheetPreviewHtmlById((prev) => ({
                        ...prev,
                        [b.id]: html,
                      }))
                    }
                    onCancel={() => {
                      setDraftById((prev) => {
                        const next = { ...prev };
                        delete next[b.id];
                        return next;
                      });
                      setSheetPreviewHtmlById((prev) => {
                        const next = { ...prev };
                        delete next[b.id];
                        return next;
                      });
                      onOpenMediaId?.(null);
                    }}
                    onSubmit={async (req) => {
                      const ok = await onEditFigure(req);
                      if (ok) {
                        onOpenMediaId?.(null);
                      }
                    }}
                    onDelete={
                      onDeleteFigure
                        ? () => {
                            void onDeleteFigure(b.id);
                            onOpenMediaId?.(null);
                          }
                        : undefined
                    }
                  />
                )}
                {imageOpen && onEditImage && (
                  <ImageEditModal
                    open
                    trapFocus={false}
                    figureId={b.id}
                    caption={b.caption || caption}
                    previewUrl={b.url}
                    busy={isEditing}
                    error={sheetError}
                    onCancel={() => onOpenMediaId?.(null)}
                    onSubmit={async (req) => {
                      const ok = await onEditImage(req);
                      if (ok) {
                        onOpenMediaId?.(null);
                      }
                    }}
                    onUpload={
                      onUploadFigure
                        ? (file, cap) => {
                            void onUploadFigure(b.id, file, cap);
                            onOpenMediaId?.(null);
                          }
                        : undefined
                    }
                    onDelete={
                      onDeleteFigure
                        ? () => {
                            void onDeleteFigure(b.id);
                            onOpenMediaId?.(null);
                          }
                        : undefined
                    }
                  />
                )}
              </>
            );
            const canEditDiagram = Boolean(isDiagram && onJumpToDiagram);
            return (
              <figure
                key={i}
                id={b.id ? `report-fig-${b.id}` : undefined}
                className={`report-fig report-block${isEditing ? " is-editing" : ""}${sheetOpen || imageOpen ? " is-tuning" : ""}${(canEditFigure || canEditImage || canEditDiagram) && !sheetOpen && !imageOpen ? " is-editable-idle" : ""}`}
                style={delayStyle}
              >
                {isChart ? (
                  <ChartCard
                    insight={b.insight}
                    highlights={b.highlights}
                    chartType={b.chartType}
                  >
                    {figInner}
                  </ChartCard>
                ) : (
                  figInner
                )}
              </figure>
            );
          }
          return null;
        })}
      </div>
  );
}
