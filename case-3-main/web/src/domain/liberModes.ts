/** Liber composer work modes. */

export type LiberWorkMode = "report" | "diagram" | "presentation" | null;

export const LIBER_MODE_PILLS: {
  id: Exclude<LiberWorkMode, null>;
  label: string;
  hint: string;
}[] = [
  { id: "report", label: "Отчёт", hint: "Превью · Схема · PDF/DOCX" },
  { id: "diagram", label: "Схема", hint: "Только схема — без отчёта" },
  {
    id: "presentation",
    label: "Презентация",
    hint: "Только презентация · PPTX и PDF — без отчёта, схемы на слайдах",
  },
];

export function modeToOutputMode(mode: LiberWorkMode): string {
  return mode ?? "auto";
}

export type LiberOutputMode = "report" | "diagram" | "presentation" | "auto" | "chat";

export function normalizeOutputMode(
  mode?: string | null,
): LiberOutputMode {
  if (
    mode === "diagram" ||
    mode === "presentation" ||
    mode === "report" ||
    mode === "chat"
  ) {
    return mode;
  }
  return "auto";
}

/** Surfaces allowed per Liber work mode (rail tabs + in-chat cards). */
export function modeSurfaces(mode?: string | null) {
  const m = normalizeOutputMode(mode);
  return {
    mode: m,
    /** TeX/block preview of the report */
    showReportPreview: m === "report" || m === "auto",
    /** Print PDF / DOCX of the report */
    showReportPdf: m === "report" || m === "auto",
    /** Mermaid schema tab / cards */
    showDiagram: m === "diagram" || m === "report" || m === "auto",
    /** PPTX + deck PDF twin */
    showPresentation: m === "presentation" || m === "auto",
    /** Diagram mode: schema only in rail (no Source clutter). Chat has no rail. */
    showSource: m !== "diagram" && m !== "chat",
  };
}
