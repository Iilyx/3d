/** Shared Liber desk types (chat + run payload). */

import type { ThinkingLine, ThinkingMode } from "./pipelinePhrases";
import type { ReportPreview } from "./reportPreview";

export type { PreviewBlock, ReportPreview } from "./reportPreview";

export type PaletteInfo = {
  id: string;
  label: string;
  swatches: string[];
};

export type DeskProbe = {
  id: string;
  label: string;
  status: "green" | "amber" | "red" | string;
  ok?: boolean;
  configured?: boolean;
  hint?: string | null;
  path?: string | null;
  error?: string | null;
};

export type Health = {
  ok: boolean;
  docker_ok: boolean;
  playwright_ok: boolean;
  vision_configured: boolean;
  vision_ok?: boolean;
  vision_error?: string | null;
  kandinsky_configured: boolean;
  image_api_configured?: boolean;
  /** Live probe of IMAGE_API_BASE_URL (short timeout). */
  image_api_ok?: boolean;
  image_api_error?: string | null;
  image_api_base_url?: string | null;
  docker_error?: string | null;
  playwright_error?: string | null;
  soffice_ok?: boolean;
  soffice_path?: string | null;
  soffice_hint?: string | null;
  probes?: DeskProbe[];
  chart_types?: string[];
  chart_palettes?: PaletteInfo[];
  defaults?: {
    max_charts?: number;
    max_diagrams?: number;
    /** Settings input max for schemas (CASE3_MAX_DIAGRAMS hard ceiling). */
    max_diagrams_cap?: number;
    max_images?: number;
  };
};

export type MediaPreview = {
  id: string;
  kind: string;
  url: string;
};

export type DiagramResult = {
  id: string;
  title: string;
  type?: string;
  mermaid: string;
};

export type RunResult = {
  run_id: string;
  status: string;
  downloads: Record<string, string>;
  previews?: MediaPreview[];
  preview?: ReportPreview;
  charts_ok: number;
  figures_ok: number;
  charts_planned: string[];
  figures_planned: string[];
  diagrams?: DiagramResult[];
  diagrams_ok?: number;
  diagrams_planned?: string[];
  warnings: string[];
  media_status?: Record<string, unknown>;
  /** Sidebar and header name. Not the user's raw message. */
  title?: string;
  chat_summary?: string;
  /** Line spoken before an artifact job. Same as chat_summary for a chat turn. */
  chat_opening?: string;
  summary_status?: string | null;
  slides_status?: string | null;
  slides_stage?: string | null;
  slides_error?: string | null;
  slide_pngs?: string[];
  /** How deck PDF was built: `lo` (LibreOffice) or `png_stitch`. */
  deck_pdf_mode?: string | null;
  /** Previous run in this same chat. */
  prior_run_id?: string;
  /** Conversation head when this payload is an older file shown in the rail. */
  chain_head?: string;
  /** Quiet warning when this chat is near the 48-turn cap. */
  chat_notice?: string;
  /** How many pipeline turns this chat already holds. */
  turn_count?: number;
  /** Last report section this chat edited. */
  memory_section?: string;
  /** This run is a file from another chat. Do not continue its transcript. */
  isolated?: boolean;
  /** Live deck IR for editable twin canvas */
  deck?: import("../deckTypes").DeckIR | null;
  /** Liber composer mode that produced this run */
  output_mode?: string;
  /** Source the user sent. Restored when a chat is opened from history. */
  user_text?: string;
  /** Set when input lacked enough factual data to build artifacts */
  insufficient_data?: boolean;
  error?: string;
  detail?: string;
};

export type SourceAttachment = {
  title: string;
  text: string;
  fileName?: string;
  /** Office PDF/DOCX: open as viewer, not extract text. */
  viewMode?: "text" | "document";
  previewUrl?: string | null;
  originalUrl?: string | null;
  ingestId?: string;
  format?: string;
};

export type SourcePart = {
  name: string;
  text: string;
  title?: string;
  viewMode?: "text" | "document";
  previewUrl?: string | null;
  originalUrl?: string | null;
  ingestId?: string;
  format?: string;
};

export type SourceDraft = {
  title: string;
  /** Extract for /api/run. Hidden in UI when viewMode === "document". */
  text: string;
  fileName?: string;
  /** text = editable; document = native PDF/office preview only. */
  viewMode?: "text" | "document";
  /** pdf.js URL (blob: or /api/source/files/.../preview). */
  previewUrl?: string | null;
  /** Download original office file. */
  originalUrl?: string | null;
  ingestId?: string;
  format?: string;
  /** Documents kept in this chat. The joined text is what /api/run receives. */
  parts?: SourcePart[];
  /** Dashboard capture or a screen PNG. The plaque says the model could read it. */
  fromScreen?: boolean;
};

export type UserMsg = {
  id: string;
  role: "user";
  text: string;
  /** @deprecated prefer chips — kept for session history */
  tags?: string;
  /** C6: settings as chips under collapsed Intent. */
  chips?: string[];
  /** Pasted / attached source shown as doc plaque on the bubble. */
  attachment?: SourceAttachment;
  /** Individual plaques when 1+ documents were attached to this send. */
  attachments?: SourceAttachment[];
  /** Photos attached to this send. */
  photos?: UserPhotoThumb[];
};

export type UserPhotoThumb = {
  url: string;
  name?: string;
};

export type BotMsg = {
  id: string;
  role: "bot";
  text: string;
  /** Full-width agent line: opening before an artifact, or the chat answer. */
  lead?: string;
  /** Chat is full: show a button that starts an empty chat. */
  offerNewChat?: boolean;
  result?: RunResult;
  pending?: boolean;
  pendingStage?: string;
  pendingDetail?: string | null;
  /** LLM chat summary streaming into the bubble */
  streamingSummary?: boolean;
  /** True while streamPacer is actively typing characters; false while waiting on post-text visuals */
  streamTyping?: boolean;
  /** Collapsible pipeline phrases in the bubble */
  thinking?: ThinkingLine[];
  thinkingStartedAt?: number;
  thinkingStageKey?: string;
  thinkingStageAt?: number;
  /** Frozen when run finishes (for collapsed fold meta). */
  thinkingElapsedSec?: number;
  /** Phrase pool: report / diagram / presentation */
  thinkingMode?: ThinkingMode;
  /** Model sentences for steps that have started. */
  stageLines?: Record<string, string> | null;
  /** SSE phase 2A: nested chart/figure beats */
  craftSubsteps?: import("./craftSteps").CraftSubstep[];
  /** photos → skip reason */
  craftSkipped?: Partial<Record<import("./craftSteps").CraftStepId, string>>;
  /** SSE 2B film thumbnails */
  craftFilm?: import("./craftSteps").CraftFilmFrame[];
  /** Success recap one-liner */
  craftRecap?: string | null;
  /** Server ETA for current stage (seconds) */
  etaSec?: number | null;
  /** Cancel froze the checklist */
  craftFrozen?: boolean;
  /** Actionable error line under fold */
  errorHint?: string | null;
  /** Wait line that is not a pipeline stage. */
  waitLabel?: string;
  /** Dashboard the user can reopen and shoot again. */
  dashboard?: import("./dashboardCapture").DashboardCard;
  error?: string;
  /** Same run_id eligible for POST /resume */
  canResume?: boolean;
  failedRunId?: string | null;
  failedStage?: string | null;
};

export type Msg = UserMsg | BotMsg;
