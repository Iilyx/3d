/** Julius-style file card: matte stage, icon, hover CTA, footer. */

import { DeckChatHero } from "./DeckChatHero";
import { DECK_DOWNLOAD_BLOCKED_LABEL, DECK_DOWNLOAD_BLOCKED_TITLE } from "./domain/deckDownloads";
import { prefersLiveChatHero } from "./domain/chatDeckHero";
import type { DeckIR } from "./deckTypes";
import { PdfThumb } from "./PdfThumb";

type Kind = "pptx" | "deck_pdf" | "pdf" | "docx";

type Props = {
  kind: Kind;
  href: string;
  previewUrl?: string | null;
  /** Deck twin / legacy: first-page render. Report PDF uses compact teaser only. */
  pdfUrl?: string | null;
  fileLabel?: string;
  /** Human report title for the compact PDF teaser. */
  docTitle?: string | null;
  /** Same Source → DOCX twin; download on the same report card. */
  docxHref?: string | null;
  /** Companion presentation PDF next to PPTX on the single presentation card. */
  deckPdfHref?: string | null;
  onPrimary?: () => void;
  primaryLabel?: string;
  /** Extra slide thumbs under the hero (deck). */
  filmstrip?: string[];
  /** Live IR twin for crisp chat hero (PPTX / deck PDF cards). */
  deck?: DeckIR | null;
  runId?: string | null;
  /** Unsaved deck edits: do not hand out the file on disk. */
  downloadsBlocked?: boolean;
};

function FileGlyph({ kind }: { kind: Kind }) {
  if (kind === "pptx") {
    return (
      <svg
        className="deck-file-card-glyph"
        width="22"
        height="22"
        viewBox="0 0 22 22"
        aria-hidden
      >
        <rect
          x="2.5"
          y="4"
          width="17"
          height="13"
          rx="2.2"
          fill="currentColor"
          opacity="0.14"
        />
        <rect
          x="2.5"
          y="4"
          width="17"
          height="13"
          rx="2.2"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        <path
          d="M6 8.2h10M6 11h7.5M6 13.8h5"
          stroke="currentColor"
          strokeWidth="1.35"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  if (kind === "docx") {
    return (
      <svg
        className="deck-file-card-glyph"
        width="22"
        height="22"
        viewBox="0 0 22 22"
        aria-hidden
      >
        <path
          d="M6 2.8h7.2L17.2 7v12.2a1.6 1.6 0 0 1-1.6 1.6H6A1.6 1.6 0 0 1 4.4 19.2V4.4A1.6 1.6 0 0 1 6 2.8Z"
          fill="currentColor"
          opacity="0.12"
        />
        <path
          d="M6 2.8h7.2L17.2 7v12.2a1.6 1.6 0 0 1-1.6 1.6H6A1.6 1.6 0 0 1 4.4 19.2V4.4A1.6 1.6 0 0 1 6 2.8Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.35"
          strokeLinejoin="round"
        />
        <path
          d="M13.1 2.9V7h4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.35"
          strokeLinejoin="round"
        />
        <path
          d="M7.6 12.2h6.8M7.6 15h4.8"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  return (
    <svg
      className="deck-file-card-glyph"
      width="22"
      height="22"
      viewBox="0 0 22 22"
      aria-hidden
    >
      <path
        d="M6 2.8h7.2L17.2 7v12.2a1.6 1.6 0 0 1-1.6 1.6H6A1.6 1.6 0 0 1 4.4 19.2V4.4A1.6 1.6 0 0 1 6 2.8Z"
        fill="currentColor"
        opacity="0.12"
      />
      <path
        d="M6 2.8h7.2L17.2 7v12.2a1.6 1.6 0 0 1-1.6 1.6H6A1.6 1.6 0 0 1 4.4 19.2V4.4A1.6 1.6 0 0 1 6 2.8Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinejoin="round"
      />
      <path
        d="M13.1 2.9V7h4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinejoin="round"
      />
      <path
        d="M7.4 11.2h7.2M7.4 14h5.4"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function DeckFileCard({
  kind,
  href,
  previewUrl = null,
  pdfUrl = null,
  fileLabel,
  docTitle = null,
  docxHref = null,
  deckPdfHref = null,
  onPrimary,
  primaryLabel,
  filmstrip = [],
  deck = null,
  runId = null,
  downloadsBlocked = false,
}: Props) {
  const isPptx = kind === "pptx";
  const isReportPdf = kind === "pdf";
  const isDocx = kind === "docx";
  const title =
    fileLabel ||
    (isPptx
      ? "deck_slides.pptx"
      : isReportPdf
        ? "report.pdf"
        : isDocx
          ? "report.docx"
          : "deck.pdf");
  const badge = isPptx ? "PPTX" : isDocx ? "DOCX" : "PDF";
  const isDeckPdf = kind === "deck_pdf";
  const kindHint = isPptx
    ? "Презентация · PowerPoint"
    : isReportPdf
      ? "PDF отчёта"
      : isDocx
        ? "DOCX отчёта"
        : "Презентация · PDF";
  const defaultPrimary = isPptx || isDeckPdf ? "Просмотр" : "Открыть";
  const actionLabel = primaryLabel || defaultPrimary;
  const liveHero =
    (isPptx || isDeckPdf) &&
    Boolean(runId) &&
    prefersLiveChatHero(deck);
  const kindClass = [
    isPptx
      ? "is-pptx"
      : isReportPdf
        ? "is-pdf is-report-pdf"
        : isDocx
          ? "is-docx is-report-docx"
          : "is-pdf is-deck-pdf",
    liveHero ? "has-live-twin" : "",
  ]
    .filter(Boolean)
    .join(" ");
  const emptyHint = isPptx
    ? "Презентация · PPTX"
    : isReportPdf
      ? "PDF отчёта"
      : isDocx
        ? "DOCX отчёта"
        : "Презентация · PDF";
  const strip = filmstrip.filter(Boolean).slice(0, 6);
  const teaserTitle = (docTitle || "").trim() || title;
  const hasDocxTwin = Boolean(docxHref);

  /* One report card: Source → PDF (+ DOCX twin downloads). */
  if (isReportPdf) {
    const eyebrow = hasDocxTwin ? "Отчёт · PDF · DOCX" : "Отчёт · PDF";
    return (
      <article className={`deck-file-card ${kindClass} is-compact`}>
        <button
          type="button"
          className="deck-file-card-compact"
          onClick={onPrimary}
          disabled={!onPrimary}
          aria-label={
            onPrimary ? `${actionLabel}: ${teaserTitle}` : teaserTitle
          }
        >
          <span className="deck-file-card-compact-mark" aria-hidden>
            <FileGlyph kind="pdf" />
            <span className="deck-file-card-compact-badge">PDF</span>
          </span>
          <span className="deck-file-card-compact-copy">
            <span className="deck-file-card-compact-eyebrow">{eyebrow}</span>
            <span className="deck-file-card-compact-title">{teaserTitle}</span>
            <span className="deck-file-card-compact-file" title={title}>
              {title}
            </span>
          </span>
          <span className="deck-file-card-compact-actions">
            <a
              href={href}
              download
              className="deck-file-card-compact-dl"
              onClick={(e) => e.stopPropagation()}
            >
              PDF
            </a>
            {docxHref ? (
              <a
                href={docxHref}
                download
                className="deck-file-card-compact-dl"
                onClick={(e) => e.stopPropagation()}
              >
                DOCX
              </a>
            ) : null}
            {onPrimary ? (
              <span className="deck-file-card-compact-go" aria-hidden>
                {actionLabel}
                <span>→</span>
              </span>
            ) : null}
          </span>
        </button>
      </article>
    );
  }

  /* DOCX-only fallback (no PDF yet) */
  if (isDocx) {
    return (
      <article className={`deck-file-card ${kindClass} is-compact`}>
        <a
          href={href}
          download
          className="deck-file-card-compact"
          aria-label={`Скачать ${teaserTitle}`}
        >
          <span className="deck-file-card-compact-mark" aria-hidden>
            <FileGlyph kind="docx" />
            <span className="deck-file-card-compact-badge">DOCX</span>
          </span>
          <span className="deck-file-card-compact-copy">
            <span className="deck-file-card-compact-eyebrow">Отчёт · DOCX</span>
            <span className="deck-file-card-compact-title">{teaserTitle}</span>
            <span className="deck-file-card-compact-file" title={title}>
              {title}
            </span>
          </span>
          <span className="deck-file-card-compact-actions">
            <span className="deck-file-card-compact-dl">Скачать</span>
          </span>
        </a>
      </article>
    );
  }

  return (
    <article className={`deck-file-card ${kindClass}`}>
      <header className="deck-file-card-head">
        <span className="deck-file-card-mark" aria-hidden>
          <FileGlyph kind={kind} />
          <span className="deck-file-card-badge">{badge}</span>
        </span>
        <span className="deck-file-card-meta">
          <span className="deck-file-card-path" title={title}>
            {title}
          </span>
          <span className="deck-file-card-hint">{kindHint}</span>
        </span>
        <span className="deck-file-card-actions">
          {downloadsBlocked && (isPptx || isDeckPdf) ? (
            <button
              type="button"
              className="deck-file-card-action"
              disabled
              title={DECK_DOWNLOAD_BLOCKED_TITLE}
            >
              {DECK_DOWNLOAD_BLOCKED_LABEL}
            </button>
          ) : isPptx ? (
            <>
              {href && href !== "#" ? (
                <a href={href} download className="deck-file-card-action">
                  {deckPdfHref ? "PPTX" : "Скачать"}
                </a>
              ) : null}
              {deckPdfHref ? (
                <a href={deckPdfHref} download className="deck-file-card-action">
                  PDF
                </a>
              ) : null}
            </>
          ) : href && href !== "#" ? (
            <a href={href} download className="deck-file-card-action">
              Скачать
            </a>
          ) : null}
          {onPrimary ? (
            <button
              type="button"
              className="deck-file-card-action is-strong is-pill"
              onClick={onPrimary}
            >
              {actionLabel}
            </button>
          ) : null}
        </span>
      </header>

      <div
        className={`deck-file-card-preview${onPrimary ? " is-action" : ""}`}
        role={onPrimary ? "button" : undefined}
        tabIndex={onPrimary ? 0 : undefined}
        onClick={onPrimary}
        onKeyDown={
          onPrimary
            ? (e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onPrimary();
                }
              }
            : undefined
        }
        aria-label={
          onPrimary ? `${actionLabel}: ${title}` : `Превью ${title}`
        }
      >
        <span
          className="deck-file-card-mat"
          aria-hidden={!liveHero && !previewUrl && !pdfUrl}
        >
          <span
            className={`deck-file-card-sheet${liveHero ? " is-live-twin" : ""}`}
          >
            {liveHero && deck && runId ? (
              <DeckChatHero runId={runId} deck={deck} />
            ) : previewUrl ? (
              <img src={previewUrl} alt="" />
            ) : pdfUrl ? (
              <PdfThumb
                pdfUrl={pdfUrl}
                className="deck-file-card-preview-img"
                targetWidth={920}
              />
            ) : (
              <span className="deck-file-card-preview-empty">{emptyHint}</span>
            )}
          </span>
        </span>
        {onPrimary ? (
          <span className="deck-file-card-veil" aria-hidden>
            <span className="deck-file-card-veil-label">
              {actionLabel}
              <span className="deck-file-card-veil-arrow">→</span>
            </span>
          </span>
        ) : null}
      </div>

      {strip.length > 1 ? (
        <div className="deck-file-card-filmstrip" role="list" aria-label="Слайды">
          {strip.map((src, i) => (
            <button
              key={`${src}-${i}`}
              type="button"
              className={`deck-file-card-film-thumb${i === 0 ? " is-active" : ""}`}
              onClick={onPrimary}
              aria-label={`Слайд ${i + 1}`}
            >
              <img src={src} alt="" />
              <span>{i + 1}</span>
            </button>
          ))}
        </div>
      ) : null}

    </article>
  );
}
