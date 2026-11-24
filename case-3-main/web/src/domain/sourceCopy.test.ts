import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ATTACHED_TOAST,
  SCREEN_READ_NOTE,
  SOURCE_LABEL,
  screenReadNote,
  sourceCameFromScreen,
} from "./sourceCopy";

describe("source copy", () => {
  it("uses one name for the attached document", () => {
    assert.equal(SOURCE_LABEL, "Документ");
    assert.equal(SOURCE_LABEL.includes("Source"), false);
    assert.notEqual(SOURCE_LABEL, "Текст");
  });

  it("says the model could read numbers from the screen", () => {
    assert.equal(screenReadNote(true), SCREEN_READ_NOTE);
    assert.match(SCREEN_READ_NOTE, /экран/i);
    assert.match(SCREEN_READ_NOTE, /модель/i);
    assert.equal(screenReadNote(false), "");
  });

  it("keeps the screen note off a PDF table", () => {
    const table = [
      "# Данные дашборда",
      "Числа скопированы из ячеек PDF.",
      "## Таблица PDF",
      "| Область | Сумма |",
      "| Минская | 105865 |",
    ].join("\n");
    const both = [
      "# Данные дашборда",
      "Числа в разделе «Таблица PDF» скопированы из ячеек файла.",
      "## Экран",
      "Фильтр: год",
      "## Таблица PDF",
      "| Область | Сумма |",
    ].join("\n");
    const screen = [
      "# Данные дашборда",
      "Текст ниже — чтение снимка.",
      "## Экран",
      "Минская 105865",
    ].join("\n");
    assert.equal(sourceCameFromScreen(table), false);
    assert.equal(sourceCameFromScreen(both), false);
    assert.equal(sourceCameFromScreen(screen), true);
    assert.equal(sourceCameFromScreen("Обычный текст 20"), false);
  });

  it("names a successful attach", () => {
    assert.equal(ATTACHED_TOAST, "Данные прикреплены");
  });
});
