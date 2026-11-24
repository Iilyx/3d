/** Full-viewport Source PDF lightbox (pdf.js page slider). */

import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "./useFocusTrap";

const PdfFirstPage = lazy(() =>
  import("./PdfFirstPage").then((m) => ({ default: m.PdfFirstPage })),
);

type Props = {
  title: string;
  url: string;
  page: number;
  onPageChange: (page: number) => void;
  originalUrl?: string | null;
  fileName?: string;
  onClose: () => void;
};

export function SourceDocFullscreen({
  title,
  url,
  page,
  onPageChange,
  originalUrl,
  fileName,
  onClose,
}: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [localPage, setLocalPage] = useState(page);
  useFocusTrap(dialogRef, { active: true });

  useEffect(() => {
    setLocalPage(page);
  }, [page]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey, true);
    };
  }, [onClose]);

  return createPortal(
    <div
      ref={dialogRef}
      className="source-doc-fullscreen"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
    >
      <div
        className="source-doc-fullscreen-sheet"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="source-doc-fullscreen-head">
          <div>
            <h2 className="source-doc-fullscreen-title">{title}</h2>
            <p className="source-doc-fullscreen-sub muted">
              Esc — закрыть · страница на весь экран
            </p>
          </div>
          <div className="source-doc-fullscreen-actions">
            {originalUrl ? (
              <a
                className="btn btn-ghost"
                href={originalUrl}
                download={fileName || true}
              >
                Скачать
              </a>
            ) : null}
            <button
              type="button"
              className="btn source-doc-fullscreen-close"
              onClick={onClose}
            >
              Закрыть
            </button>
          </div>
        </header>
        <div className="source-doc-fullscreen-body">
          <Suspense
            fallback={
              <div className="pdf-skeleton pdf-skeleton-solo" aria-busy>
                <div className="pdf-skeleton-shine" />
                <p className="artifact-rail-loading">Загружаю документ…</p>
              </div>
            }
          >
            <PdfFirstPage
              key={url}
              url={url}
              page={localPage}
              onPageChange={(p) => {
                setLocalPage(p);
                onPageChange(p);
              }}
            />
          </Suspense>
        </div>
      </div>
    </div>,
    document.body,
  );
}
