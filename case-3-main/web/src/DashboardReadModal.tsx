/** Full-screen readout of a parsed dashboard. Tables stay wide enough to read. */

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { shotTitle, splitPackedSources } from "./domain/dashboardCapture";
import {
  cellSemanticTone,
  isTotalTableRow,
  splitDashboardSections,
  tableToCsv,
  tableToTsv,
} from "./domain/dashboardTables";
import type { DashboardBlock } from "./domain/dashboardTables";
import { useFocusTrap } from "./useFocusTrap";

type Props = {
  title: string;
  text: string;
  onClose: () => void;
};

function cellClass(numeric: boolean, tone: "pos" | "neg" | null): string {
  const base = numeric ? "is-num" : "is-label";
  if (tone === "pos") return `${base} is-pos-cell`;
  if (tone === "neg") return `${base} is-neg-cell`;
  return base;
}

function TableBlockView({
  block,
  query,
  docTitle,
}: {
  block: Extract<DashboardBlock, { kind: "table" }>;
  query: string;
  docTitle: string;
}) {
  const [copied, setCopied] = useState(false);
  const q = query.trim().toLocaleLowerCase("ru");

  const filteredRows = useMemo(() => {
    if (!q) return block.rows;
    return block.rows.filter(
      (row) =>
        isTotalTableRow(row) ||
        row.some((cell) => (cell || "").toLocaleLowerCase("ru").includes(q)),
    );
  }, [block.rows, q]);

  async function copyTable() {
    try {
      await navigator.clipboard.writeText(tableToTsv(block.header, filteredRows));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* ignore */
    }
  }

  function downloadCsv() {
    const csv = tableToCsv(block.header, filteredRows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const safeName =
      (docTitle || "dashboard")
        .replace(/[\\/:*?"<>|]+/g, "_")
        .replace(/\s+/g, "_")
        .slice(0, 60) || "dashboard";
    a.href = url;
    a.download = `${safeName}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="stimul-table-card">
      <div className="stimul-table-bar">
        <span className="stimul-table-meta">
          Строк: {filteredRows.length}
          {q && filteredRows.length !== block.rows.length
            ? ` из ${block.rows.length}`
            : ""}
          {" · "}Колонок: {block.header.length}
        </span>
        <div className="stimul-table-actions">
          <button
            type="button"
            className="stimul-table-btn"
            onClick={() => void copyTable()}
          >
            {copied ? "Скопировано для Excel" : "Копировать таблицу"}
          </button>
          <button
            type="button"
            className="stimul-table-btn"
            onClick={downloadCsv}
          >
            Скачать CSV
          </button>
        </div>
      </div>
      <div className="stimul-grid-scroll">
        <table className="stimul-grid">
          <thead>
            <tr>
              {block.header.map((cell, index) => (
                <th key={index} className={cellClass(block.numeric[index], null)}>
                  {cell}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row, rowIndex) => {
              const isTotal = isTotalTableRow(row);
              return (
                <tr
                  key={rowIndex}
                  className={isTotal ? "is-total-row" : undefined}
                >
                  {block.header.map((colName, index) => {
                    const val = row[index] || "";
                    const tone = block.numeric[index]
                      ? cellSemanticTone(val, colName)
                      : null;
                    return (
                      <td
                        key={index}
                        className={cellClass(block.numeric[index], tone)}
                      >
                        {val}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BlockView({
  block,
  query,
  docTitle,
}: {
  block: DashboardBlock;
  query: string;
  docTitle: string;
}) {
  if (block.kind === "heading") {
    return <h3 className="stimul-read-title">{block.text}</h3>;
  }
  if (block.kind === "text") {
    return <p className="stimul-read-text">{block.text}</p>;
  }
  if (block.kind === "list") {
    return (
      <ul className="stimul-read-list">
        {block.items.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    );
  }
  return <TableBlockView block={block} query={query} docTitle={docTitle} />;
}

export function DashboardReadModal({ title, text, onClose }: Props) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState<"main" | "derivatives">("main");
  const [query, setQuery] = useState("");
  useFocusTrap(dialogRef, { active: true });

  const docs = useMemo(
    () =>
      splitPackedSources(text).map((doc) => {
        const sections = splitDashboardSections(doc.markdown);
        return {
          title: shotTitle(doc.name, doc.markdown),
          mainBlocks: sections.mainBlocks,
          derivativeBlocks: sections.derivativeBlocks,
        };
      }),
    [text],
  );

  const hasDerivatives = docs.some((doc) => doc.derivativeBlocks.length > 0);
  const heading = docs.length === 1 ? docs[0].title : title;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <div
      ref={dialogRef}
      className="stimul-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="stimul-sheet is-read">
        <header className="settings-modal-head">
          <div>
            <p className="settings-modal-eyebrow">дашборд · числа и авто-расчёты</p>
            <h2 id={titleId} className="settings-modal-title">
              {heading}
            </h2>
          </div>
          <div className="dash-read-head-controls">
            {tab === "main" ? (
              <input
                type="search"
                className="dash-read-search"
                placeholder="Найти строку, область, инспекцию…"
                aria-label="Поиск по таблице дашборда"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            ) : null}
            {hasDerivatives ? (
              <div className="dash-read-tabs" role="tablist" aria-label="Режим просмотра">
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "main"}
                  className={`dash-read-tab${tab === "main" ? " is-active" : ""}`}
                  onClick={() => setTab("main")}
                >
                  Таблица и экран
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "derivatives"}
                  className={`dash-read-tab${tab === "derivatives" ? " is-active" : ""}`}
                  onClick={() => setTab("derivatives")}
                >
                  Авто-расчёты (доли и отклонения)
                </button>
              </div>
            ) : null}
            <button
              type="button"
              className="settings-modal-x"
              onClick={onClose}
              aria-label="Закрыть"
            >
              ×
            </button>
          </div>
        </header>
        <div className="settings-modal-body dash-read-body">
          {docs.length > 1 ? (
            <nav className="dash-read-nav" aria-label="Снимки">
              {docs.map((doc, index) => (
                <button
                  key={`${doc.title}-${index}`}
                  type="button"
                  onClick={() =>
                    document
                      .getElementById(`dash-read-${index}`)
                      ?.scrollIntoView({ block: "start" })
                  }
                >
                  {doc.title}
                </button>
              ))}
            </nav>
          ) : null}
          {docs.length ? (
            docs.map((doc, index) => {
              const activeBlocks =
                tab === "derivatives" && doc.derivativeBlocks.length > 0
                  ? doc.derivativeBlocks
                  : doc.mainBlocks;
              return (
                <section
                  key={`${doc.title}-${index}`}
                  id={`dash-read-${index}`}
                  className="stimul-readout"
                >
                  {docs.length > 1 ? (
                    <h3 className="stimul-read-title">{doc.title}</h3>
                  ) : null}
                  {activeBlocks.map((block, blockIndex) => (
                    <BlockView
                      key={blockIndex}
                      block={block}
                      query={query}
                      docTitle={doc.title}
                    />
                  ))}
                </section>
              );
            })
          ) : (
            <p className="stimul-read-text">В снимке нет текста.</p>
          )}
        </div>
      </div>
    </div>
  );
}
