/** Liber desk: edit one report table — caption + spreadsheet-feel grid. */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { submitChord } from "./domain/undoChord";
import { useFocusTrap } from "./useFocusTrap";

export type TableEditRequest = {
  tableIndex: number;
  caption: string;
  headers: string[];
  rows: string[][];
};

export type TableEditDraft = {
  caption: string;
  headers: string[];
  rows: string[][];
};

type Props = {
  open: boolean;
  /** When false, skip focus trap (multi-open edit desk). */
  trapFocus?: boolean;
  tableIndex: number;
  initialCaption?: string;
  initialHeaders: string[];
  initialRows: string[][];
  busy?: boolean;
  error?: string | null;
  onCancel: () => void;
  onSubmit: (req: TableEditRequest) => void;
  onDraftChange?: (draft: TableEditDraft) => void;
};

const MAX_COLS = 40;
const MAX_ROWS = 200;

function cloneGrid(headers: string[], rows: string[][]): {
  headers: string[];
  rows: string[][];
} {
  return {
    headers: headers.map((h) => h ?? ""),
    rows: rows.map((r) => r.map((c) => c ?? "")),
  };
}

function looksNumeric(s: string): boolean {
  const t = (s || "").trim().replace(/\s/g, "").replace(",", ".");
  if (!t) return false;
  return (
    /^-?\d+(\.\d+)?%?$/.test(t) ||
    /^-?\d{1,3}([. ]\d{3})+(,\d+)?%?$/.test(t)
  );
}

function colIsNumeric(headers: string[], rows: string[][], ci: number): boolean {
  let n = 0;
  let total = 0;
  for (const row of rows) {
    const cell = row[ci];
    if (cell == null || !String(cell).trim()) continue;
    total += 1;
    if (looksNumeric(String(cell))) n += 1;
  }
  if (total === 0) return false;
  if (n / total >= 0.6) return true;
  const h = (headers[ci] || "").toLowerCase();
  return /\d|%|год|года|шт|руб|млн|тыс|доля|рост/.test(h) && n / total >= 0.35;
}

export function TableEditSheet({
  open,
  trapFocus = true,
  tableIndex,
  initialCaption = "",
  initialHeaders,
  initialRows,
  busy,
  error,
  onCancel,
  onSubmit,
  onDraftChange,
}: Props) {
  const [caption, setCaption] = useState(initialCaption);
  const [headers, setHeaders] = useState(initialHeaders);
  const [rows, setRows] = useState(initialRows);
  const [localError, setLocalError] = useState<string | null>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const captionRef = useRef<HTMLInputElement>(null);
  const uid = useId();
  useFocusTrap(sheetRef, { active: open && trapFocus });

  useEffect(() => {
    if (!open) return;
    setCaption(initialCaption || "");
    const g = cloneGrid(initialHeaders, initialRows);
    setHeaders(g.headers);
    setRows(g.rows.length ? g.rows : [g.headers.map(() => "")]);
    setLocalError(null);
    const t = window.setTimeout(() => captionRef.current?.focus(), 40);
    return () => window.clearTimeout(t);
  }, [open, tableIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open || !onDraftChange) return;
    onDraftChange({ caption, headers, rows });
  }, [open, caption, headers, rows, onDraftChange]);

  const cols = headers.length;
  const canDeleteCol = cols > 1;
  const canDeleteRow = rows.length > 1;
  const numericCols = headers.map((_, ci) => colIsNumeric(headers, rows, ci));
  const displayError = localError || error;

  const apply = useCallback(() => {
    if (busy) return;
    const emptyHi = headers.findIndex((h) => !h.trim());
    if (emptyHi >= 0) {
      setLocalError(`Заполните заголовок столбца ${emptyHi + 1}`);
      return;
    }
    setLocalError(null);
    onSubmit({
      tableIndex,
      caption: caption.trim(),
      headers: headers.map((h) => h.trim()),
      rows: rows.map((r) => r.map((c) => c.trim())),
    });
  }, [busy, headers, rows, caption, tableIndex, onSubmit]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (busy) return;
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        apply();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, apply]);

  function setHeader(ci: number, value: string) {
    setLocalError(null);
    setHeaders((prev) => prev.map((h, i) => (i === ci ? value : h)));
  }

  function setCell(ri: number, ci: number, value: string) {
    setLocalError(null);
    setRows((prev) =>
      prev.map((row, i) =>
        i === ri ? row.map((c, j) => (j === ci ? value : c)) : row,
      ),
    );
  }

  function addRow() {
    if (rows.length >= MAX_ROWS) return;
    setRows((prev) => [...prev, headers.map(() => "")]);
  }

  function addCol() {
    if (cols >= MAX_COLS) return;
    setHeaders((prev) => [...prev, ""]);
    setRows((prev) => prev.map((r) => [...r, ""]));
  }

  function deleteRow(ri: number) {
    if (!canDeleteRow) return;
    setRows((prev) => prev.filter((_, i) => i !== ri));
  }

  function deleteCol(ci: number) {
    if (!canDeleteCol) return;
    setHeaders((prev) => prev.filter((_, i) => i !== ci));
    setRows((prev) => prev.map((r) => r.filter((_, i) => i !== ci)));
  }

  if (!open) return null;

  return (
    <div
      ref={sheetRef}
      className="chart-edit-sheet table-edit-sheet"
      role="region"
      aria-label="Изменить таблицу"
    >
      <header className="chart-edit-head table-edit-head">
        <h3 className="chart-edit-title">Таблица {tableIndex}</h3>
        <button
          type="button"
          className="chart-edit-x"
          onClick={onCancel}
          disabled={busy}
          aria-label="Закрыть"
        >
          ×
        </button>
      </header>

      <section className="chart-edit-block">
        <label className="field" htmlFor={`${uid}-cap`}>
          Подпись
        </label>
        <input
          ref={captionRef}
          id={`${uid}-cap`}
          type="text"
          value={caption}
          disabled={busy}
          placeholder="Ключевые показатели…"
          onChange={(e) => {
            setLocalError(null);
            setCaption(e.target.value);
          }}
        />
      </section>

      <section className="chart-edit-block">
        <div className="chart-edit-labelrow">
          <span className="field">Ячейки</span>
          <span className="chart-edit-badge" aria-live="polite">
            {rows.length}×{cols}
          </span>
        </div>
        <div className="table-edit-scroll">
          <table className="table-edit-grid">
            <thead>
              <tr>
                <th className="table-edit-gutter" aria-hidden />
                {headers.map((h, ci) => (
                  <th
                    key={ci}
                    className={`table-edit-col${numericCols[ci] ? " is-num" : ""}`}
                  >
                    <div className="table-edit-colhead">
                      <input
                        type="text"
                        value={h}
                        disabled={busy}
                        placeholder={`Столбец ${ci + 1}`}
                        aria-label={`Заголовок столбца ${ci + 1}`}
                        onChange={(e) => setHeader(ci, e.target.value)}
                      />
                      {canDeleteCol && (
                        <button
                          type="button"
                          className="table-edit-delcol"
                          disabled={busy}
                          title="Удалить столбец"
                          aria-label={`Удалить столбец ${ci + 1}`}
                          onClick={() => deleteCol(ci)}
                        >
                          ×
                        </button>
                      )}
                    </div>
                  </th>
                ))}
                <th className="table-edit-edge">
                  <button
                    type="button"
                    className="table-edit-edge-btn"
                    disabled={busy || cols >= MAX_COLS}
                    title="Добавить столбец"
                    aria-label="Добавить столбец"
                    onClick={addCol}
                  >
                    +
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="table-edit-row">
                  <td className="table-edit-gutter">
                    {canDeleteRow ? (
                      <button
                        type="button"
                        className="table-edit-delrow"
                        disabled={busy}
                        title="Удалить строку"
                        aria-label={`Удалить строку ${ri + 1}`}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          deleteRow(ri);
                        }}
                      >
                        ×
                      </button>
                    ) : (
                      <span className="table-edit-rownum" aria-hidden>
                        {ri + 1}
                      </span>
                    )}
                  </td>
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className={numericCols[ci] ? "is-num" : undefined}
                    >
                      <input
                        type="text"
                        value={cell}
                        disabled={busy}
                        aria-label={`Ячейка ${ri + 1},${ci + 1}`}
                        onChange={(e) => setCell(ri, ci, e.target.value)}
                      />
                    </td>
                  ))}
                  <td className="table-edit-edge" aria-hidden />
                </tr>
              ))}
              <tr className="table-edit-addrow">
                <td className="table-edit-gutter" />
                <td colSpan={cols}>
                  <button
                    type="button"
                    className="table-edit-edge-btn is-row"
                    disabled={busy || rows.length >= MAX_ROWS}
                    onClick={addRow}
                  >
                    + строка
                  </button>
                </td>
                <td className="table-edit-edge" aria-hidden />
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {displayError && <p className="err">{displayError}</p>}

      <footer className="chart-edit-foot">
        <p className="chart-edit-foot-hint">
          Черновик выше. Нажмите «В превью», чтобы обновить черновик; PDF и Word
          обновятся по кнопке «Готово». {submitChord()}.
        </p>
        <div className="chart-edit-actions">
          <button
            type="button"
            className="chart-edit-apply"
            disabled={busy}
            onClick={apply}
          >
            {busy ? "Обновляю…" : "В превью"}
          </button>
          <button
            type="button"
            className="chart-edit-cancel"
            disabled={busy}
            onClick={onCancel}
          >
            Отмена
          </button>
        </div>
      </footer>
    </div>
  );
}
