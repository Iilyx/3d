/** Manager-facing flowchart editor: React Flow canvas + inspector (no Mermaid). */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type DragEvent,
} from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  MarkerType,
  type Node,
  type Edge,
  type Connection,
  type NodeProps,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  DEFAULT_COLORS,
  diagramStructureEqual,
  type DiaKind,
  type DiagramIR,
  parseMermaidFlowchart,
  serializeMermaidFlowchart,
} from "./diagramIr";
import { layoutPositions } from "./diagramLayout";
import { useConfirm } from "./ConfirmModal";
import { useFocusTrap } from "./useFocusTrap";
import { redoChord, undoChord } from "./domain/undoChord";

/** React Flow fires dimensions/select on mount — those must not mark dirty. */
function isUserNodeChange(
  chs: { type?: string; dragging?: boolean }[],
): { dirty: boolean; pushHist: boolean } {
  let dirty = false;
  let pushHist = false;
  for (const c of chs) {
    if (c.type === "remove" || c.type === "add" || c.type === "replace") {
      dirty = true;
      pushHist = true;
    } else if (c.type === "position") {
      if (c.dragging === true) dirty = true;
      if (c.dragging === false) {
        dirty = true;
        pushHist = true;
      }
    }
    // ignore: dimensions, select, reset, …
  }
  return { dirty, pushHist };
}

function isUserEdgeChange(chs: { type?: string }[]): boolean {
  return chs.some(
    (c) => c.type === "remove" || c.type === "add" || c.type === "replace",
  );
}

const KIND_OPTIONS: { id: DiaKind; label: string }[] = [
  { id: "start", label: "Старт" },
  { id: "process", label: "Процесс" },
  { id: "decision", label: "Решение" },
  { id: "ok", label: "Успех" },
  { id: "warn", label: "Риск / возврат" },
  { id: "data", label: "Данные" },
];

const HISTORY_MAX = 40;

type NodeData = {
  label: string;
  kind: DiaKind;
};

type Snap = {
  nodes: Node[];
  edges: Edge[];
  direction: "TD" | "LR";
  title: string;
};

function draftKey(diagramId: string) {
  return `liber-diagram-draft:${diagramId}`;
}

function LiberNode({ data, selected }: NodeProps) {
  const d = data as NodeData;
  const colors = DEFAULT_COLORS[d.kind] || DEFAULT_COLORS.process;
  const isDecision = d.kind === "decision";
  const style: CSSProperties = {
    background: colors.fill,
    border: `2px solid ${selected ? "#1a2e22" : colors.stroke}`,
    color: "#1a2e22",
    borderRadius: isDecision ? 4 : d.kind === "ok" ? 999 : 10,
    padding: isDecision ? "18px 14px" : "10px 14px",
    minWidth: 140,
    maxWidth: 280,
    textAlign: "center",
    fontSize: 15,
    fontFamily: "Georgia, 'Times New Roman', serif",
    lineHeight: 1.25,
    boxShadow: selected
      ? "0 0 0 3px color-mix(in srgb, #6b8f76 35%, transparent)"
      : "0 2px 8px rgba(20,40,28,0.08)",
  };
  return (
    <div
      style={style}
      className={isDecision ? "dia-node is-decision" : "dia-node"}
    >
      <Handle type="target" position={Position.Top} className="dia-handle" />
      <div className="dia-node-label">{d.label || "Блок"}</div>
      <Handle type="source" position={Position.Bottom} className="dia-handle" />
      <Handle
        type="source"
        position={Position.Right}
        id="r"
        className="dia-handle"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="l"
        className="dia-handle"
      />
    </div>
  );
}

const nodeTypes = { liber: LiberNode };

function irToFlow(ir: DiagramIR): { nodes: Node[]; edges: Edge[] } {
  const pos = layoutPositions(ir);
  const nodes: Node[] = ir.nodes.map((n) => ({
    id: n.id,
    type: "liber",
    position: pos[n.id] || { x: 0, y: 0 },
    data: { label: n.label, kind: n.kind } satisfies NodeData,
  }));
  const edges: Edge[] = ir.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
    style: { stroke: "#5a7a64", strokeWidth: 1.6 },
    interactionWidth: 24,
    labelStyle: { fill: "#1a2e22", fontSize: 12 },
    labelBgStyle: { fill: "#f7faf7" },
    labelBgPadding: [4, 6] as [number, number],
  }));
  return { nodes, edges };
}

function flowToIr(
  meta: { id: string; title: string; direction: "TD" | "LR" },
  nodes: Node[],
  edges: Edge[],
): DiagramIR {
  return {
    id: meta.id,
    title: meta.title,
    direction: meta.direction,
    nodes: nodes.map((n) => {
      const d = n.data as NodeData;
      return {
        id: n.id,
        label: String(d.label || n.id),
        kind: (d.kind || "process") as DiaKind,
      };
    }),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: typeof e.label === "string" ? e.label : undefined,
    })),
  };
}

function nextId(nodes: Node[], prefix = "n"): string {
  const used = new Set(nodes.map((n) => n.id));
  for (let i = 1; i < 1000; i++) {
    const id = `${prefix}${i}`;
    if (!used.has(id)) return id;
  }
  return `${prefix}${Date.now()}`;
}

type Props = {
  open: boolean;
  diagramId: string;
  title: string;
  mermaid: string;
  busy?: boolean;
  error?: string | null;
  /** Select this node after open (e.g. dblclick from pane). */
  focusNodeId?: string | null;
  onCancel: () => void;
  onSave: (mermaid: string, title: string) => void;
};

function FitOnFocus({
  nodeId,
  nodeCount,
}: {
  nodeId: string | null;
  nodeCount: number;
}) {
  const { setCenter, getNode } = useReactFlow();
  const doneKey = useRef<string | null>(null);
  useEffect(() => {
    if (!nodeId) return;
    const key = `${nodeId}:${nodeCount}`;
    if (doneKey.current === key) return;
    const t = window.setTimeout(() => {
      const n = getNode(nodeId);
      if (n) {
        setCenter(n.position.x + 70, n.position.y + 30, {
          zoom: 1.15,
          duration: 280,
        });
        doneKey.current = key;
      }
    }, 80);
    return () => window.clearTimeout(t);
  }, [nodeId, nodeCount, setCenter, getNode]);
  return null;
}

function EditorInner({
  open,
  diagramId,
  title: initialTitle,
  mermaid,
  busy,
  error,
  focusNodeId = null,
  onCancel,
  onSave,
}: Props) {
  const confirm = useConfirm();
  const { fitView } = useReactFlow();
  const sheetRef = useRef<HTMLDivElement>(null);
  useFocusTrap(sheetRef, { active: open });

  const seed = useMemo(() => {
    try {
      const ir = parseMermaidFlowchart(mermaid, {
        id: diagramId,
        title: initialTitle,
      });
      return { ir, flow: irToFlow(ir), err: null as string | null };
    } catch (e) {
      return {
        ir: null as DiagramIR | null,
        flow: { nodes: [] as Node[], edges: [] as Edge[] },
        err: e instanceof Error ? e.message : String(e),
      };
    }
  }, [diagramId, initialTitle, mermaid]);

  const [title, setTitle] = useState(initialTitle);
  const [direction, setDirection] = useState<"TD" | "LR">(
    seed.ir?.direction || "TD",
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(seed.flow.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(seed.flow.edges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [showMiniMap, setShowMiniMap] = useState(false);
  const [parseErr] = useState(seed.err);
  const [dirty, setDirty] = useState(false);
  const [draftBanner, setDraftBanner] = useState(false);
  const [histEpoch, setHistEpoch] = useState(0);
  const savedColors = seed.ir?.colors;

  const pastRef = useRef<Snap[]>([]);
  const futureRef = useRef<Snap[]>([]);
  const skipHist = useRef(false);
  const applying = useRef(false);

  const takeSnap = useCallback(
    (): Snap => ({
      nodes: nodes.map((n) => ({
        ...n,
        position: { ...n.position },
        data: { ...(n.data as object) },
      })),
      edges: edges.map((e) => ({ ...e })),
      direction,
      title,
    }),
    [nodes, edges, direction, title],
  );

  const pushHistory = useCallback(() => {
    if (skipHist.current || applying.current) return;
    pastRef.current = [...pastRef.current.slice(-(HISTORY_MAX - 1)), takeSnap()];
    futureRef.current = [];
    setHistEpoch((n) => n + 1);
  }, [takeSnap]);

  const applySnap = useCallback(
    (s: Snap, markDirty = true) => {
      applying.current = true;
      setNodes(s.nodes);
      setEdges(s.edges);
      setDirection(s.direction);
      setTitle(s.title);
      if (markDirty) setDirty(true);
      queueMicrotask(() => {
        applying.current = false;
      });
    },
    [setNodes, setEdges],
  );

  const undo = useCallback(() => {
    const past = pastRef.current;
    if (!past.length) return;
    const prev = past[past.length - 1];
    pastRef.current = past.slice(0, -1);
    futureRef.current = [takeSnap(), ...futureRef.current].slice(0, HISTORY_MAX);
    applySnap(prev);
    setHistEpoch((n) => n + 1);
  }, [applySnap, takeSnap]);

  const redo = useCallback(() => {
    const fut = futureRef.current;
    if (!fut.length) return;
    const next = fut[0];
    futureRef.current = fut.slice(1);
    pastRef.current = [...pastRef.current, takeSnap()].slice(-HISTORY_MAX);
    applySnap(next);
    setHistEpoch((n) => n + 1);
  }, [applySnap, takeSnap]);

  const clearDraft = useCallback(() => {
    try {
      sessionStorage.removeItem(draftKey(diagramId));
    } catch {
      /* ignore */
    }
  }, [diagramId]);

  useEffect(() => {
    if (!open) return;
    pastRef.current = [];
    futureRef.current = [];
    setDraftBanner(false);

    let restored: Snap | null = null;
    try {
      const raw = sessionStorage.getItem(draftKey(diagramId));
      if (raw) {
        const parsed = JSON.parse(raw) as Snap & { mermaidHash?: string };
        if (
          parsed?.nodes &&
          Array.isArray(parsed.nodes) &&
          parsed.nodes.length > 0
        ) {
          restored = {
            nodes: parsed.nodes,
            edges: parsed.edges || [],
            direction: parsed.direction === "LR" ? "LR" : "TD",
            title: parsed.title || initialTitle,
          };
        }
      }
    } catch {
      restored = null;
    }

    skipHist.current = true;
    if (restored) {
      applySnap(restored, true);
      setDraftBanner(true);
      setSelectedNodeId(focusNodeId);
    } else {
      setTitle(initialTitle);
      setDirection(seed.ir?.direction || "TD");
      setNodes(seed.flow.nodes);
      setEdges(seed.flow.edges);
      setSelectedNodeId(focusNodeId);
      setDirty(false);
    }
    setSelectedEdgeId(null);
    queueMicrotask(() => {
      skipHist.current = false;
    });
  }, [
    open,
    diagramId,
    initialTitle,
    seed,
    focusNodeId,
    setNodes,
    setEdges,
    applySnap,
  ]);

  // Autosave draft
  useEffect(() => {
    if (!open || !dirty || parseErr) return;
    const t = window.setTimeout(() => {
      try {
        sessionStorage.setItem(
          draftKey(diagramId),
          JSON.stringify(takeSnap()),
        );
      } catch {
        /* quota */
      }
    }, 400);
    return () => window.clearTimeout(t);
  }, [open, dirty, parseErr, diagramId, takeSnap]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (
        mod &&
        (e.key.toLowerCase() === "y" ||
          (e.key.toLowerCase() === "z" && e.shiftKey))
      ) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, undo, redo]);

  const requestClose = async () => {
    if (dirty) {
      const ok = await confirm({
        title: "Несохранённые изменения",
        eyebrow: "схема · редактор",
        message:
          "Закрыть редактор схемы без сохранения? Черновик останется в этой вкладке.",
        confirmLabel: "Закрыть без сохранения",
        cancelLabel: "Продолжить редактирование",
        danger: true,
      });
      if (!ok) return;
    }
    onCancel();
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null;
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId) || null;

  const mutate = useCallback(
    (fn: () => void) => {
      pushHistory();
      setDirty(true);
      fn();
    },
    [pushHistory],
  );

  const onConnect = useCallback(
    (c: Connection) => {
      mutate(() => {
        setEdges((eds) =>
          addEdge(
            {
              ...c,
              id: `e_${c.source}_${c.target}_${eds.length}`,
              markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
              style: { stroke: "#5a7a64", strokeWidth: 1.6 },
              interactionWidth: 24,
              labelStyle: { fill: "#1a2e22", fontSize: 12 },
              labelBgStyle: { fill: "#f7faf7" },
              labelBgPadding: [4, 6] as [number, number],
            },
            eds,
          ),
        );
      });
    },
    [mutate, setEdges],
  );

  const addBlock = (kind: DiaKind = "process") => {
    const id = nextId(nodes);
    const label =
      KIND_OPTIONS.find((k) => k.id === kind)?.label.replace(" / возврат", "") ||
      "Новый блок";
    mutate(() => {
      setNodes((ns) => [
        ...ns,
        {
          id,
          type: "liber",
          position: { x: 120 + ns.length * 24, y: 80 + ns.length * 28 },
          data: { label, kind },
        },
      ]);
      setSelectedNodeId(id);
      setSelectedEdgeId(null);
    });
  };

  const addYesNoFork = () => {
    const base = nodes.length
      ? nodes[nodes.length - 1].position
      : { x: 280, y: 80 };
    const dId = nextId(nodes, "d");
    const yId = nextId([...nodes, { id: dId } as Node], "y");
    const nId = nextId(
      [...nodes, { id: dId } as Node, { id: yId } as Node],
      "n",
    );
    const gap = direction === "LR" ? { dx: 220, dy: 90 } : { dx: 160, dy: 120 };
    mutate(() => {
      setNodes((ns) => [
        ...ns,
        {
          id: dId,
          type: "liber",
          position: { x: base.x + 40, y: base.y + 40 },
          data: { label: "Условие?", kind: "decision" as DiaKind },
        },
        {
          id: yId,
          type: "liber",
          position: {
            x: base.x + 40 - gap.dx,
            y: base.y + 40 + gap.dy,
          },
          data: { label: "Да", kind: "ok" as DiaKind },
        },
        {
          id: nId,
          type: "liber",
          position: {
            x: base.x + 40 + gap.dx,
            y: base.y + 40 + gap.dy,
          },
          data: { label: "Нет", kind: "warn" as DiaKind },
        },
      ]);
      setEdges((es) => [
        ...es,
        {
          id: `e_${dId}_${yId}`,
          source: dId,
          target: yId,
          label: "да",
          markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
          style: { stroke: "#5a7a64", strokeWidth: 1.6 },
          interactionWidth: 24,
          labelStyle: { fill: "#1a2e22", fontSize: 12 },
          labelBgStyle: { fill: "#f7faf7" },
          labelBgPadding: [4, 6] as [number, number],
        },
        {
          id: `e_${dId}_${nId}`,
          source: dId,
          target: nId,
          label: "нет",
          markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
          style: { stroke: "#5a7a64", strokeWidth: 1.6 },
          interactionWidth: 24,
          labelStyle: { fill: "#1a2e22", fontSize: 12 },
          labelBgStyle: { fill: "#f7faf7" },
          labelBgPadding: [4, 6] as [number, number],
        },
      ]);
      setSelectedNodeId(dId);
      setSelectedEdgeId(null);
    });
  };

  const relayout = (dir: "TD" | "LR") => {
    mutate(() => {
      setDirection(dir);
      const ir = flowToIr({ id: diagramId, title, direction: dir }, nodes, edges);
      const pos = layoutPositions(ir);
      setNodes((ns) =>
        ns.map((n) => ({
          ...n,
          position: pos[n.id] || n.position,
        })),
      );
    });
    window.setTimeout(() => {
      void fitView({ padding: 0.2, duration: 320 });
    }, 40);
  };

  const deleteSelected = () => {
    mutate(() => {
      if (selectedNodeId) {
        setNodes((ns) => ns.filter((n) => n.id !== selectedNodeId));
        setEdges((es) =>
          es.filter(
            (e) => e.source !== selectedNodeId && e.target !== selectedNodeId,
          ),
        );
        setSelectedNodeId(null);
        return;
      }
      if (selectedEdgeId) {
        setEdges((es) => es.filter((e) => e.id !== selectedEdgeId));
        setSelectedEdgeId(null);
      }
    });
  };

  const save = () => {
    const ir = flowToIr({ id: diagramId, title, direction }, nodes, edges);
    ir.colors = savedColors;
    const titleOut = title.trim() || diagramId;
    // No-op: keep original Mermaid so Liber/Mermaid layout stays as generated.
    if (
      seed.ir &&
      diagramStructureEqual(ir, seed.ir) &&
      titleOut === (initialTitle || "").trim()
    ) {
      setDirty(false);
      clearDraft();
      onSave(mermaid, titleOut);
      return;
    }
    const out = serializeMermaidFlowchart(ir);
    setDirty(false);
    clearDraft();
    onSave(out, titleOut);
  };

  const discardDraft = () => {
    clearDraft();
    setDraftBanner(false);
    skipHist.current = true;
    setTitle(initialTitle);
    setDirection(seed.ir?.direction || "TD");
    setNodes(seed.flow.nodes);
    setEdges(seed.flow.edges);
    setDirty(false);
    pastRef.current = [];
    futureRef.current = [];
    queueMicrotask(() => {
      skipHist.current = false;
    });
  };

  const onDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const canUndo = histEpoch >= 0 && pastRef.current.length > 0;
  const canRedo = histEpoch >= 0 && futureRef.current.length > 0;

  if (!open) return null;

  return (
    <div
      className="diagram-edit-backdrop is-visual"
      role="presentation"
      onClick={requestClose}
    >
      <div
        ref={sheetRef}
        className="diagram-visual-sheet"
        role="dialog"
        aria-modal="true"
        aria-label="Редактор схемы"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="diagram-visual-head">
          <div className="diagram-visual-head-text">
            <p className="diagram-visual-eyebrow">Редактор схемы</p>
            <input
              className="diagram-visual-title-input"
              value={title}
              onChange={(e) => {
                setDirty(true);
                setTitle(e.target.value);
              }}
              maxLength={80}
              aria-label="Заголовок схемы"
              disabled={busy}
            />
          </div>
          <div className="diagram-visual-head-actions">
            <button
              type="button"
              className="btn ghost"
              onClick={requestClose}
              disabled={busy}
            >
              Отмена
            </button>
            <button
              type="button"
              className="btn primary diagram-pane-png"
              onClick={save}
              disabled={busy || Boolean(parseErr) || nodes.length === 0}
            >
              {busy ? "…" : "Сохранить"}
            </button>
          </div>
        </header>

        {draftBanner ? (
          <div className="diagram-visual-draft" role="status">
            <span>Восстановлен черновик из этой вкладки</span>
            <button type="button" className="btn ghost" onClick={discardDraft}>
              Сбросить
            </button>
          </div>
        ) : null}

        {parseErr ? (
          <p className="diagram-edit-err" role="alert">
            {parseErr}. Правьте узлы вручную или откройте другую схему.
          </p>
        ) : null}
        {error ? (
          <p className="diagram-edit-err" role="alert">
            {error}
          </p>
        ) : null}

        <div className="diagram-visual-body">
          <div className="diagram-visual-canvas" onDragOver={onDragOver}>
            <div className="diagram-visual-toolbar" role="toolbar">
              <button
                type="button"
                className="btn ghost icon"
                onClick={undo}
                disabled={!canUndo}
                title={`Отменить · ${undoChord()}`}
                aria-label="Отменить"
              >
                <svg viewBox="0 0 16 16" aria-hidden>
                  <path
                    d="M3.5 6.5H10a3.5 3.5 0 1 1 0 7H8.25"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                  <path
                    d="M6 3.5 3.5 6.5 6 9.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              <button
                type="button"
                className="btn ghost icon"
                onClick={redo}
                disabled={!canRedo}
                title={`Повторить · ${redoChord()}`}
                aria-label="Повторить"
              >
                <svg viewBox="0 0 16 16" aria-hidden>
                  <path
                    d="M12.5 6.5H6a3.5 3.5 0 1 0 0 7h1.75"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                  <path
                    d="M10 3.5 12.5 6.5 10 9.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              <span className="diagram-visual-toolbar-sep" aria-hidden />
              <button
                type="button"
                className="btn ghost"
                onClick={() => addBlock("process")}
              >
                + Блок
              </button>
              <button
                type="button"
                className="btn ghost"
                onClick={() => addBlock("decision")}
              >
                + Решение
              </button>
              <button
                type="button"
                className="btn ghost diagram-visual-fork"
                onClick={addYesNoFork}
                title="Ромб + да / нет"
              >
                Развилка да/нет
              </button>
              <button
                type="button"
                className="btn danger"
                onClick={deleteSelected}
                disabled={!selectedNodeId && !selectedEdgeId}
              >
                Удалить
              </button>
              <button
                type="button"
                className="btn ghost diagram-visual-layout-btn"
                onClick={() => relayout(direction)}
                title="Выровнять блоки схемы в 1 клик"
              >
                <svg
                  viewBox="0 0 16 16"
                  width="13"
                  height="13"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  aria-hidden
                >
                  <rect x="2" y="2" width="5" height="5" rx="1" />
                  <rect x="9" y="2" width="5" height="5" rx="1" />
                  <rect x="2" y="9" width="5" height="5" rx="1" />
                  <rect x="9" y="9" width="5" height="5" rx="1" />
                </svg>
                Выровнять
              </button>
              <label className="diagram-visual-dir">
                Направление
                <select
                  value={direction}
                  onChange={(e) =>
                    relayout(e.target.value === "LR" ? "LR" : "TD")
                  }
                >
                  <option value="TD">Сверху вниз</option>
                  <option value="LR">Слева направо</option>
                </select>
              </label>
              <button
                type="button"
                className={`btn ghost diagram-visual-minimap-btn ${showMiniMap ? "is-active" : ""}`}
                onClick={() => setShowMiniMap((v) => !v)}
                title={showMiniMap ? "Скрыть миникарту" : "Показать миникарту"}
                aria-pressed={showMiniMap}
              >
                <svg
                  viewBox="0 0 16 16"
                  width="13"
                  height="13"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  aria-hidden
                >
                  <rect x="2" y="3" width="12" height="10" rx="1.5" />
                  <path d="M6 3v10M10 3v10" strokeDasharray="1.5 1.5" />
                </svg>
                Карта
              </button>
              <span className="diagram-visual-hint">
                Тяните от точки — стрелка · {undoChord()} — отмена
              </span>
            </div>
            <div className="diagram-visual-flow">
              {nodes.length === 0 && !parseErr ? (
                <div className="diagram-visual-empty" aria-live="polite">
                  <p className="diagram-visual-empty-title">Пустая схема</p>
                  <p className="diagram-visual-empty-body">
                    Добавьте решение или блок — или вставьте развилку «да/нет»
                    одной кнопкой.
                  </p>
                  <div className="diagram-visual-empty-actions">
                    <button
                      type="button"
                      className="btn primary diagram-pane-png"
                      onClick={addYesNoFork}
                    >
                      Развилка да/нет
                    </button>
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={() => addBlock("start")}
                    >
                      + Старт
                    </button>
                  </div>
                </div>
              ) : null}
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={(chs) => {
                  if (!applying.current) {
                    const { dirty: d, pushHist } = isUserNodeChange(chs);
                    if (pushHist) pushHistory();
                    if (d) setDirty(true);
                  }
                  onNodesChange(chs);
                }}
                onEdgesChange={(chs) => {
                  if (!applying.current && isUserEdgeChange(chs)) {
                    setDirty(true);
                  }
                  onEdgesChange(chs);
                }}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                onSelectionChange={({ nodes: ns, edges: es }) => {
                  setSelectedNodeId(ns[0]?.id ?? null);
                  setSelectedEdgeId(es[0]?.id ?? null);
                }}
                deleteKeyCode={["Backspace", "Delete"]}
                proOptions={{ hideAttribution: true }}
              >
                <FitOnFocus nodeId={focusNodeId} nodeCount={nodes.length} />
                <Background gap={18} color="#d5ddd6" />
                <Controls showInteractive={false} />
                {showMiniMap ? (
                  <MiniMap
                    pannable
                    zoomable
                    nodeColor={(n) => {
                      const k = (n.data as NodeData)?.kind || "process";
                      return DEFAULT_COLORS[k]?.fill || "#dce8df";
                    }}
                  />
                ) : null}
              </ReactFlow>
            </div>
          </div>

          <aside className="diagram-visual-inspector" aria-label="Свойства">
            {selectedNode ? (
              <>
                <h4>Блок</h4>
                <label className="diagram-edit-field">
                  <span>Текст</span>
                  <textarea
                    rows={3}
                    value={String((selectedNode.data as NodeData).label || "")}
                    onChange={(e) => {
                      const v = e.target.value;
                      setDirty(true);
                      setNodes((ns) =>
                        ns.map((n) =>
                          n.id === selectedNode.id
                            ? { ...n, data: { ...n.data, label: v } }
                            : n,
                        ),
                      );
                    }}
                  />
                </label>
                <label className="diagram-edit-field">
                  <span>Роль / цвет</span>
                  <select
                    value={(selectedNode.data as NodeData).kind}
                    onChange={(e) => {
                      const kind = e.target.value as DiaKind;
                      mutate(() => {
                        setNodes((ns) =>
                          ns.map((n) =>
                            n.id === selectedNode.id
                              ? { ...n, data: { ...n.data, kind } }
                              : n,
                          ),
                        );
                      });
                    }}
                  >
                    {KIND_OPTIONS.map((k) => (
                      <option key={k.id} value={k.id}>
                        {k.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div
                  className="diagram-visual-swatches"
                  role="group"
                  aria-label="Роль блока"
                >
                  {KIND_OPTIONS.map((k) => (
                    <button
                      key={k.id}
                      type="button"
                      title={k.label}
                      aria-pressed={
                        (selectedNode.data as NodeData).kind === k.id
                      }
                      className={`diagram-visual-swatch${
                        (selectedNode.data as NodeData).kind === k.id
                          ? " is-active"
                          : ""
                      }`}
                      style={
                        {
                          ["--swatch" as string]: DEFAULT_COLORS[k.id].fill,
                        } as CSSProperties
                      }
                      onClick={() => {
                        mutate(() => {
                          setNodes((ns) =>
                            ns.map((n) =>
                              n.id === selectedNode.id
                                ? { ...n, data: { ...n.data, kind: k.id } }
                                : n,
                            ),
                          );
                        });
                      }}
                    >
                      {k.label}
                    </button>
                  ))}
                </div>
              </>
            ) : selectedEdge ? (
              <>
                <h4>Стрелка</h4>
                <label className="diagram-edit-field">
                  <span>Подпись</span>
                  <input
                    type="text"
                    value={
                      typeof selectedEdge.label === "string"
                        ? selectedEdge.label
                        : ""
                    }
                    placeholder="да / нет / …"
                    onChange={(e) => {
                      const v = e.target.value;
                      setDirty(true);
                      setEdges((es) =>
                        es.map((ed) =>
                          ed.id === selectedEdge.id ? { ...ed, label: v } : ed,
                        ),
                      );
                    }}
                  />
                </label>
                <p className="diagram-visual-inspector-hint">
                  {selectedEdge.source} → {selectedEdge.target}
                </p>
              </>
            ) : (
              <>
                <h4>Схема</h4>
                <p className="diagram-visual-inspector-hint">
                  Выберите блок или стрелку. Кнопка «Развилка да/нет» ставит
                  ромб и две ветки за один клик.
                </p>
                <ul className="diagram-visual-legend">
                  {KIND_OPTIONS.map((k) => (
                    <li key={k.id}>
                      <span
                        className="diagram-legend-swatch"
                        style={{ background: DEFAULT_COLORS[k.id].fill }}
                      />
                      {k.label}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}

export function DiagramVisualEditor(props: Props) {
  if (!props.open) return null;
  return (
    <ReactFlowProvider>
      <EditorInner {...props} />
    </ReactFlowProvider>
  );
}
