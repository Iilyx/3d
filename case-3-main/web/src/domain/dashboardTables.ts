/** Turn dashboard markdown into headings and real tables. Numbers stay as printed. */

export type DashboardBlock =
  | { kind: "heading"; text: string }
  | { kind: "text"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "table"; header: string[]; rows: string[][]; numeric: boolean[] };

const MACHINE_LINE =
  /^(?:# Данные дашборда|Числа скопированы из ячеек PDF\.|Числа в разделе «Таблица PDF».*|Текст ниже — чтение снимка\..*|Раздел «Экран».*|Доли, суммы и отклонения посчитаны из ячеек\..*)$/;

const NUMBER_CELL = /^[+\-−]?\d[\d\s\u00a0]*(?:[.,]\d+)?%?$/;

function splitRow(line: string): string[] {
  const body = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  const cells: string[] = [];
  let current = "";
  for (let index = 0; index < body.length; index += 1) {
    const char = body[index];
    if (char === "\\" && body[index + 1] === "|") {
      current += "|";
      index += 1;
      continue;
    }
    if (char === "|") {
      cells.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }
  cells.push(current.trim());
  return cells;
}

function isTableRow(line: string): boolean {
  return /^\s*\|.+\|\s*$/.test(line);
}

function isSeparator(line: string): boolean {
  return /^\s*\|[\s:|-]+\|\s*$/.test(line) && line.includes("-");
}

const BULLET = /^\s*(?:[-*•]|\d+\.)\s+(.+)$/;
const BOLD_TITLE = /^\s*\*\*[^*]+\*\*\s*$/;
const RULE = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;

/** Qwen writes **bold** and * bullets. The window shows the words, not the marks. */
export function stripInline(value: string): string {
  return value
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/(^|[\s(])\*([^*\n]+?)\*(?=[\s).,;:]|$)/g, "$1$2")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function numericColumns(header: string[], rows: string[][]): boolean[] {
  return header.map((_, column) => {
    if (column === 0) return false;
    let filled = 0;
    let numeric = 0;
    for (const row of rows) {
      const cell = (row[column] || "").trim();
      if (!cell) continue;
      filled += 1;
      if (NUMBER_CELL.test(cell)) numeric += 1;
    }
    return filled > 0 && numeric / filled >= 0.6;
  });
}

export function splitDashboardBlocks(markdown: string): DashboardBlock[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: DashboardBlock[] = [];
  const prose: string[] = [];

  function flushProse() {
    const lines = prose.splice(0);
    let list: string[] = [];
    let text: string[] = [];
    function flushList() {
      if (!list.length) return;
      blocks.push({ kind: "list", items: list });
      list = [];
    }
    function flushText() {
      const joined = text.join("\n").trim();
      text = [];
      if (joined) blocks.push({ kind: "text", text: joined });
    }
    for (const raw of lines) {
      const line = raw.trim();
      if (!line || RULE.test(line) || MACHINE_LINE.test(line)) continue;
      if (BOLD_TITLE.test(line)) {
        flushList();
        flushText();
        blocks.push({ kind: "heading", text: stripInline(line) });
        continue;
      }
      const heading = /^(#{1,3})\s+(.+)$/.exec(line);
      if (heading) {
        flushList();
        flushText();
        blocks.push({ kind: "heading", text: stripInline(heading[2]) });
        continue;
      }
      const bullet = BULLET.exec(line);
      if (bullet) {
        flushText();
        const item = stripInline(bullet[1]);
        if (item) list.push(item);
        continue;
      }
      flushList();
      const plain = stripInline(line);
      if (plain) text.push(plain);
    }
    flushList();
    flushText();
  }

  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (
      isTableRow(line) &&
      index + 1 < lines.length &&
      isSeparator(lines[index + 1])
    ) {
      flushProse();
      const header = splitRow(line).map(stripInline);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && isTableRow(lines[index])) {
        const cells = splitRow(lines[index]).map(stripInline);
        while (cells.length < header.length) cells.push("");
        rows.push(cells.slice(0, header.length));
        index += 1;
      }
      if (header.length > 0) {
        blocks.push({
          kind: "table",
          header,
          rows,
          numeric: numericColumns(header, rows),
        });
      }
      continue;
    }
    prose.push(line);
    index += 1;
  }
  flushProse();
  return blocks;
}

export type DashboardSections = {
  mainBlocks: DashboardBlock[];
  derivativeBlocks: DashboardBlock[];
};

/** Separate main screen/PDF table blocks from auto-calculated `## Производные`. */
export function splitDashboardSections(markdown: string): DashboardSections {
  const normalized = (markdown || "").replace(/\r\n/g, "\n");
  const marker = /^##[ \t]+Производные[ \t]*$/im.exec(normalized);
  if (!marker || marker.index === undefined) {
    return {
      mainBlocks: splitDashboardBlocks(normalized),
      derivativeBlocks: [],
    };
  }
  const mainMd = normalized.slice(0, marker.index).trim();
  const derivMd = normalized
    .slice(marker.index + marker[0].length)
    .trim();
  return {
    mainBlocks: splitDashboardBlocks(mainMd),
    derivativeBlocks: splitDashboardBlocks(derivMd),
  };
}

const TOTAL_ROW_RE =
  /^(?:итого|всего|промежуточн\p{L}*\s+итог|total|subtotal|grand\s+total|sum|сумма)(?:\b|\s|:|$)/iu;

export function isTotalTableRow(row: string[]): boolean {
  for (let i = 0; i < Math.min(row.length, 3); i += 1) {
    const cell = (row[i] || "").trim();
    if (cell && TOTAL_ROW_RE.test(cell)) return true;
  }
  return false;
}

function parseCellFloat(raw: string): number | null {
  const cleaned = (raw || "")
    .trim()
    .replace(/^[+]/, "")
    .replace(/^−/, "-")
    .replace(/%$/, "")
    .replace(/[\s\u00a0\u202f]/g, "")
    .replace(",", ".");
  if (!cleaned || !/^-?\d+(?:\.\d+)?$/.test(cleaned)) return null;
  const val = Number(cleaned);
  return Number.isFinite(val) ? val : null;
}

const COMPLETION_COL_RE = /(?:выполн|%\s*план|план.*%|исполн)/i;
const DELTA_COL_RE = /(?:откл|разниц|дельта|прирост|изменен|динамик)/i;

/**
 * Determine semantic tone ("pos" | "neg" | null) for a table cell:
 * - Explicit negative sign (`-1 353,6` or `−5,2%`) -> "neg"
 * - Explicit positive sign (`+5 020,0`) -> "pos"
 * - Plan completion column (`Выполнение, %`): < 100 -> "neg", >= 100 -> "pos"
 * - Deviation column (`Откл.`): < 0 -> "neg", > 0 -> "pos"
 */
export function cellSemanticTone(
  cellValue: string,
  columnHeader = "",
): "pos" | "neg" | null {
  const trimmed = (cellValue || "").trim();
  if (!trimmed) return null;
  const num = parseCellFloat(trimmed);
  if (num === null) return null;
  if (/^[-−]/.test(trimmed) && num < 0) return "neg";
  if (/^\+/.test(trimmed) && num > 0) return "pos";
  if (COMPLETION_COL_RE.test(columnHeader)) {
    if (num < 100) return "neg";
    if (num >= 100) return "pos";
  }
  if (DELTA_COL_RE.test(columnHeader)) {
    if (num < 0) return "neg";
    if (num > 0) return "pos";
  }
  return null;
}

function escapeCsvField(field: string, sep = ";"): string {
  const clean = (field || "").replace(/\r?\n/g, " ").trim();
  if (clean.includes(sep) || clean.includes('"')) {
    return `"${clean.replace(/"/g, '""')}"`;
  }
  return clean;
}

/** Build UTF-8 BOM semicolon-delimited CSV ready for Russian Microsoft Excel. */
export function tableToCsv(header: string[], rows: string[][]): string {
  const lines: string[] = [
    header.map((h) => escapeCsvField(h)).join(";"),
    ...rows.map((r) =>
      header.map((_, i) => escapeCsvField(r[i] || "")).join(";"),
    ),
  ];
  return `\uFEFF${lines.join("\r\n")}\r\n`;
}

export function tableToTsv(header: string[], rows: string[][]): string {
  const lines: string[] = [
    header.map((h) => (h || "").replace(/\t|\r?\n/g, " ").trim()).join("\t"),
    ...rows.map((r) =>
      header
        .map((_, i) => (r[i] || "").replace(/\t|\r?\n/g, " ").trim())
        .join("\t"),
    ),
  ];
  return lines.join("\n");
}

export type DashboardStarterChip = {
  label: string;
  prompt: string;
};

/** Context-aware, emoji-free analytical starter chips for 1 or 2+ dashboard shots. */
export function dashboardStarterChips(
  sourceText: string,
  shotCount = 1,
): DashboardStarterChip[] {
  const hasMultipleShots =
    shotCount >= 2 ||
    (sourceText.match(/(?:^|\n)# Данные дашборда\b/g) || []).length >= 2 ||
    (sourceText.match(/^===== .+ =====$/gm) || []).length >= 2;
  const hasRegionsOrGroups =
    /(?:област|регион|район|инспекц|имнс|бюджет|филиал|подразделен)/i.test(
      sourceText || "",
    );

  const chips: DashboardStarterChip[] = [];
  if (hasMultipleShots) {
    chips.push({
      label: "Сравнить снимки в динамике",
      prompt:
        "Сравни показатели между снимками дашборда в динамике: покажи таблицу изменений в абсолютных числах и процентах и построй график сравнения.",
    });
  }
  chips.push({
    label: "Лидеры, отстающие и отклонения",
    prompt:
      "Проанализируй данные дашборда: ключевые итоги, кто лидирует, кто отстаёт от плана и где самые заметные отклонения.",
  });
  if (hasRegionsOrGroups) {
    chips.push({
      label: "Сравнить области и доли",
      prompt:
        "Сравни показатели и доли по областям и инспекциям: кто вносит наибольший вклад в общий результат, а где дефицит?",
    });
  } else {
    chips.push({
      label: "Структура и доли показателей",
      prompt:
        "Разбери структуру показателей и их доли в общем итоге: выдели топ-позиции и концентрацию.",
    });
  }
  chips.push(
    {
      label: "Построить график",
      prompt: "Построй наглядный график сравнения основных показателей по этим данным.",
    },
    {
      label: "Собрать отчёт",
      prompt: "Сделай подробный аналитический отчёт по этому дашборду с таблицами и графиками.",
    },
    {
      label: "Собрать презентацию",
      prompt: "Сделай презентацию по этим данным с ключевыми выводами и графиками.",
    },
  );
  return chips;
}
