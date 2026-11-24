/** Empty-state presentation starters — Liber twin preview + gallery thumbs.
 *  2026-10-24: no tone chips / light-dark filter on cards.
 */

import type { CSSProperties } from "react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  FALLBACK_DECK_PACKS,
  applyPackToStyle,
  type DeckStyle,
  type DeckThemePackInfo,
} from "./deckStyle";
import { DECK_TEMPLATE_CARDS, type DeckTemplateCard } from "./deckTemplates";
import {
  hasPreviewPngs,
  previewPngUrls,
  previewSlidesFor,
  type PreviewSlide,
} from "./deckTemplatePreviews";
import { useFocusTrap } from "./useFocusTrap";

type Props = {
  deckStyle: DeckStyle;
  deckPacks?: DeckThemePackInfo[];
  busy?: boolean;
  /** Apply pack + structure; parent fills composer with starterPrompt. */
  onApply: (
    next: DeckStyle,
    meta: { title: string; arc: string; starterPrompt: string },
  ) => void;
};

function withStructure(
  style: DeckStyle,
  structureId: string,
  templateId: string,
): DeckStyle {
  return { ...style, structureId, templateId };
}

function cardTone(packId: string, structureId: string): "light" | "dark" {
  if (
    packId === "botanical" ||
    packId === "signal" ||
    packId === "ink" ||
    packId === "voltage" ||
    structureId === "performance" ||
    structureId === "investor" ||
    structureId === "survey" ||
    structureId === "launch"
  ) {
    return "dark";
  }
  return "light";
}

function slideClass(slide: PreviewSlide, structureId: string): string {
  const base = ["deck-slide-mock", `is-${slide.kind}`];
  if (slide.dark) base.push("is-dark");
  if (structureId === "board_update" && slide.kind === "title") base.push("is-board");
  if (structureId === "performance") base.push("is-signal-tone");
  if (structureId === "qbr" && slide.kind === "title") base.push("is-qbr");
  if (structureId === "survey") {
    base.push("is-survey-tone");
    if (slide.kind === "title") base.push("is-survey");
  }
  if (structureId === "launch") {
    base.push("is-launch-tone");
    if (slide.kind === "title" || slide.kind === "closing") base.push("is-launch");
  }
  if (structureId === "campaign" && slide.kind === "title") base.push("is-campaign");
  if (structureId === "workshop" && (slide.kind === "agenda" || slide.kind === "cards")) {
    base.push("is-workshop");
  }
  return base.join(" ");
}

/** Rich mock frame — used for gallery thumb (slide 0) and modal fallback. */
export function PreviewSlideFrame({
  slide,
  structureId,
  compact = false,
}: {
  slide: PreviewSlide;
  structureId: string;
  compact?: boolean;
}) {
  const dark = Boolean(slide.dark);
  return (
    <div
      className={`${slideClass(slide, structureId)}${compact ? " is-compact" : ""}`}
      data-kind={slide.kind}
    >
      {slide.kind === "title" || slide.kind === "closing" || slide.kind === "quote" ? (
        <>
          {structureId === "qbr" && slide.kind === "title" ? (
            <span className="deck-slide-orb" aria-hidden />
          ) : null}
          {structureId === "survey" && slide.kind === "title" ? (
            <span className="deck-slide-bolt" aria-hidden />
          ) : null}
          {slide.kind === "title" && structureId === "performance" ? (
            <span className="deck-slide-block">SIGNAL</span>
          ) : slide.kicker ? (
            <span
              className={`deck-slide-kicker${dark ? " is-glow" : ""}${
                structureId === "launch" ? " is-gold" : ""
              }`}
            >
              {slide.kicker}
            </span>
          ) : null}
          <span
            className={`deck-slide-headline${dark ? " is-light" : ""}${
              slide.kind === "quote" || structureId === "qbr" || structureId === "workshop"
                ? " is-serif"
                : ""
            }${structureId === "launch" && slide.kind === "title" ? " is-center" : ""}`}
          >
            {slide.title}
          </span>
          {slide.subtitle ? (
            <span className={`deck-slide-meta${dark ? " is-light-meta" : ""}`}>
              {slide.subtitle}
            </span>
          ) : null}
          {slide.bars?.length ? (
            <span className="deck-slide-bars" aria-hidden>
              {slide.bars.map((h, i) => (
                <i key={i} style={{ height: `${h}%` }} />
              ))}
            </span>
          ) : null}
        </>
      ) : null}

      {slide.kind === "scorecard" ? (
        <>
          {slide.kicker ? <span className="deck-slide-kicker">{slide.kicker}</span> : null}
          <span className={`deck-slide-headline${dark ? " is-light" : ""}`}>{slide.title}</span>
          <div className="deck-slide-scoregrid" aria-hidden>
            {(slide.cells || []).map((c) => (
              <div key={c.label} className="deck-slide-scorecell">
                <span className="deck-slide-scorelabel">{c.label}</span>
                <span className="deck-slide-scorevalue">{c.value}</span>
                {c.delta ? <span className="deck-slide-scoredelta">{c.delta}</span> : null}
              </div>
            ))}
          </div>
        </>
      ) : null}

      {slide.kind === "chart" || slide.kind === "signal" ? (
        <>
          {slide.kind === "signal" && !slide.kicker ? (
            <span className="deck-slide-block">SIGNAL</span>
          ) : slide.kicker ? (
            <span className={`deck-slide-kicker${dark ? " is-glow" : ""}`}>{slide.kicker}</span>
          ) : null}
          <span className={`deck-slide-headline${dark ? " is-light" : ""}`}>{slide.title}</span>
          <div className="deck-slide-chartpad" aria-hidden>
            <span className="deck-slide-bars is-tall">
              {(slide.bars || [40, 55, 48, 70, 62, 85]).map((h, i) => (
                <i key={i} style={{ height: `${h}%` }} />
              ))}
            </span>
            <span className="deck-slide-chartline" />
          </div>
        </>
      ) : null}

      {slide.kind === "table" ? (
        <>
          {slide.kicker ? <span className="deck-slide-kicker">{slide.kicker}</span> : null}
          <span className={`deck-slide-headline${dark ? " is-light" : ""}`}>{slide.title}</span>
          <div className="deck-slide-table" aria-hidden>
            {(slide.rows || []).map((row, ri) => (
              <div
                key={ri}
                className={`deck-slide-tr${ri === 0 ? " is-head" : ""}`}
              >
                {row.map((cell, ci) => (
                  <span key={ci}>{cell}</span>
                ))}
              </div>
            ))}
          </div>
        </>
      ) : null}

      {slide.kind === "cards" || slide.kind === "agenda" ? (
        <>
          {slide.kicker ? (
            <span className={`deck-slide-kicker${structureId === "workshop" ? " is-ink" : ""}`}>
              {slide.kicker}
            </span>
          ) : null}
          <span
            className={`deck-slide-headline${dark ? " is-light" : ""}${
              slide.kind === "agenda" || structureId === "workshop" ? " is-serif" : ""
            }`}
          >
            {slide.title}
          </span>
          {slide.subtitle ? (
            <span className="deck-slide-meta">{slide.subtitle}</span>
          ) : null}
          <div className="deck-slide-cardrow" aria-hidden>
            {(slide.cards || []).map((c) => (
              <div key={c} className="deck-slide-cardchip">
                {c}
              </div>
            ))}
          </div>
        </>
      ) : null}

      {slide.kind === "split" ? (
        <>
          <span className="deck-slide-split-top">
            {slide.kicker ? <span className="deck-slide-kicker">{slide.kicker}</span> : null}
            <span className="deck-slide-headline">{slide.title}</span>
            {slide.subtitle ? <span className="deck-slide-meta">{slide.subtitle}</span> : null}
          </span>
          <span className="deck-slide-split-bot">
            <i>Ask</i>
            <i>Cash</i>
            <i>Risk</i>
          </span>
        </>
      ) : null}
    </div>
  );
}

type PreviewState = {
  card: DeckTemplateCard;
  pack: DeckThemePackInfo;
  swatches: string[];
  tone: "light" | "dark";
};

export function DeckTemplateGallery({
  deckStyle,
  deckPacks = FALLBACK_DECK_PACKS,
  busy = false,
  onApply,
}: Props) {
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const reduce = useReducedMotion();
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const filmRef = useRef<HTMLDivElement>(null);
  const [activeSlide, setActiveSlide] = useState(0);
  useFocusTrap(panelRef, { active: Boolean(preview) });

  const cards = DECK_TEMPLATE_CARDS;

  const previewFrames = useMemo(
    () => (preview ? previewSlidesFor(preview.card.structureId) : []),
    [preview],
  );
  const previewPngs = useMemo(
    () => {
      const key = preview?.card.previewId || preview?.card.structureId || "";
      return preview && hasPreviewPngs(key) ? previewPngUrls(key) : [];
    },
    [preview],
  );
  const useRaster = previewPngs.length >= 6;
  const slideCount = useRaster ? previewPngs.length : previewFrames.length;
  const activeIndex = Math.min(activeSlide, Math.max(0, slideCount - 1));

  useEffect(() => {
    if (!preview) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPreview(null);
        return;
      }
      if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        e.preventDefault();
        setActiveSlide((i) => Math.min(i + 1, Math.max(0, slideCount - 1)));
      }
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        setActiveSlide((i) => Math.max(i - 1, 0));
      }
      if (e.key === "Enter" && !busy) {
        e.preventDefault();
        applyPreviewRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    setActiveSlide(0);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- apply via ref
  }, [preview, slideCount, busy]);

  useEffect(() => {
    const el = filmRef.current?.querySelector<HTMLElement>(
      `[data-film-slide="${activeIndex}"]`,
    );
    el?.scrollIntoView({
      behavior: reduce ? "auto" : "smooth",
      inline: "center",
      block: "nearest",
    });
  }, [activeIndex, reduce, preview]);

  function openPreview(card: DeckTemplateCard) {
    const pack =
      deckPacks.find((p) => p.id === card.packId) ||
      FALLBACK_DECK_PACKS.find((p) => p.id === card.packId);
    if (!pack) return;
    const swatches = pack.swatches || ["#2E4208", "#4F6B14", "#FFFCF7", "#14161a"];
    setPreview({
      card,
      pack,
      swatches,
      tone: cardTone(card.packId, card.structureId),
    });
  }

  function applyPreview() {
    if (!preview) return;
    onApply(
        withStructure(
        applyPackToStyle(preview.pack, deckStyle),
        preview.card.structureId,
        preview.card.id,
      ),
      {
        title: preview.card.title,
        arc: preview.card.arc,
        starterPrompt: preview.card.starterPrompt,
      },
    );
    setPreview(null);
  }

  const applyPreviewRef = useRef(applyPreview);
  applyPreviewRef.current = applyPreview;

  const packVars = (swatches: string[]): CSSProperties =>
    ({
      ["--pack-primary" as string]: swatches[0],
      ["--pack-accent" as string]: swatches[1],
      ["--pack-bg" as string]: swatches[2],
      ["--pack-ink" as string]: swatches[3] || "#14161a",
    }) as CSSProperties;

  function goSlide(next: number) {
    if (slideCount <= 0) return;
    setActiveSlide(Math.max(0, Math.min(next, slideCount - 1)));
  }

  return (
    <div className="deck-template-gallery" aria-label="Шаблоны презентаций">
      <div className="deck-template-gallery-head">
        <div className="deck-template-gallery-title-row">
          <div className="deck-template-gallery-lead">
            <h3>Шаблоны</h3>
          </div>
        </div>
      </div>
      <div className="deck-template-grid" role="list">
        {cards.map((card, i) => {
          const pack =
            deckPacks.find((p) => p.id === card.packId) ||
            FALLBACK_DECK_PACKS.find((p) => p.id === card.packId);
          const swatches = pack?.swatches || ["#2E4208", "#4F6B14", "#FFFCF7", "#14161a"];
          const previewKey = card.previewId || card.structureId;
          const on = deckStyle.templateId
            ? deckStyle.templateId === card.id
            : deckStyle.themePack === card.packId &&
              deckStyle.structureId === card.structureId;
          const thumb = previewSlidesFor(card.structureId)[0];
          const pngs = hasPreviewPngs(previewKey)
            ? previewPngUrls(previewKey)
            : [];
          const thumbPng = pngs[0] || null;
          const strip = pngs.slice(0, 3);
          return (
            <motion.button
              key={card.id}
              type="button"
              role="listitem"
              className={`deck-template-card${on ? " is-on" : ""}`}
              disabled={busy || !pack}
              aria-label={`Превью шаблона ${card.title}`}
              aria-pressed={on}
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: reduce ? 0 : 0.28,
                delay: reduce ? 0 : Math.min(i * 0.04, 0.28),
                ease: [0.22, 1, 0.36, 1],
              }}
              onClick={() => openPreview(card)}
            >
              <div
                className="deck-template-thumb"
                style={packVars(swatches)}
                aria-hidden
              >
                {thumbPng ? (
                  <span className="deck-template-thumb-mat">
                    <img
                      className="deck-template-thumb-img"
                      src={thumbPng}
                      alt=""
                      loading="lazy"
                      decoding="async"
                    />
                  </span>
                ) : thumb ? (
                  <PreviewSlideFrame
                    slide={thumb}
                    structureId={card.structureId}
                    compact
                  />
                ) : null}
                <span className="deck-template-thumb-veil">
                  <span className="deck-template-thumb-cta">Смотреть слайды</span>
                </span>
                {on ? (
                  <span className="deck-template-selected-chip">Выбран</span>
                ) : null}
              </div>
              {strip.length >= 2 ? (
                <span className="deck-template-strip" aria-hidden>
                  {strip.map((src) => (
                    <img key={src} src={src} alt="" loading="lazy" decoding="async" />
                  ))}
                  {pngs.length > 3 ? (
                    <span className="deck-template-strip-more">+{pngs.length - 3}</span>
                  ) : null}
                </span>
              ) : null}
              <span className="deck-template-caption">
                <span className="deck-template-name">{card.title}</span>
              </span>
            </motion.button>
          );
        })}
      </div>

      {preview ? (
        <div
          className="deck-template-preview"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setPreview(null);
          }}
        >
          <div className="deck-template-preview-panel" ref={panelRef}>
            <header className="deck-template-preview-head">
              <div className="deck-template-preview-head-copy">
                <p className="deck-template-preview-eyebrow">
                  {preview.pack.label}
                </p>
                <h2 id={titleId}>{preview.card.title}</h2>
                <div className="deck-template-preview-swatches" aria-hidden>
                  {preview.swatches.slice(0, 4).map((c) => (
                    <i key={c} style={{ background: c }} />
                  ))}
                </div>
              </div>
              <button
                type="button"
                className="deck-template-preview-x"
                aria-label="Закрыть"
                onClick={() => setPreview(null)}
              >
                ×
              </button>
            </header>

            <div className="deck-template-preview-stage-wrap" style={packVars(preview.swatches)}>
              <div className="deck-template-preview-nav">
                <button
                  type="button"
                  className="deck-template-preview-nav-btn"
                  aria-label="Предыдущий слайд"
                  disabled={activeIndex <= 0}
                  onClick={() => goSlide(activeIndex - 1)}
                >
                  ‹
                </button>
                <span className="deck-template-preview-count" aria-live="polite">
                  {String(activeIndex + 1).padStart(2, "0")}
                  <span aria-hidden> / </span>
                  {String(slideCount).padStart(2, "0")}
                </span>
                <button
                  type="button"
                  className="deck-template-preview-nav-btn"
                  aria-label="Следующий слайд"
                  disabled={activeIndex >= slideCount - 1}
                  onClick={() => goSlide(activeIndex + 1)}
                >
                  ›
                </button>
              </div>

              <div
                className={`deck-template-preview-stage${useRaster ? " is-raster" : ""}`}
                data-tone={
                  useRaster
                    ? "raster"
                    : previewFrames[activeIndex]?.dark
                      ? "dark"
                      : "light"
                }
              >
                {useRaster ? (
                  <img
                    className="deck-template-preview-stage-img"
                    src={previewPngs[activeIndex]}
                    alt={`Слайд ${activeIndex + 1}`}
                    key={previewPngs[activeIndex]}
                  />
                ) : previewFrames[activeIndex] ? (
                  <PreviewSlideFrame
                    slide={previewFrames[activeIndex]}
                    structureId={preview.card.structureId}
                  />
                ) : null}
              </div>

              <div
                className="deck-template-preview-film"
                ref={filmRef}
                role="tablist"
                aria-label="Слайды шаблона"
              >
                {(useRaster ? previewPngs : previewFrames).map((item, i) => (
                  <button
                    key={useRaster ? `png-${i}` : `${(item as PreviewSlide).kind}-${i}`}
                    type="button"
                    role="tab"
                    data-film-slide={i}
                    aria-selected={activeIndex === i}
                    className={`deck-template-preview-film-item${
                      activeIndex === i ? " is-on" : ""
                    }`}
                    aria-label={`Слайд ${i + 1}`}
                    onClick={() => goSlide(i)}
                  >
                    {useRaster ? (
                      <img src={item as string} alt="" loading="lazy" decoding="async" />
                    ) : (
                      <span className="deck-template-preview-film-mock" style={packVars(preview.swatches)}>
                        <PreviewSlideFrame
                          slide={item as PreviewSlide}
                          structureId={preview.card.structureId}
                          compact
                        />
                      </span>
                    )}
                    <span className="deck-template-preview-film-num" aria-hidden>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </button>
                ))}
              </div>
              <p className="deck-template-preview-keys" aria-hidden>
                ← → листать · Enter взять · Esc закрыть
              </p>
            </div>

            <footer className="deck-template-preview-foot">
              <button
                type="button"
                className="deck-template-preview-ghost"
                onClick={() => setPreview(null)}
              >
                Отмена
              </button>
              <button
                type="button"
                className="deck-template-preview-use"
                disabled={busy}
                onClick={applyPreview}
              >
                Взять шаблон
              </button>
            </footer>
          </div>
        </div>
      ) : null}
    </div>
  );
}
