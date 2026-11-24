/** Diagram body: premium Mermaid frame + legend + edit/PNG. */

import { lazy, Suspense, useCallback, useMemo, useRef, useState } from "react";
import {
  DiagramFullscreen,
  type DiagramInfo,
} from "./DiagramFullscreen";
import { DiagramZoomView } from "./DiagramZoomView";
import { DiagramCodeModal } from "./DiagramCodeModal";

const DiagramVisualEditor = lazy(() =>
  import("./DiagramVisualEditor").then((m) => ({
    default: m.DiagramVisualEditor,
  })),
);
import { isSupportedFlowchartSubset } from "./diagramIr";
import { diagramTypeLabel } from "./diagramLabels";
import { nodeIdsForRole, parseDiagramLegend } from "./diagramLegend";
import {
  downloadDiagramPng,
  downloadDiagramSvg,
  slugDiagramFilename,
} from "./downloadDiagramPng";

export type DiagramUpdateMeta = {
  undo?: { kind?: string; target?: string } | null;
  toast?: string;
};

type Props = {
  diagram?: DiagramInfo | null;
  siblings?: DiagramInfo[];
  onSelectSibling?: (id: string) => void;
  runId?: string | null;
  onDiagramsUpdated?: (
    diagrams: DiagramInfo[],
    meta?: DiagramUpdateMeta,
  ) => void;
  /** Empty-run CTA: regenerate without a current diagram. */
  emptyMode?: boolean;
};

export function DiagramPane({
  diagram = null,
  siblings,
  onSelectSibling,
  runId,
  onDiagramsUpdated,
  emptyMode = false,
}: Props) {
  const paneSvgRef = useRef<SVGSVGElement | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [codeOpen, setCodeOpen] = useState(false);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [activeRole, setActiveRole] = useState<string | null>(null);
  const mermaidSrc = diagram?.mermaid || "";
  const visualOk = isSupportedFlowchartSubset(mermaidSrc);

  const legend = useMemo(
    () => parseDiagramLegend(mermaidSrc),
    [mermaidSrc],
  );
  const typeRu = diagramTypeLabel(diagram?.type);

  const highlightNodeIds = useMemo(() => {
    if (!activeRole) return null;
    return nodeIdsForRole(mermaidSrc, activeRole);
  }, [activeRole, mermaidSrc]);

  const onPaneSvg = useCallback((el: SVGSVGElement | null) => {
    paneSvgRef.current = el;
  }, []);

  const openEditor = useCallback(
    (nodeId?: string | null) => {
      setFocusNodeId(nodeId || null);
      setEditOpen(true);
      setErr(null);
    },
    [],
  );

  const doDownloadPng = useCallback(
    async (el: SVGSVGElement | null) => {
      if (!el || !diagram) {
        setErr("Схема ещё не готова");
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
    },
    [diagram],
  );

  const doDownloadSvg = useCallback(
    async (el: SVGSVGElement | null) => {
      if (!diagram) {
        setErr("Схема ещё не готова");
        return;
      }
      setBusy(true);
      setErr(null);
      try {
        if (el) {
          await downloadDiagramSvg(
            el,
            slugDiagramFilename(diagram.title, diagram.id, "svg"),
          );
          return;
        }
        if (!runId) {
          setErr("Схема ещё не готова");
          return;
        }
        // Fallback: server Playwright SVG
        const a = document.createElement("a");
        a.href = `/api/runs/${encodeURIComponent(runId)}/diagrams/${encodeURIComponent(diagram.id)}/svg`;
        a.download = slugDiagramFilename(diagram.title, diagram.id, "svg");
        a.rel = "noopener";
        document.body.appendChild(a);
        a.click();
        a.remove();
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [diagram, runId],
  );

  const doApplyEdit = useCallback(
    async (mermaid: string, title: string) => {
      if (!runId || !diagram) {
        setErr("Сначала откройте сохранённый материал");
        return;
      }
      setEditBusy(true);
      setErr(null);
      try {
        const res = await fetch(
          `/api/runs/${encodeURIComponent(runId)}/diagrams/${encodeURIComponent(diagram.id)}/edit`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mermaid, title }),
          },
        );
        const data = await res.json();
        if (!res.ok) {
          throw new Error(
            typeof data.detail === "string"
              ? data.detail
              : data.error || res.statusText,
          );
        }
        const next = Array.isArray(data.diagrams) ? data.diagrams : [];
        onDiagramsUpdated?.(next, {
          undo: data.undo ?? null,
          toast: "Схема сохранена",
        });
        setEditOpen(false);
        setCodeOpen(false);
        setFocusNodeId(null);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        setEditBusy(false);
      }
    },
    [diagram, onDiagramsUpdated, runId],
  );

  const doRegenerate = useCallback(async () => {
    if (!runId) {
      setErr("Сначала откройте сохранённый материал");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(
        `/api/runs/${encodeURIComponent(runId)}/diagrams/regenerate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        },
      );
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : data.error || res.statusText,
        );
      }
      const next = Array.isArray(data.diagrams) ? data.diagrams : [];
      if (!next.length) {
        throw new Error("Модель не вернула схему — попробуйте ещё раз");
      }
      onDiagramsUpdated?.(next, {
        undo: data.undo ?? null,
        toast: "Новый вариант схемы",
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [onDiagramsUpdated, runId]);

  const [copilotPrompt, setCopilotPrompt] = useState("");
  const [copilotBusy, setCopilotBusy] = useState(false);

  const doRefine = useCallback(async () => {
    const text = copilotPrompt.trim();
    if (!text || !runId || !diagram) return;
    setCopilotBusy(true);
    setErr(null);
    try {
      const res = await fetch(
        `/api/runs/${encodeURIComponent(runId)}/diagrams/${encodeURIComponent(diagram.id)}/refine`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ instruction: text }),
        },
      );
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : data.error || res.statusText,
        );
      }
      const next = Array.isArray(data.diagrams) ? data.diagrams : [];
      if (!next.length) {
        throw new Error("Модель не вернула обновлённую схему");
      }
      setCopilotPrompt("");
      onDiagramsUpdated?.(next, {
        undo: data.undo ?? null,
        toast: "Изменения применены",
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setCopilotBusy(false);
    }
  }, [copilotPrompt, diagram, onDiagramsUpdated, runId]);

  if (emptyMode || !diagram) {
    return (
      <div className="diagram-pane is-premium is-empty">
        <header className="diagram-pane-hero">
          <div className="diagram-pane-hero-text">
            <p className="diagram-pane-eyebrow">Схема</p>
            <h3 className="diagram-pane-title">Схема не собралась</h3>
            <p className="diagram-pane-empty-hint muted">
              Можно запросить новый вариант или отправить запрос снова.
            </p>
          </div>
          <div className="diagram-pane-actions">
            <button
              type="button"
              className="btn primary diagram-pane-png"
              disabled={busy || !runId}
              onClick={() => void doRegenerate()}
            >
              {busy ? "…" : "Ещё вариант"}
            </button>
          </div>
        </header>
        {err ? (
          <p className="diagram-pane-err" role="alert">
            {err}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="diagram-pane is-premium">
      {siblings && siblings.length > 1 && onSelectSibling ? (
        <div className="diagram-pane-siblings" role="tablist" aria-label="Схемы">
          {siblings.map((d) => (
            <button
              key={d.id}
              type="button"
              role="tab"
              aria-selected={d.id === diagram.id}
              className={`diagram-pane-sib${d.id === diagram.id ? " is-active" : ""}`}
              onClick={() => {
                setActiveRole(null);
                onSelectSibling(d.id);
              }}
              onDoubleClick={() => {
                onSelectSibling(d.id);
                openEditor(null);
              }}
              title="Двойной клик — открыть редактор"
            >
              {d.title || d.id}
            </button>
          ))}
        </div>
      ) : null}

      <header className="diagram-pane-hero">
        <div className="diagram-pane-hero-text">
          <p className="diagram-pane-eyebrow">
            <span className="diagram-pane-type">{typeRu}</span>
          </p>
          <h3 className="diagram-pane-title">{diagram.title}</h3>
        </div>
        <div className="diagram-pane-actions">
          <button
            type="button"
            className="btn ghost"
            disabled={busy || !runId}
            title="Сгенерировать новый вариант схемы"
            onClick={() => void doRegenerate()}
          >
            {busy ? "…" : "Ещё вариант"}
          </button>
          {visualOk ? (
            <button
              type="button"
              className="btn ghost"
              disabled={busy}
              title="Визуальный редактор блок-схемы"
              onClick={() => openEditor(null)}
            >
              Изменить
            </button>
          ) : (
            <button
              type="button"
              className="btn ghost"
              disabled={busy}
              title="Редактировать код схемы"
              onClick={() => {
                setCodeOpen(true);
                setErr(null);
              }}
            >
              Изменить
            </button>
          )}
          <button
            type="button"
            className="btn ghost"
            disabled={busy}
            title="Редактировать код схемы"
            onClick={() => {
              setCodeOpen(true);
              setErr(null);
            }}
          >
            Код
          </button>
          <button
            type="button"
            className="btn ghost"
            onClick={() => setFullscreen(true)}
          >
            На весь экран
          </button>
          <button
            type="button"
            className="btn ghost"
            disabled={busy}
            onClick={() => void doDownloadSvg(paneSvgRef.current)}
          >
            {busy ? "…" : "SVG"}
          </button>
          <button
            type="button"
            className="btn primary diagram-pane-png"
            disabled={busy}
            onClick={() => void doDownloadPng(paneSvgRef.current)}
          >
            {busy ? "…" : "Скачать PNG"}
          </button>
        </div>
      </header>

      <form
        className="diagram-copilot-bar"
        onSubmit={(e) => {
          e.preventDefault();
          void doRefine();
        }}
      >
        <div className="diagram-copilot-input-wrap">
          <svg
            className="diagram-copilot-icon"
            viewBox="0 0 16 16"
            width="13"
            height="13"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden
          >
            <path d="M8 1v3M8 12v3M1 8h3M12 8h3M3.05 3.05l2.12 2.12M10.83 10.83l2.12 2.12M3.05 12.95l2.12-2.12M10.83 5.17l2.12-2.12" />
          </svg>
          <input
            type="text"
            className="diagram-copilot-input"
            value={copilotPrompt}
            onChange={(e) => setCopilotPrompt(e.target.value)}
            placeholder="Напишите, что изменить"
            disabled={copilotBusy || busy}
          />
        </div>
        <button
          type="submit"
          className="btn ghost diagram-copilot-btn"
          disabled={copilotBusy || busy || !copilotPrompt.trim()}
          title="Отправить изменения"
        >
          {copilotBusy ? "Идёт редактирование…" : "Отправить изменения"}
        </button>
      </form>

      {err ? (
        <p className="diagram-pane-err" role="alert">
          {err}
        </p>
      ) : null}

      <div className="diagram-pane-canvas">
        <p className="diagram-pane-canvas-hint">
          Двойной клик по блоку — редактор · клик по легенде — подсветка роли
        </p>
        <DiagramZoomView
          source={mermaidSrc}
          onSvgReady={onPaneSvg}
          className="is-premium is-centered"
          fitViewport
          highlightNodeIds={highlightNodeIds}
          onNodeDblClick={(id) => openEditor(id)}
        />
      </div>

      {legend.length > 0 ? (
        <ul className="diagram-legend is-interactive" aria-label="Легенда ролей">
          {legend.map((item) => {
            const on = activeRole === item.role;
            return (
              <li key={item.role}>
                <button
                  type="button"
                  className={`diagram-legend-item${on ? " is-active" : ""}`}
                  aria-pressed={on}
                  title={
                    on
                      ? "Снять подсветку"
                      : `Подсветить: ${item.label}`
                  }
                  onClick={() =>
                    setActiveRole((r) => (r === item.role ? null : item.role))
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

      {fullscreen ? (
        <DiagramFullscreen
          diagram={diagram}
          onClose={() => setFullscreen(false)}
        />
      ) : null}

      {visualOk && editOpen ? (
        <Suspense fallback={null}>
          <DiagramVisualEditor
            open={editOpen}
            diagramId={diagram.id}
            title={diagram.title}
            mermaid={diagram.mermaid}
            busy={editBusy}
            error={err}
            focusNodeId={focusNodeId}
            onCancel={() => {
              setEditOpen(false);
              setFocusNodeId(null);
              setErr(null);
            }}
            onSave={(m, t) => void doApplyEdit(m, t)}
          />
        </Suspense>
      ) : null}

      {codeOpen && diagram ? (
        <DiagramCodeModal
          open={codeOpen}
          diagramId={diagram.id}
          title={diagram.title}
          mermaid={diagram.mermaid}
          busy={editBusy}
          error={err}
          onCancel={() => {
            setCodeOpen(false);
            setErr(null);
          }}
          onSave={(m, t) => void doApplyEdit(m, t)}
        />
      ) : null}
    </div>
  );
}
