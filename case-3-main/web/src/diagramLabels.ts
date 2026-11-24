/** RU labels for Mermaid diagram types (Liber UI). */

const TYPE_RU: Record<string, string> = {
  flowchart: "Процесс",
  sequence: "Диалог",
  mindmap: "Карта",
  timeline: "Таймлайн",
  stateDiagram: "Состояния",
  state: "Состояния",
};

export function diagramTypeLabel(type?: string | null): string {
  const t = (type || "").trim();
  if (!t) return "Схема";
  return TYPE_RU[t] || t;
}
