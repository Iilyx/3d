/** Node smoke for pure Liber helpers (run: npx tsx --test if available). */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { FALLBACK_PALETTES } from "./domain/liberConstants";
import { LIBER_MODE_PILLS, modeSurfaces } from "./domain/liberModes";
import {
  effectiveThinkingMode,
  formatRunStatusError,
  isRunInFlight,
  provisionalSessionTitle,
  reportReadyText,
  reportTitle,
  rollbackOptimisticRun,
  softMediaFailToast,
  slidesTerminalKind,
  pipelineWatchKind,
  stageLabel,
} from "./domain/runHelpers";

describe("liber surface copy", () => {
  it("presentation hint keeps diagrams on the deck", () => {
    const presentation = LIBER_MODE_PILLS.find((p) => p.id === "presentation");
    assert.equal(
      presentation?.hint,
      "Только презентация · PPTX и PDF — без отчёта, схемы на слайдах",
    );
  });

  it("fallback sunset swatch is the chart palette, not purple", () => {
    const sunset = FALLBACK_PALETTES.find((p) => p.id === "sunset");
    assert.equal(sunset?.swatches[0], "#EE6677");
    assert.equal(sunset?.swatches.includes("#4A154B"), false);
  });
});

describe("liberRunHelpers", () => {
  it("stageLabel charts detail", () => {
    assert.equal(stageLabel("charts", "cht_01"), "Рисую график…");
    assert.equal(stageLabel("latex"), "Собираю PDF…");
    assert.equal(stageLabel("queued"), "В очереди…");
    assert.equal(stageLabel("queued", "Жду прогон holder"), "Жду прогон holder");
  });

  it("slides terminal kind unblocks a deck wait", () => {
    assert.equal(slidesTerminalKind("running"), null);
    assert.equal(slidesTerminalKind("llm_retry"), null);
    assert.equal(slidesTerminalKind("ok"), "done");
    assert.equal(slidesTerminalKind("error"), "error");
    assert.equal(slidesTerminalKind("cancelled"), "cancelled");
  });

  it("queued run stays in flight", () => {
    assert.equal(isRunInFlight("queued"), true);
    assert.equal(isRunInFlight("running"), true);
    assert.equal(isRunInFlight("ok"), false);
  });

  it("stageLabel scales by thinking mode", () => {
    assert.match(stageLabel("llm", null, "diagram"), /схем/i);
    assert.match(stageLabel("diagram_repair", null, "diagram"), /схем/i);
    assert.match(stageLabel("llm", null, "presentation"), /слайд/i);
    assert.match(stageLabel("slides_render", null, "presentation"), /слайд/i);
  });

  it("reportReadyText prefers chat_summary", () => {
    assert.equal(
      reportReadyText({ chat_summary: "  Итог  " } as never, "stream"),
      "Итог",
    );
    assert.equal(reportReadyText(undefined, " streamed "), "streamed");
    assert.equal(reportReadyText(), "Отчёт готов");
  });

  it("reportReadyText handles insufficient_data", () => {
    assert.equal(
      reportReadyText({
        insufficient_data: true,
        chat_summary: "Недостаточно данных для отчета.",
      } as never),
      "Недостаточно данных для отчета.",
    );
    assert.match(
      reportReadyText({
        insufficient_data: true,
      } as never),
      /недостаточно данных/i,
    );
  });

  it("reportReadyText is honest when diagram mode has zero diagrams", () => {
    assert.match(
      reportReadyText({
        output_mode: "diagram",
        diagrams: [],
      } as never),
      /не собралась|Ещё вариант/i,
    );
  });

  it("softMediaFailToast is suppressed for executive presentation mode", () => {
    assert.equal(
      softMediaFailToast({
        failed_charts: ["cht_01"],
        failed_figures: [],
      }),
      null,
    );
    assert.equal(softMediaFailToast({ warnings: [] }), null);
  });

  it("reportTitle prefers preview.title", () => {
    assert.equal(
      reportTitle({
        run_id: "r1",
        preview: { title: "  Board Update  " },
      } as never),
      "Board Update",
    );
    assert.equal(
      reportTitle({ run_id: "r2", output_mode: "diagram" } as never),
      "Схема · r2",
    );
    assert.equal(
      reportTitle({
        run_id: "r3",
        output_mode: "chat",
        title: "Поступления за январь 2025 года",
        chat_summary: "дай мне название данных\n\nРазбор.",
      } as never),
      "Поступления за январь 2025 года",
    );
    assert.equal(
      reportTitle({
        run_id: "r4",
        output_mode: "chat",
        chat_summary: "Выручка выросла с 10 до 12.\n\n| a | b |",
      } as never),
      "Выручка выросла с 10 до 12.",
    );
  });

  it("provisionalSessionTitle by mode", () => {
    assert.equal(provisionalSessionTitle("report"), "Новый отчёт");
    assert.equal(provisionalSessionTitle("diagram"), "Новая схема");
    assert.equal(provisionalSessionTitle("presentation"), "Новая презентация");
  });

  it("modeSurfaces gates artifacts by Liber mode", () => {
    const report = modeSurfaces("report");
    assert.equal(report.showReportPreview, true);
    assert.equal(report.showDiagram, true);
    assert.equal(report.showPresentation, false);

    const diagram = modeSurfaces("diagram");
    assert.equal(diagram.showReportPreview, false);
    assert.equal(diagram.showReportPdf, false);
    assert.equal(diagram.showDiagram, true);
    assert.equal(diagram.showPresentation, false);
    assert.equal(diagram.showSource, false);

    const deck = modeSurfaces("presentation");
    assert.equal(deck.showReportPreview, false);
    assert.equal(deck.showDiagram, false);
    assert.equal(deck.showPresentation, true);
  });

  it("formatRunStatusError includes chart + TeX tail", () => {
    const msg = formatRunStatusError(
      {
        error: "latexmk failed",
        failed_charts: ["cht_02"],
        failed_figures: [],
        latex_log_tail: "a\n! Misplaced &\nend",
      },
      "run_x",
    );
    assert.match(msg, /latexmk failed/);
    assert.match(msg, /график cht_02/);
    assert.match(msg, /TeX:/);
    assert.match(msg, /Misplaced/);
    assert.match(msg, /run run_x/);
  });

  it("pipelineWatchKind settles a dead run and waits for a live deck", () => {
    assert.equal(pipelineWatchKind("error"), "error");
    assert.equal(pipelineWatchKind("cancelled"), "cancelled");
    assert.equal(pipelineWatchKind("running"), null);
    assert.equal(pipelineWatchKind("ok", null, "report"), "done");
    assert.equal(pipelineWatchKind("ok", "running", "presentation"), null);
    assert.equal(pipelineWatchKind("ok", "idle", "presentation"), null);
    assert.equal(pipelineWatchKind("ok", "error", "presentation"), "error");
    assert.equal(pipelineWatchKind("ok", "ok", "presentation"), "done");
  });

  it("effectiveThinkingMode respects workMode and server output_mode", () => {
    assert.equal(effectiveThinkingMode(null), "chat");
    assert.equal(effectiveThinkingMode("report"), "report");
    assert.equal(effectiveThinkingMode("diagram"), "diagram");
    assert.equal(effectiveThinkingMode("presentation"), "presentation");
    assert.equal(effectiveThinkingMode(null, "diagram"), "diagram");
    assert.equal(effectiveThinkingMode("report", "chat"), "chat");
    assert.match(stageLabel("queued", null, "chat"), /изучаю|чат|запрос/i);
    assert.match(stageLabel("llm", null, "chat"), /ответ/i);
  });

  it("rollbackOptimisticRun removes unstarted user and pending bot messages", () => {
    const msgs = [
      { id: "u0", role: "user" as const, text: "старое" },
      { id: "b0", role: "bot" as const, text: "ответ" },
      { id: "u1", role: "user" as const, text: "не ушло" },
      { id: "b1", role: "bot" as const, text: "", pending: true },
    ];
    const next = rollbackOptimisticRun(msgs, "u1", "b1");
    assert.deepEqual(
      next.map((m) => m.id),
      ["u0", "b0"],
    );
  });
});
