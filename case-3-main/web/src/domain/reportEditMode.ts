/** Preview edit-mode: document click-to-edit + session undo/redo. */

import { undoChord } from "./undoChord";

export type EditHistoryDesc = {
  canUndo: boolean;
  canRedo: boolean;
  depth: number;
  kind?: string | null;
  target?: string | null;
};

/** Show block edit affordances only while edit mode is on and a handler exists. */
export function blockEditVisible(
  editMode: boolean,
  hasHandler: boolean,
): boolean {
  return editMode && hasHandler;
}

/** Top «Редактировать» only when at least one editor is wired. */
export function reportEditToggleVisible(opts: {
  onEditFigure?: unknown;
  onEditImage?: unknown;
  onEditTable?: unknown;
  onEditParagraph?: unknown;
  onEditHeading?: unknown;
  onEditTitle?: unknown;
  onEditList?: unknown;
}): boolean {
  return Boolean(
    opts.onEditFigure ||
      opts.onEditImage ||
      opts.onEditTable ||
      opts.onEditParagraph ||
      opts.onEditHeading ||
      opts.onEditTitle ||
      opts.onEditList,
  );
}

/** Hint under the top toggle. */
export function reportEditModeHint(editMode: boolean, platform?: string): string {
  return editMode
    ? `Клик · ${undoChord(platform)} · PDF/DOCX на Готово`
    : "Чтение · правки документов";
}

/** Toast «Отменить» restores the edit. PDF/DOCX stay until «Готово». */
export function toastUndoRebuildsDocs(): boolean {
  return false;
}

/** Session has Preview edits not yet flushed to print artifacts. */
export function docsNeedRebuild(
  history: EditHistoryDesc | null | undefined,
): boolean {
  if (!history) return false;
  return history.depth > 0 || history.canRedo;
}

/** Entering edit expands every section (empty collapse set). */
export function collapseSetForEditMode(editMode: boolean): Set<string> | null {
  return editMode ? new Set() : null;
}

/** Parse API ``undo`` object into bar enablement. */
export function parseEditHistory(
  undo: {
    kind?: string | null;
    target?: string | null;
    can_undo?: boolean;
    can_redo?: boolean;
    depth?: number;
  } | null | undefined,
): EditHistoryDesc {
  if (!undo) {
    return { canUndo: false, canRedo: false, depth: 0 };
  }
  const canUndo =
    typeof undo.can_undo === "boolean"
      ? undo.can_undo
      : Boolean(undo.kind);
  const canRedo = Boolean(undo.can_redo);
  const depth =
    typeof undo.depth === "number" && undo.depth >= 0
      ? undo.depth
      : canUndo
        ? 1
        : 0;
  return {
    canUndo,
    canRedo,
    depth,
    kind: undo.kind ?? null,
    target: undo.target ?? null,
  };
}

/** Toast «Отменить» only outside report edit mode and when undo is available. */
export function toastUndoVisible(
  editMode: boolean,
  history: EditHistoryDesc | null | undefined,
): boolean {
  if (editMode) return false;
  return Boolean(history?.canUndo);
}

/** Batch «Перекрасить графики» button is shown only inside active report edit mode. */
export function recolorChartsButtonVisible(
  editMode: boolean,
  hasCharts: boolean,
  hasHandler: boolean,
): boolean {
  return Boolean(editMode && hasCharts && hasHandler);
}

/** «Копировать MD» button is shown in read-only mode when preview blocks exist. */
export function copyMarkdownButtonVisible(
  editMode: boolean,
  hasPreview: boolean,
): boolean {
  return Boolean(!editMode && hasPreview);
}

/** Distinct label for presentation slides PDF film tab (avoids two "PDF" tabs). */
export function slidesFilmTabLabel(): string {
  return "Слайды (PDF)";
}

/** Ignore deck window keydown when user is typing in inputs, contentEditable, or modals. */
export function shouldIgnoreDeckHotkey(
  target: unknown,
  hasOpenModal?: boolean,
): boolean {
  if (hasOpenModal) return true;
  if (!target || typeof target !== "object") return false;
  const el = target as {
    isContentEditable?: boolean;
    tagName?: string;
    closest?: (sel: string) => unknown;
  };
  if (el.isContentEditable) return true;
  const tag = (el.tagName || "").toUpperCase();
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (
    typeof el.closest === "function" &&
    el.closest(".modal-backdrop, [role='dialog']:not(.artifact-rail-backdrop)")
  ) {
    return true;
  }
  return false;
}


