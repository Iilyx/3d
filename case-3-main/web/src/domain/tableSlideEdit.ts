/** Table slide cell and structure editing utilities.
 * Caps match slides_ir._MAX_TABLE_ROWS / _MAX_TABLE_COLS.
 */

export const MAX_TABLE_ROWS = 8;
export const MAX_TABLE_COLS = 5;

export function updateTableCell(
  rows: string[][],
  rowIndex: number,
  colIndex: number,
  nextValue: string,
): string[][] {
  const next = rows.map((r) => [...r]);
  if (rowIndex >= 0 && rowIndex < next.length) {
    if (colIndex >= 0 && colIndex < next[rowIndex].length) {
      next[rowIndex][colIndex] = (nextValue || "").replace(/\s+/g, " ").trim();
    }
  }
  return next;
}

export function addTableRow(
  rows: string[][],
  defaultColValue: string = "—",
): string[][] {
  const cols = rows[0]?.length || 3;
  const newRow = Array.from({ length: cols }, (_, i) =>
    i === 0 ? "Новая строка" : defaultColValue,
  );
  return [...rows.map((r) => [...r]), newRow];
}

export function deleteTableRow(
  rows: string[][],
  rowIndex: number,
): string[][] {
  if (rowIndex <= 0 || rows.length <= 2) {
    return rows;
  }
  return rows.filter((_, idx) => idx !== rowIndex);
}

export function addTableCol(
  rows: string[][],
  headerTitle?: string,
  defaultValue: string = "—",
): string[][] {
  const colNum = (rows[0]?.length || 0) + 1;
  const title = headerTitle || `Колонка ${colNum}`;
  return rows.map((r, ri) => [
    ...r,
    ri === 0 ? title : defaultValue,
  ]);
}

export function deleteTableCol(
  rows: string[][],
  colIndex: number,
): string[][] {
  const currentCols = rows[0]?.length || 0;
  if (currentCols <= 2 || colIndex < 0 || colIndex >= currentCols) {
    return rows;
  }
  return rows.map((r) => r.filter((_, ci) => ci !== colIndex));
}

export function ensureTableRows(rows?: string[][]): string[][] {
  if (rows && rows.length >= 2 && rows[0]?.length >= 2) {
    return rows;
  }
  return [
    ["Параметр", "План", "Факт"],
    ["Выручка", "10 млн", "12 млн"],
    ["NPS", "40", "45"],
  ];
}
