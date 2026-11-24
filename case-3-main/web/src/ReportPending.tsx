/** Soft atelier node-flow while the pipeline runs. */

import { PipelineFlow } from "./PipelineFlow";

export function ReportPending({
  label = "Набираю отчёт на столе…",
  stage,
  detail,
  mode = "report",
}: {
  label?: string;
  stage?: string | null;
  detail?: string | null;
  mode?: "report" | "diagram" | "presentation" | string | null;
}) {
  return (
    <div className="report-pending">
      <PipelineFlow stage={stage} label={label} detail={detail} mode={mode} />
    </div>
  );
}
