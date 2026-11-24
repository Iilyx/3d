/** Which rail a chat edit should reopen. */

import { attachSlidesPayload } from "./attachSlidesPayload";
import type { Msg, RunResult } from "./liberTypes";
import { slidesJobInFlight } from "./runHelpers";
import type { ArtifactTab } from "../ArtifactRail";

export function offersNewChat(op: string): boolean {
  return op === "full";
}

export function reviseSurface(
  op: string,
  titleOn = "",
): "deck" | "report" | null {
  if (
    op === "recolor_deck" ||
    op === "delete_slide" ||
    op === "reorder_slide" ||
    op === "add_slide" ||
    op === "slide_text" ||
    op === "slide_bullets" ||
    op === "restyle_structure"
  ) {
    return "deck";
  }
  if (op === "retitle" && titleOn === "deck") return "deck";
  if (
    op === "rewrite" ||
    op === "recolor_charts" ||
    op === "retype_charts" ||
    op === "retype_chart" ||
    op === "undo" ||
    op === "redo" ||
    op === "retitle" ||
    op === "rename_heading" ||
    op === "replace_cell" ||
    op === "replace_item" ||
    op === "add_item" ||
    op === "refine_diagram"
  ) {
    return "report";
  }
  return null;
}

export type RefreshStep = {
  surface: "deck" | "report";
  artifactRunId: string;
  op?: string;
};

export function refreshSteps(data: {
  op?: string;
  surface?: string;
  artifact_run_id?: string;
  surfaces?: Array<{ surface?: string; artifact_run_id?: string; op?: string }>;
}): RefreshStep[] {
  const listed = Array.isArray(data.surfaces) ? data.surfaces : [];
  const steps: RefreshStep[] = [];
  for (const item of listed) {
    const surface =
      item?.surface === "deck" || item?.surface === "report" ? item.surface : null;
    if (!surface) continue;
    const step: RefreshStep = {
      surface,
      artifactRunId: (item.artifact_run_id || "").trim(),
    };
    if (item.op === "refine_diagram") step.op = "refine_diagram";
    steps.push(step);
  }
  if (steps.length) return steps;
  const single =
    data.surface === "deck" || data.surface === "report"
      ? data.surface
      : reviseSurface(data.op || "");
  if (!single) return [];
  const step: RefreshStep = {
    surface: single,
    artifactRunId: (data.artifact_run_id || "").trim(),
  };
  if (data.op === "refine_diagram") step.op = "refine_diagram";
  return [step];
}

export function revisedRailPlan(
  head: string,
  artifact: string,
  surface: "deck" | "report",
  op = "",
): { fetchId: string; chainHead: string; tab: "presentation" | "preview" | "diagram" } {
  const chainHead = head.trim();
  const file = artifact.trim() || chainHead;
  return {
    fetchId: file,
    chainHead,
    tab:
      surface === "deck"
        ? "presentation"
        : op === "refine_diagram"
          ? "diagram"
          : "preview",
  };
}

export function historyRailRun(
  head: {
    run_id?: string;
    preview?: { blocks?: unknown[] } | null;
    deck?: { slides?: unknown[] } | null;
    downloads?: { pdf?: string; pptx?: string; deck_pdf?: string } | null;
    slide_pngs?: string[] | null;
  } | null,
  artifactId: string,
): string {
  const artifact = artifactId.trim();
  const headId = head?.run_id?.trim() || "";
  if (!artifact) return headId;
  const hasFile = Boolean(
    head?.preview?.blocks?.length ||
      head?.deck?.slides?.length ||
      head?.downloads?.pdf ||
      head?.downloads?.pptx ||
      head?.downloads?.deck_pdf ||
      head?.slide_pngs?.length,
  );
  if (hasFile && headId) return headId;
  return artifact;
}

export function chatToReopen(
  items: { runId: string }[],
  openId: string,
  messagesOpen: boolean,
): string {
  if (messagesOpen) return "";
  const id = openId.trim();
  if (!id) return "";
  return items.some((item) => item.runId === id) ? id : "";
}

type RefreshHosts = {
  setMsgs: (fn: (msgs: Msg[]) => Msg[]) => void;
  rememberRun: (result: RunResult) => void;
  openReportArtifact: (msgId: string, result: RunResult, tab?: ArtifactTab) => void;
};

async function readStatus(runId: string): Promise<RunResult | null> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/status`);
  if (!res.ok) return null;
  return (await res.json()) as RunResult;
}

export async function refreshRevisedArtifact(
  runId: string,
  surface: "deck" | "report",
  msgId: string,
  hosts: RefreshHosts,
  artifactRunId = "",
  options?: { remember?: boolean; isolated?: boolean; op?: string; memorySection?: string },
): Promise<void> {
  const plan = revisedRailPlan(runId, artifactRunId, surface, options?.op || "");
  let result = await readStatus(plan.fetchId);
  if (!result) return;
  if (surface === "deck") {
    for (let i = 0; i < 20 && slidesJobInFlight(result.slides_status); i += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 700));
      const next = await readStatus(plan.fetchId);
      if (next) result = next;
    }
    try {
      const slides = await fetch(
        `/api/runs/${encodeURIComponent(plan.fetchId)}/slides`,
      );
      if (slides.ok) result = attachSlidesPayload(result, await slides.json());
    } catch {
      /* status is enough to open the rail */
    }
  }
  if (!options?.isolated && plan.chainHead && plan.chainHead !== result.run_id) {
    result = { ...result, chain_head: plan.chainHead };
  }
  if (options?.isolated) result = { ...result, isolated: true };
  if (typeof options?.memorySection === "string") {
    result = { ...result, memory_section: options.memorySection };
  } else if (options?.op === "undo") {
    result = { ...result, memory_section: "" };
  }
  hosts.setMsgs((msgs) =>
    msgs.map((msg) => {
      if (msg.id !== msgId || msg.role !== "bot") return msg;
      return { ...msg, result, pending: false };
    }),
  );
  if (options?.remember !== false) {
    hosts.rememberRun(
      plan.chainHead && plan.chainHead !== result.run_id
        ? { ...result, run_id: plan.chainHead }
        : result,
    );
  }
  hosts.openReportArtifact(msgId, result, plan.tab);
}
