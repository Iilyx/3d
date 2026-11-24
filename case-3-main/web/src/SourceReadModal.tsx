/** Full-screen Markdown modal for any attached document + original download. */

import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { SourceAttachment } from "./domain/liberTypes";
import {
  resolveOriginalDownload,
  sourceModalEyebrow,
} from "./domain/sourceRead";
import { renderLightMd } from "./lightMd";
import { useFocusTrap } from "./useFocusTrap";

type Props = {
  docs: SourceAttachment[];
  onClose: () => void;
};

export function SourceReadModal({ docs, onClose }: Props) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState(false);
  useFocusTrap(dialogRef, { active: true });

  useEffect(() => {
    setActiveIdx(0);
    setQuery("");
  }, [docs]);

  const safeIdx = Math.min(activeIdx, Math.max(0, docs.length - 1));
  const activeDoc = docs[safeIdx] || docs[0];

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const html = useMemo(
    () => (activeDoc ? renderLightMd(activeDoc.text || "", query) : ""),
    [activeDoc, query],
  );

  if (!activeDoc) return null;

  const heading = activeDoc.title || activeDoc.fileName || "Документ";
  const eyebrow = sourceModalEyebrow(activeDoc);
  const downloadTarget = resolveOriginalDownload(activeDoc);

  async function copyMarkdown() {
    try {
      await navigator.clipboard.writeText(activeDoc.text || "");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  }

  function downloadBlobFallback() {
    if (downloadTarget.kind !== "blob") return;
    const blob = new Blob([downloadTarget.text], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadTarget.fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div
      ref={dialogRef}
      className="stimul-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="stimul-sheet is-read">
        <header className="settings-modal-head">
          <div>
            <p className="settings-modal-eyebrow">{eyebrow}</p>
            <h2 id={titleId} className="settings-modal-title">
              {heading}
            </h2>
          </div>
          <div className="dash-read-head-controls">
            <input
              type="search"
              className="dash-read-search"
              placeholder="Найти в документе…"
              aria-label="Поиск по документу"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button
              type="button"
              className={`stimul-copy-btn${copied ? " is-ok" : ""}`}
              onClick={() => void copyMarkdown()}
            >
              {copied ? "Скопировано" : "Копировать"}
            </button>
            {downloadTarget.kind === "url" ? (
              <a
                className="stimul-download-btn"
                href={downloadTarget.href}
                download={downloadTarget.fileName || true}
              >
                Скачать оригинал
              </a>
            ) : (
              <button
                type="button"
                className="stimul-download-btn"
                onClick={downloadBlobFallback}
              >
                Скачать оригинал
              </button>
            )}
            <button
              type="button"
              className="settings-modal-x"
              onClick={onClose}
              aria-label="Закрыть"
            >
              ×
            </button>
          </div>
        </header>
        <div className="settings-modal-body source-read-body">
          {docs.length > 1 ? (
            <nav className="dash-read-nav" aria-label="Прикреплённые документы">
              {docs.map((doc, idx) => (
                <button
                  key={`${doc.fileName || doc.title}-${idx}`}
                  type="button"
                  className={idx === safeIdx ? "is-active" : undefined}
                  onClick={() => {
                    setActiveIdx(idx);
                    setCopied(false);
                  }}
                >
                  {doc.fileName || doc.title}
                </button>
              ))}
            </nav>
          ) : null}
          {activeDoc.text?.trim() ? (
            <div
              className="msg-body msg-md source-read-md"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          ) : (
            <p className="stimul-read-text">В документе нет текста для предпросмотра.</p>
          )}
        </div>
      </div>
    </div>
  );
}
