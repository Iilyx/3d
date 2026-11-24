/** Build multipart body for POST /api/run from Liber desk composer state. */

import { deckStyleToApiPayload, type DeckStyle } from "../deckStyle";
import type { LiberWorkMode } from "../domain/liberModes";
import type { SourceDraft } from "../domain/liberTypes";
import { asksForPhoto } from "../domain/photoChip";
import { attachmentsFromDraft } from "../domain/sourcePack";

/** Fixed run defaults — chart type/style/title come from model + ChartEditSheet. */
const CHART_AUTO = true;
const CHART_TYPES: string[] = [];
const CHART_HINTS = "";
const CHART_PALETTE = "atelier";
const CHART_STYLE = "";
const DOC_TITLE = "";

export type BuildRunFormDataArgs = {
  file: File | null;
  draftSnap: SourceDraft | null;
  chatTrim: string;
  intentText: string;
  photosSnapshot: File[];
  forbidCharts: boolean;
  forbidImages: boolean;
  maxCharts: number;
  maxImages: number;
  maxDiagrams: number;
  dryRun: boolean;
  workMode: LiberWorkMode;
  deckStyle: DeckStyle;
  /** Palette preset for generated charts (atelier, editorial, ocean, sunset, mono). */
  chartPalette?: string;
  /** Wish for deck length (6–24). Model may emit fewer if Source is thin. */
  targetSlides?: number;
  /** Previous bot run in this chat. Empty on the first send. */
  priorRunId?: string | null;
  /** A file from the previous chat. Its dialogue is not this chat. */
  carriedRunId?: string | null;
  /** Force chat when the dashboard shots are analyzed. */
  outputMode?: "chat" | "auto";
};

export function buildRunFormData(args: BuildRunFormDataArgs): FormData {
  const {
    file,
    draftSnap,
    chatTrim,
    intentText,
    photosSnapshot,
    forbidCharts,
    forbidImages,
    maxCharts,
    maxImages,
    maxDiagrams,
    dryRun,
    workMode,
    deckStyle,
    chartPalette,
    targetSlides,
    priorRunId,
    carriedRunId,
    outputMode,
  } = args;

  const fd = new FormData();
  // Photo-edit UI parked; Liber desk always posts document runs.
  // Standalone img2img remains POST /api/photo/edit.
  fd.append("photo_mode", "document");
  for (const p of photosSnapshot) fd.append("photos", p);
  if (
    file &&
    draftSnap?.text &&
    (Boolean(draftSnap.fileName) || /\.(txt|md)$/i.test(file.name || ""))
  ) {
    const uploadName = (file.name || draftSnap.fileName || "source.txt").replace(
      /\.(pdf|docx?|docm|rtf)$/i,
      ".md",
    );
    fd.append(
      "source",
      new File([draftSnap.text], uploadName || "source.md", {
        type: "text/markdown",
      }),
    );
    fd.append("intent", intentText);
  } else if (file) {
    fd.append("source", file);
    fd.append("intent", intentText);
  } else if (draftSnap?.text) {
    fd.append("source_text", draftSnap.text);
    fd.append("intent", intentText);
  } else {
    // Chat-only: same text is Source + Intent
    fd.append("source_text", chatTrim);
    fd.append("intent", intentText);
  }
  const photoBudget =
    photosSnapshot.length > 0
      ? Math.max(maxImages, photosSnapshot.length)
      : asksForPhoto(`${chatTrim}\n${intentText}`)
        ? maxImages
        : 0;
  fd.append("max_charts", String(forbidCharts ? 0 : maxCharts));
  fd.append("max_diagrams", String(maxDiagrams));
  fd.append(
    "max_images",
    String(forbidImages && !photosSnapshot.length ? 0 : photoBudget),
  );
  fd.append("chart_types", CHART_AUTO ? "" : CHART_TYPES.join(","));
  fd.append("chart_hints", CHART_HINTS.trim());
  fd.append("chart_auto", String(CHART_AUTO));
  fd.append(
    "chart_palette",
    (chartPalette || "").trim() ? (chartPalette || "").trim() : CHART_PALETTE,
  );
  fd.append("chart_style", CHART_STYLE.trim());
  fd.append("doc_title", DOC_TITLE.trim().slice(0, 200));
  fd.append("forbid_charts", String(forbidCharts));
  fd.append(
    "forbid_images",
    String((forbidImages && photosSnapshot.length === 0) || photoBudget === 0),
  );
  fd.append("output_mode", outputMode || "auto");
  fd.append("artifact_bias", workMode ?? "");
  fd.append("deck_pack", deckStyle.themePack || "atelier");
  const deckPayload = deckStyleToApiPayload(deckStyle);
  if (deckPayload.structure_id) {
    fd.append("deck_structure_id", deckPayload.structure_id);
  }
  fd.append("deck_style_json", JSON.stringify(deckPayload.style_settings || {}));
  const slidesWish = Math.max(6, Math.min(24, Math.round(targetSlides || 12)));
  fd.append("target_slides", String(slidesWish));
  fd.append("formats", "both");
  fd.append("dry_run", String(dryRun));
  const prior = (priorRunId || "").trim();
  if (prior) fd.append("prior_run_id", prior);
  const carried = (carriedRunId || "").trim();
  if (carried) fd.append("carried_run_id", carried);
  if (draftSnap?.text) {
    const metas = attachmentsFromDraft(draftSnap).map((a) => ({
      title: a.title,
      fileName: a.fileName,
      viewMode: a.viewMode,
      previewUrl: a.previewUrl,
      originalUrl: a.originalUrl,
      ingestId: a.ingestId,
      format: a.format,
    }));
    if (metas.length) {
      fd.append("attachments_json", JSON.stringify(metas));
    }
  }
  return fd;
}
