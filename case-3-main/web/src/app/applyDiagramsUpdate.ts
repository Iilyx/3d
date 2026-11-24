/** Apply diagram list (+ undo toast) after Liber edit/regenerate. */

import type { Dispatch, SetStateAction } from "react";
import type { DiagramUpdateMeta } from "../DiagramPane";
import type { DiagramInfo } from "../DiagramFullscreen";
import type { Msg } from "../domain/liberTypes";
import type { ActiveArtifact } from "../ArtifactRail";

type UndoOffer = { msgId: string; runId: string } | null;

export function applyDiagramsUpdate(opts: {
  msgId: string;
  runId?: string;
  diagrams: DiagramInfo[];
  meta?: DiagramUpdateMeta;
  setMsgs: Dispatch<SetStateAction<Msg[]>>;
  setActiveArtifact: Dispatch<SetStateAction<ActiveArtifact | null>>;
  setUndoOffer: Dispatch<SetStateAction<UndoOffer>>;
  rememberRun: (result: NonNullable<Extract<Msg, { role: "bot" }>["result"]>) => void;
  showToast: (message: string, ms?: number) => void;
}): void {
  const {
    msgId,
    runId,
    diagrams,
    meta,
    setMsgs,
    setActiveArtifact,
    setUndoOffer,
    rememberRun,
    showToast,
  } = opts;
  setMsgs((list) =>
    list.map((msg) => {
      if (msg.id !== msgId || msg.role !== "bot" || !msg.result) return msg;
      const prevPreview = msg.result.preview;
      let nextPreview = prevPreview;
      if (prevPreview?.blocks) {
        const now = Date.now();
        const nextBlocks = prevPreview.blocks.map((b) => {
          if (
            b.type === "figure" &&
            (b.kind === "diagram" || b.id.startsWith("dia_"))
          ) {
            const updated = diagrams.find((d) => d.id === b.id);
            if (updated) {
              const base = (
                b.url || `/api/runs/${runId || msg.result?.run_id}/figures/${b.id}.png`
              ).split("?")[0];
              return {
                ...b,
                caption: updated.title || b.caption,
                url: `${base}?v=${now}`,
              };
            }
          }
          return b;
        });
        nextPreview = { ...prevPreview, blocks: nextBlocks };
      }
      const next = {
        ...msg,
        result: {
          ...msg.result,
          diagrams,
          preview: nextPreview,
        },
      };
      if (next.result) rememberRun(next.result);
      return next;
    }),
  );
  setActiveArtifact((prev) => {
    if (!prev || prev.kind !== "report") return prev;
    const keep =
      diagrams.find((d) => d.id === prev.activeDiagramId)?.id ??
      diagrams[0]?.id ??
      null;
    return { ...prev, activeDiagramId: keep };
  });
  if (meta?.undo?.kind && runId) {
    setUndoOffer({ msgId, runId });
  } else {
    setUndoOffer(null);
  }
  showToast(meta?.toast || "Схема обновлена", 4200);
}
