import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  blockEditVisible,
  collapseSetForEditMode,
  copyMarkdownButtonVisible,
  docsNeedRebuild,
  parseEditHistory,
  toastUndoRebuildsDocs,
  recolorChartsButtonVisible,
  reportEditModeHint,
  reportEditToggleVisible,
  shouldIgnoreDeckHotkey,
  slidesFilmTabLabel,
  toastUndoVisible,
} from "./reportEditMode";
import { wrapChartScriptIife } from "../LiveChart";

describe("reportEditMode", () => {
  it("hides block edits when mode is off", () => {
    assert.equal(blockEditVisible(false, true), false);
    assert.equal(blockEditVisible(true, true), true);
    assert.equal(blockEditVisible(true, false), false);
  });

  it("shows top toggle when any editor is wired", () => {
    assert.equal(reportEditToggleVisible({}), false);
    assert.equal(
      reportEditToggleVisible({ onEditParagraph: () => true }),
      true,
    );
    assert.equal(
      reportEditToggleVisible({ onEditFigure: () => true }),
      true,
    );
    assert.equal(
      reportEditToggleVisible({ onEditHeading: () => true }),
      true,
    );
    assert.equal(
      reportEditToggleVisible({ onEditTitle: () => true }),
      true,
    );
    assert.equal(
      reportEditToggleVisible({ onEditList: () => true }),
      true,
    );
  });

  it("hint describes click-to-edit + deferred print", () => {
    assert.match(reportEditModeHint(true), /Готово/i);
    assert.match(reportEditModeHint(false), /Чтение/);
  });

  it("toast undo does not rebuild PDF", () => {
    assert.equal(toastUndoRebuildsDocs(), false);
  });

  it("docsNeedRebuild when stack or redo branch has work", () => {
    assert.equal(docsNeedRebuild(null), false);
    assert.equal(
      docsNeedRebuild({ canUndo: false, canRedo: false, depth: 0 }),
      false,
    );
    assert.equal(
      docsNeedRebuild({ canUndo: true, canRedo: false, depth: 1 }),
      true,
    );
    assert.equal(
      docsNeedRebuild({ canUndo: false, canRedo: true, depth: 0 }),
      true,
    );
  });

  it("entering edit clears collapsed sections", () => {
    const cleared = collapseSetForEditMode(true);
    assert.ok(cleared);
    assert.equal(cleared!.size, 0);
    assert.equal(collapseSetForEditMode(false), null);
  });

  it("parses undo stack descriptor", () => {
    assert.deepEqual(parseEditHistory(null), {
      canUndo: false,
      canRedo: false,
      depth: 0,
    });
    assert.deepEqual(
      parseEditHistory({
        kind: "paragraph",
        target: "1",
        can_undo: true,
        can_redo: false,
        depth: 2,
      }),
      {
        canUndo: true,
        canRedo: false,
        depth: 2,
        kind: "paragraph",
        target: "1",
      },
    );
    assert.equal(
      parseEditHistory({ can_undo: false, can_redo: true, depth: 0 }).canRedo,
      true,
    );
    // Legacy one-slot shape
    assert.equal(parseEditHistory({ kind: "chart", target: "x" }).canUndo, true);
  });

  it("hides toast undo while report edit mode is on", () => {
    assert.equal(
      toastUndoVisible(true, { canUndo: true, canRedo: false, depth: 1 }),
      false,
    );
    assert.equal(
      toastUndoVisible(false, { canUndo: true, canRedo: false, depth: 1 }),
      true,
    );
    assert.equal(toastUndoVisible(false, { canUndo: false, canRedo: true, depth: 0 }), false);
  });

  it("shows recolor charts button only in edit mode and copy MD only in read-only mode", () => {
    assert.equal(recolorChartsButtonVisible(false, true, true), false);
    assert.equal(recolorChartsButtonVisible(true, true, true), true);
    assert.equal(recolorChartsButtonVisible(true, false, true), false);
    assert.equal(recolorChartsButtonVisible(true, true, false), false);

    assert.equal(copyMarkdownButtonVisible(false, true), true);
    assert.equal(copyMarkdownButtonVisible(true, true), false);
    assert.equal(copyMarkdownButtonVisible(false, false), false);
  });

  it("gives slides film tab a distinct label from report PDF tab", () => {
    assert.equal(slidesFilmTabLabel(), "Слайды (PDF)");
    assert.notEqual(slidesFilmTabLabel(), "PDF");
  });

  it("ignores deck hotkeys when typing in INPUT, TEXTAREA, SELECT, contentEditable, or modal", () => {
    assert.equal(shouldIgnoreDeckHotkey({ tagName: "TEXTAREA" }), true);
    assert.equal(shouldIgnoreDeckHotkey({ tagName: "INPUT" }), true);
    assert.equal(shouldIgnoreDeckHotkey({ tagName: "SELECT" }), true);
    assert.equal(shouldIgnoreDeckHotkey({ tagName: "DIV", isContentEditable: true }), true);
    assert.equal(shouldIgnoreDeckHotkey({ tagName: "DIV" }, true), true);
    assert.equal(shouldIgnoreDeckHotkey({ tagName: "DIV" }, false), false);
    assert.equal(shouldIgnoreDeckHotkey(null, false), false);
  });

  it("wraps LiveChart script in an IIFE so top-level const declarations do not collide", () => {
    const s1 = wrapChartScriptIife("const ctx = 1; globalThis.__c1 = ctx;");
    const s2 = wrapChartScriptIife("const ctx = 2; globalThis.__c2 = ctx;");
    // Executing both in the same scope would throw SyntaxError without IIFE wrapping
    const fn = new Function(`${s1}\n${s2}`);
    fn();
    assert.equal((globalThis as { __c1?: number }).__c1, 1);
    assert.equal((globalThis as { __c2?: number }).__c2, 2);
  });
});

