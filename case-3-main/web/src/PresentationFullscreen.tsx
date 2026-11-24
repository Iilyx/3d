/** Fullscreen Liber deck — PNG or live twin (Julius Present: click-advance, idle chrome). */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { createPortal } from "react-dom";
import { DeckCanvas } from "./DeckCanvas";
import type { DeckIR } from "./deckTypes";
import { fullscreenCount } from "./domain/slideStrip";
import { DiagramFullscreen, type DiagramInfo } from "./DiagramFullscreen";
import { useFocusTrap } from "./useFocusTrap";

type Props = {
  slides: string[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
  deck?: DeckIR | null;
  runId?: string;
  diagramMermaid?: string | null;
  diagramPalette?: string;
};

const IDLE_MS = 2200;

export function PresentationFullscreen({
  slides,
  index,
  onIndex,
  onClose,
  deck = null,
  runId = "",
  diagramMermaid = null,
  diagramPalette,
}: Props) {
  const reduce = useReducedMotion();
  const mode = fullscreenCount({
    liveSlides: deck?.slides?.length || 0,
    pngs: slides.length,
  });
  const n = mode.n;
  const safe = n ? Math.min(Math.max(index, 0), n - 1) : 0;
  const src = !mode.useDeck && n ? slides[safe] : null;
  const [dir, setDir] = useState(0);
  const [chromeOn, setChromeOn] = useState(true);
  const [zoomDiagram, setZoomDiagram] = useState<DiagramInfo | null>(null);
  const idleTimer = useRef<number | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, { active: true });

  const bumpChrome = useCallback(() => {
    setChromeOn(true);
    if (idleTimer.current) window.clearTimeout(idleTimer.current);
    idleTimer.current = window.setTimeout(() => setChromeOn(false), IDLE_MS);
  }, []);

  const go = useCallback(
    (delta: number) => {
      if (!n) return;
      setDir(delta >= 0 ? 1 : -1);
      onIndex((safe + delta + n) % n);
      bumpChrome();
    },
    [bumpChrome, n, onIndex, safe],
  );

  useEffect(() => {
    bumpChrome();
    return () => {
      if (idleTimer.current) window.clearTimeout(idleTimer.current);
    };
  }, [bumpChrome]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      bumpChrome();
      if (document.querySelector(".diagram-fullscreen")) return;
      if (e.key === "Escape") onClose();
      if (!n) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        go(-1);
      }
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        go(1);
      }
    };
    const onMove = () => bumpChrome();
    const onTouch = () => bumpChrome();
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("touchstart", onTouch, { passive: true });
    window.addEventListener("touchmove", onTouch, { passive: true });
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("touchstart", onTouch);
      window.removeEventListener("touchmove", onTouch);
    };
  }, [bumpChrome, go, n, onClose]);

  const variants = reduce
    ? { enter: { opacity: 1 }, center: { opacity: 1 }, exit: { opacity: 1 } }
    : {
        enter: (d: number) => ({ opacity: 0, x: d >= 0 ? 40 : -40 }),
        center: { opacity: 1, x: 0 },
        exit: (d: number) => ({ opacity: 0, x: d >= 0 ? -36 : 36 }),
      };

  const onStageClick = (e: ReactMouseEvent<HTMLDivElement>) => {
    if (!n) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    // Left third = back; rest = forward (Julius-style click advance).
    if (x < rect.width * 0.28) go(-1);
    else go(1);
  };

  return createPortal(
    <motion.div
      ref={dialogRef}
      className={`presentation-fullscreen${chromeOn ? " is-chrome" : " is-idle"}`}
      role="dialog"
      aria-modal="true"
      aria-label="Презентация"
      onClick={onClose}
      initial={reduce ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div
        className="presentation-fullscreen-sheet"
        onClick={(e) => e.stopPropagation()}
      >
        <header
          className="presentation-fullscreen-head"
          aria-hidden={!chromeOn}
        >
          <span className="presentation-fullscreen-count">
            {n ? `${safe + 1} / ${n}` : "—"}
          </span>
          <button
            type="button"
            className="presentation-fullscreen-close"
            onClick={onClose}
          >
            Esc
          </button>
        </header>
        <div
          className="presentation-fullscreen-stage"
          onClick={onStageClick}
          role="presentation"
          title="Клик: вперёд · левая треть: назад"
        >
          <AnimatePresence mode="wait" custom={dir}>
            <motion.div
              key={mode.useDeck ? deck!.slides[safe]?.id : src || safe}
              className="presentation-fullscreen-frame"
              custom={dir}
              variants={variants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            >
              {mode.useDeck && deck && runId ? (
                <DeckCanvas
                  runId={runId}
                  deck={deck}
                  index={safe}
                  editing={false}
                  onDeckChange={() => undefined}
                  onPatch={async () => undefined}
                  diagramMermaid={diagramMermaid}
                  diagramPalette={diagramPalette}
                  onDiagramZoom={(dia) => setZoomDiagram(dia)}
                />
              ) : src ? (
                <img src={src} alt="" className="presentation-fullscreen-img" />
              ) : null}
            </motion.div>
          </AnimatePresence>
        </div>
        {zoomDiagram ? (
          <DiagramFullscreen
            diagram={zoomDiagram}
            onClose={() => setZoomDiagram(null)}
          />
        ) : null}
        <div
          className="presentation-fullscreen-nav"
          aria-hidden={!chromeOn}
        >
          <button
            type="button"
            onClick={() => go(-1)}
            aria-label="Назад"
          >
            ←
          </button>
          <button
            type="button"
            onClick={() => go(1)}
            aria-label="Вперёд"
          >
            →
          </button>
        </div>
        <p className="presentation-fullscreen-hint" aria-hidden={!chromeOn}>
          ← → / Space / клик — листать · Esc — выход
        </p>
      </div>
    </motion.div>,
    document.body,
  );
}
