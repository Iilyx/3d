/** One name for the attached document. The screen note is only for a capture. */

export const SOURCE_LABEL = "Документ";

export const SCREEN_READ_NOTE = "Числа с экрана модель могла прочитать";

export const ATTACHED_TOAST = "Данные прикреплены";

export function screenReadNote(fromScreen: boolean): string {
  return fromScreen ? SCREEN_READ_NOTE : "";
}

const PDF_TABLE = /^## Таблица PDF\s*$/m;
const SCREEN_SECTION = /^## Экран\s*$/m;

/** A PDF table was copied from cells. The screen note is only for a screenshot. */
export function sourceCameFromScreen(markdown: string): boolean {
  const text = markdown || "";
  if (PDF_TABLE.test(text) || /скопированы из ячеек/i.test(text)) return false;
  return SCREEN_SECTION.test(text) || /чтение снимка/i.test(text);
}
