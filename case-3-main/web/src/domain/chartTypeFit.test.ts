import assert from "node:assert/strict";
import test from "node:test";
import {
  chartNumberEditConfirm,
  chartTypeEditConfirm,
  numberChangeFromEditError,
} from "./chartTypeFit.ts";

test("empty warning does not ask", () => {
  assert.equal(chartTypeEditConfirm(""), null);
  assert.equal(chartTypeEditConfirm("   "), null);
});

test("warning becomes a non-destructive confirm", () => {
  const opts = chartTypeEditConfirm("Сейчас это одно число (KPI).");
  assert.ok(opts);
  assert.equal(opts?.danger, false);
  assert.match(opts?.confirmLabel || "", /Всё равно/);
  assert.match(opts?.message || "", /KPI/);
});

test("number change confirm names the numbers", () => {
  const opts = chartNumberEditConfirm("Модель изменила числа.");
  assert.ok(opts);
  assert.equal(opts?.danger, false);
  assert.match(opts?.title || "", /числа/);
  assert.match(opts?.confirmLabel || "", /Всё равно/);
});

test("reads a numbers_changed payload", () => {
  const err = Object.assign(new Error("Модель изменила числа."), {
    detail: { code: "numbers_changed", message: "Модель изменила числа.", html: "<canvas>" },
  });
  const got = numberChangeFromEditError(err);
  assert.equal(got?.html, "<canvas>");
  assert.equal(numberChangeFromEditError(new Error("bad")), null);
});
