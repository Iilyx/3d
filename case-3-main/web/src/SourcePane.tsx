/** Source viewer: editable text/md, or read-only native PDF for office files. */

import {
  Suspense,
  lazy,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import {
  enterSourceEdit,
  exitSourceEditOnBlur,
  exitSourceEditOnKey,
  type SourceViewMode,
} from "./domain/sourceDraftEdit";
import { renderLightMd } from "./lightMd";
import { SourceDocFullscreen } from "./SourceDocFullscreen";

const PdfFirstPage = lazy(() =>
  import("./PdfFirstPage").then((m) => ({ default: m.PdfFirstPage })),
);

type Props = {
  title: string;
  text: string;
  fileName?: string;
  /** Pre-run sourceDraft only — enables click-to-edit for text mode. */
  editable?: boolean;
  onTextChange?: (text: string) => void;
  /** document = native PDF preview; text = markdown/plain. */
  viewMode?: "text" | "document";
  previewUrl?: string | null;
  originalUrl?: string | null;
  format?: string;
};

export function SourcePane({
  title,
  text,
  fileName,
  editable = false,
  onTextChange,
  viewMode = "text",
  previewUrl = null,
  originalUrl = null,
  format,
}: Props) {
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState(false);
  const [mode, setMode] = useState<SourceViewMode>("preview");
  const [pdfPage, setPdfPage] = useState(1);
  const [pdfFullscreen, setPdfFullscreen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const isDocument = viewMode === "document";
  const canEdit = editable && !isDocument;
  const editing = canEdit && mode === "editing";

  useEffect(() => {
    if (!canEdit && mode === "editing") setMode("preview");
  }, [canEdit, mode]);

  useEffect(() => {
    if (!editing) return;
    const el = textareaRef.current;
    if (!el) return;
    el.focus();
    const len = el.value.length;
    el.setSelectionRange(len, len);
  }, [editing]);

  const looksMd =
    !isDocument &&
    (/\.(md|markdown)$/i.test(fileName || title) ||
      /^#{1,3}\s|```|\*\*/m.test(text));

  const html = useMemo(
    () => (looksMd ? renderLightMd(text, query) : null),
    [looksMd, text, query],
  );

  const plainHighlight = useMemo(() => {
    if (looksMd || !query.trim()) return null;
    const q = query.trim();
    const parts = text.split(
      new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"),
    );
    return parts;
  }, [looksMd, text, query]);

  async function copyAll() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  }

  function startEdit() {
    setMode(enterSourceEdit(canEdit, mode));
  }

  function onEditorKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    const next = exitSourceEditOnKey(e.key, mode);
    if (next !== mode) {
      e.preventDefault();
      e.stopPropagation();
      setMode(next);
    }
  }

  function onEditorBlur() {
    setMode(exitSourceEditOnBlur(mode));
  }

  const emptyLabel = "Нет текста источника.";
  const bodyText = text || "";
  const fmtLabel = (format || fileName || "").toUpperCase().replace(/^\./, "");

  if (isDocument) {
    return (
      <div className="artifact-source artifact-source-doc">
        <div className="artifact-source-toolbar">
          <h2 className="artifact-source-title">{title}</h2>
          <div className="artifact-source-tools">
            <span className="artifact-source-doc-badge muted">
              Просмотр · без правки
            </span>
            {previewUrl ? (
              <button
                type="button"
                className="artifact-source-copy"
                onClick={() => setPdfFullscreen(true)}
              >
                На весь экран
              </button>
            ) : null}
            {originalUrl ? (
              <a
                className="artifact-source-copy"
                href={originalUrl}
                download={fileName || true}
              >
                Скачать
              </a>
            ) : null}
          </div>
        </div>
        {previewUrl ? (
          <div className="artifact-source-pdf">
            <Suspense
              fallback={
                <div className="pdf-skeleton pdf-skeleton-solo" aria-busy>
                  <div className="pdf-skeleton-shine" />
                  <p className="artifact-rail-loading">Загружаю документ…</p>
                </div>
              }
            >
              <PdfFirstPage
                key={previewUrl}
                url={previewUrl}
                page={pdfPage}
                onPageChange={(p) => setPdfPage(p)}
              />
            </Suspense>
          </div>
        ) : (
          <div className="artifact-source-doc-card">
            <p className="artifact-source-doc-name">{fileName || title}</p>
            <p className="muted">
              {fmtLabel || "Документ"} прикреплён. Текст и таблицы извлечены для работы;
              для просмотра исходного оформления скачайте оригинал файла.
            </p>
            {originalUrl ? (
              <a className="btn btn-ghost" href={originalUrl} download={fileName || true}>
                Скачать оригинал
              </a>
            ) : null}
          </div>
        )}
        {pdfFullscreen && previewUrl ? (
          <SourceDocFullscreen
            title={title}
            url={previewUrl}
            page={pdfPage}
            onPageChange={setPdfPage}
            originalUrl={originalUrl}
            fileName={fileName}
            onClose={() => setPdfFullscreen(false)}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div className={`artifact-source${editing ? " is-editing" : ""}`}>
      <div className="artifact-source-toolbar">
        <h2 className="artifact-source-title">{title}</h2>
        <div className="artifact-source-tools">
          {!editing ? (
            <label className="artifact-source-search">
              <span className="sr-only">Поиск</span>
              <input
                type="search"
                placeholder="Найти…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
          ) : (
            <span className="artifact-source-edit-hint muted">
              Esc — готово
            </span>
          )}
          <button
            type="button"
            className={`artifact-source-copy${copied ? " is-ok" : ""}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => void copyAll()}
          >
            {copied ? "Скопировано" : "Копировать"}
          </button>
        </div>
      </div>

      {editing ? (
        <textarea
          ref={textareaRef}
          className="artifact-source-editor"
          value={bodyText}
          aria-label="Редактировать Source"
          onChange={(e) => onTextChange?.(e.target.value)}
          onKeyDown={onEditorKeyDown}
          onBlur={onEditorBlur}
          spellCheck={false}
        />
      ) : html ? (
        <div
          className={`artifact-source-md${canEdit ? " is-editable" : ""}`}
          role={canEdit ? "button" : undefined}
          tabIndex={canEdit ? 0 : undefined}
          onClick={canEdit ? startEdit : undefined}
          onKeyDown={
            canEdit
              ? (e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    startEdit();
                  }
                }
              : undefined
          }
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre
          className={`artifact-source-pre${canEdit ? " is-editable" : ""}`}
          role={canEdit ? "button" : undefined}
          tabIndex={canEdit ? 0 : undefined}
          onClick={canEdit ? startEdit : undefined}
          onKeyDown={
            canEdit
              ? (e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    startEdit();
                  }
                }
              : undefined
          }
        >
          {plainHighlight
            ? plainHighlight.map((part, i) =>
                part.toLowerCase() === query.trim().toLowerCase() ? (
                  <mark key={i} className="src-hit">
                    {part}
                  </mark>
                ) : (
                  <span key={i}>{part}</span>
                ),
              )
            : bodyText || emptyLabel}
        </pre>
      )}
    </div>
  );
}
