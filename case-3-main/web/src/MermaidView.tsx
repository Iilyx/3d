/** Render Mermaid source → SVG (Liber soft-premium theme). */

import { useEffect, useId, useRef, useState } from "react";
import type { Mermaid } from "mermaid";
import {
  applyMermaidRoleHighlight,
  mermaidNodeIdFromElement,
} from "./mermaidSvgInteract";
import { repairMermaidSource } from "./repairMermaidSource";
import { softenMermaidSvg } from "./softenMermaidSvg";

type Props = {
  source: string;
  className?: string;
  onSvgReady?: (svg: SVGSVGElement | null) => void;
  onError?: (err: string | null) => void;
  /** Highlight these Mermaid node ids; others dim. null = clear. */
  highlightNodeIds?: Set<string> | null;
  /** Double-click a flowchart node → id */
  onNodeDblClick?: (nodeId: string) => void;
  /** Hover over a flowchart node → id, or null when pointer leaves */
  onNodeHover?: (nodeId: string | null) => void;
};

let mermaidReady = false;
let mermaidMod: Mermaid | null = null;
let renderQueue: Promise<unknown> = Promise.resolve();

function renderMermaidSync(
  id: string,
  text: string,
): Promise<{ svg: string; bindFunctions?: (el: Element) => void }> {
  const run = async () => {
    const mermaid = await loadMermaid();
    return await mermaid.render(id, text);
  };
  const task = renderQueue.then(run, run);
  renderQueue = task.then(
    () => {},
    () => {},
  );
  return task;
}

// Safeguard against Mermaid's internal btoa calls on Cyrillic / Unicode strings
if (typeof window !== "undefined" && typeof window.btoa === "function") {
  const origBtoa = window.btoa.bind(window);
  window.btoa = (str: string) => {
    try {
      return origBtoa(str);
    } catch {
      return origBtoa(
        encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (_, p1) =>
          String.fromCharCode(parseInt(p1, 16)),
        ),
      );
    }
  };
}

async function loadMermaid(): Promise<Mermaid> {
  if (typeof document !== "undefined" && document.fonts?.ready) {
    try {
      await document.fonts.ready;
    } catch {
      /* ignore font loading timeouts */
    }
  }
  if (mermaidMod) return mermaidMod;
  const mod = await import("mermaid");
  const mermaid = mod.default;
  if (!mermaidReady) {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "loose",
      theme: "base",
      // Match Liber visual editor: soft curves, not sharp orthogonal edges.
      flowchart: {
        curve: "basis",
        padding: 20,
        nodeSpacing: 52,
        rankSpacing: 64,
        htmlLabels: true,
        useMaxWidth: true,
      },
      themeVariables: {
        primaryColor: "#dce8df",
        primaryTextColor: "#1a2e22",
        primaryBorderColor: "#6b8f76",
        secondaryColor: "#f4f7f4",
        tertiaryColor: "#eef3ef",
        lineColor: "#5a7a64",
        fontFamily: "Georgia, 'Times New Roman', serif",
        fontSize: "15px",
        nodeBorder: "#6b8f76",
        mainBkg: "#eef3ef",
        clusterBkg: "#f4f7f4",
        edgeLabelBackground: "#f7faf7",
      },
    });
    mermaidReady = true;
  }
  mermaidMod = mermaid;
  return mermaid;
}

export function MermaidView({
  source,
  className,
  onSvgReady,
  onError,
  highlightNodeIds = null,
  onNodeDblClick,
  onNodeHover,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const onReadyRef = useRef(onSvgReady);
  onReadyRef.current = onSvgReady;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;
  const dblRef = useRef(onNodeDblClick);
  dblRef.current = onNodeDblClick;
  const hoverRef = useRef(onNodeHover);
  hoverRef.current = onNodeHover;
  const reactId = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    const host = hostRef.current;
    if (!host) return;
    const src = repairMermaidSource(source || "");
    setLoading(true);
    if (!src) {
      host.innerHTML = "";
      svgRef.current = null;
      onReadyRef.current?.(null);
      setError("Пустая схема");
      onErrorRef.current?.("Пустая схема");
      setLoading(false);
      return;
    }
    let retryTimer: number | null = null;
    let fallbackSrc = src;

    const tryRender = async (attempt = 0) => {
      retryTimer = null;
      if (attempt === 0) {
        // Yield to browser layout so font metrics and container dimensions are non-zero
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
      if (cancelled || !hostRef.current) return;
      // Must be clean alphanumeric ID — consecutive underscores break Dagre label calculations in Mermaid
      const rand = Math.random().toString(36).replace(/[^a-zA-Z0-9]/g, "").slice(0, 6);
      const renderId = `mmd${reactId}${rand}`;
      try {
        if (cancelled || !hostRef.current) return;
        const { svg } = await renderMermaidSync(renderId, fallbackSrc);
        if (cancelled || !hostRef.current) return;
        hostRef.current.innerHTML = svg;
        setError(null);
        onErrorRef.current?.(null);
        const el = hostRef.current.querySelector("svg");
        svgRef.current = el;
        if (el) {
          softenMermaidSvg(el);
          const vb = el.getAttribute("viewBox");
          if (vb) {
            const parts = vb.trim().split(/[\s,]+/).map(Number);
            if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
              const [, , w, h] = parts;
              el.setAttribute("width", String(w));
              el.setAttribute("height", String(h));
              el.style.aspectRatio = `${w} / ${h}`;
            }
          }
          el.querySelectorAll("g.node").forEach((g) => {
            (g as SVGElement).style.cursor = dblRef.current
              ? "pointer"
              : "";
          });
        }
        onReadyRef.current?.(el);
        applyMermaidRoleHighlight(el, highlightNodeIds);
        setLoading(false);
      } catch (err) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        const stack = err instanceof Error ? err.stack : "";
        if (typeof window !== "undefined") {
          (window as unknown as { __lastMermaidErr?: unknown }).__lastMermaidErr = {
            msg,
            stack,
            attempt,
            renderId,
            srcLen: fallbackSrc.length,
          };
        }
        document
          .querySelectorAll(`[id*="${renderId}"]`)
          .forEach((el) => el.remove());

        // If failure was due to layout/DOM zero-dimension timing or dagre spline edge calculation,
        // retry up to 3 times with fallback curve ("cardinal" -> "linear") and relaxed rank spacing.
        if (
          attempt < 3 &&
          (msg.includes("suitable point") ||
            msg.includes("getBoundingClientRect") ||
            msg.includes("point for the given distance"))
        ) {
          try {
            const m = await loadMermaid();
            m.initialize({
              startOnLoad: false,
              securityLevel: "loose",
              theme: "base",
              flowchart: {
                curve: attempt === 0 ? "cardinal" : "linear",
                padding: 22,
                nodeSpacing: 56,
                rankSpacing: 70,
                htmlLabels: true,
                useMaxWidth: true,
              },
            });
          } catch {
            /* ignore init reset error */
          }
          if (attempt >= 1) {
            // Strip edge labels as safety net if Dagre label position keeps failing on tight edges
            fallbackSrc = fallbackSrc.replace(/-->\s*\|[^|]+\|\s*/g, "--> ");
          }
          retryTimer = window.setTimeout(() => {
            if (!cancelled) void tryRender(attempt + 1);
          }, 80 * (attempt + 1));
          return;
        }

        setError(msg);
        onErrorRef.current?.(msg);
        if (hostRef.current) hostRef.current.innerHTML = "";
        svgRef.current = null;
        onReadyRef.current?.(null);
        setLoading(false);
      }
    };

    void tryRender(0);
    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
    };
  }, [source, reactId]); // eslint-disable-line react-hooks/exhaustive-deps -- highlight applied below

  useEffect(() => {
    applyMermaidRoleHighlight(svgRef.current, highlightNodeIds ?? null);
  }, [highlightNodeIds]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !onNodeDblClick) return;
    const onDbl = (e: MouseEvent) => {
      const id = mermaidNodeIdFromElement(e.target as Element);
      if (id) {
        e.preventDefault();
        e.stopPropagation();
        dblRef.current?.(id);
      }
    };
    host.addEventListener("dblclick", onDbl);
    return () => host.removeEventListener("dblclick", onDbl);
  }, [onNodeDblClick, loading, source]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !onNodeHover) return;
    const onMove = (e: MouseEvent) => {
      const id = mermaidNodeIdFromElement(e.target as Element);
      hoverRef.current?.(id || null);
    };
    const onLeave = () => {
      hoverRef.current?.(null);
    };
    host.addEventListener("mousemove", onMove);
    host.addEventListener("mouseleave", onLeave);
    return () => {
      host.removeEventListener("mousemove", onMove);
      host.removeEventListener("mouseleave", onLeave);
    };
  }, [onNodeHover, loading, source]);

  return (
    <div className={`mermaid-view${className ? ` ${className}` : ""}`}>
      {loading && !error ? (
        <p className="mermaid-view-loading" aria-live="polite">
          Рисую схему…
        </p>
      ) : null}
      {error ? (
        <div className="mermaid-view-error" role="alert">
          <p>Не удалось отрисовать схему</p>
          {error !== "Пустая схема" ? (
            <p className="mermaid-view-error-detail">{error}</p>
          ) : null}
        </div>
      ) : null}
      <div
        ref={hostRef}
        className={`mermaid-view-svg${loading && !error ? " is-loading" : ""}`}
        aria-hidden={Boolean(error) || loading}
      />
    </div>
  );
}
