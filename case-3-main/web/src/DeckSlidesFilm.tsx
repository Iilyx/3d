/** Vertical deck-PDF film — all slide PNGs stacked, jump anchors 1…N. */

import { useEffect, useId, useRef, useState } from "react";

type Props = {
  slides: string[];
  /** Absolute or proxied URL for deck PDF download. */
  downloadHref?: string | null;
  /** Unsaved deck edits: the file on disk is behind the screen. */
  downloadBlocked?: boolean;
  onBlockedClick?: () => void;
  title?: string;
};

export function DeckSlidesFilm({
  slides,
  downloadHref = null,
  downloadBlocked = false,
  onBlockedClick,
  title = "Презентация · PDF",
}: Props) {
  const labelId = useId();
  const urls = slides.filter(Boolean);
  const [active, setActive] = useState(0);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const frameRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    setActive(0);
    frameRefs.current = [];
  }, [urls.join("|")]);

  useEffect(() => {
    const root = scrollerRef.current;
    if (!root || urls.length < 2) return;
    const obs = new IntersectionObserver(
      (entries) => {
        let best: { i: number; ratio: number } | null = null;
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          const i = Number((e.target as HTMLElement).dataset.slideIndex);
          if (!Number.isFinite(i)) continue;
          if (!best || e.intersectionRatio > best.ratio) {
            best = { i, ratio: e.intersectionRatio };
          }
        }
        if (best) setActive(best.i);
      },
      { root, threshold: [0.35, 0.55, 0.75] },
    );
    for (const el of frameRefs.current) {
      if (el) obs.observe(el);
    }
    return () => obs.disconnect();
  }, [urls.length]);

  const jump = (i: number) => {
    const el = frameRefs.current[i];
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    setActive(i);
  };

  if (!urls.length) {
    return (
      <div className="deck-slides-film is-empty" aria-labelledby={labelId}>
        <header className="deck-slides-film-head">
          <h2 id={labelId} className="deck-slides-film-title">
            {title}
          </h2>
          <p className="deck-slides-film-sub">Превью ещё не готово</p>
        </header>
      </div>
    );
  }

  return (
    <div className="deck-slides-film" aria-labelledby={labelId}>
      <header className="deck-slides-film-head">
        <div className="deck-slides-film-titles">
          <p className="deck-slides-film-eyebrow">Презентация · PDF</p>
          <h2 id={labelId} className="deck-slides-film-title">
            {title}
          </h2>
        </div>
        <div className="deck-slides-film-actions">
          <span className="deck-slides-film-count" aria-live="polite">
            {active + 1}
            <span aria-hidden> / </span>
            {urls.length}
          </span>
          {downloadBlocked ? (
            <button
              type="button"
              className="deck-slides-film-dl"
              title="Сначала сохраните или отмените изменения"
              onClick={onBlockedClick}
            >
              Сначала Готово
            </button>
          ) : downloadHref ? (
            <a
              href={downloadHref}
              download
              className="deck-slides-film-dl"
            >
              Скачать
            </a>
          ) : null}
        </div>
      </header>

      <div className="deck-slides-film-body">
        <div
          ref={scrollerRef}
          className="deck-slides-film-scroller"
          tabIndex={0}
        >
          {urls.map((src, i) => (
            <figure
              key={`${src}-${i}`}
              data-slide-index={i}
              ref={(el) => {
                frameRefs.current[i] = el;
              }}
              className={`deck-slides-film-frame${i === active ? " is-active" : ""}`}
              id={`deck-slide-frame-${i}`}
            >
              <img
                src={src}
                alt={`Слайд ${i + 1} из ${urls.length}`}
                loading={i < 2 ? "eager" : "lazy"}
              />
              <figcaption className="deck-slides-film-cap">
                {String(i + 1).padStart(2, "0")}
              </figcaption>
            </figure>
          ))}
        </div>

        {urls.length > 1 ? (
          <nav className="deck-slides-film-rail" aria-label="Слайды">
            {urls.map((_, i) => (
              <button
                key={i}
                type="button"
                className={`deck-slides-film-anchor${i === active ? " is-on" : ""}`}
                aria-current={i === active ? "true" : undefined}
                aria-label={`Слайд ${i + 1}`}
                onClick={() => jump(i)}
              >
                {i + 1}
              </button>
            ))}
          </nav>
        ) : null}
      </div>
    </div>
  );
}
