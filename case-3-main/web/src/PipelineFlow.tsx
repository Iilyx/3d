/** Liber atelier — soft pipeline nodes while the agent runs. */

import { motion, useReducedMotion } from "framer-motion";

export type FlowStage =
  | "queued"
  | "llm"
  | "images"
  | "charts"
  | "inject"
  | "latex"
  | "docx"
  | "ok"
  | "error"
  | string;

export type NodeDef = {
  id: string;
  label: string;
  /** Pipeline stages that light this node. */
  stages: string[];
};

const REPORT_NODES: NodeDef[] = [
  { id: "desk", label: "Стол", stages: ["queued"] },
  { id: "think", label: "Текст", stages: ["llm"] },
  { id: "viz", label: "Фигуры", stages: ["images", "charts"] },
  { id: "bind", label: "Вёрстка", stages: ["inject"] },
  { id: "print", label: "Печать", stages: ["latex", "docx", "summary"] },
];

/** No Печать — diagram finishes on Схема (Mermaid only). */
const DIAGRAM_NODES: NodeDef[] = [
  { id: "desk", label: "Стол", stages: ["queued"] },
  { id: "think", label: "Текст", stages: ["llm"] },
  {
    id: "schema",
    label: "Схема",
    stages: ["inject", "images", "charts", "summary", "latex", "docx"],
  },
];

/**
 * Presentation: pipeline then slides job. Unknown slides_* must NOT fall back to Стол.
 */
const PRESENTATION_NODES: NodeDef[] = [
  { id: "desk", label: "Стол", stages: ["queued"] },
  { id: "think", label: "Текст", stages: ["llm"] },
  {
    id: "viz",
    label: "Фигуры",
    stages: ["images", "charts", "inject"],
  },
  {
    id: "plan",
    label: "План",
    stages: [
      "pipeline_ok",
      "summary",
      "latex",
      "docx",
      "slides_queued",
      "slides_starting",
      "starting",
      "slides_llm",
      "llm_retry",
      "slides_llm_retry",
      "slides_plan",
      "plan",
    ],
  },
  {
    id: "pack",
    label: "Дека",
    stages: [
      "slides_diagrams",
      "slides_media",
      "slides_charts",
      "diagrams",
      "media",
      "slides_render",
      "render",
      "slides_pptx",
      "pptx",
      "slides_patch",
      "patch",
    ],
  },
];

/** Normalize UI/API stage aliases for node lookup. */
export function normalizePipelineStage(stage?: string | null): string {
  const raw = (stage || "queued").toLowerCase();
  if (!raw || raw === "queued") return "queued";
  if (raw === "ok" || raw === "slides_ok") return "ok";
  if (raw === "error" || raw === "slides_error") return "error";
  // Bare slides stages from SSE scope=slides → already prefixed in App, but accept both.
  if (
    [
      "starting",
      "llm_retry",
      "plan",
      "diagrams",
      "media",
      "render",
      "pptx",
      "patch",
    ].includes(raw)
  ) {
    return `slides_${raw}`;
  }
  return raw;
}

export function pipelineNodesForMode(
  mode?: "report" | "diagram" | "presentation" | string | null,
): NodeDef[] {
  if (mode === "diagram") return DIAGRAM_NODES;
  if (mode === "presentation") return PRESENTATION_NODES;
  return REPORT_NODES;
}

export function pipelineActiveIndex(
  nodes: NodeDef[],
  stage?: string | null,
): number {
  const s = normalizePipelineStage(stage);
  if (s === "queued") return 0;
  if (s === "ok") return nodes.length; // all complete
  if (s === "error") return -1;
  const i = nodes.findIndex((n) => n.stages.includes(s));
  if (i >= 0) return i;
  // Presentation: any unmatched slides_* advances to План (never stick on Стол).
  if (s.startsWith("slides_")) {
    const planIdx = nodes.findIndex((n) => n.id === "plan");
    return planIdx >= 0 ? planIdx : Math.max(0, nodes.length - 2);
  }
  return 0;
}

type Props = {
  stage?: string | null;
  label?: string;
  detail?: string | null;
  /** Liber mode — diagram uses a short track without Печать. */
  mode?: "report" | "diagram" | "presentation" | string | null;
};

export function PipelineFlow({
  stage = "queued",
  label,
  detail,
  mode = "report",
}: Props) {
  const reduce = useReducedMotion();
  const nodes = pipelineNodesForMode(mode);
  const idx = pipelineActiveIndex(nodes, stage);
  const failed = normalizePipelineStage(stage) === "error";
  const done = normalizePipelineStage(stage) === "ok";

  return (
    <div
      className={`pipeline-flow${failed ? " is-error" : ""}${done ? " is-done" : ""}`}
      role="status"
      aria-live="polite"
      aria-label={
        label ||
        (mode === "diagram"
          ? "Сборка схемы"
          : mode === "presentation"
            ? "Сборка презентации"
            : "Сборка отчёта")
      }
    >
      <div className="pipeline-flow-track" aria-hidden>
        {nodes.map((node, i) => {
          const complete = done || (idx > i && idx !== -1);
          const active = !done && !failed && idx === i;
          const upcoming = !complete && !active && !failed;

          return (
            <div key={node.id} className="pipeline-flow-unit">
              {i > 0 && (
                <div
                  className={`pipeline-flow-edge${complete ? " is-lit" : ""}${active ? " is-flowing" : ""}`}
                >
                  <span className="pipeline-flow-edge-fill" />
                  {!reduce && active && (
                    <span className="pipeline-flow-sheen" />
                  )}
                </div>
              )}
              <div
                className={`pipeline-flow-node${complete ? " is-complete" : ""}${active ? " is-active" : ""}${upcoming ? " is-upcoming" : ""}${failed && i === Math.max(idx, 0) ? " is-failed" : ""}`}
              >
                <span className="pipeline-flow-ring">
                  {active && !reduce && (
                    <motion.span
                      className="pipeline-flow-pulse"
                      initial={false}
                      animate={{ scale: [1, 1.35], opacity: [0.35, 0] }}
                      transition={{
                        duration: 2.4,
                        ease: [0.33, 0, 0.2, 1],
                        repeat: Infinity,
                        repeatType: "loop",
                      }}
                    />
                  )}
                  {/* no layout prop — Framer layout was shifting dots along the track */}
                  <motion.span
                    className="pipeline-flow-dot"
                    transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
                  >
                    {complete ? (
                      <motion.svg
                        viewBox="0 0 16 16"
                        width="12"
                        height="12"
                        aria-hidden
                        initial={reduce ? false : { opacity: 0, scale: 0.7 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                      >
                        <path
                          d="M3.5 8.2 L6.5 11.2 L12.5 4.8"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </motion.svg>
                    ) : (
                      <span className="pipeline-flow-core" />
                    )}
                  </motion.span>
                </span>
                <span className="pipeline-flow-caption">{node.label}</span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="pipeline-flow-label">
        {failed
          ? "Сбой на столе"
          : label ||
            (mode === "presentation"
              ? "Собираю презентацию…"
              : "Набираю отчёт…")}
        {detail && !failed ? (
          <span className="pipeline-flow-detail"> · {detail}</span>
        ) : null}
      </p>
    </div>
  );
}
