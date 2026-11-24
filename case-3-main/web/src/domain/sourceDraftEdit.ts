/** Pure helpers for pre-run Source draft click-to-edit. */

export type SourceViewMode = "preview" | "editing";

export function enterSourceEdit(
  editable: boolean,
  mode: SourceViewMode,
): SourceViewMode {
  return editable ? "editing" : mode;
}

export function exitSourceEditOnKey(
  key: string,
  mode: SourceViewMode,
): SourceViewMode {
  if (mode === "editing" && key === "Escape") return "preview";
  return mode;
}

export function exitSourceEditOnBlur(mode: SourceViewMode): SourceViewMode {
  return mode === "editing" ? "preview" : mode;
}

export function patchSourceDraftText<T extends { text: string }>(
  draft: T,
  text: string,
): T {
  return { ...draft, text };
}
