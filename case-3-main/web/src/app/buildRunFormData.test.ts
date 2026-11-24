import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildRunFormData } from "./buildRunFormData";
import { DEFAULT_DECK_STYLE } from "../deckStyle";

describe("buildRunFormData", () => {
  it("posts document photo_mode and report formats", () => {
    const fd = buildRunFormData({
      file: null,
      draftSnap: null,
      chatTrim: "hello",
      intentText: "hello",
      photosSnapshot: [],
      forbidCharts: false,
      forbidImages: false,
      maxCharts: 2,
      maxImages: 2,
      maxDiagrams: 2,
      dryRun: true,
      workMode: "report",
      deckStyle: DEFAULT_DECK_STYLE,
    });
    assert.equal(fd.get("photo_mode"), "document");
    assert.equal(fd.get("formats"), "both");
    assert.equal(fd.get("dry_run"), "true");
    assert.equal(fd.get("source_text"), "hello");
    assert.equal(fd.get("output_mode"), "auto");
    assert.equal(fd.get("artifact_bias"), "report");
    assert.equal(fd.get("target_slides"), "12");
    assert.equal(fd.get("prior_run_id"), null);
  });

  it("sends prior_run_id when this chat already has a run", () => {
    const fd = buildRunFormData({
      file: null,
      draftSnap: null,
      chatTrim: "сделай короче",
      intentText: "сделай короче",
      photosSnapshot: [],
      forbidCharts: false,
      forbidImages: false,
      maxCharts: 2,
      maxImages: 2,
      maxDiagrams: 2,
      dryRun: false,
      workMode: "report",
      deckStyle: DEFAULT_DECK_STYLE,
      priorRunId: "source_abc",
    });
    assert.equal(fd.get("prior_run_id"), "source_abc");
  });

  it("sends the carried file without making it the transcript", () => {
    const fd = buildRunFormData({
      file: null,
      draftSnap: null,
      chatTrim: "короче",
      intentText: "короче",
      photosSnapshot: [],
      forbidCharts: false,
      forbidImages: false,
      maxCharts: 2,
      maxImages: 2,
      maxDiagrams: 2,
      dryRun: false,
      workMode: null,
      deckStyle: DEFAULT_DECK_STYLE,
      carriedRunId: "source_old",
    });
    assert.equal(fd.get("prior_run_id"), null);
    assert.equal(fd.get("carried_run_id"), "source_old");
  });

  it("clamps a presentation slide wish into 6–24", () => {
    const fd = buildRunFormData({
      file: null,
      draftSnap: null,
      chatTrim: "deck",
      intentText: "deck",
      photosSnapshot: [],
      forbidCharts: false,
      forbidImages: false,
      maxCharts: 2,
      maxImages: 2,
      maxDiagrams: 0,
      dryRun: false,
      workMode: "presentation",
      deckStyle: DEFAULT_DECK_STYLE,
      targetSlides: 40,
    });
    assert.equal(fd.get("target_slides"), "24");
    assert.equal(fd.get("formats"), "both");
    assert.equal(fd.get("artifact_bias"), "presentation");
    assert.equal(fd.get("output_mode"), "auto");
  });

  it("sends the diagram plaque as a bias and leaves budgets to the server", () => {
    const fd = buildRunFormData({
      file: null,
      draftSnap: null,
      chatTrim: "flow",
      intentText: "flow",
      photosSnapshot: [],
      forbidCharts: false,
      forbidImages: false,
      maxCharts: 2,
      maxImages: 2,
      maxDiagrams: 1,
      dryRun: false,
      workMode: "diagram",
      deckStyle: DEFAULT_DECK_STYLE,
    });
    assert.equal(fd.get("artifact_bias"), "diagram");
    assert.equal(fd.get("output_mode"), "auto");
    assert.equal(fd.get("max_charts"), "2");
    assert.equal(fd.get("formats"), "both");
  });

  it("passes dynamic chart_palette when provided", () => {
    const fd = buildRunFormData({
      file: null,
      draftSnap: null,
      chatTrim: "hello",
      intentText: "hello",
      photosSnapshot: [],
      forbidCharts: false,
      forbidImages: false,
      maxCharts: 2,
      maxImages: 2,
      maxDiagrams: 2,
      dryRun: true,
      workMode: "report",
      deckStyle: DEFAULT_DECK_STYLE,
      chartPalette: "sunset",
    });
    assert.equal(fd.get("chart_palette"), "sunset");
  });

  it("prefers edited draftSnap.text over stale attached .txt File", async () => {
    const staleFile = new File(["Старый текст до правки"], "brief.txt", {
      type: "text/plain",
    });
    const fd = buildRunFormData({
      file: staleFile,
      draftSnap: {
        title: "brief.txt",
        text: "Отредактированный текст в SourcePane",
        fileName: "brief.txt",
      },
      chatTrim: "Собери отчёт",
      intentText: "Собери отчёт",
      photosSnapshot: [],
      forbidCharts: false,
      forbidImages: false,
      maxCharts: 2,
      maxImages: 2,
      maxDiagrams: 2,
      dryRun: true,
      workMode: "report",
      deckStyle: DEFAULT_DECK_STYLE,
    });
    const uploaded = fd.get("source");
    if (uploaded instanceof File) {
      assert.equal(await uploaded.text(), "Отредактированный текст в SourcePane");
    } else {
      assert.equal(fd.get("source_text"), "Отредактированный текст в SourcePane");
    }
  });
});

