/** Zoom / pan wrapper around Mermaid SVG for Liber Schema tab. */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";
import { MermaidView } from "./MermaidView";

const MIN = 0.35;
/** Allow ~3× for small schemas in fullscreen fit. */
const MAX = 3.5;
const STEP = 0.15;
/** Keep a margin so the graph never touches the frame. */
const FIT_PAD = 0.84;

type Props = {
  source: string;
  onSvgReady?: (svg: SVGSVGElement | null) => void;
  className?: string;
  /** Scale up to fill the viewport (capped), without overflowing. */
  fitViewport?: boolean;
  highlightNodeIds?: Set<string> | null;
  onNodeDblClick?: (nodeId: string) => void;
};

function svgNaturalSize(svg: SVGSVGElement): { w: number; h: number } {
  const vb = svg.viewBox?.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) {
    return { w: vb.width, h: vb.height };
  }
  const rawVb = svg.getAttribute("viewBox");
  if (rawVb) {
    const parts = rawVb.trim().split(/[\s,]+/).map(Number);
    if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
      return { w: parts[2], h: parts[3] };
    }
  }
  try {
    const box = svg.getBBox();
    if (box.width > 0 && box.height > 0) return { w: box.width, h: box.height };
  } catch {
    /* not in DOM yet */
  }
  const wAttr = svg.getAttribute("width") || "";
  const hAttr = svg.getAttribute("height") || "";
  const wNum = parseFloat(wAttr);
  const hNum = parseFloat(hAttr);
  if (wNum > 0 && hNum > 0 && !wAttr.includes("%") && !hAttr.includes("%")) {
    return { w: wNum, h: hNum };
  }
  return { w: svg.clientWidth || 0, h: svg.clientHeight || 0 };
}

/** Mermaid often emits width="100%" — that collapses inside max-content flex. */
function pinSvgPixelSize(svg: SVGSVGElement): { w: number; h: number } {
  const nat = svgNaturalSize(svg);
  if (nat.w > 0 && nat.h > 0) {
    svg.setAttribute("width", String(nat.w));
    svg.setAttribute("height", String(nat.h));
    svg.style.width = `${nat.w}px`;
    svg.style.height = `${nat.h}px`;
    svg.style.maxWidth = "none";
  }
  return nat;
}

function computeFitScale(
  svg: SVGSVGElement,
  viewport: HTMLElement,
): number {
  const vw = viewport.clientWidth;
  const vh = viewport.clientHeight;
  if (vw < 32 || vh < 32) return 1;

  const { w, h } = pinSvgPixelSize(svg);
  if (!w || !h) return 1;

  const sx = (vw * FIT_PAD) / w;
  const sy = (vh * FIT_PAD) / h;
  const raw = Math.min(sx, sy);
  if (!Number.isFinite(raw) || raw <= 0) return 1;
  return Math.min(MAX, Math.max(MIN, Math.round(raw * 100) / 100));
}

export function DiagramZoomView({
  source,
  onSvgReady,
  className,
  fitViewport = false,
  highlightNodeIds = null,
  onNodeDblClick,
}: Props) {
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{
    x: number;
    y: number;
    panX: number;
    panY: number;
  } | null>(null);
  const onReadyRef = useRef(onSvgReady);
  onReadyRef.current = onSvgReady;

  const applyFit = useCallback(() => {
    const svg = svgRef.current;
    const vp = viewportRef.current;
    if (!svg || !vp) {
      setScale(1);
      setPan({ x: 0, y: 0 });
      return;
    }
    const next = computeFitScale(svg, vp);
    setScale(next);
    setPan({ x: 0, y: 0 });
    // Flex-centered overflow hid the top — pin scroll to the start of the graph.
    requestAnimationFrame(() => {
      vp.scrollTop = 0;
      vp.scrollLeft = Math.max(0, (vp.scrollWidth - vp.clientWidth) / 2);
    });
  }, []);

  useEffect(() => {
    setScale(1);
    setPan({ x: 0, y: 0 });
  }, [source]);

  const zoomBy = useCallback((delta: number) => {
    setScale((s) =>
      Math.min(MAX, Math.max(MIN, Math.round((s + delta) * 100) / 100)),
    );
  }, []);

  const onWheel = useCallback(
    (e: ReactWheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        zoomBy(e.deltaY > 0 ? -STEP : STEP);
      }
    },
    [zoomBy],
  );

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      // Pan whenever zoomed away from 100% (incl. fit < 1 for large graphs).
      if (e.button !== 0 || Math.abs(scale - 1) < 0.02) return;
      e.currentTarget.setPointerCapture(e.pointerId);
      dragRef.current = {
        x: e.clientX,
        y: e.clientY,
        panX: pan.x,
        panY: pan.y,
      };
    },
    [pan.x, pan.y, scale],
  );

  const onPointerMove = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    const d = dragRef.current;
    if (!d) return;
    setPan({
      x: d.panX + (e.clientX - d.x),
      y: d.panY + (e.clientY - d.y),
    });
  }, []);

  const onPointerUp = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    if (dragRef.current) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        /* already released */
      }
    }
    dragRef.current = null;
  }, []);

  const handleSvgReady = useCallback(
    (el: SVGSVGElement | null) => {
      svgRef.current = el;
      if (el) {
        pinSvgPixelSize(el);
      }
      onReadyRef.current?.(el);
      if (el && fitViewport) {
        // Wait for flex layout so viewport has real clientHeight.
        requestAnimationFrame(() => {
          requestAnimationFrame(() => applyFit());
        });
      }
    },
    [applyFit, fitViewport],
  );

  useEffect(() => {
    if (!fitViewport) return;
    const vp = viewportRef.current;
    if (!vp || typeof ResizeObserver === "undefined") return;
    let t: number | null = null;
    const ro = new ResizeObserver(() => {
      if (t != null) window.clearTimeout(t);
      t = window.setTimeout(() => {
        if (svgRef.current && vp.clientHeight >= 32) applyFit();
      }, 80);
    });
    ro.observe(vp);
    return () => {
      ro.disconnect();
      if (t != null) window.clearTimeout(t);
    };
  }, [applyFit, fitViewport]);

  return (
    <div className={`diagram-zoom${className ? ` ${className}` : ""}`}>
      <div className="diagram-zoom-bar" role="toolbar" aria-label="Масштаб схемы">
        <button
          type="button"
          className="diagram-zoom-btn"
          aria-label="Уменьшить"
          onClick={() => zoomBy(-STEP)}
          disabled={scale <= MIN}
        >
          −
        </button>
        <button
          type="button"
          className="diagram-zoom-btn"
          aria-label="Вписать"
          onClick={applyFit}
        >
          {Math.round(scale * 100)}%
        </button>
        <button
          type="button"
          className="diagram-zoom-btn"
          aria-label="Увеличить"
          onClick={() => zoomBy(STEP)}
          disabled={scale >= MAX}
        >
          +
        </button>
        <span
          className="diagram-zoom-hint"
          title="Ctrl+колёсико · перетаскивание при zoom"
        >
          ⌘/Ctrl + scroll
        </span>
      </div>
      <div
        ref={viewportRef}
        className={`diagram-zoom-viewport${Math.abs(scale - 1) >= 0.02 ? " is-pannable" : ""}`}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div
          className="diagram-zoom-stage"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
          }}
        >
          <MermaidView
            source={source}
            onSvgReady={handleSvgReady}
            highlightNodeIds={highlightNodeIds}
            onNodeDblClick={onNodeDblClick}
          />
        </div>
      </div>
    </div>
  );
}
