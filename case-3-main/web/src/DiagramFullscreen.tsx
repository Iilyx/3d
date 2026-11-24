/** Portal fullscreen overlay for a Mermaid diagram. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { DiagramZoomView } from "./DiagramZoomView";
import {
  downloadDiagramPng,
  downloadDiagramSvg,
  slugDiagramFilename,
} from "./downloadDiagramPng";
import { nodeIdsForRole, parseDiagramLegend } from "./diagramLegend";
import { useFocusTrap } from "./useFocusTrap";

export type DiagramInfo = {
  id: string;
  title: string;
  type?: string;
  mermaid: string;
};

type Props = {
  diagram: DiagramInfo;
  onClose: () => void;
};

export function DiagramFullscreen({ diagram, onClose }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [activeRole, setActiveRole] = useState<string | null>(null);
  useFocusTrap(dialogRef, { active: true });

  const legend = useMemo(
    () => parseDiagramLegend(diagram.mermaid || ""),
    [diagram.mermaid],
  );
  const highlightNodeIds = useMemo(() => {
    if (!activeRole) return null;
    return nodeIdsForRole(diagram.mermaid || "", activeRole);
  }, [activeRole, diagram.mermaid]);

  const onSvgReady = useCallback((el: SVGSVGElement | null) => {
    svgRef.current = el;
  }, []);

  const onDownloadPng = useCallback(async () => {
    const el = svgRef.current;
    if (!el) {
      setErr("Схема ещё не готова — подождите секунду");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await downloadDiagramPng(
        el,
        slugDiagramFilename(diagram.title, diagram.id, "png"),
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [diagram.id, diagram.title]);

  const onDownloadSvg = useCallback(async () => {
    const el = svgRef.current;
    if (!el) {
      setErr("Схема ещё не готова — подождите секунду");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await downloadDiagramSvg(
        el,
        slugDiagramFilename(diagram.title, diagram.id, "svg"),
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [diagram.id, diagram.title]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return createPortal(
    <div
      ref={dialogRef}
      className="diagram-fullscreen"
      role="dialog"
      aria-modal="true"
      aria-label={diagram.title}
      onClick={onClose}
    >
      <div
        className="diagram-fullscreen-sheet"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="diagram-fullscreen-head">
          <div>
            <h2 className="diagram-fullscreen-title">{diagram.title}</h2>
            <p className="diagram-fullscreen-sub">
              Векторная схема · масштаб и экспорт в SVG / PNG
            </p>
          </div>
          <div className="diagram-fullscreen-actions">
            <button
              type="button"
              className="btn ghost"
              disabled={busy}
              onClick={() => void onDownloadSvg()}
            >
              {busy ? "…" : "SVG"}
            </button>
            <button
              type="button"
              className="btn primary diagram-pane-png"
              disabled={busy}
              onClick={() => void onDownloadPng()}
            >
              {busy ? "…" : "Скачать PNG"}
            </button>
            <button
              type="button"
              className="diagram-fullscreen-close"
              aria-label="Закрыть"
              onClick={onClose}
            >
              ×
            </button>
          </div>
        </header>
        {err ? (
          <p className="diagram-pane-err" role="alert" style={{ margin: "0 1rem" }}>
            {err}
          </p>
        ) : null}
        <div className="diagram-fullscreen-body">
          <DiagramZoomView
            source={diagram.mermaid}
            onSvgReady={onSvgReady}
            className="is-centered"
            fitViewport
            highlightNodeIds={highlightNodeIds}
          />
          {legend.length > 0 ? (
            <ul
              className="diagram-legend is-interactive diagram-fullscreen-legend"
              aria-label="Легенда ролей"
            >
              {legend.map((item) => {
                const on = activeRole === item.role;
                return (
                  <li key={item.role}>
                    <button
                      type="button"
                      className={`diagram-legend-item${on ? " is-active" : ""}`}
                      aria-pressed={on}
                      onClick={() =>
                        setActiveRole((r) =>
                          r === item.role ? null : item.role,
                        )
                      }
                    >
                      <span
                        className="diagram-legend-swatch"
                        style={{ background: item.fill }}
                        aria-hidden
                      />
                      <span className="diagram-legend-label">{item.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      </div>
    </div>,
    document.body,
  );
}
