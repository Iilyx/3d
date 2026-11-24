import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { normalizeConfirmOptions, type ConfirmOptions } from "./ConfirmModal";

describe("ConfirmModal options and defaults", () => {
  it("provides sensible defaults for minimal options", () => {
    const raw: ConfirmOptions = {
      title: "Удалить слайд?",
      message: "Слайд будет удален безвозвратно.",
    };
    const norm = normalizeConfirmOptions(raw);
    assert.equal(norm.title, "Удалить слайд?");
    assert.equal(norm.message, "Слайд будет удален безвозвратно.");
    assert.equal(norm.eyebrow, "liber · подтверждение");
    assert.equal(norm.confirmLabel, "Удалить");
    assert.equal(norm.cancelLabel, "Отмена");
    assert.equal(norm.danger, true);
  });

  it("preserves custom labels and non-danger mode", () => {
    const raw: ConfirmOptions = {
      title: "Сохранить изменения?",
      eyebrow: "черновик · сохранение",
      message: "Применить все изменения сейчас?",
      confirmLabel: "Сохранить",
      cancelLabel: "Вернуться",
      danger: false,
    };
    const norm = normalizeConfirmOptions(raw);
    assert.equal(norm.title, "Сохранить изменения?");
    assert.equal(norm.eyebrow, "черновик · сохранение");
    assert.equal(norm.confirmLabel, "Сохранить");
    assert.equal(norm.cancelLabel, "Вернуться");
    assert.equal(norm.danger, false);
  });
});
